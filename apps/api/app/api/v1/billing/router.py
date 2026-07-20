"""
app/api/v1/billing/router.py

Commercial Billing & Entitlements REST API Endpoints (Sprint 10).
Exposes subscription plan details, metered usage accounting, and entitlement feature checks.
"""
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.security.security_context import SecurityContext, get_current_security_context
from app.services.billing_service import BillingService
from app.models.enums import SubscriptionPlan, EntitlementFeature

router = APIRouter(prefix="/billing", tags=["Commercial Billing & Metering"])


@router.get(
    "/subscription",
    summary="Get Tenant Subscription & Entitlements",
    description="Fetches current tenant subscription status, quota policies, and feature entitlements (CTO #4).",
)
async def get_subscription(
    sec_ctx: SecurityContext = Depends(get_current_security_context),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    service = BillingService(db)
    sub = await service.get_or_create_subscription(sec_ctx.organization_id)
    return {
        "organization_id": str(sub.organization_id),
        "plan": sub.plan.value,
        "status": sub.status,
        "quota_policy": sub.quota_policy_json,
        "entitlements": sub.entitlements_json.get("features", []),
        "started_at": sub.started_at.isoformat(),
    }


@router.get(
    "/usage",
    summary="Get Metered Usage Accounting Report",
    description="Fetches tenant metered usage totals and invoice summary across all generic metrics (CTO #2, #4).",
)
async def get_usage_accounting(
    sec_ctx: SecurityContext = Depends(get_current_security_context),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    service = BillingService(db)
    return await service.get_invoice_summary(sec_ctx.organization_id)


@router.post(
    "/check-entitlement",
    summary="Check Entitlement Feature Gate",
    description="Verifies if current tenant is entitled to a specific commercial feature gate (CTO #4).",
)
async def check_entitlement(
    feature: EntitlementFeature = Body(..., embed=True),
    sec_ctx: SecurityContext = Depends(get_current_security_context),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    service = BillingService(db)
    entitled = await service.check_feature_entitled(sec_ctx.organization_id, feature)
    return {
        "organization_id": str(sec_ctx.organization_id),
        "feature": feature.value,
        "entitled": entitled,
    }
