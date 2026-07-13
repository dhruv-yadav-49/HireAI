import time
from typing import Any, Optional


class MockLLMProvider:
    """Mock LLM provider wrapper to simulate generation and function/tool calling locally."""

    capabilities = {
        "supports_streaming": True,
        "supports_tools": True,
        "supports_images": False,
        "supports_reasoning": False,
        "supports_json": True,
        "supports_vision": False,
    }

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
        start_time = time.time()
        
        user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_msg = m.get("content", "")
                break

        tool_calls = None
        content = "This is a mock assistant response."

        # Check if conversation messages request tool simulation
        if any(m.get("role") == "tool" for m in messages):
            # If a tool call was already made and answered, return a final summary response!
            content = "I have successfully run the tool call to create the lead."
        elif "simulate tool" in user_msg.lower():
            tool_calls = [{
                "id": "call_mock_123",
                "name": "create_lead",
                "arguments": {
                    "action": "create_lead",
                    "lead_data": {
                        "first_name": "MockLead",
                        "last_name": "Test",
                        "email": "mock@example.com",
                        "company_name": "MockCorp",
                        "job_title": "MockManager"
                    }
                }
            }]
            content = None
        elif "simulate fail tool" in user_msg.lower():
            tool_calls = [{
                "id": "call_mock_456",
                "name": "invalid_tool_name_trigger",
                "arguments": {}
            }]
            content = None

        latency_ms = int((time.time() - start_time) * 1000)

        raw = {
            "id": "mock-gen-123",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                },
                "finish_reason": "stop" if not tool_calls else "tool_calls"
            }],
            "usage": {
                "prompt_tokens": 15,
                "completion_tokens": 10,
                "total_tokens": 25
            }
        }
        if tool_calls:
            raw["choices"][0]["message"]["tool_calls"] = tool_calls

        return {
            "content": content,
            "tool_calls": tool_calls,
            "input_tokens": 15,
            "output_tokens": 10,
            "latency_ms": latency_ms,
            "finish_reason": "stop" if not tool_calls else "tool_calls",
            "raw_response": raw
        }

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
        yield {"content": "This ", "finish_reason": None}
        yield {"content": "is ", "finish_reason": None}
        yield {"content": "a ", "finish_reason": None}
        yield {"content": "mocked ", "finish_reason": None}
        yield {"content": "streamed ", "finish_reason": None}
        yield {"content": "response.", "finish_reason": "stop"}

    async def count_tokens(self, messages: list[dict[str, Any]], model: str) -> int:
        # Simple character count heuristic for mocking
        total_chars = sum(len(m.get("content") or "") for m in messages)
        return total_chars // 4

    async def health_check(self, model: str, credentials: Optional[dict[str, Any]] = None) -> bool:
        return True
