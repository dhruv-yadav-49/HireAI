import uuid
from typing import Any, Optional, Protocol
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.embedding import Embedding


class VectorStore(Protocol):
    """Protocol interface defining operations for vector databases."""

    async def insert(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        chunk_id: uuid.UUID,
        provider: str,
        model: str,
        dimensions: int,
        vector: list[float],
        checksum: str
    ) -> uuid.UUID:
        """Stores vector representation in the vector store."""
        ...

    async def search(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        query_vector: list[float],
        limit: int = 5
    ) -> list[dict[str, Any]]:
        """Searches nearest neighbor float vectors using cosine similarity distance metric."""
        ...

    async def delete_by_document(self, db: AsyncSession, org_id: uuid.UUID, document_id: uuid.UUID) -> None:
        """Removes all embeddings corresponding to a specified document's chunks."""
        ...


class PgVectorStore(VectorStore):
    """SQLAlchemy implementation of VectorStore using PostgreSQL REAL[] native arrays with custom plpgsql fallback."""

    async def insert(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        chunk_id: uuid.UUID,
        provider: str,
        model: str,
        dimensions: int,
        vector: list[float],
        checksum: str
    ) -> uuid.UUID:
        embedding = Embedding(
            organization_id=org_id,
            chunk_id=chunk_id,
            provider=provider,
            provider_model=model,
            dimensions=dimensions,
            checksum_sha256=checksum,
            vector=vector
        )
        db.add(embedding)
        await db.flush()
        return embedding.id

    async def search(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        query_vector: list[float],
        limit: int = 5
    ) -> list[dict[str, Any]]:
        # Query utilizing PL/pgSQL public.cosine_similarity
        query = text("""
            SELECT e.chunk_id, kc.content, kc.metadata_json, public.cosine_similarity(e.vector, CAST(:query_vector AS REAL[])) AS similarity
            FROM embeddings e
            JOIN knowledge_chunks kc ON kc.id = e.chunk_id
            WHERE e.organization_id = :org_id
            ORDER BY similarity DESC
            LIMIT :limit
        """)

        
        result = await db.execute(query, {
            "query_vector": query_vector,
            "org_id": org_id,
            "limit": limit
        })
        
        records = []
        for row in result.all():
            records.append({
                "chunk_id": row.chunk_id,
                "content": row.content,
                "metadata_json": row.metadata_json,
                "score": float(row.similarity or 0.0)
            })
        return records

    async def delete_by_document(self, db: AsyncSession, org_id: uuid.UUID, document_id: uuid.UUID) -> None:
        # Cascades deletes of associated embeddings automatically since foreign keys are configured with ondelete='CASCADE'
        pass
