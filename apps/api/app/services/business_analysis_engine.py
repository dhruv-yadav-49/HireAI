import uuid
from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.enums import ForecastPeriod, BusinessReportType
from app.models.ai_kpi_snapshot import AIKPISnapshot
from app.models.ai_forecast import AIForecast
from app.models.ai_business_report import AIBusinessReport
from app.models.ai_recommendation import AIRecommendation

from app.services.kpi_engine import KPIEngine
from app.services.pipeline_health_engine import PipelineHealthEngine
from app.services.trend_analyzer import TrendAnalyzer
from app.services.forecast_engine import ForecastEngine
from app.services.anomaly_detector import AnomalyDetector
from app.services.recommendation_engine import RecommendationEngine
from app.services.executive_report_engine import ExecutiveReportEngine


class BusinessAnalysisEngine:
    @classmethod
    async def run_full_analysis(
        cls,
        db: AsyncSession,
        ctx: RequestContext,
        forecast_period: ForecastPeriod = ForecastPeriod.F_30_DAYS
    ) -> dict[str, Any]:
        """Runs the complete multi-stage BI pipeline for an organization."""
        org_id = ctx.tenant_id

        # 1. KPI Calculation
        snapshot = await KPIEngine.calculate_kpis(db, org_id)
        db.add(snapshot)
        await db.flush()

        # 2. Pipeline Health
        health_result = PipelineHealthEngine.calculate_health(snapshot)

        # 3. Trend Analysis
        trends = await TrendAnalyzer.analyze_trends(db, org_id, snapshot)

        # 4. Forecast
        forecast = ForecastEngine.generate_forecast(org_id, snapshot, forecast_period)
        db.add(forecast)
        await db.flush()

        # 5. Anomaly Detection
        anomalies = AnomalyDetector.detect_anomalies(snapshot, trends)

        # 6. Recommendations
        recommendations = RecommendationEngine.generate_recommendations(
            org_id, snapshot, forecast, health_result, anomalies
        )
        for r in recommendations:
            db.add(r)
        await db.flush()

        return {
            "snapshot": snapshot,
            "health_result": health_result,
            "trends": trends,
            "forecast": forecast,
            "anomalies": anomalies,
            "recommendations": recommendations
        }
