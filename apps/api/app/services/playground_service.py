"""
app/services/playground_service.py

Playground Service Orchestrator.

High-level business logic coordinating PlaygroundEngine, PlaygroundRepository,
AuditLogger (7C), and event publication.
"""
import uuid
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AIProvider, AuditAction, ComparisonType, PolicyPackType, SandboxIsolationLevel
from app.models.playground_session import PlaygroundSession
from app.playground.playground_context import PlaygroundContext, build_playground_context
from app.playground.playground_engine import PlaygroundEngine
from app.playground.playground_metrics import PlaygroundMetricsService, PlaygroundMetricsSummary
from app.repositories.playground_repository import PlaygroundRepository
from app.security.audit_logger import AuditLogger
from app.security.security_context import SecurityContext


class PlaygroundService:
    """Orchestrates developer playground session lifecycle, prompt execution, and comparisons."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = PlaygroundRepository(db)

    async def start_session(
        self,
        sec_ctx: SecurityContext,
        name: str = "Playground Session",
        isolation_level: SandboxIsolationLevel = SandboxIsolationLevel.READ_ONLY,
    ) -> PlaygroundSession:
        session = await self._repo.create_session(
            org_id=sec_ctx.organization_id,
            user_id=sec_ctx.user_id,
            name=name,
            isolation_level=isolation_level,
        )

        await AuditLogger.log(
            self._db,
            action=AuditAction.CREATE,
            organization_id=sec_ctx.organization_id,
            user_id=sec_ctx.user_id,
            resource_type="PlaygroundSession",
            resource_id=str(session.id),
            success=True,
            request_id=sec_ctx.request_id,
        )

        return session

    async def end_session(self, sec_ctx: SecurityContext, session_id: uuid.UUID) -> None:
        await self._repo.end_session(session_id)
        await AuditLogger.log(
            self._db,
            action=AuditAction.DELETE,
            organization_id=sec_ctx.organization_id,
            user_id=sec_ctx.user_id,
            resource_type="PlaygroundSession",
            resource_id=str(session_id),
            success=True,
            request_id=sec_ctx.request_id,
        )

    async def run_prompt_experiment(
        self,
        sec_ctx: SecurityContext,
        session_id: uuid.UUID,
        template: str,
        variables: Optional[Dict[str, Any]] = None,
        provider: AIProvider = AIProvider.MOCK,
        model_name: str = "mock-llm-v1",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        isolation_level: SandboxIsolationLevel = SandboxIsolationLevel.READ_ONLY,
    ) -> Dict[str, Any]:
        play_ctx = build_playground_context(
            security_context=sec_ctx,
            session_id=session_id,
            provider=provider,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            isolation_level=isolation_level,
        )

        engine = PlaygroundEngine(play_ctx)
        run_res = await engine.execute_prompt_run(
            template=template,
            variables=variables,
            model_name=model_name,
            temperature=temperature,
        )

        # Create experiment and run trial in repository
        exp = await self._repo.create_experiment(
            session_id=session_id,
            org_id=sec_ctx.organization_id,
            experiment_name=f"Run: {template[:30]}",
            comparison_type=ComparisonType.PROMPT,
        )

        trial = await self._repo.create_prompt_experiment_run(
            experiment_id=exp.id,
            prompt_text=run_res.prompt_text,
            output_text=run_res.output_text,
            prompt_hash=run_res.prompt_hash,
            compiled_prompt_hash=run_res.compiled_prompt_hash,
            model_name=run_res.model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            latency_ms=run_res.latency_ms,
            token_cost=run_res.token_cost,
        )

        return {
            "session_id": str(session_id),
            "experiment_id": str(exp.id),
            "run_id": str(trial.id),
            "prompt_text": run_res.prompt_text,
            "compiled_prompt": run_res.compiled_prompt,
            "output_text": run_res.output_text,
            "prompt_hash": run_res.prompt_hash,
            "compiled_prompt_hash": run_res.compiled_prompt_hash,
            "latency_ms": run_res.latency_ms,
            "token_cost": run_res.token_cost,
            "model_name": run_res.model_name,
        }

    async def replay_trace(
        self,
        sec_ctx: SecurityContext,
        session_id: uuid.UUID,
        trace_id: uuid.UUID,
        prompt_override: Optional[str] = None,
        model_override: Optional[str] = None,
        temperature_override: Optional[float] = None,
    ) -> Dict[str, Any]:
        play_ctx = build_playground_context(security_context=sec_ctx, session_id=session_id)
        engine = PlaygroundEngine(play_ctx)
        return await engine.replay_trace(
            db=self._db,
            trace_id=trace_id,
            prompt_override=prompt_override,
            model_override=model_override,
            temperature_override=temperature_override,
        )

    async def run_comparison(
        self,
        sec_ctx: SecurityContext,
        session_id: uuid.UUID,
        comparison_type: ComparisonType,
        prompt_a: Optional[str] = None,
        prompt_b: Optional[str] = None,
        models: Optional[List[str]] = None,
        action_type: Optional[str] = None,
        action_payload: Optional[Dict[str, Any]] = None,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        play_ctx = build_playground_context(security_context=sec_ctx, session_id=session_id)
        engine = PlaygroundEngine(play_ctx)
        return await engine.compare(
            comparison_type=comparison_type,
            prompt_a=prompt_a,
            prompt_b=prompt_b,
            models=models,
            action_type=action_type,
            action_payload=action_payload,
            variables=variables,
        )
