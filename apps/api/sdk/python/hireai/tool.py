"""
hireai.sdk.tool — Tool SDK Module.

CTO Refinements #1, #3:
  - Formal Tool Contract: ToolMetadata, InputSchema, OutputSchema, PermissionScope, BaseTool, @tool
  - Makes tools portable across runtimes.
"""
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Type
from pydantic import BaseModel, Field


class PermissionScope(BaseModel):
    """Declared security permission scope requirement for a tool (CTO #3)."""
    scope: str
    description: str = "Requires scope access"


class ToolMetadata(BaseModel):
    """Portable tool metadata contract (CTO #3)."""
    name: str
    description: str
    version: str = "1.0.0"
    permission_scopes: List[PermissionScope] = Field(default_factory=list)


class InputSchema(BaseModel):
    """Base input schema for tool invocation."""
    pass


class OutputSchema(BaseModel):
    """Base output schema for tool execution result."""
    status: str = "SUCCESS"
    data: Dict[str, Any] = Field(default_factory=dict)


class BaseTool(ABC):
    """Base class for custom reusable platform tools (CTO #3)."""

    def __init__(self, metadata: ToolMetadata) -> None:
        self.metadata = metadata

    @abstractmethod
    def run(self, input_data: Dict[str, Any]) -> OutputSchema:
        """Executes tool logic against input schema."""
        pass


def tool(
    name: str,
    description: str,
    version: str = "1.0.0",
    scopes: Optional[List[str]] = None,
) -> Callable:
    """Decorator converting standard Python functions into validated HireAI Tool contracts (CTO #3)."""

    def decorator(func: Callable) -> Callable:
        perm_scopes = [PermissionScope(scope=s) for s in (scopes or [])]
        meta = ToolMetadata(name=name, description=description, version=version, permission_scopes=perm_scopes)

        def wrapper(*args, **kwargs) -> OutputSchema:
            res = func(*args, **kwargs)
            if isinstance(res, OutputSchema):
                return res
            return OutputSchema(status="SUCCESS", data={"result": res})

        wrapper.__hireai_tool_meta__ = meta
        return wrapper

    return decorator
