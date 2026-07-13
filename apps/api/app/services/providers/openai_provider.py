import time
from typing import Any, Optional
import httpx
from app.core.exceptions import ValidationException


class OpenAIProvider:
    """OpenAI API Provider wrapper conforming to the BaseLLMProvider protocol."""

    capabilities = {
        "supports_streaming": True,
        "supports_tools": True,
        "supports_images": True,
        "supports_reasoning": True,
        "supports_json": True,
        "supports_vision": True,
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
        api_key = (credentials or {}).get("api_key")
        if not api_key:
            raise ValidationException("Missing OpenAI API Key in provider credentials.")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if tools:
            payload["tools"] = tools
        if response_format:
            payload["response_format"] = response_format

        start_time = time.time()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=60.0
            )
        latency_ms = int((time.time() - start_time) * 1000)

        if response.status_code != 200:
            raise ValidationException(f"OpenAI API call failed: {response.text}")

        res_data = response.json()
        choice = res_data["choices"][0]
        msg = choice["message"]
        content = msg.get("content")
        
        tool_calls = None
        if "tool_calls" in msg:
            tool_calls = []
            for tc in msg["tool_calls"]:
                tool_calls.append({
                    "id": tc["id"],
                    "name": tc["function"]["name"],
                    "arguments": tc["function"]["arguments"]  # Note: stringified JSON from OpenAI
                })

        usage = res_data.get("usage", {})
        
        return {
            "content": content,
            "tool_calls": tool_calls,
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "latency_ms": latency_ms,
            "finish_reason": choice.get("finish_reason"),
            "raw_response": res_data
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
        # Streaming placeholder implementation
        yield {"content": "OpenAI streaming placeholder", "finish_reason": "stop"}

    async def count_tokens(self, messages: list[dict[str, Any]], model: str) -> int:
        total_chars = sum(len(m.get("content") or "") for m in messages)
        return total_chars // 4

    async def health_check(self, model: str, credentials: Optional[dict[str, Any]] = None) -> bool:
        api_key = (credentials or {}).get("api_key")
        if not api_key:
            return False
        # Minimal models request to verify key validation
        headers = {"Authorization": f"Bearer {api_key}"}
        async with httpx.AsyncClient() as client:
            res = await client.get("https://api.openai.com/v1/models", headers=headers, timeout=10.0)
        return res.status_code == 200
