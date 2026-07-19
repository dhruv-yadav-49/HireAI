"""
app/repositories/playground_repository.py

Data Access Layer for Playground Sessions, Experiments, and Prompt Runs.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ComparisonType, ExperimentStatus, PlaygroundSessionStatus, SandboxIsolationLevel
from app.models.playground_experiment import PlaygroundExperiment
from app.models.playground_session import PlaygroundSession
from app.models.prompt_experiment import PromptExperiment


class PlaygroundRepository:
    """Repository for developer playground data models."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Playground Session ─────────────────────────────────────────────────────

    async def create_session(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        name: str = "Playground Session",
        isolation_level: SandboxIsolationLevel = SandboxIsolationLevel.READ_ONLY,
        ttl_hours: int = 24,
    ) -> PlaygroundSession:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=ttl_hours)

        session = PlaygroundSession(
            id=uuid.uuid4(),
            organization_id=org_id,
            user_id=user_id,
            name=name,
            status=PlaygroundSessionStatus.ACTIVE,
            isolation_level=isolation_level,
            started_at=now,
            expires_at=expires_at,
        )
        self._db.add(session)
        await self._db.flush()
        return session

    async def get_session(self, session_id: uuid.UUID) -> Optional[PlaygroundSession]:
        stmt = select(PlaygroundSession).where(PlaygroundSession.id == session_id)
        res = await self._db.execute(stmt)
        return res.scalar_one_or_none()

    async def end_session(self, session_id: uuid.UUID) -> None:
        now = datetime.now(timezone.utc)
        stmt = (
            update(PlaygroundSession)
            .where(PlaygroundSession.id == session_id)
            .values(
                status=PlaygroundSessionStatus.EXPIRED,
                ended_at=now,
            )
        )
        await self._db.execute(stmt)
        await self._db.flush()

    # ── Playground Experiment ──────────────────────────────────────────────────

    async def create_experiment(
        self,
        session_id: uuid.UUID,
        org_id: uuid.UUID,
        experiment_name: str,
        comparison_type: ComparisonType = ComparisonType.PROMPT,
        description: Optional[str] = None,
        matrix_config: Optional[Dict[str, Any]] = None,
    ) -> PlaygroundExperiment:
        exp = PlaygroundExperiment(
            id=uuid.uuid4(),
            session_id=session_id,
            organization_id=org_id,
            experiment_name=experiment_name,
            description=description,
            status=ExperimentStatus.RUNNING,
            comparison_type=comparison_type,
            matrix_config_json=matrix_config or {},
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(exp)
        await self._db.flush()
        return exp

    async def create_prompt_experiment_run(
        self,
        experiment_id: uuid.UUID,
        prompt_text: str,
        output_text: str,
        prompt_hash: str,
        compiled_prompt_hash: str,
        model_name: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        latency_ms: int = 0,
        token_cost: float = 0.0,
        evaluation_score: float = 0.0,
        governance_decision: Optional[str] = None,
        normalized_metrics: Optional[Dict[str, Any]] = None,
    ) -> PromptExperiment:
        run = PromptExperiment(
            id=uuid.uuid4(),
            experiment_id=experiment_id,
            prompt_version=1,
            experiment_version=1,
            runtime_version="1.0",
            provider_version="1.0",
            prompt_hash=prompt_hash,
            compiled_prompt_hash=compiled_prompt_hash,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            prompt_text=prompt_text,
            output_text=output_text,
            latency_ms=latency_ms,
            token_cost=token_cost,
            evaluation_score=evaluation_score,
            governance_decision=governance_decision,
            normalized_metrics_json=normalized_metrics or {},
            created_at=datetime.now(timezone.utc),
        )
        self._db.add(run)
        await self._db.flush()
        return run

    async def list_runs_for_experiment(self, experiment_id: uuid.UUID) -> List[PromptExperiment]:
        stmt = (
            select(PromptExperiment)
            .where(PromptExperiment.experiment_id == experiment_id)
            .order_by(PromptExperiment.created_at.asc())
        )
        res = await self._db.execute(stmt)
        return list(res.scalars().all())
