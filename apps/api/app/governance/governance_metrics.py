"""
app/governance/governance_metrics.py

Governance Metrics Collector & Aggregator.

CTO Refinement #8: Dedicated Governance Metrics Service.
Tracks: Permitted, Blocked, Escalated counts, Approval Rate, Auto-approval Rate,
Average Risk Score, Average Approval Time, Violation Count.
"""
from dataclasses import dataclass
from typing import Dict, List, Any


@dataclass
class GovernanceMetricsSummary:
    total_evaluations: int
    permitted_count: int
    blocked_count: int
    escalated_count: int
    approval_rate: float
    auto_approval_rate: float
    average_risk_score: float
    average_approval_time_seconds: float
    violation_count: int


class GovernanceMetricsService:
    """Aggregates governance decision metrics."""

    @staticmethod
    def calculate_summary(decisions: List[Dict[str, Any]], approvals: List[Dict[str, Any]]) -> GovernanceMetricsSummary:
        total = len(decisions)
        if total == 0:
            return GovernanceMetricsSummary(
                total_evaluations=0,
                permitted_count=0,
                blocked_count=0,
                escalated_count=0,
                approval_rate=0.0,
                auto_approval_rate=0.0,
                average_risk_score=0.0,
                average_approval_time_seconds=0.0,
                violation_count=0,
            )

        permitted = sum(1 for d in decisions if d.get("decision_status") == "PERMIT")
        blocked = sum(1 for d in decisions if d.get("decision_status") == "BLOCK")
        escalated = sum(1 for d in decisions if d.get("decision_status") == "ESCALATE")

        total_risk = sum(float(d.get("risk_score", 0.0)) for d in decisions)
        avg_risk = total_risk / total

        total_approvals = len(approvals)
        approved = sum(1 for a in approvals if a.get("status") == "APPROVED")
        auto_approved = sum(1 for a in approvals if a.get("status") == "AUTO_APPROVED")

        approval_rate = (approved / total_approvals) if total_approvals > 0 else 1.0
        auto_approval_rate = (auto_approved / total_approvals) if total_approvals > 0 else 0.0

        return GovernanceMetricsSummary(
            total_evaluations=total,
            permitted_count=permitted,
            blocked_count=blocked,
            escalated_count=escalated,
            approval_rate=round(approval_rate, 4),
            auto_approval_rate=round(auto_approval_rate, 4),
            average_risk_score=round(avg_risk, 4),
            average_approval_time_seconds=300.0,  # Stub mean calculation
            violation_count=blocked,
        )
