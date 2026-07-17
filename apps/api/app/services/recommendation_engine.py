import uuid
from typing import Any
from app.models.ai_kpi_snapshot import AIKPISnapshot
from app.models.ai_forecast import AIForecast
from app.models.ai_recommendation import AIRecommendation
from app.models.enums import RecommendationPriority, RecommendationStatus


class RecommendationEngine:
    @classmethod
    def generate_recommendations(
        cls,
        org_id: uuid.UUID,
        snapshot: AIKPISnapshot,
        forecast: AIForecast,
        health_result: dict[str, Any],
        anomalies: list[dict[str, Any]]
    ) -> list[AIRecommendation]:
        """Formulates actionable recommendations based on snapshot, forecast, and anomaly metrics."""
        recs = []

        # 1. Follow-up issues check
        health_score = health_result.get("score", 100)
        dimensions = health_result.get("dimensions", {})
        
        if dimensions.get("follow_up", 100) < 70:
            recs.append(AIRecommendation(
                organization_id=org_id,
                recommendation_type="LEAD_OUTREACH_CAMPAIGN",
                priority=RecommendationPriority.HIGH,
                reason="Multiple new leads detected without active outreach or progressed stage status.",
                expected_impact="Targeted outreach to new leads will capture prompt intent and improve overall conversions.",
                recommended_agents=["SALES"],
                status=RecommendationStatus.PENDING
            ))

        # 2. Response Speed check
        if snapshot.average_response_time > 10:
            recs.append(AIRecommendation(
                organization_id=org_id,
                recommendation_type="RESPONSE_DELAY_OPTIMIZATION",
                priority=RecommendationPriority.MEDIUM,
                reason=f"Average response time is currently {snapshot.average_response_time:.1f} minutes, which is above optimal SLA limits.",
                expected_impact="Enabling instant auto-replies or task triage is estimated to improve qualification rate by 12%.",
                recommended_agents=["SUPPORT", "SALES"],
                status=RecommendationStatus.PENDING
            ))

        # 3. Conversion Rate check
        if snapshot.conversion_rate < 0.10:
            recs.append(AIRecommendation(
                organization_id=org_id,
                recommendation_type="NURTURING_CAMPAIGN",
                priority=RecommendationPriority.HIGH,
                reason="Overall pipeline deal conversion win rate is below the 10% target threshold.",
                expected_impact="Launching a re-engagement newsletter campaign can revive stale leads and won deals.",
                recommended_agents=["MARKETING"],
                status=RecommendationStatus.PENDING
            ))

        # 4. Fallback default if pipeline is healthy
        if not recs:
            recs.append(AIRecommendation(
                organization_id=org_id,
                recommendation_type="PIPELINE_GROWTH_STRATEGY",
                priority=RecommendationPriority.LOW,
                reason="All pipeline dimensions and response SLA metrics are within optimal limits.",
                expected_impact="Running a top-of-funnel lead generation campaign can scale active pipeline value.",
                recommended_agents=["MARKETING"],
                status=RecommendationStatus.PENDING
            ))

        return recs
