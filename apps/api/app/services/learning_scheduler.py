import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LearningTriggerMode
from app.services.learning_engine import LearningEngine
from app.services.improvement_engine import ImprovementEngine
from app.core.events import DomainEvent, get_event_publisher


class LearningScheduler:
    """Nightly scheduler that runs learning updates and triggers optimizations.

    ADR-018: Continuous Improvement Loop.
    CTO refinement #9: Trigger modes (MANUAL, SCHEDULED, EVENT_DRIVEN).
    """

    @classmethod
    async def run_scheduler(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        trigger_mode: LearningTriggerMode = LearningTriggerMode.SCHEDULED
    ) -> dict:
        """Processes the continuous improvement loop for an organization."""
        # 1. Ingest traces into the dataset
        dataset_count = await LearningEngine.process_learning_cycle(db, org_id)

        # 2. Run optimizers to create suggest updates
        optimization_results = await ImprovementEngine.run_optimization_cycle(db, org_id)

        # 3. Publish completion events
        await cls._publish_event(org_id, "learning.scheduler.completed", {
            "trigger_mode": trigger_mode.value,
            "dataset_rows_added": dataset_count,
            "bundle_id": optimization_results.get("bundle_id")
        })

        return {
            "trigger_mode": trigger_mode.value,
            "dataset_rows_added": dataset_count,
            **optimization_results
        }

    @staticmethod
    async def _publish_event(org_id: uuid.UUID, event_name: str, payload: dict) -> None:
        event = DomainEvent(
            event_name=event_name,
            tenant_id=org_id,
            request_id=uuid.uuid4(),
            actor_id=None,
            payload=payload
        )
        try:
            pub = get_event_publisher()
            await pub.publish(event)
        except Exception:
            pass
