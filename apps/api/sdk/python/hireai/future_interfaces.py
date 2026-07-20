"""
hireai.sdk.future_interfaces — Reserved Extension Hooks.

CTO Refinement #12:
  Reserves future compatibility interfaces:
  Remote Debugger, Live Trace Streaming, Performance Profiler, AI Benchmark Runner, Auto Updates
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class IRemoteDebugger(ABC):
    """Interface for attaching live debuggers to running agent containers."""
    @abstractmethod
    def attach_session(self, session_id: str) -> bool:
        pass


class ILiveTraceStreamer(ABC):
    """Interface for streaming step-by-step reasoning traces in real time."""
    @abstractmethod
    def stream_trace(self, trace_id: str, payload: Dict[str, Any]) -> None:
        pass


class IPerformanceProfiler(ABC):
    """Interface for profiling agent step latency and token usage budgets."""
    @abstractmethod
    def profile_execution(self, agent_name: str) -> Dict[str, float]:
        pass
