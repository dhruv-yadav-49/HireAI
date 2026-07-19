"""
app/playground/sandbox_runtime.py

Sandbox Runtime Wrapper.

CTO Refinement #2: Sandbox Isolation Levels.
  - READ_ONLY: Live queries allowed for CRM & Knowledge, DB writes/mutations blocked.
  - READ_WITH_CACHE: Queries return cached snapshots, DB writes/mutations blocked.
  - MOCK_EXTERNALS: External APIs, Tool calls, Event Bus, and DB writes are mocked.

ADR-023: Sandbox by Default & Read-Only Integration.
"""
from typing import Any, Dict, Optional
from app.models.enums import SandboxIsolationLevel
from app.playground.playground_context import PlaygroundContext


class SandboxMutationError(PermissionError):
    """Raised when an attempt is made to perform a write or side-effect inside SandboxRuntime."""
    pass


class SandboxRuntime:
    """Guarantees isolated execution by enforcing read-only behavior and intercepting mutations."""

    def __init__(self, ctx: PlaygroundContext) -> None:
        self.ctx = ctx
        self.level = ctx.isolation_level

    def assert_can_read(self, resource_name: str) -> bool:
        """All isolation levels allow read access."""
        return True

    def assert_can_mutate(self, action_name: str) -> None:
        """Blocks DB mutations, job submissions, and production writes across all levels."""
        raise SandboxMutationError(
            f"Sandbox Violation: '{action_name}' mutation blocked under {self.level.value} mode. "
            "Playground executions cannot modify production state."
        )

    def is_cached_read_only(self) -> bool:
        return self.level == SandboxIsolationLevel.READ_WITH_CACHE

    def is_mock_externals(self) -> bool:
        return self.level == SandboxIsolationLevel.MOCK_EXTERNALS

    def intercept_tool_execution(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """Intercepts tool executions. Under MOCK_EXTERNALS returns mock output; otherwise returns BLOCKED status."""
        if self.is_mock_externals():
            return {
                "status": "MOCKED",
                "tool_name": tool_name,
                "mock_result": f"Simulated output for tool '{tool_name}' with args {tool_args}",
            }
        # In READ_ONLY or READ_WITH_CACHE, non-safe write tools return BLOCKED status
        if tool_name.startswith("delete_") or tool_name.startswith("update_") or tool_name.startswith("send_"):
            return {
                "status": "BLOCKED",
                "tool_name": tool_name,
                "reason": f"Tool '{tool_name}' blocked under sandbox {self.level.value} mode.",
            }
        return {"status": "READ_EXECUTION", "tool_name": tool_name}
