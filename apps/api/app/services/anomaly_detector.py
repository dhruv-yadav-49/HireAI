from typing import Any
from app.models.ai_kpi_snapshot import AIKPISnapshot
from app.models.enums import AnomalySeverity, TrendDirection


class AnomalyDetector:
    @classmethod
    def detect_anomalies(
        cls,
        snapshot: AIKPISnapshot,
        trends: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Scans calculated snapshot metrics and trends for business anomalies."""
        anomalies = []

        # 1. Check response delay limits
        if snapshot.average_response_time > 60:
            anomalies.append({
                "metric": "Average Response Time",
                "severity": AnomalySeverity.CRITICAL,
                "description": f"Average response delay of {snapshot.average_response_time:.1f} minutes exceeds warning thresholds."
            })
        elif snapshot.average_response_time > 30:
            anomalies.append({
                "metric": "Average Response Time",
                "severity": AnomalySeverity.MEDIUM,
                "description": f"Average response delay has risen to {snapshot.average_response_time:.1f} minutes."
            })

        # 2. Check conversion rate
        if snapshot.conversion_rate < 0.05 and snapshot.total_leads > 10:
            anomalies.append({
                "metric": "Conversion Rate",
                "severity": AnomalySeverity.CRITICAL,
                "description": f"Conversion rate is critically low at {snapshot.conversion_rate * 100:.1f}%."
            })

        # 3. Check trend variables
        for trend in trends:
            m = trend["metric"]
            direction = trend["direction"]
            change = trend["change_percent"]

            if m == "Conversion Rate" and direction == TrendDirection.DOWN and change <= -10.0:
                anomalies.append({
                    "metric": "Conversion Rate",
                    "severity": AnomalySeverity.HIGH,
                    "description": f"Conversion rate has dropped rapidly by {change:.1f}% compared to previous snapshot."
                })
            elif m == "Pipeline Value" and direction == TrendDirection.DOWN and change <= -15.0:
                anomalies.append({
                    "metric": "Pipeline Value",
                    "severity": AnomalySeverity.CRITICAL,
                    "description": f"Pipeline value collapsed by {change:.1f}% compared to previous snapshot."
                })

        return anomalies

