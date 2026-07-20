"""
app/marketplace/marketplace_metrics.py

Marketplace Operational Metrics Service.

CTO Refinement #12:
  Tracks platform KPIs:
  - Packages Published
  - Validation Success Rate
  - Total & Active Installations
  - Enable Rate
  - Compatibility Failure Count
  - Rollback Count
"""
from typing import Any, Dict, List


class MarketplaceMetricsSummary:
    def __init__(
        self,
        packages_published: int,
        validation_success_rate: float,
        total_installations: int,
        active_installations: int,
        enable_rate: float,
        compatibility_failures: int,
        rollback_count: int,
    ) -> None:
        self.packages_published = packages_published
        self.validation_success_rate = validation_success_rate
        self.total_installations = total_installations
        self.active_installations = active_installations
        self.enable_rate = enable_rate
        self.compatibility_failures = compatibility_failures
        self.rollback_count = rollback_count


class MarketplaceMetricsService:
    """Calculates operational KPIs for agent marketplace platform (CTO #12)."""

    @classmethod
    def compute_summary(cls, logs_and_installations: List[Dict[str, Any]]) -> MarketplaceMetricsSummary:
        total = len(logs_and_installations)
        if total == 0:
            return MarketplaceMetricsSummary(0, 100.0, 0, 0, 100.0, 0, 0)

        active = sum(1 for item in logs_and_installations if item.get("status") == "ACTIVE")
        failed = sum(1 for item in logs_and_installations if item.get("status") == "FAILED")
        rollbacks = sum(1 for item in logs_and_installations if item.get("rolled_back") is True)
        validations_passed = sum(1 for item in logs_and_installations if item.get("validation_passed") is True)

        enable_rate = round((active / total * 100.0), 2) if total > 0 else 100.0
        val_success_rate = round((validations_passed / total * 100.0), 2) if total > 0 else 100.0

        return MarketplaceMetricsSummary(
            packages_published=total,
            validation_success_rate=val_success_rate,
            total_installations=total,
            active_installations=active,
            enable_rate=enable_rate,
            compatibility_failures=failed,
            rollback_count=rollbacks,
        )
