from typing import Callable, Dict, Any, Optional

class EventRegistry:
    """Registry mapping subscriber names to execution callable handlers and versions."""

    _registry: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def register(
        cls,
        subscriber_name: str,
        handler: Callable,
        subscriber_version: str = "v1",
        handler_version: str = "v1",
        supports_idempotency: bool = True,
        timeout_seconds: int = 60
    ) -> None:
        """Registers a subscriber handler with version and execution metadata."""
        cls._registry[subscriber_name] = {
            "handler": handler,
            "subscriber_version": subscriber_version,
            "handler_version": handler_version,
            "supports_idempotency": supports_idempotency,
            "timeout_seconds": timeout_seconds
        }

    @classmethod
    def get_handler(cls, subscriber_name: str) -> Optional[Callable]:
        """Gets the execution function for a subscriber name."""
        meta = cls._registry.get(subscriber_name)
        return meta["handler"] if meta else None

    @classmethod
    def get_metadata(cls, subscriber_name: str) -> Optional[Dict[str, Any]]:
        """Gets all registration metadata for a subscriber."""
        return cls._registry.get(subscriber_name)

    @classmethod
    def list_subscribers(cls) -> Dict[str, Dict[str, Any]]:
        """Returns all registered subscribers."""
        return cls._registry
