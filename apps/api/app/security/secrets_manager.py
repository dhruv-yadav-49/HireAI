"""
app/security/secrets_manager.py

Secret management abstraction layer.

ADR-021: Secret Abstraction — business code never directly accesses secret
providers. The SecretsManager facade shields the application from provider
details. Swapping from env variables to HashiCorp Vault requires only a new
provider implementation.

CTO refinement #4: Full interface includes get/set/rotate/delete/list.
"""
import logging
import os
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


# ── Provider interface (CTO refinement #4) ────────────────────────────────────

class SecretsProvider(ABC):
    """Abstract interface for secret storage backends.

    Implementations:
        EnvSecretsProvider      — environment variables (MVP)
        VaultSecretsProvider    — HashiCorp Vault (future)
        AWSSecretsProvider      — AWS Secrets Manager (future)
        AzureSecretsProvider    — Azure Key Vault (future)
    """

    @abstractmethod
    def get(self, name: str) -> Optional[str]:
        """Retrieve a secret value by name. Returns None if not found."""
        ...

    @abstractmethod
    def set(self, name: str, value: str) -> None:
        """Store or update a secret. May not be supported by read-only providers."""
        ...

    @abstractmethod
    def rotate(self, name: str, new_value: str) -> None:
        """Rotate a secret to a new value, preserving the previous version briefly."""
        ...

    @abstractmethod
    def delete(self, name: str) -> None:
        """Delete a secret permanently."""
        ...

    @abstractmethod
    def list(self, prefix: str = "") -> list[str]:
        """List secret names, optionally filtered by prefix."""
        ...


class EnvSecretsProvider(SecretsProvider):
    """Environment variable backed secrets provider (MVP).

    Reads from os.environ. Set/rotate/delete modify the in-process
    environment (not persisted across restarts — acceptable for development
    and simple deployments).
    """

    def get(self, name: str) -> Optional[str]:
        value = os.environ.get(name)
        if value is None:
            logger.debug("Secret not found in environment: %s", name)
        return value

    def set(self, name: str, value: str) -> None:
        os.environ[name] = value

    def rotate(self, name: str, new_value: str) -> None:
        """Rotate: store new value. Previous value is lost in-process."""
        old = os.environ.get(name)
        os.environ[name] = new_value
        logger.info("Secret rotated: %s (had value: %s)", name, "***" if old else "None")

    def delete(self, name: str) -> None:
        os.environ.pop(name, None)

    def list(self, prefix: str = "") -> list[str]:
        if prefix:
            return [k for k in os.environ if k.startswith(prefix)]
        return list(os.environ.keys())


# ── SecretsManager facade ──────────────────────────────────────────────────────

class SecretsManager:
    """Thin facade over a SecretsProvider.

    ADR-021: Business code calls SecretsManager, never a provider directly.
    Raw values are never logged.
    """

    def __init__(self, provider: Optional[SecretsProvider] = None) -> None:
        self._provider: SecretsProvider = provider or EnvSecretsProvider()

    def get_secret(self, name: str) -> Optional[str]:
        """Retrieve a secret. Returns None if not found. Never logs the value."""
        return self._provider.get(name)

    def get_secret_or_raise(self, name: str) -> str:
        """Retrieve a secret, raising ValueError if not configured."""
        value = self._provider.get(name)
        if value is None:
            raise ValueError(f"Required secret '{name}' is not configured.")
        return value

    def set_secret(self, name: str, value: str) -> None:
        self._provider.set(name, value)

    def rotate_secret(self, name: str, new_value: str) -> None:
        self._provider.rotate(name, new_value)

    def delete_secret(self, name: str) -> None:
        self._provider.delete(name)

    def list_secrets(self, prefix: str = "") -> list[str]:
        return self._provider.list(prefix)

    def swap_provider(self, provider: SecretsProvider) -> None:
        """Hot-swap the backend provider (useful for staged migration)."""
        self._provider = provider


# ── Application singleton ──────────────────────────────────────────────────────
_secrets_manager = SecretsManager()


def get_secrets_manager() -> SecretsManager:
    """Return the application-wide SecretsManager instance."""
    return _secrets_manager
