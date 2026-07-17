import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.ai_agent_definition import AIAgentDefinition
from app.models.enums import AgentType


class AgentCapability:
    def __init__(
        self,
        name: str,
        description: str,
        supported_actions: list[str],
        required_tools: list[str],
        supported_goals: list[str]
    ):
        self.name = name
        self.description = description
        self.supported_actions = supported_actions
        self.required_tools = required_tools
        self.supported_goals = supported_goals


class AIAgentRegistry:
    @classmethod
    async def get_agent_definition(cls, db: AsyncSession, agent_type: AgentType) -> Optional[AIAgentDefinition]:
        stmt = select(AIAgentDefinition).where(AIAgentDefinition.agent_type == agent_type)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @classmethod
    async def get_agent_capability(cls, db: AsyncSession, agent_type: AgentType) -> AgentCapability:
        """Resolves capability parameters dynamically from database or fallback defaults."""
        defn = await cls.get_agent_definition(db, agent_type)
        
        # In-memory default fallbacks if database definitions are not loaded yet
        fallbacks = {
            AgentType.SALES: AgentCapability(
                name="Sales Executive",
                description="Manages outbound CRM campaigns, drafts proposals, updates lead statuses.",
                supported_actions=["SEND_EMAIL", "CREATE_TASK", "UPDATE_LEAD", "CHANGE_STATUS"],
                required_tools=["LeadTool", "TaskTool", "CommunicationTool"],
                supported_goals=["hot lead", "discount", "follow up", "intro mail", "outreach"]
            ),
            AgentType.SUPPORT: AgentCapability(
                name="Customer Support",
                description="Triages incoming queries, drafts replies, updates task checklists.",
                supported_actions=["SEND_EMAIL", "SEND_WHATSAPP", "CREATE_TASK"],
                required_tools=["TaskTool", "CommunicationTool"],
                supported_goals=["not replying", "complain", "issue", "support", "triage"]
            ),
            AgentType.MARKETING: AgentCapability(
                name="Marketing Analyst",
                description="Drafts promotional materials, tracks segment campaigns, delays communications.",
                supported_actions=["SEND_EMAIL", "WAIT"],
                required_tools=["CommunicationTool"],
                supported_goals=["wait", "nurture", "delay", "newsletter", "campaign"]
            ),
            AgentType.BUSINESS_ANALYST: AgentCapability(
                name="Business Analyst",
                description="Analyzes deal value, counts metrics, forecast outputs.",
                supported_actions=["ANALYZE_LEAD", "CREATE_TASK"],
                required_tools=["LeadTool", "TaskTool"],
                supported_goals=["forecast", "deal value", "metrics", "pipeline"]
            ),
            AgentType.FINANCE: AgentCapability(
                name="Finance Officer",
                description="Authorizes discount rates, approves invoices and billing records.",
                supported_actions=["CREATE_TASK"],
                required_tools=["TaskTool"],
                supported_goals=["discount approval", "invoice", "payment"]
            ),
            AgentType.HUMAN: AgentCapability(
                name="Human Operator",
                description="Human override agent resolving escalations and approval steps.",
                supported_actions=["REQUEST_APPROVAL"],
                required_tools=[],
                supported_goals=["approval", "override", "escalate"]
            )
        }

        if defn and defn.enabled:
            return AgentCapability(
                name=defn.display_name,
                description=defn.description,
                supported_actions=defn.supported_goals.get("actions", []),
                required_tools=defn.required_tools.get("tools", []),
                supported_goals=defn.supported_goals.get("goals", [])
            )
        
        return fallbacks.get(agent_type, AgentCapability(
            name=agent_type.value,
            description="Autonomous agent worker.",
            supported_actions=[],
            required_tools=[],
            supported_goals=[]
        ))

    @classmethod
    async def get_agent_health(cls, db: AsyncSession, agent_type: AgentType) -> str:
        """Determines if the agent is ready to receive tasks."""
        defn = await cls.get_agent_definition(db, agent_type)
        if defn:
            if not defn.enabled:
                return "DISABLED"
            return "READY"
        return "READY"
