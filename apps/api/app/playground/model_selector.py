"""
app/playground/model_selector.py

Model Selector and Provider Adapter.

Wraps existing LLMProviderRegistry (Sprint 5) for multi-model playground runs.
Calculates token usage and estimated cost across providers.
"""
from typing import Dict, List, Any, Tuple
from app.models.enums import AIProvider
from app.services.llm_provider_registry import LLMProviderRegistry


_MODEL_COST_PER_1K_TOKENS = {
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "claude-3-5-sonnet": {"input": 0.003, "output": 0.015},
    "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
    "mock-llm-v1": {"input": 0.0, "output": 0.0},
}


class ModelSelector:
    """Model selection facade providing cost estimates and registry lookup."""

    @staticmethod
    def get_supported_providers() -> List[str]:
        return [p.value for p in LLMProviderRegistry.PROVIDERS.keys()]

    @staticmethod
    def estimate_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
        cost_info = _MODEL_COST_PER_1K_TOKENS.get(
            model_name, {"input": 0.002, "output": 0.006}
        )
        in_cost = (input_tokens / 1000.0) * cost_info["input"]
        out_cost = (output_tokens / 1000.0) * cost_info["output"]
        return round(in_cost + out_cost, 6)

    @staticmethod
    def resolve_provider_enum(provider_str: str) -> AIProvider:
        try:
            return AIProvider(provider_str.upper())
        except ValueError:
            return AIProvider.MOCK
