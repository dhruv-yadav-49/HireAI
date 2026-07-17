import uuid
from typing import Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.enums import (
    CampaignType,
    CampaignGoal,
    CampaignStatus,
    CampaignPriority,
    AudienceType,
    ContentType,
    AIActionType,
    AgentType
)
from app.models.ai_campaign import AICampaign
from app.models.ai_audience_segment import AIAudienceSegment
from app.models.ai_marketing_content import AIMarketingContent
from app.models.ai_ab_test import AIABTest
from app.models.ai_campaign_execution import AICampaignExecution
from app.repositories.marketing_ai_repository import MarketingAIRepository

from app.services.campaign_planner import CampaignPlanner
from app.services.audience_segmentation_engine import AudienceSegmentationEngine
from app.services.campaign_strategy_engine import CampaignStrategyEngine
from app.services.content_generation_engine import ContentGenerationEngine
from app.services.ab_testing_engine import ABTestingEngine
from app.services.nurturing_engine import NurturingEngine
from app.services.campaign_performance_engine import CampaignPerformanceEngine
from app.services.policy_engine import AIPolicyEngine, PolicyDecision
from app.services.orchestrator import Orchestrator
from app.core.events import DomainEvent, get_event_publisher


class MarketingAIService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = MarketingAIRepository(db)

    async def publish_event(self, ctx: RequestContext, event_name: str, payload: dict) -> None:
        """Publishes local marketing domain events inside transaction."""
        event = DomainEvent(
            event_name=event_name,
            tenant_id=ctx.tenant_id,
            request_id=ctx.request_id,
            actor_id=ctx.user.id if ctx.user else None,
            payload=payload
        )
        pub = get_event_publisher()
        await pub.publish(event)

    async def create_campaign(
        self,
        ctx: RequestContext,
        name: str,
        campaign_type: CampaignType,
        campaign_goal: CampaignGoal,
        priority: CampaignPriority = CampaignPriority.MEDIUM,
        strategy_json: Optional[dict] = None,
        parent_campaign_id: Optional[uuid.UUID] = None
    ) -> AICampaign:
        """Creates a planned marketing campaign, validating against policy rules."""
        
        # 1. Proposal defaults
        proposal = CampaignPlanner.propose_campaign(ctx.tenant_id, campaign_goal, priority)
        final_strategy = strategy_json or proposal["strategy_json"]
        compiled_strategy = CampaignStrategyEngine.compile_strategy(campaign_type, final_strategy)

        # 2. Query Policy Engine to check approval rules
        policy_res = await AIPolicyEngine.evaluate(
            db=self.db,
            ctx=ctx,
            agent_type="MARKETING",
            action_type=AIActionType.SEND_EMAIL if campaign_type == CampaignType.EMAIL else AIActionType.SEND_WHATSAPP,
            tool_name="CommunicationTool",
            input_json={"is_bulk": True, "recipients": [1] * 20},
            plan_id=uuid.uuid4()
        )

        status = CampaignStatus.DRAFT
        if policy_res["decision"] == PolicyDecision.REQUIRE_APPROVAL:
            status = CampaignStatus.REVIEW
        elif policy_res["decision"] == PolicyDecision.ALLOW:
            status = CampaignStatus.APPROVED

        campaign = AICampaign(
            organization_id=ctx.tenant_id,
            name=name,
            campaign_type=campaign_type,
            campaign_goal=campaign_goal,
            status=status,
            priority=priority,
            strategy_json=compiled_strategy,
            campaign_version=1,
            parent_campaign_id=parent_campaign_id,
            created_by=ctx.user.id if ctx.user else None
        )

        await self.repo.create_campaign(campaign)

        await self.publish_event(ctx, "marketing.campaign.created", {
            "campaign_id": str(campaign.id),
            "name": campaign.name,
            "status": campaign.status.value
        })

        return campaign

    async def create_segment(
        self,
        ctx: RequestContext,
        name: str,
        segment_type: AudienceType,
        criteria_json: dict
    ) -> AIAudienceSegment:
        """Runs dynamic DB queries to generate an audience segment."""
        segment, leads = await AudienceSegmentationEngine.segment_audience(
            self.db, ctx.tenant_id, name, segment_type, criteria_json
        )
        
        segment.generated_by = ctx.user.id if ctx.user else None
        await self.repo.create_segment(segment)

        await self.publish_event(ctx, "marketing.segment.created", {
            "segment_id": str(segment.id),
            "name": segment.name,
            "estimated_size": segment.estimated_size
        })

        return segment

    async def generate_content(
        self,
        ctx: RequestContext,
        campaign_id: uuid.UUID,
        content_type: ContentType,
        subject: Optional[str] = None,
        body_override: Optional[str] = None,
        parent_content_id: Optional[uuid.UUID] = None,
        generation_prompt: Optional[str] = None
    ) -> AIMarketingContent:
        """Drafts campaign content templates."""
        campaign = await self.repo.get_campaign_by_id(ctx, campaign_id)
        if not campaign:
            raise ValueError("Campaign not found or unauthorized.")

        content = ContentGenerationEngine.generate_content(
            ctx.tenant_id, campaign, content_type, subject, body_override, parent_content_id, generation_prompt
        )
        await self.repo.create_content(content)

        await self.publish_event(ctx, "marketing.content.generated", {
            "content_id": str(content.id),
            "campaign_id": str(campaign_id),
            "content_type": content.content_type.value
        })

        return content

    async def setup_ab_test(
        self,
        ctx: RequestContext,
        campaign_id: uuid.UUID,
        variants_config: list[dict[str, Any]]
    ) -> AIABTest:
        """Saves a multivariate A/B test setup in database."""
        campaign = await self.repo.get_campaign_by_id(ctx, campaign_id)
        if not campaign:
            raise ValueError("Campaign not found or unauthorized.")

        test = ABTestingEngine.setup_ab_test(campaign_id, variants_config)
        await self.repo.create_ab_test(test)
        return test

    async def execute_campaign(
        self,
        ctx: RequestContext,
        campaign_id: uuid.UUID,
        segment_id: uuid.UUID,
        attribution_model: str = "LAST_TOUCH"
    ) -> AICampaignExecution:
        """Executes campaign plans by spawning workflow tasks through the Multi-Agent Orchestrator."""
        campaign = await self.repo.get_campaign_by_id(ctx, campaign_id)
        if not campaign:
            raise ValueError("Campaign not found or unauthorized.")

        if campaign.status == CampaignStatus.REVIEW:
            raise ValueError("Campaign is currently in REVIEW and requires human policy approval.")

        segment = await self.repo.get_segment_by_id(ctx, segment_id)
        if not segment:
            raise ValueError("Audience segment not found or unauthorized.")

        # 1. Dynamic query of leads pool to snapshot
        _, leads = await AudienceSegmentationEngine.segment_audience(
            self.db, ctx.tenant_id, segment.name, segment.segment_type, segment.criteria_json
        )
        lead_ids = [str(l.id) for l in leads]

        campaign.status = CampaignStatus.RUNNING
        await self.repo.update_campaign(campaign)

        # 2. Setup execution statistics and snapshot
        execution = AICampaignExecution(
            campaign_id=campaign_id,
            segment_id=segment_id,
            status=CampaignStatus.RUNNING,
            audience_snapshot_json={"lead_ids": lead_ids},
            statistics_json={
                "delivery": {"sent": 0, "bounced": 0, "spam_complaints": 0},
                "engagement": {"opened": 0, "clicked": 0, "unsubscribed": 0},
                "business": {"replied": 0, "converted": 0, "revenue_attribution": 0.0}
            },
            attribution_model=attribution_model
        )
        await self.repo.create_execution(execution)

        # 3. Compile campaign nurturing workflow DAG
        workflow_steps = campaign.strategy_json.get("steps", [])
        graph = NurturingEngine.compile_nurturing_graph(workflow_steps)

        # 4. Invoke Multi-Agent Orchestrator workflow session
        orchestrator = Orchestrator(self.db)
        session = await orchestrator.create_session(ctx, initiator_agent=AgentType.MARKETING)
        
        # Spawns tasks matching workflow cadences
        for step in workflow_steps:
            goal_text = f"Perform multi-channel marketing campaign outreach: channel={step['channel']}, target_leads={len(lead_ids)}"
            await orchestrator.delegate_task(
                ctx,
                session_id=session.id,
                goal=goal_text,
                priority=campaign.priority.value if hasattr(campaign.priority, 'value') else campaign.priority
            )

        await self.publish_event(ctx, "marketing.execution.started", {
            "execution_id": str(execution.id),
            "campaign_id": str(campaign_id),
            "orchestrator_session_id": str(session.id)
        })

        return execution

    async def complete_execution(
        self,
        ctx: RequestContext,
        execution_id: uuid.UUID,
        metrics_payload: Optional[dict[str, Any]] = None
    ) -> AICampaignExecution:
        """Completes execution tracking and saves performance metrics."""
        exec_rec = await self.repo.get_execution_by_id(ctx, execution_id)
        if not exec_rec:
            raise ValueError("Campaign execution not found or unauthorized.")

        campaign = await self.repo.get_campaign_by_id(ctx, exec_rec.campaign_id)
        if campaign:
            campaign.status = CampaignStatus.COMPLETED
            await self.repo.update_campaign(campaign)

        exec_rec.status = CampaignStatus.COMPLETED
        if metrics_payload:
            exec_rec.statistics_json = CampaignPerformanceEngine.compile_statistics(
                sent=metrics_payload.get("sent", 100),
                opened=metrics_payload.get("opened", 45),
                clicked=metrics_payload.get("clicked", 18),
                replied=metrics_payload.get("replied", 8),
                converted=metrics_payload.get("converted", 4),
                bounced=metrics_payload.get("bounced", 2),
                unsubscribed=metrics_payload.get("unsubscribed", 1),
                spam_complaints=metrics_payload.get("spam_complaints", 0),
                revenue=metrics_payload.get("revenue", 24000.00)
            )

        await self.repo.update_execution(exec_rec)

        await self.publish_event(ctx, "marketing.execution.completed", {
            "execution_id": str(execution_id),
            "campaign_id": str(exec_rec.campaign_id)
        })
        await self.publish_event(ctx, "marketing.performance.calculated", {
            "execution_id": str(execution_id),
            "statistics": exec_rec.statistics_json
        })

        return exec_rec
