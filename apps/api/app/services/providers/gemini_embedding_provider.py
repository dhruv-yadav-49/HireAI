from typing import Any, Optional
from app.core.exceptions import ValidationException


class GeminiEmbeddingProvider:
    """Gemini API Provider wrapper for text embeddings (placeholder)."""

    async def embed(self, text: str, credentials: Optional[dict[str, Any]] = None) -> list[float]:
        # Return mock 768-dim vector for Gemini
        return [0.1] * 768

    async def batch_embed(self, texts: list[str], credentials: Optional[dict[str, Any]] = None) -> list[list[float]]:
        return [[0.1] * 768 for _ in texts]

    async def dimensions(self) -> int:
        return 768

    async def health_check(self, credentials: Optional[dict[str, Any]] = None) -> bool:
        return (credentials or {}).get("api_key") is not None
