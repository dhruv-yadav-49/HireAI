import uuid
from typing import Optional, Any
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_request_context
from app.core.context import RequestContext
from app.db.session import get_db
from app.models.enums import EmbeddingProvider, ConversationMemoryScope, MemoryType, RetrievalSource
from app.services.knowledge_service import KnowledgeService
from app.services.memory_service import MemoryService
from app.services.retrieval_service import RetrievalService
from app.services.embedding_service import EmbeddingService

router = APIRouter(prefix="/memory", tags=["memory-knowledge"])


# ── Schemas ──

class KnowledgeIngestRequest(BaseModel):
    title: str = Field(..., max_length=200)
    content: str = Field(...)
    mime_type: str = "text/plain"
    storage_path: str = "upload://default"
    provider: EmbeddingProvider = EmbeddingProvider.MOCK
    model: str = "mock-embedding-v1"
    description: Optional[str] = None


class KnowledgeDocumentResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    title: str
    description: Optional[str]
    mime_type: str
    file_size: int
    storage_path: str
    status: str
    chunk_count: int
    embedding_provider: str
    embedding_model: str

    class Config:
        from_attributes = True


class MemoryCreateRequest(BaseModel):
    content: str = Field(...)
    scope: ConversationMemoryScope = ConversationMemoryScope.ORGANIZATION
    memory_type: MemoryType = MemoryType.LONG_TERM
    source: str = "MANUAL"
    conversation_id: Optional[uuid.UUID] = None
    lead_id: Optional[uuid.UUID] = None
    user_id: Optional[uuid.UUID] = None
    importance_score: float = 1.0
    confidence_score: float = 1.0


class MemoryResponse(BaseModel):
    id: uuid.UUID
    content: str
    scope: str
    memory_type: str
    importance_score: float
    confidence_score: float
    effective_score: float
    memory_version: int
    source: str
    supersedes_memory_id: Optional[uuid.UUID]


class HybridSearchRequest(BaseModel):
    query: str = Field(...)
    lead_id: Optional[uuid.UUID] = None
    user_id: Optional[uuid.UUID] = None
    limit: int = 5


class HybridSearchResultItem(BaseModel):
    source: str
    content: str
    raw_score: float
    normalized_score: float
    rerank_score: float
    final_score: float
    metadata: dict[str, Any]


class EmbeddingHealthRequest(BaseModel):
    provider: EmbeddingProvider = EmbeddingProvider.MOCK
    credentials: Optional[dict[str, Any]] = None


# ── Knowledge Ingestion Endpoints ───────────────────────────────────────────

@router.post(
    "/knowledge/upload",
    response_model=KnowledgeDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest new document into Knowledge Base",
)
async def ingest_knowledge(
    data: KnowledgeIngestRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeDocumentResponse:
    doc = await KnowledgeService.ingest_document(
        db=db,
        org_id=ctx.tenant_id,
        user_id=ctx.user.id if ctx.user else uuid.UUID(int=0), # fallback if test context doesn't supply user
        title=data.title,
        content_str=data.content,
        mime_type=data.mime_type,
        storage_path=data.storage_path,
        provider_type=data.provider,
        model_name=data.model,
        description=data.description
    )
    return KnowledgeDocumentResponse.model_validate(doc)


@router.get(
    "/knowledge",
    response_model=list[KnowledgeDocumentResponse],
    summary="List all ingested documents",
)
async def list_knowledge(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> list[KnowledgeDocumentResponse]:
    docs = await KnowledgeService.list_documents(db, ctx.tenant_id, limit=limit, offset=offset)
    return [KnowledgeDocumentResponse.model_validate(d) for d in docs]


@router.delete(
    "/knowledge/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete knowledge document, chunks, and embeddings",
)
async def delete_knowledge(
    doc_id: uuid.UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
):
    await KnowledgeService.delete_document(db, ctx.tenant_id, doc_id)
    return status.HTTP_204_NO_CONTENT


# ── AI Memory Endpoints ─────────────────────────────────────────────────────

@router.post(
    "/memory",
    response_model=MemoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record manually parsed memory fact",
)
async def create_memory_fact(
    data: MemoryCreateRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> MemoryResponse:
    mem = await MemoryService.create_memory(
        db=db,
        org_id=ctx.tenant_id,
        content=data.content,
        scope=data.scope,
        memory_type=data.memory_type,
        source=data.source,
        conversation_id=data.conversation_id,
        lead_id=data.lead_id,
        user_id=data.user_id,
        importance_score=data.importance_score,
        confidence_score=data.confidence_score
    )
    # Convert to schema response
    return MemoryResponse(
        id=mem.id,
        content=mem.content,
        scope=mem.scope.value if hasattr(mem.scope, "value") else mem.scope,
        memory_type=mem.memory_type.value if hasattr(mem.memory_type, "value") else mem.memory_type,
        importance_score=float(mem.importance_score),
        confidence_score=float(mem.confidence_score),
        effective_score=float(mem.importance_score * mem.confidence_score),
        memory_version=mem.memory_version,
        source=mem.source,
        supersedes_memory_id=mem.supersedes_memory_id
    )


@router.get(
    "/memory",
    response_model=list[MemoryResponse],
    summary="Get active scoped memories",
)
async def list_memories(
    scope: Optional[ConversationMemoryScope] = None,
    lead_id: Optional[uuid.UUID] = None,
    user_id: Optional[uuid.UUID] = None,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> list[MemoryResponse]:
    memories = await MemoryService.get_active_memories(
        db, ctx.tenant_id, lead_id=lead_id, user_id=user_id, scope=scope
    )
    return [MemoryResponse(**m) for m in memories]


# ── Hybrid Retrieval API Endpoints ──────────────────────────────────────────

@router.post(
    "/retrieval/search",
    response_model=list[HybridSearchResultItem],
    summary="Test query hybrid retrieval and reranking",
)
async def hybrid_search_test(
    data: HybridSearchRequest,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
) -> list[HybridSearchResultItem]:
    results = await RetrievalService.retrieve(
        db=db,
        org_id=ctx.tenant_id,
        query=data.query,
        lead_id=data.lead_id,
        user_id=data.user_id,
        provider=EmbeddingProvider.MOCK,
        limit=data.limit
    )
    return [
        HybridSearchResultItem(
            source=r.source.value if hasattr(r.source, "value") else r.source,
            content=r.content,
            raw_score=r.raw_score,
            normalized_score=r.normalized_score,
            rerank_score=r.rerank_score,
            final_score=r.final_score,
            metadata=r.metadata
        ) for r in results
    ]


@router.post(
    "/embeddings/health",
    status_code=status.HTTP_200_OK,
    summary="Embedding connection health state audit",
)
async def health_check_embeddings(
    data: EmbeddingHealthRequest,
    db: AsyncSession = Depends(get_db),
):
    provider_impl = EmbeddingService.get_provider(data.provider)
    healthy = await provider_impl.health_check(data.credentials)
    return {"status": "healthy" if healthy else "unhealthy"}
