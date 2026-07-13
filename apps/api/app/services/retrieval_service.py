import uuid
import time
import math
from typing import Optional, Any
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import RetrievalSource, EmbeddingProvider
from app.models.lead import Lead
from app.models.lead_note import LeadNote
from app.models.task import Task
from app.models.workflow import Workflow
from app.models.retrieval_log import RetrievalLog
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import PgVectorStore
from app.services.memory_service import MemoryService
from app.services.reranker import Reranker


class RetrievalResult(BaseModel):
    """Standardized retrieval result representation across all sources."""
    source: RetrievalSource
    content: str
    raw_score: float
    normalized_score: float
    rerank_score: float = 0.0
    final_score: float = 0.0
    metadata: dict[str, Any] = {}


class VectorRetriever:
    """Retrieves document chunks matching semantic query vectors."""
    @classmethod
    async def retrieve(
        cls, db: AsyncSession, org_id: uuid.UUID, query: str, provider: EmbeddingProvider, limit: int = 5
    ) -> tuple[list[RetrievalResult], int]:
        start = time.time()
        # Embed query text
        query_vector = await EmbeddingService.embed_text(provider, query)
        embed_latency_ms = int((time.time() - start) * 1000)

        start_vs = time.time()
        vs = PgVectorStore()
        records = await vs.search(db, org_id, query_vector, limit=limit)
        vector_latency_ms = int((time.time() - start_vs) * 1000)

        results = []
        for r in records:
            # Map score to [0, 1] range (cosine similarity is in [-1, 1])
            norm_score = (r["score"] + 1.0) / 2.0
            results.append(RetrievalResult(
                source=RetrievalSource.VECTOR,
                content=r["content"],
                raw_score=r["score"],
                normalized_score=norm_score,
                metadata=r["metadata_json"] or {}
            ))
        return results, embed_latency_ms, vector_latency_ms


class MemoryRetriever:
    """Retrieves long-term facts/preferences and decay-scored memories."""
    @classmethod
    async def retrieve(
        cls, db: AsyncSession, org_id: uuid.UUID, lead_id: Optional[uuid.UUID] = None, limit: int = 5
    ) -> tuple[list[RetrievalResult], int]:
        start = time.time()
        memories = await MemoryService.get_active_memories(db, org_id, lead_id=lead_id)
        latency_ms = int((time.time() - start) * 1000)

        results = []
        for m in memories[:limit]:
            results.append(RetrievalResult(
                source=RetrievalSource.MEMORY,
                content=m["content"],
                raw_score=m["effective_score"],
                normalized_score=m["effective_score"], # already normalized [0, 1]
                metadata={"memory_id": str(m["id"]), "source": m["source"], "memory_version": m["memory_version"]}
            ))
        return results, latency_ms


class CRMRetriever:
    """Retrieves structured CRM profiles (leads, tasks, notes)."""
    @classmethod
    async def retrieve(
        cls, db: AsyncSession, org_id: uuid.UUID, lead_id: Optional[uuid.UUID] = None, limit: int = 5
    ) -> tuple[list[RetrievalResult], int]:
        if not lead_id:
            return [], 0
            
        start = time.time()
        results = []
        
        # 1. Lead details
        lead_stmt = select(Lead).where(Lead.id == lead_id, Lead.organization_id == org_id)
        lead = (await db.execute(lead_stmt)).scalar_one_or_none()
        if lead:
            results.append(RetrievalResult(
                source=RetrievalSource.CRM,
                content=f"Lead Profile - Name: {lead.name}, Email: {lead.email or 'N/A'}, Phone: {lead.phone or 'N/A'}, Status: {lead.status.value if hasattr(lead.status, 'value') else lead.status}",
                raw_score=1.0,
                normalized_score=1.0,
                metadata={"lead_id": str(lead.id)}
            ))

        # 2. Lead Notes
        notes_stmt = select(LeadNote).where(LeadNote.lead_id == lead_id).limit(limit)
        notes = (await db.execute(notes_stmt)).scalars().all()
        for note in notes:
            results.append(RetrievalResult(
                source=RetrievalSource.CRM,
                content=f"Lead Note: {note.content}",
                raw_score=0.9,
                normalized_score=0.9,
                metadata={"note_id": str(note.id)}
            ))

        # 3. Lead Tasks
        tasks_stmt = select(Task).where(Task.lead_id == lead_id).limit(limit)
        tasks = (await db.execute(tasks_stmt)).scalars().all()
        for task in tasks:
            results.append(RetrievalResult(
                source=RetrievalSource.CRM,
                content=f"Lead Task: {task.title} - Description: {task.description or 'N/A'} - Status: {task.status.value if hasattr(task.status, 'value') else task.status}",
                raw_score=0.85,
                normalized_score=0.85,
                metadata={"task_id": str(task.id)}
            ))

        latency_ms = int((time.time() - start) * 1000)
        return results[:limit], latency_ms


class WorkflowRetriever:
    """Retrieves active workflows configured for the organization."""
    @classmethod
    async def retrieve(
        cls, db: AsyncSession, org_id: uuid.UUID, limit: int = 5
    ) -> tuple[list[RetrievalResult], int]:
        start = time.time()
        stmt = select(Workflow).where(
            Workflow.organization_id == org_id,
            Workflow.enabled == True,
            Workflow.deleted_at.is_(None)
        ).limit(limit)
        
        workflows = (await db.execute(stmt)).scalars().all()
        results = []
        for wf in workflows:
            results.append(RetrievalResult(
                source=RetrievalSource.WORKFLOW,
                content=f"Active Workflow: {wf.name} - Trigger: {wf.trigger_type.value if hasattr(wf.trigger_type, 'value') else wf.trigger_type}",
                raw_score=0.8,
                normalized_score=0.8,
                metadata={"workflow_id": str(wf.id)}
            ))
            
        latency_ms = int((time.time() - start) * 1000)
        return results, latency_ms


class RetrievalService:
    """Coordinating hybrid retrieval pipeline returning unified, reranked RetrievalResult resources."""

    @classmethod
    async def retrieve(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        query: str,
        conversation_id: Optional[uuid.UUID] = None,
        lead_id: Optional[uuid.UUID] = None,
        user_id: Optional[uuid.UUID] = None,
        provider: EmbeddingProvider = EmbeddingProvider.MOCK,
        limit: int = 5
    ) -> list[RetrievalResult]:
        start_total = time.time()

        # Call individual retrievers
        vec_res, embed_lat, vector_lat = await VectorRetriever.retrieve(
            db, org_id, query, provider, limit=limit
        )
        mem_res, mem_lat = await MemoryRetriever.retrieve(db, org_id, lead_id=lead_id, limit=limit)
        crm_res, crm_lat = await CRMRetriever.retrieve(db, org_id, lead_id=lead_id, limit=limit)
        wf_res, wf_lat = await WorkflowRetriever.retrieve(db, org_id, limit=limit)

        # Merge results
        merged_raw = []
        for r in (vec_res + mem_res + crm_res + wf_res):
            merged_raw.append(r.dict())

        # Rerank
        start_rerank = time.time()
        reranked = Reranker.rerank(query, merged_raw, limit=limit)
        rerank_lat = int((time.time() - start_rerank) * 1000)

        total_latency = int((time.time() - start_total) * 1000)

        # Log metrics to database
        log = RetrievalLog(
            conversation_id=conversation_id,
            query=query,
            retrieval_source=RetrievalSource.HYBRID,
            retrieved_chunks=reranked,
            retrieval_latency_ms=total_latency,
            embedding_latency_ms=embed_lat,
            vector_search_latency_ms=vector_lat,
            crm_latency_ms=crm_lat,
            memory_latency_ms=mem_lat,
            rerank_latency_ms=rerank_lat,
            total_chunks=len(reranked),
            total_tokens=sum(len(r["content"].split()) for r in reranked) # rough approximation for logging
        )
        db.add(log)
        await db.commit()

        # Parse back to Pydantic objects
        return [RetrievalResult(**r) for r in reranked]
