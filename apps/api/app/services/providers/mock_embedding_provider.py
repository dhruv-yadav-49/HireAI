import hashlib
import time
from typing import Any, Optional


class MockEmbeddingProvider:
    """Mock embedding provider producing deterministic 1536-dimensional vectors for local smoke tests."""

    async def embed(self, text: str, credentials: Optional[dict[str, Any]] = None) -> list[float]:
        # Small artificial delay to simulate API call
        time.sleep(0.001)
        
        # Hash text deterministically to generate floats
        h = hashlib.sha256(text.encode("utf-8")).digest()
        vector = []
        for i in range(1536):
            # Deterministic float in range [-1.0, 1.0]
            val = ((h[i % len(h)] * (i + 1)) % 1000) / 500.0 - 1.0
            vector.append(val)
        return vector

    async def batch_embed(self, texts: list[str], credentials: Optional[dict[str, Any]] = None) -> list[list[float]]:
        results = []
        for txt in texts:
            vec = await self.embed(txt, credentials)
            results.append(vec)
        return results

    async def dimensions(self) -> int:
        return 1536

    async def health_check(self, credentials: Optional[dict[str, Any]] = None) -> bool:
        return True
