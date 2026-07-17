import uuid
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.ai_kpi_snapshot import AIKPISnapshot
from app.models.ai_forecast import AIForecast
from app.models.ai_business_report import AIBusinessReport
from app.models.ai_recommendation import AIRecommendation


class BusinessAIRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_kpi_snapshot(self, snapshot: AIKPISnapshot) -> AIKPISnapshot:
        self.db.add(snapshot)
        await self.db.flush()
        return snapshot

    async def list_kpi_snapshots(
        self,
        ctx: RequestContext,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[list[AIKPISnapshot], int]:
        stmt = select(AIKPISnapshot).where(AIKPISnapshot.organization_id == ctx.tenant_id)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        stmt = stmt.order_by(AIKPISnapshot.calculated_at.desc()).offset(offset).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def create_forecast(self, forecast: AIForecast) -> AIForecast:
        self.db.add(forecast)
        await self.db.flush()
        return forecast

    async def list_forecasts(
        self,
        ctx: RequestContext,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[list[AIForecast], int]:
        stmt = select(AIForecast).where(AIForecast.organization_id == ctx.tenant_id)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        stmt = stmt.order_by(AIForecast.created_at.desc()).offset(offset).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def create_report(self, report: AIBusinessReport) -> AIBusinessReport:
        self.db.add(report)
        await self.db.flush()
        return report

    async def get_report_by_id(self, ctx: RequestContext, report_id: uuid.UUID) -> AIBusinessReport | None:
        result = await self.db.execute(
            select(AIBusinessReport).where(
                AIBusinessReport.id == report_id,
                AIBusinessReport.organization_id == ctx.tenant_id
            )
        )
        return result.scalar_one_or_none()

    async def list_reports(
        self,
        ctx: RequestContext,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[list[AIBusinessReport], int]:
        stmt = select(AIBusinessReport).where(AIBusinessReport.organization_id == ctx.tenant_id)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        stmt = stmt.order_by(AIBusinessReport.generated_at.desc()).offset(offset).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def create_recommendation(self, rec: AIRecommendation) -> AIRecommendation:
        self.db.add(rec)
        await self.db.flush()
        return rec

    async def get_recommendation_by_id(self, ctx: RequestContext, rec_id: uuid.UUID) -> AIRecommendation | None:
        result = await self.db.execute(
            select(AIRecommendation).where(
                AIRecommendation.id == rec_id,
                AIRecommendation.organization_id == ctx.tenant_id
            )
        )
        return result.scalar_one_or_none()

    async def update_recommendation(self, rec: AIRecommendation) -> AIRecommendation:
        self.db.add(rec)
        await self.db.flush()
        return rec

    async def list_recommendations(
        self,
        ctx: RequestContext,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[list[AIRecommendation], int]:
        stmt = select(AIRecommendation).where(AIRecommendation.organization_id == ctx.tenant_id)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        stmt = stmt.order_by(AIRecommendation.created_at.desc()).offset(offset).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total
