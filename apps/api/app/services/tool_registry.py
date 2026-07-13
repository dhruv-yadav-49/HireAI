from typing import Any, Optional
from jsonschema import validate, ValidationError
from app.core.exceptions import ValidationException

from app.services.tool_handlers.lead_tool import LeadTool
from app.services.tool_handlers.task_tool import TaskTool
from app.services.tool_handlers.workflow_tool import WorkflowTool
from app.services.tool_handlers.communication_tool import CommunicationTool
from app.services.tool_handlers.scheduler_tool import SchedulerTool


class ToolDefinition:
    """Represents a registered LLM callable tool schema and handler definition."""

    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        parameters_schema: dict,
        handler: Any,
        deprecated: bool = False
    ):
        self.name = name
        self.version = version
        self.description = description
        self.parameters_schema = parameters_schema
        self.handler = handler
        self.deprecated = deprecated

    def to_openai_tool(self) -> dict:
        """Serializes the definition to OpenAI function call schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            }
        }


class ToolRegistry:
    """Core registry indexing all callable system tools and running input validations."""

    _tools: dict[str, ToolDefinition] = {}

    @classmethod
    def register(cls, tool: ToolDefinition) -> None:
        cls._tools[tool.name] = tool

    @classmethod
    def get_tool(cls, name: str) -> ToolDefinition:
        tool = cls._tools.get(name)
        if not tool:
            raise ValidationException(f"Requested tool '{name}' is not registered.")
        if tool.deprecated:
            raise ValidationException(f"Requested tool '{name}' has been deprecated.")
        return tool

    @classmethod
    def get_all_openai_tools(cls) -> list[dict]:
        """Returns all registered tool schemas formatted for LLM tool call APIs."""
        return [tool.to_openai_tool() for tool in cls._tools.values() if not tool.deprecated]

    @classmethod
    async def validate_and_execute(cls, name: str, arguments: dict, db: Any, ctx: Any) -> dict:
        """Validates incoming arguments against parameter schema rules, executing the registered handler."""
        tool_def = cls.get_tool(name)

        # Structured validation guard: Never trust raw LLM output arguments directly
        try:
            validate(instance=arguments, schema=tool_def.parameters_schema)
        except ValidationError as e:
            raise ValidationException(f"Tool call arguments validation failed for '{name}': {e.message}")

        # Execute hander action
        return await tool_def.handler.execute(db, ctx, arguments)


# ── Register Default System Tools ──────────────────────────────────────────────

ToolRegistry.register(
    ToolDefinition(
        name="create_lead",
        version="1.0",
        description="Creates a new lead inside the CRM database with the given information.",
        parameters_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["create_lead"], "default": "create_lead"},
                "lead_data": {
                    "type": "object",
                    "properties": {
                        "first_name": {"type": "string"},
                        "last_name": {"type": "string"},
                        "email": {"type": "string"},
                        "phone": {"type": "string"},
                        "company_name": {"type": "string"},
                        "job_title": {"type": "string"},
                        "status": {"type": "string", "enum": ["NEW", "CONTACTED", "LOST"]},
                        "priority": {"type": "string", "enum": ["LOW", "NORMAL", "HIGH", "URGENT"]}
                    },
                    "required": ["first_name", "last_name", "email"]
                }
            },
            "required": ["action", "lead_data"]
        },
        handler=LeadTool()
    )
)

ToolRegistry.register(
    ToolDefinition(
        name="manage_task",
        version="1.0",
        description="Creates or updates task records in the CRM database.",
        parameters_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string"},
                "task_data": {"type": "object"}
            },
            "required": ["action"]
        },
        handler=TaskTool()
    )
)

ToolRegistry.register(
    ToolDefinition(
        name="trigger_workflow",
        version="1.0",
        description="Executes or registers workflows for leads or tasks.",
        parameters_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string"},
                "workflow_id": {"type": "string"}
            },
            "required": ["action", "workflow_id"]
        },
        handler=WorkflowTool()
    )
)

ToolRegistry.register(
    ToolDefinition(
        name="send_communication",
        version="1.0",
        description="Dispatches email, SMS or WhatsApp communication templates.",
        parameters_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string"},
                "channel": {"type": "string", "enum": ["EMAIL", "WHATSAPP", "SMS"]}
            },
            "required": ["action", "channel"]
        },
        handler=CommunicationTool()
    )
)

ToolRegistry.register(
    ToolDefinition(
        name="manage_scheduler",
        version="1.0",
        description="Triggers and parses recurrence schedulers.",
        parameters_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string"}
            },
            "required": ["action"]
        },
        handler=SchedulerTool()
    )
)
