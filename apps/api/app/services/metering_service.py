"""
app/services/metering_service.py

Usage Metering Service.

CTO Refinement #2:
  Generic usage event recorder metering:
  AI tokens, API calls, agent tasks, LLM cost, workflow executions,
  tool invocations, playground sessions, marketplace downloads, storage MB
"""
import uuid
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.usage_meter_log import UsageMeterLog
from app.models.enums import MeteredMetricType


class UsageMeteringService:
    """Records generic metered usage events for tenant accounting (CTO #2)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record_usage_event(
        self,
        org_id: uuid.UUID,
        metric_type: MeteredMetricType,
        quantity: float = 1.0,
        cost_units: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UsageMeterLog:
        """Records generic usage event."""
        log = UsageMeterLog(
            organization_id=org_id,
            metric_type=metric_type,
            quantity=quantity,
            cost_units=cost_units,
            metadata_json=metadata or {},
        )
        self.db.add(log)
        await self.db.commit()
        return log

    async def get_usage_summary(self, org_id: uuid.UUID) -> Dict[str, float]:
        """Calculates aggregated usage totals for current billing cycle."""
        stmt = select(
            UsageMeterLog.metric_type,
            func.sum(UsageMeterLog.quantity),
            func.sum(UsageMeterLog.cost_units),
        ).where(UsageMeterLog.organization_id == org_id).group_by(UsageMeterLog.metric_type)

        res = await self.db.execute(stmt)
        summary: Dict[str, float] = {}
        total_cost = 0.0

        for row in res.all():
            m_type, qty, cost = row[0], float(row[1] or 0.0), float(row[2] or 0.0)
            summary[f"{m_type.value.lower()}_count"] = qty
            total_cost += cost

        summary["total_cost_units"] = round(total_cost, 4)
        return summary
