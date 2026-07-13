import httpx
from typing import Any, Optional
from app.core.exceptions import ValidationException


class OpenAIEmbeddingProvider:
    """OpenAI API wrapper for generating text embeddings using standard HTTP requests."""

    async def embed(self, text: str, credentials: Optional[dict[str, Any]] = None) -> list[float]:
        results = await self.batch_embed([text], credentials)
        return results[0]

    async def batch_embed(self, texts: list[str], credentials: Optional[dict[str, Any]] = None) -> list[list[float]]:
        api_key = (credentials or {}).get("api_key")
        if not api_key:
            raise ValidationException("Missing OpenAI API Key in provider credentials.")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "text-embedding-3-small",
            "input": texts
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                json=payload,
                headers=headers,
                timeout=30.0
            )

        if response.status_code != 200:
            raise ValidationException(f"OpenAI Embeddings call failed: {response.text}")

        res_data = response.json()
        embeddings = [data["embedding"] for data in res_data["data"]]
        return embeddings

    async def dimensions(self) -> int:
        return 1536

    async def health_check(self, credentials: Optional[dict[str, Any]] = None) -> bool:
        try:
            await self.embed("health check", credentials)
            return True
        except Exception:
            return False
