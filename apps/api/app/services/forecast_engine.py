import uuid
from typing import Any
from app.models.ai_kpi_snapshot import AIKPISnapshot
from app.models.ai_forecast import AIForecast
from app.models.enums import ForecastPeriod


class ForecastEngine:
    @classmethod
    def generate_forecast(
        cls,
        org_id: uuid.UUID,
        snapshot: AIKPISnapshot,
        period: ForecastPeriod
    ) -> AIForecast:
        """Calculates revenue and conversion rate forecasts deterministically based on pipeline value."""
        conv_rate = float(snapshot.conversion_rate or 0.15)
        # default fallback to 0.15 if no conversions yet
        if conv_rate == 0.0:
            conv_rate = 0.15

        pipe_value = float(snapshot.pipeline_value or 10000.0)

        # Scale predicted revenue by period length
        period_multipliers = {
            ForecastPeriod.F_7_DAYS: 7.0 / 30.0,
            ForecastPeriod.F_30_DAYS: 1.0,
            ForecastPeriod.F_90_DAYS: 3.0,
            ForecastPeriod.F_180_DAYS: 6.0
        }
        mult = period_multipliers.get(period, 1.0)
        
        predicted_rev = pipe_value * conv_rate * mult
        confidence = 0.85 if period == ForecastPeriod.F_7_DAYS else (0.80 - (mult * 0.05))
        confidence = max(confidence, 0.50)

        assumptions = [
            "Deal pipeline values remain stable.",
            "Historical conversion rates remain steady throughout the forecast period.",
            f"Active leads pool of {snapshot.total_leads} is representative."
        ]

        forecast = AIForecast(
            organization_id=org_id,
            forecast_period=period,
            predicted_revenue=predicted_rev,
            predicted_conversion_rate=conv_rate,
            confidence_score=confidence,
            forecast_model="PIPELINE_REVENUE_PROJECTION_MODEL",
            forecast_version=1,
            training_period="LAST_30_DAYS",
            assumptions_json={"assumptions": assumptions},
            forecast_json={
                "reason": f"Projected revenue of ${predicted_rev:.2f} using conversion rate of {conv_rate * 100:.1f}%.",
                "calculated_from_pipeline": pipe_value,
                "period_length_multiplier": mult
            }
        )
        return forecast
