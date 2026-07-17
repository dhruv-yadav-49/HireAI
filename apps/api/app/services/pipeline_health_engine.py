from typing import Any
from app.models.ai_kpi_snapshot import AIKPISnapshot
from app.models.enums import PipelineHealth


class PipelineHealthEngine:
    @classmethod
    def calculate_health(
        cls,
        snapshot: AIKPISnapshot
    ) -> dict[str, Any]:
        """Evaluates pipeline health score across multiple weighted dimensions."""
        issues = []

        # 1. Lead Quality Dimension
        total = snapshot.total_leads
        qual = snapshot.qualified_leads
        lead_quality = int((qual / total * 100)) if total > 0 else 80
        if lead_quality < 50:
            issues.append("Low ratio of qualified leads in pipeline.")

        # 2. Follow Up Dimension
        # Check if there are stale leads in NEW status
        new_leads = total - snapshot.qualified_leads - snapshot.won_deals - snapshot.lost_deals
        follow_up = max(100 - (new_leads * 10), 30)
        if follow_up < 70:
            issues.append(f"Found {new_leads} new leads without progressed stage outreach.")

        # 3. Response Speed Dimension
        resp_time = snapshot.average_response_time
        response_speed = max(int(100 - resp_time), 20)
        if resp_time > 30:
            issues.append("High average lead response delay.")

        # 4. Deal Progress Dimension
        won = snapshot.won_deals
        lost = snapshot.lost_deals
        deal_progress = int((won / (won + lost) * 100)) if (won + lost) > 0 else 80
        if deal_progress < 60:
            issues.append("Low win-to-loss deal conversion ratio.")

        # Overall Health Score (Weighted average)
        overall = int(
            (lead_quality * 0.3) +
            (follow_up * 0.2) +
            (response_speed * 0.2) +
            (deal_progress * 0.3)
        )

        health_enum = PipelineHealth.HEALTHY
        if overall < 60:
            health_enum = PipelineHealth.CRITICAL
        elif overall < 80:
            health_enum = PipelineHealth.WARNING

        return {
            "health": health_enum,
            "score": overall,
            "dimensions": {
                "lead_quality": lead_quality,
                "follow_up": follow_up,
                "response_speed": response_speed,
                "deal_progress": deal_progress
            },
            "issues": issues
        }
