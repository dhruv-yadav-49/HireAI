import uuid
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.ai_campaign import AICampaign
from app.models.ai_audience_segment import AIAudienceSegment
from app.models.ai_marketing_content import AIMarketingContent
from app.models.ai_ab_test import AIABTest
from app.models.ai_campaign_execution import AICampaignExecution


class MarketingAIRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_campaign(self, campaign: AICampaign) -> AICampaign:
        self.db.add(campaign)
        await self.db.flush()
        return campaign

    async def get_campaign_by_id(self, ctx: RequestContext, campaign_id: uuid.UUID) -> AICampaign | None:
        result = await self.db.execute(
            select(AICampaign).where(
                AICampaign.id == campaign_id,
                AICampaign.organization_id == ctx.tenant_id
            )
        )
        return result.scalar_one_or_none()

    async def list_campaigns(
        self,
        ctx: RequestContext,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[list[AICampaign], int]:
        stmt = select(AICampaign).where(AICampaign.organization_id == ctx.tenant_id)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        stmt = stmt.order_by(AICampaign.created_at.desc()).offset(offset).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def update_campaign(self, campaign: AICampaign) -> AICampaign:
        self.db.add(campaign)
        await self.db.flush()
        return campaign

    async def create_segment(self, segment: AIAudienceSegment) -> AIAudienceSegment:
        self.db.add(segment)
        await self.db.flush()
        return segment

    async def get_segment_by_id(self, ctx: RequestContext, segment_id: uuid.UUID) -> AIAudienceSegment | None:
        result = await self.db.execute(
            select(AIAudienceSegment).where(
                AIAudienceSegment.id == segment_id,
                AIAudienceSegment.organization_id == ctx.tenant_id
            )
        )
        return result.scalar_one_or_none()

    async def list_segments(
        self,
        ctx: RequestContext,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[list[AIAudienceSegment], int]:
        stmt = select(AIAudienceSegment).where(AIAudienceSegment.organization_id == ctx.tenant_id)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        stmt = stmt.order_by(AIAudienceSegment.created_at.desc()).offset(offset).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def create_content(self, content: AIMarketingContent) -> AIMarketingContent:
        self.db.add(content)
        await self.db.flush()
        return content

    async def get_content_by_id(self, ctx: RequestContext, content_id: uuid.UUID) -> AIMarketingContent | None:
        result = await self.db.execute(
            select(AIMarketingContent).where(
                AIMarketingContent.id == content_id,
                AIMarketingContent.organization_id == ctx.tenant_id
            )
        )
        return result.scalar_one_or_none()

    async def list_contents(
        self,
        ctx: RequestContext,
        campaign_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[list[AIMarketingContent], int]:
        stmt = select(AIMarketingContent).where(
            AIMarketingContent.campaign_id == campaign_id,
            AIMarketingContent.organization_id == ctx.tenant_id
        )
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        stmt = stmt.order_by(AIMarketingContent.created_at.desc()).offset(offset).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def create_ab_test(self, test: AIABTest) -> AIABTest:
        self.db.add(test)
        await self.db.flush()
        return test

    async def get_ab_test_by_id(self, ctx: RequestContext, test_id: uuid.UUID) -> AIABTest | None:
        # Joining on AICampaign to check tenant isolation bounds on A/B tests
        result = await self.db.execute(
            select(AIABTest)
            .join(AICampaign, AIABTest.campaign_id == AICampaign.id)
            .where(
                AIABTest.id == test_id,
                AICampaign.organization_id == ctx.tenant_id
            )
        )
        return result.scalar_one_or_none()

    async def update_ab_test(self, test: AIABTest) -> AIABTest:
        self.db.add(test)
        await self.db.flush()
        return test

    async def create_execution(self, exec_rec: AICampaignExecution) -> AICampaignExecution:
        self.db.add(exec_rec)
        await self.db.flush()
        return exec_rec

    async def get_execution_by_id(self, ctx: RequestContext, exec_id: uuid.UUID) -> AICampaignExecution | None:
        result = await self.db.execute(
            select(AICampaignExecution)
            .join(AICampaign, AICampaignExecution.campaign_id == AICampaign.id)
            .where(
                AICampaignExecution.id == exec_id,
                AICampaign.organization_id == ctx.tenant_id
            )
        )
        return result.scalar_one_or_none()

    async def update_execution(self, exec_rec: AICampaignExecution) -> AICampaignExecution:
        self.db.add(exec_rec)
        await self.db.flush()
        return exec_rec

    async def list_executions(
        self,
        ctx: RequestContext,
        campaign_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[list[AICampaignExecution], int]:
        stmt = select(AICampaignExecution).where(
            AICampaignExecution.campaign_id == campaign_id
        )
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar() or 0

        offset = (page - 1) * page_size
        stmt = stmt.order_by(AICampaignExecution.created_at.desc()).offset(offset).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total
