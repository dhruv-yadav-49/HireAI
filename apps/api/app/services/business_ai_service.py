import uuid
from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.enums import ForecastPeriod, BusinessReportType, RecommendationStatus, AgentType
from app.models.ai_business_report import AIBusinessReport
from app.models.ai_recommendation import AIRecommendation
from app.repositories.business_ai_repository import BusinessAIRepository
from app.services.business_analysis_engine import BusinessAnalysisEngine
from app.services.executive_report_engine import ExecutiveReportEngine
from app.services.orchestrator import Orchestrator
from app.core.events import DomainEvent, get_event_publisher


class BusinessAIService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = BusinessAIRepository(db)

    async def publish_event(self, ctx: RequestContext, event_name: str, payload: dict) -> None:
        """Publishes local domain events inside transaction."""
        event = DomainEvent(
            event_name=event_name,
            tenant_id=ctx.tenant_id,
            request_id=ctx.request_id,
            actor_id=ctx.user.id if ctx.user else None,
            payload=payload
        )
        pub = get_event_publisher()
        await pub.publish(event)

    async def run_analysis(
        self,
        ctx: RequestContext,
        forecast_period: ForecastPeriod = ForecastPeriod.F_30_DAYS
    ) -> dict[str, Any]:
        """Runs BI calculation pipelines and stores snapshots, forecasts, and recommendations."""
        res = await BusinessAnalysisEngine.run_full_analysis(self.db, ctx, forecast_period)

        # Publish Domain Events
        await self.publish_event(ctx, "business.snapshot.created", {
            "snapshot_id": str(res["snapshot"].id),
            "total_leads": res["snapshot"].total_leads
        })
        await self.publish_event(ctx, "business.forecast.generated", {
            "forecast_id": str(res["forecast"].id),
            "predicted_revenue": float(res["forecast"].predicted_revenue)
        })
        for r in res["recommendations"]:
            await self.publish_event(ctx, "business.recommendation.created", {
                "recommendation_id": str(r.id),
                "type": r.recommendation_type
            })

        return res

    async def generate_report(
        self,
        ctx: RequestContext,
        report_type: BusinessReportType,
        title: str,
        parent_report_id: Optional[uuid.UUID] = None
    ) -> AIBusinessReport:
        """Runs analysis pipelines and generates a formal immutable Business Intelligence executive report."""
        # 1. Run full analysis
        analysis = await self.run_analysis(ctx)
        
        # 2. Compile report
        report = ExecutiveReportEngine.generate_report(
            org_id=ctx.tenant_id,
            report_type=report_type,
            title=title,
            snapshot=analysis["snapshot"],
            forecast=analysis["forecast"],
            health_result=analysis["health_result"],
            trends=analysis["trends"],
            anomalies=analysis["anomalies"],
            recommendations=analysis["recommendations"],
            parent_report_id=parent_report_id,
            generated_by=ctx.user.id if ctx.user else None
        )
        await self.repo.create_report(report)

        await self.publish_event(ctx, "business.report.generated", {
            "report_id": str(report.id),
            "title": report.title
        })

        return report

    async def delegate_recommendation(
        self,
        ctx: RequestContext,
        recommendation_id: uuid.UUID,
        session_id: Optional[uuid.UUID] = None
    ) -> dict[str, Any]:
        """Delegates recommendation actions to execution layers using the Multi-Agent Orchestrator."""
        rec = await self.repo.get_recommendation_by_id(ctx, recommendation_id)
        if not rec:
            raise ValueError("Recommendation not found or unauthorized.")

        if rec.status != RecommendationStatus.PENDING:
            raise ValueError("Only PENDING recommendations can be delegated.")

        # Determine target executor agent (default to first agent listed in recommended_agents array)
        target_agent_str = rec.recommended_agents[0] if rec.recommended_agents else "SALES"
        target_agent = AgentType[target_agent_str]

        # Use Orchestrator to delegate task execution safely
        orchestrator = Orchestrator(self.db)
        if not session_id:
            # Spawn a new orchestrator workflow session initiated by Business Analyst
            session = await orchestrator.create_session(ctx, initiator_agent=AgentType.BUSINESS_ANALYST)
            session_id = session.id

        delegation_res = await orchestrator.delegate_task(
            ctx,
            session_id=session_id,
            goal=f"Execute recommendation: {rec.reason}. Recommended actions: {rec.expected_impact}",
            priority=rec.priority.value if hasattr(rec.priority, 'value') else rec.priority
        )

        # Update recommendation status
        rec.status = RecommendationStatus.DELEGATED
        await self.repo.update_recommendation(rec)

        await self.publish_event(ctx, "business.recommendation.delegated", {
            "recommendation_id": str(recommendation_id),
            "session_id": str(session_id),
            "task_id": str(delegation_res["task"].id)
        })

        return {
            "task": delegation_res["task"],
            "session_id": session_id,
            "delegation_metrics": delegation_res["delegation_metrics"]
        }
