import json
import uuid
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import RequestContext
from app.models.enums import AIProvider
from app.models.ai_agent import AIAgent, AIProviderConfig
from app.services.llm_provider_registry import LLMProviderRegistry
from app.services.retrieval_service import RetrievalService
from app.services.sales_strategy_engine import SalesStrategyEngine


class ReasoningEngine:
    @classmethod
    async def analyze_lead(
        cls,
        db: AsyncSession,
        ctx: RequestContext,
        lead_id: uuid.UUID,
        goal: str = "Analyze lead and suggest next steps"
    ) -> dict[str, Any]:
        """Analyzes lead details, memory, knowledge, strategy and returns a structured reasoning payload."""
        # 1. Fetch Lead
        from app.models.lead import Lead
        lead = await db.get(Lead, lead_id)
        if not lead or lead.organization_id != ctx.tenant_id or lead.deleted_at is not None:
            raise ValueError("Lead not found or inaccessible.")

        # 2. Map status to Strategy Rule
        strategy_rule = SalesStrategyEngine.get_strategy_rule(lead.status.value if hasattr(lead.status, 'value') else lead.status)
        strategy = strategy_rule.strategy

        # 3. Retrieve Memory + CRM Context
        retrieved_results = await RetrievalService.retrieve(
            db=db,
            org_id=ctx.tenant_id,
            query=f"Lead analysis for {lead.first_name} {lead.last_name} status {lead.status}",
            lead_id=lead_id,
            limit=5
        )
        context_str = "\n".join([f"- [{r.source.value}] {r.content}" for r in retrieved_results])

        # 4. Resolve AIAgent provider & model configurations
        agent_stmt = select(AIAgent).where(
            AIAgent.organization_id == ctx.tenant_id,
            AIAgent.enabled == True,
            AIAgent.deleted_at.is_(None)
        ).limit(1)
        agent = (await db.execute(agent_stmt)).scalar_one_or_none()

        provider_type = AIProvider.MOCK
        model_name = "mock-model"
        temperature = 0.3
        credentials = {}

        if agent:
            provider_type = agent.provider
            model_name = agent.model
            temperature = agent.temperature or 0.3
            if agent.provider_config_id:
                config = await db.get(AIProviderConfig, agent.provider_config_id)
                if config and config.enabled:
                    credentials = config.credentials_json

        # 5. Formulate prompt
        system_prompt = (
            "You are a sales reasoning engine. You must output a JSON object with exactly these fields:\n"
            '  "reason": Why you recommend this action.\n'
            '  "recommended_action": Choose from: "ANALYZE_LEAD", "CREATE_TASK", "SEND_EMAIL", "SEND_WHATSAPP", "UPDATE_LEAD", "CHANGE_STATUS", "WAIT", "COMPLETE".\n'
            '  "confidence": Float between 0.0 and 1.0.\n'
            '  "risk": Choose from "LOW", "MEDIUM", "HIGH".\n'
            '  "priority": Choose from "LOW", "MEDIUM", "HIGH", "URGENT".\n'
            '  "expected_outcome": Description of expected business outcome.\n'
            "Strictly output only JSON, no markdown formatting."
        )

        user_prompt = (
            f"Lead Profile:\n"
            f"Name: {lead.first_name} {lead.last_name}\n"
            f"Status: {lead.status}\n"
            f"Deterministic Strategy: {strategy}\n"
            f"Allowed Actions for Strategy: {[a.value for a in strategy_rule.allowed_actions]}\n"
            f"CRM & Memory Context:\n{context_str}\n\n"
            f"Goal: {goal}\n"
            f"Produce reasoning output."
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
            result = json.loads(clean_content)
        except Exception:
            # Fallback
            result = {
                "reason": f"Lead in stage {lead.status} has no active follow-up. Initiating strategy: {strategy}.",
                "recommended_action": "SEND_EMAIL" if lead.status in ("NEW", "CONTACTED") else "CREATE_TASK",
                "confidence": 0.90,
                "risk": "LOW",
                "priority": "HIGH",
                "expected_outcome": f"Re-engage lead via {strategy} campaign."
            }

        return {
            "lead_id": lead_id,
            "lead_status": lead.status.value if hasattr(lead.status, 'value') else lead.status,
            "strategy": strategy,
            "reason": result.get("reason", "Default reason"),
            "recommended_action": result.get("recommended_action", "COMPLETE"),
            "confidence": float(result.get("confidence", 0.9)),
            "risk": result.get("risk", "LOW"),
            "priority": result.get("priority", "MEDIUM"),
            "expected_outcome": result.get("expected_outcome", "Establish contact"),
            "retrieved_context": [r.dict() for r in retrieved_results]
        }
