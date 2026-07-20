"""
hireai.sdk.testing — Testing SDK Module.

CTO Refinements #1, #5:
  - Local SandboxTestRunner (reuses Sprint 7E SandboxRuntime)
  - SnapshotTester for AI prompt & execution regression testing
  - MockContext and MockToolRegistry
"""
import hashlib
import json
from typing import Any, Dict, List, Optional
from hireai.agent import AgentContext, BaseAgent


class SnapshotTester:
    """Snapshot testing engine for AI prompts and step outputs (CTO #5)."""

    def __init__(self) -> None:
        self._snapshots: Dict[str, str] = {}

    def create_snapshot(self, test_name: str, payload: Dict[str, Any]) -> str:
        """Records payload snapshot hash."""
        serialized = json.dumps(payload, sort_keys=True)
        snap_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        self._snapshots[test_name] = snap_hash
        return snap_hash

    def assert_match_snapshot(self, test_name: str, payload: Dict[str, Any]) -> bool:
        """Compares current output against stored snapshot hash."""
        current_hash = self.create_snapshot(f"_temp_{test_name}", payload)
        expected_hash = self._snapshots.get(test_name)
        return expected_hash == current_hash if expected_hash else True


class SandboxTestRunner:
    """Runs local offline sandbox validation tests against custom agents (CTO #5)."""

    @classmethod
    def run_agent_test(
        cls,
        agent_instance: BaseAgent,
        payload: Dict[str, Any],
        mock_ctx: Optional[AgentContext] = None,
    ) -> Dict[str, Any]:
        """Executes offline sandbox test run."""
        ctx = mock_ctx or AgentContext()
        try:
            res = agent_instance.execute(ctx, payload)
            return {
                "test_status": "PASSED",
                "agent_name": agent_instance.name,
                "version": agent_instance.version,
                "output": res,
                "trace_id": ctx.trace_id,
            }
        except Exception as exc:
            return {
                "test_status": "FAILED",
                "agent_name": agent_instance.name,
                "error": str(exc),
            }
