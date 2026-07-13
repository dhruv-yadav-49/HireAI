from typing import Any, Optional
from app.models.enums import EmbeddingProvider
from app.services.providers.base_embedding_provider import BaseEmbeddingProvider
from app.services.providers.openai_embedding_provider import OpenAIEmbeddingProvider
from app.services.providers.gemini_embedding_provider import GeminiEmbeddingProvider
from app.services.providers.mock_embedding_provider import MockEmbeddingProvider


class EmbeddingService:
    """Orchestration service managing embedding generations across multiple vendor providers."""

    PROVIDERS = {
        EmbeddingProvider.OPENAI: OpenAIEmbeddingProvider(),
        EmbeddingProvider.GEMINI: GeminiEmbeddingProvider(),
        EmbeddingProvider.MOCK: MockEmbeddingProvider()
    }

    @classmethod
    def get_provider(cls, provider_type: EmbeddingProvider) -> BaseEmbeddingProvider:
        """Retrieves the registered embedding provider instance."""
        p_type = EmbeddingProvider(provider_type)
        provider = cls.PROVIDERS.get(p_type)
        if not provider:
            raise ValueError(f"Unsupported Embedding Provider: {provider_type}")
        return provider

    @classmethod
    async def embed_text(
        cls, provider_type: EmbeddingProvider, text: str, credentials: Optional[dict[str, Any]] = None
    ) -> list[float]:
        """Convenience method to embed a single text block."""
        provider = cls.get_provider(provider_type)
        return await provider.embed(text, credentials)

    @classmethod
    async def batch_embed_texts(
        cls, provider_type: EmbeddingProvider, texts: list[str], credentials: Optional[dict[str, Any]] = None
    ) -> list[list[float]]:
        """Convenience method to embed multiple text blocks in parallel."""
        provider = cls.get_provider(provider_type)
        return await provider.batch_embed(texts, credentials)
