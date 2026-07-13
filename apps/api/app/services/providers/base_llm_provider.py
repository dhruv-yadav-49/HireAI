from typing import Any, Optional, Protocol


class BaseLLMProvider(Protocol):
    """Protocol defining the standard interface for LLM provider wrappers (OpenAI, Gemini, Anthropic)."""

    capabilities: dict[str, bool]
    # Required capability keys:
    # - supports_streaming: bool
    # - supports_tools: bool
    # - supports_images: bool
    # - supports_reasoning: bool
    # - supports_json: bool
    # - supports_vision: bool

    async def generate(
        self,
        messages: list[dict[str, Any]],
        model: str,
        tools: Optional[list[dict[str, Any]]] = None,
        response_format: Optional[dict[str, Any]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        credentials: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Dispatches payload to the LLM vendor API and returns a standard response dictionary.
        
        Response Format:
        {
            "content": str | None,
            "tool_calls": list[dict[str, Any]] | None, # Tool call dict keys: id, name, arguments (dict)
            "input_tokens": int,
            "output_tokens": int,
            "latency_ms": int,
            "finish_reason": str | None,
            "raw_response": dict[str, Any]
        }
        """
        ...

    async def stream(
        self,
        messages: list[dict[str, Any]],
        model: str,
        tools: Optional[list[dict[str, Any]]] = None,
        response_format: Optional[dict[str, Any]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        credentials: Optional[dict[str, Any]] = None,
    ):
        """Asynchronously streams chunks of LLM generation output."""
        ...

    async def count_tokens(self, messages: list[dict[str, Any]], model: str) -> int:
        """Estimates or counts tokens for a given prompt/message history block."""
        ...

    async def health_check(self, model: str, credentials: Optional[dict[str, Any]] = None) -> bool:
        """Verifies API credentials connection health state."""
        ...
