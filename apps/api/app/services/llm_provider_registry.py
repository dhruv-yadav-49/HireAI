from typing import Optional
from app.models.enums import AIProvider
from app.services.providers.base_llm_provider import BaseLLMProvider
from app.services.providers.openai_provider import OpenAIProvider
from app.services.providers.anthropic_provider import AnthropicProvider
from app.services.providers.gemini_provider import GeminiProvider
from app.services.providers.mock_provider import MockLLMProvider


class LLMProviderRegistry:
    """Registry mapping AIProvider enums to concrete provider wrappers and failover chains."""

    PROVIDERS = {
        AIProvider.OPENAI: OpenAIProvider(),
        AIProvider.ANTHROPIC: AnthropicProvider(),
        AIProvider.GEMINI: GeminiProvider(),
        AIProvider.MOCK: MockLLMProvider()
    }

    @classmethod
    def get_provider(cls, provider_type: AIProvider) -> BaseLLMProvider:
        """Retrieves the registered LLM provider instance."""
        provider = cls.PROVIDERS.get(provider_type)
        if not provider:
            raise ValueError(f"Unsupported AI Provider type: {provider_type}")
        return provider

    @classmethod
    def fallback_provider(cls, failed_provider: AIProvider) -> Optional[AIProvider]:
        """Resolves the next failover fallback provider in chain: OPENAI -> GEMINI -> ANTHROPIC -> MOCK."""
        chain = [
            AIProvider.OPENAI,
            AIProvider.GEMINI,
            AIProvider.ANTHROPIC,
            AIProvider.MOCK
        ]
        try:
            idx = chain.index(failed_provider)
            if idx + 1 < len(chain):
                return chain[idx + 1]
        except ValueError:
            pass
        return None
