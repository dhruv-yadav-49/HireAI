"""
app/services/billing_service.py

Commercial Billing & Entitlements Management Service.

CTO Refinement #4:
  Separates Plan -> Invoice -> Usage -> Entitlements.
  Commercial feature access derives from entitlement policies, not subscription names.
"""
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.tenant_subscription import TenantSubscription
from app.models.enums import SubscriptionPlan, EntitlementFeature
from app.services.quota_policy_service import QuotaPolicyProfile
from app.services.metering_service import UsageMeteringService


class BillingService:
    """Manages tenant subscriptions, invoice summaries, usage metering, and feature entitlements (CTO #4)."""

    ENTITLEMENT_MATRIX = {
        SubscriptionPlan.FREE: [EntitlementFeature.PLAYGROUND_MATRIX],
        SubscriptionPlan.PRO: [
            EntitlementFeature.PLAYGROUND_MATRIX,
            EntitlementFeature.CUSTOM_AGENTS,
            EntitlementFeature.MARKETPLACE_PUBLISHING,
        ],
        SubscriptionPlan.ENTERPRISE: [
            EntitlementFeature.PLAYGROUND_MATRIX,
            EntitlementFeature.CUSTOM_AGENTS,
            EntitlementFeature.MARKETPLACE_PUBLISHING,
            EntitlementFeature.GOVERNANCE_APPROVALS,
            EntitlementFeature.UNLIMITED_TOKENS,
        ],
    }

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.metering_service = UsageMeteringService(db)

    async def get_or_create_subscription(self, org_id: uuid.UUID) -> TenantSubscription:
        stmt = select(TenantSubscription).where(TenantSubscription.organization_id == org_id)
        res = await self.db.execute(stmt)
        sub = res.scalar_one_or_none()
        if not sub:
            policy = QuotaPolicyProfile.get_policy(SubscriptionPlan.FREE)
            entitlements = [f.value for f in self.ENTITLEMENT_MATRIX[SubscriptionPlan.FREE]]
            sub = TenantSubscription(
                organization_id=org_id,
                plan=SubscriptionPlan.FREE,
                status="ACTIVE",
                token_budget_monthly=policy["token_budget_monthly"],
                api_call_budget_monthly=policy["api_call_budget_monthly"],
                max_concurrent_jobs=policy["concurrent_jobs_limit"],
                quota_policy_json=policy,
                entitlements_json={"features": entitlements},
            )
            self.db.add(sub)
            await self.db.commit()
        return sub

    async def check_feature_entitled(self, org_id: uuid.UUID, feature: EntitlementFeature) -> bool:
        """Verifies feature entitlement for tenant (CTO #4)."""
        sub = await self.get_or_create_subscription(org_id)
        features = sub.entitlements_json.get("features", [])
        return feature.value in features

    async def get_invoice_summary(self, org_id: uuid.UUID) -> Dict[str, Any]:
        """Generates invoice summary mapping Plan -> Invoice -> Usage -> Entitlements (CTO #4)."""
        sub = await self.get_or_create_subscription(org_id)
        usage = await self.metering_service.get_usage_summary(org_id)

        return {
            "organization_id": str(org_id),
            "subscription_plan": sub.plan.value,
            "subscription_status": sub.status,
            "quota_policy": sub.quota_policy_json,
            "entitlements": sub.entitlements_json.get("features", []),
            "current_usage": usage,
            "invoice_total_units": usage.get("total_cost_units", 0.0),
        }
