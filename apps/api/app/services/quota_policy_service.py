"""
app/services/quota_policy_service.py

Policy-Based Quota Management & Enforcement Service.

CTO Refinement #3:
  Models tenant limits as configurable policy profiles rather than hardcoded values.
"""
import uuid
from typing import Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.tenant_subscription import TenantSubscription
from app.models.enums import SubscriptionPlan


class QuotaPolicyProfile:
    """Configurable policy profile defining quota limits (CTO #3)."""

    DEFAULT_PROFILES = {
        SubscriptionPlan.FREE: {
            "token_budget_monthly": 100000,
            "api_call_budget_monthly": 5000,
            "concurrent_jobs_limit": 2,
            "storage_mb_limit": 500,
            "marketplace_packages_limit": 2,
        },
        SubscriptionPlan.PRO: {
            "token_budget_monthly": 2000000,
            "api_call_budget_monthly": 100000,
            "concurrent_jobs_limit": 10,
            "storage_mb_limit": 10000,
            "marketplace_packages_limit": 20,
        },
        SubscriptionPlan.ENTERPRISE: {
            "token_budget_monthly": 50000000,
            "api_call_budget_monthly": 2000000,
            "concurrent_jobs_limit": 50,
            "storage_mb_limit": 100000,
            "marketplace_packages_limit": 100,
        },
    }

    @classmethod
    def get_policy(cls, plan: SubscriptionPlan) -> Dict[str, Any]:
        return cls.DEFAULT_PROFILES.get(plan, cls.DEFAULT_PROFILES[SubscriptionPlan.FREE])


class TenantQuotaEnforcer:
    """Enforces policy-based quotas for tenant requests (CTO #3)."""

    @classmethod
    def check_quota_available(
        cls, policy: Dict[str, Any], current_usage: Dict[str, float], metric: str
    ) -> bool:
        budget = policy.get(f"{metric}_budget_monthly", policy.get(f"{metric}_limit", 9999999))
        used = current_usage.get(f"{metric}_count", 0.0)
        return used < budget
