import uuid
from typing import Any, Optional
from datetime import datetime, timezone
from app.models.ai_kpi_snapshot import AIKPISnapshot
from app.models.ai_forecast import AIForecast
from app.models.ai_recommendation import AIRecommendation
from app.models.ai_business_report import AIBusinessReport
from app.models.enums import BusinessReportType


class ExecutiveReportEngine:
    @classmethod
    def generate_report(
        cls,
        org_id: uuid.UUID,
        report_type: BusinessReportType,
        title: str,
        snapshot: AIKPISnapshot,
        forecast: AIForecast,
        health_result: dict[str, Any],
        trends: list[dict[str, Any]],
        anomalies: list[dict[str, Any]],
        recommendations: list[AIRecommendation],
        parent_report_id: Optional[uuid.UUID] = None,
        generated_by: Optional[uuid.UUID] = None
    ) -> AIBusinessReport:
        """Combines metrics and insights into a standardized business intelligence report document."""
        # 1. Formulate summary paragraph
        health_score = health_result.get("score", 100)
        health_state = health_result.get("health").value if hasattr(health_result.get("health"), 'value') else health_result.get("health")
        issues_count = len(health_result.get("issues", []))

        summary_text = (
            f"The business pipeline health score is currently evaluated at {health_score}/100, "
            f"classified as {health_state}. "
        )
        if issues_count > 0:
            summary_text += f"We detected {issues_count} operational warnings requiring immediate actions, primarily regarding lead follow-ups."
        else:
            summary_text += "Pipeline indicators are stable with optimal SLA and conversion performance."

        # 2. Package standardized report json schema
        report_payload = {
            "summary": {
                "overall_state": health_state,
                "health_score": health_score,
                "description": summary_text
            },
            "kpis": {
                "total_leads": snapshot.total_leads,
                "qualified_leads": snapshot.qualified_leads,
                "won_deals": snapshot.won_deals,
                "lost_deals": snapshot.lost_deals,
                "pipeline_value": float(snapshot.pipeline_value),
                "conversion_rate": float(snapshot.conversion_rate),
                "average_sales_cycle": float(snapshot.average_sales_cycle),
                "average_response_time": float(snapshot.average_response_time),
                "calculated_at": snapshot.calculated_at.isoformat()
            },
            "forecast": {
                "period": forecast.forecast_period.value if hasattr(forecast.forecast_period, 'value') else forecast.forecast_period,
                "predicted_revenue": float(forecast.predicted_revenue),
                "predicted_conversion_rate": float(forecast.predicted_conversion_rate),
                "confidence_score": float(forecast.confidence_score),
                "model": forecast.forecast_model,
                "assumptions": forecast.assumptions_json.get("assumptions", [])
            },
            "trends": [
                {
                    "metric": t["metric"],
                    "direction": t["direction"].value if hasattr(t["direction"], 'value') else t["direction"],
                    "change_percent": t["change_percent"]
                } for t in trends
            ],
            "anomalies": [
                {
                    "metric": a["metric"],
                    "severity": a["severity"].value if hasattr(a["severity"], 'value') else a["severity"],
                    "description": a["description"]
                } for a in anomalies
            ],
            "recommendations": [
                {
                    "id": str(r.id),
                    "type": r.recommendation_type,
                    "priority": r.priority.value if hasattr(r.priority, 'value') else r.priority,
                    "reason": r.reason,
                    "expected_impact": r.expected_impact,
                    "recommended_agents": r.recommended_agents
                } for r in recommendations
            ]
        }

        report = AIBusinessReport(
            organization_id=org_id,
            report_type=report_type,
            title=title,
            summary=summary_text,
            report_json=report_payload,
            parent_report_id=parent_report_id,
            generated_by=generated_by,
            generated_at=datetime.now(timezone.utc)
        )
        return report
