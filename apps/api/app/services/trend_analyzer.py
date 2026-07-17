import uuid
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.ai_kpi_snapshot import AIKPISnapshot
from app.models.enums import TrendDirection


class TrendAnalyzer:
    @classmethod
    async def analyze_trends(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        current: AIKPISnapshot
    ) -> list[dict[str, Any]]:
        """Compares current snapshot with historical snapshot to evaluate trend directions."""
        # Find last snapshot in database
        stmt = (
            select(AIKPISnapshot)
            .where(
                AIKPISnapshot.organization_id == org_id
            )
            .order_by(AIKPISnapshot.calculated_at.desc())
            .offset(1)  # Get the one before the current one (which was flushed/added)
            .limit(1)
        )
        res = await db.execute(stmt)
        previous = res.scalar_one_or_none()

        trends = []

        def get_direction(change: float) -> TrendDirection:
            if change > 0.5:
                return TrendDirection.UP
            elif change < -0.5:
                return TrendDirection.DOWN
            return TrendDirection.STABLE

        metrics_config = [
            ("total_leads", "Total Leads"),
            ("pipeline_value", "Pipeline Value"),
            ("conversion_rate", "Conversion Rate"),
            ("average_response_time", "Average Response Time")
        ]

        for attr, display in metrics_config:
            curr_val = float(getattr(current, attr) or 0.0)
            # Default comparison value if no history exists (returns STABLE trend)
            prev_val = float(getattr(previous, attr) or 0.0) if previous else curr_val
            
            if prev_val > 0.0:
                change = ((curr_val - prev_val) / prev_val) * 100.0
            else:
                change = 0.0
            
            trends.append({
                "metric": display,
                "direction": get_direction(change),
                "change_percent": round(change, 2)
            })

        return trends
