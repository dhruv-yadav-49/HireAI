import json
import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.ai_plan import AIPlan
from app.models.enums import PlannerState, AIProvider
from app.models.ai_agent import AIAgent, AIProviderConfig
from app.services.llm_provider_registry import LLMProviderRegistry
from app.services.retrieval_service import RetrievalService
from app.services.reasoning_engine import ReasoningEngine


class Planner:
    @classmethod
    async def create_plan(
        cls,
        db: AsyncSession,
        ctx: RequestContext,
        lead_id: uuid.UUID,
        goal: str,
        conversation_id: Optional[uuid.UUID] = None
    ) -> AIPlan:
        """Generates a structured multi-step plan based on a goal, lead profile, retrieved memories, and CRM context."""
        # 1. Gather reasoning explanation first
        reasoning_snap = await ReasoningEngine.analyze_lead(db, ctx, lead_id, goal=goal)

        # 2. Retrieve CRM + Knowledge Context for Planner
        retrieved_results = await RetrievalService.retrieve(
            db=db,
            org_id=ctx.tenant_id,
            query=f"Build plan for: {goal}",
            lead_id=lead_id,
            limit=5
        )
        context_str = "\n".join([f"- [{r.source.value}] {r.content}" for r in retrieved_results])

        from app.models.lead import Lead
        lead = await db.get(Lead, lead_id)
        if not lead or lead.organization_id != ctx.tenant_id:
            raise ValueError("Lead not found or inaccessible.")

        # 3. Resolve LLM details
        agent_stmt = select(AIAgent).where(
            AIAgent.organization_id == ctx.tenant_id,
            AIAgent.enabled == True,
            AIAgent.deleted_at.is_(None)
        ).limit(1)
        agent = (await db.execute(agent_stmt)).scalar_one_or_none()

        provider_type = AIProvider.MOCK
        model_name = "mock-model"
        temperature = 0.2
        credentials = {}

        if agent:
            provider_type = agent.provider
            model_name = agent.model
            temperature = agent.temperature or 0.2
            if agent.provider_config_id:
                config = await db.get(AIProviderConfig, agent.provider_config_id)
                if config and config.enabled:
                    credentials = config.credentials_json

        # 4. Formulate Prompt to generate structured steps
        system_prompt = (
            "You are a sales planning assistant. Output a JSON object containing a structured step-by-step plan.\n"
            "The JSON must have this exact structure:\n"
            "{\n"
            '  "goal": "Description of goal",\n'
            '  "steps": [\n'
            "    {\n"
            '      "id": 1,\n'
            '      "action": "ANALYZE_LEAD",\n'
            '      "description": "Short explanation",\n'
            '      "tool": "LeadTool"\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "Each step must map to a valid AIActionType: "
            '"ANALYZE_LEAD", "CREATE_TASK", "SEND_EMAIL", "SEND_WHATSAPP", "UPDATE_LEAD", "CHANGE_STATUS", "WAIT", "COMPLETE".\n'
            "And tool must map to a valid registered tool handler: "
            '"LeadTool", "TaskTool", "CommunicationTool", or null.\n'
            "Strictly output only JSON, no markdown formatting."
        )

        user_prompt = (
            f"Goal: {goal}\n"
            f"Lead Profile: {lead.first_name} {lead.last_name} (Status: {lead.status})\n"
            f"Reasoning Recommendation: {reasoning_snap.get('recommended_action')}\n"
            f"Reasoning Justification: {reasoning_snap.get('reason')}\n"
            f"Retrieved context:\n{context_str}\n\n"
            f"Generate the plan JSON."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        provider = LLMProviderRegistry.get_provider(provider_type)
        response = await provider.generate(
            messages=messages,
            model=model_name,
            temperature=temperature,
            credentials=credentials
        )

        content = response.get("content") or ""
        try:
            clean_content = content.strip()
            if clean_content.startswith("```"):
                lines = clean_content.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                clean_content = "\n".join(lines).strip()
            plan_data = json.loads(clean_content)
        except Exception:
            # Fallback structured steps
            plan_data = {
                "goal": goal,
                "steps": [
                    {
                        "id": 1,
                        "action": "ANALYZE_LEAD",
                        "description": "Perform deeper CRM profile lookup and analyze history context.",
                        "tool": "LeadTool"
                    },
                    {
                        "id": 2,
                        "action": "SEND_EMAIL",
                        "description": "Send follow-up introductory email to the lead.",
                        "tool": "CommunicationTool"
                    },
                    {
                        "id": 3,
                        "action": "CREATE_TASK",
                        "description": "Create follow-up task to review response in 3 days.",
                        "tool": "TaskTool"
                    }
                ]
            }

        # 5. Create AIPlan record
        plan = AIPlan(
            organization_id=ctx.tenant_id,
            agent_type="SALES",
            conversation_id=conversation_id,
            lead_id=lead_id,
            goal=goal,
            plan_json=plan_data,
            status=PlannerState.PLANNED,
            planner_version=1,
            reasoning_snapshot=reasoning_snap
        )
        db.add(plan)
        await db.flush()

        return plan
