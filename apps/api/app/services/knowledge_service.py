import hashlib
import uuid
import traceback
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationException
from app.models.enums import KnowledgeDocumentStatus, EmbeddingStatus, EmbeddingProvider, ChunkStrategy
from app.models.knowledge_document import KnowledgeDocument
from app.models.knowledge_chunk import KnowledgeChunk
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import PgVectorStore


class KnowledgeService:
    """Ingests business documents, handles token chunking, calls embeddings, and indexes vectors."""

    @classmethod
    async def ingest_document(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str,
        content_str: str,
        mime_type: str,
        storage_path: str,
        provider_type: EmbeddingProvider,
        model_name: str,
        description: Optional[str] = None,
        strategy: ChunkStrategy = ChunkStrategy.SLIDING,
        chunk_size: int = 512,
        chunk_overlap: int = 128
    ) -> KnowledgeDocument:
        # Calculate checksum for duplicate detection
        checksum = hashlib.sha256(content_str.encode("utf-8")).hexdigest()
        
        # Check if already exists in org
        stmt = select(KnowledgeDocument).where(
            KnowledgeDocument.organization_id == org_id,
            KnowledgeDocument.checksum_sha256 == checksum,
            KnowledgeDocument.deleted_at.is_(None)
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            raise ValidationException(f"Document with identical contents already exists (ID: {existing.id})")

        # Create record
        doc = KnowledgeDocument(
            organization_id=org_id,
            title=title,
            description=description,
            mime_type=mime_type,
            file_size=len(content_str.encode("utf-8")),
            storage_path=storage_path,
            checksum_sha256=checksum,
            status=KnowledgeDocumentStatus.PROCESSING,
            embedding_provider=provider_type,
            embedding_model=model_name,
            created_by=user_id,
            updated_by=user_id,
            processing_started_at=datetime.utcnow()
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        try:
            # 1. Chunking
            chunks_data = ChunkingService.chunk_text(
                text=content_str,
                strategy=strategy,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )
            
            doc.chunk_count = len(chunks_data)
            
            # Save chunks as pending
            chunks = []
            for item in chunks_data:
                chunk = KnowledgeChunk(
                    document_id=doc.id,
                    organization_id=org_id,
                    chunk_index=item["chunk_index"],
                    content=item["content"],
                    metadata_json=item["metadata"],
                    token_count=item["token_count"],
                    embedding_status=EmbeddingStatus.PENDING
                )
                db.add(chunk)
                chunks.append(chunk)
            
            await db.flush()

            # 2. Embedding generation
            texts = [c.content for c in chunks]
            vectors = await EmbeddingService.batch_embed_texts(
                provider_type=provider_type,
                texts=texts
            )

            # Get dimensions
            provider_impl = EmbeddingService.get_provider(provider_type)
            dims = await provider_impl.dimensions()

            # 3. Vector Store Insertion
            vs = PgVectorStore()
            for chunk, vec in zip(chunks, vectors):
                vector_id = await vs.insert(
                    db=db,
                    org_id=org_id,
                    chunk_id=chunk.id,
                    provider=provider_type.value,
                    model=model_name,
                    dimensions=dims,
                    vector=vec,
                    checksum=hashlib.sha256(chunk.content.encode("utf-8")).hexdigest()
                )
                chunk.embedding_vector_id = vector_id
                chunk.embedding_status = EmbeddingStatus.EMBEDDED

            # Update document to complete
            doc.status = KnowledgeDocumentStatus.READY
            doc.processing_finished_at = datetime.utcnow()
            await db.commit()
            await db.refresh(doc)
            return doc

        except Exception as e:
            db.add(doc) # Ensure doc is in session state
            doc.status = KnowledgeDocumentStatus.FAILED
            doc.processing_error = traceback.format_exc()
            doc.processing_finished_at = datetime.utcnow()
            await db.commit()
            await db.refresh(doc)
            raise e

    @classmethod
    async def get_document(cls, db: AsyncSession, org_id: uuid.UUID, doc_id: uuid.UUID) -> Optional[KnowledgeDocument]:
        stmt = select(KnowledgeDocument).where(
            KnowledgeDocument.organization_id == org_id,
            KnowledgeDocument.id == doc_id,
            KnowledgeDocument.deleted_at.is_(None)
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    @classmethod
    async def list_documents(cls, db: AsyncSession, org_id: uuid.UUID, limit: int = 20, offset: int = 0) -> list[KnowledgeDocument]:
        stmt = select(KnowledgeDocument).where(
            KnowledgeDocument.organization_id == org_id,
            KnowledgeDocument.deleted_at.is_(None)
        ).order_by(KnowledgeDocument.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def delete_document(cls, db: AsyncSession, org_id: uuid.UUID, doc_id: uuid.UUID) -> None:
        doc = await cls.get_document(db, org_id, doc_id)
        if not doc:
            raise ValidationException("Document not found or access denied.")
        
        # Soft delete document
        doc.deleted_at = datetime.utcnow()
        
        # Delete chunks & embeddings (hard delete chunks + vectors because soft deletes are for core CRM entities, not intermediate index artifacts)
        # Cascade configuration will handle deleting from 'embeddings' and 'knowledge_chunks' tables automatically when doc_id is hard deleted,
        # but since we soft delete the document, let's explicitly delete chunks & embeddings to clean up index storage!
        await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == doc_id))
        await db.commit()
