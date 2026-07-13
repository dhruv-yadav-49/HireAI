import uuid
from typing import Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class CommunicationProvider(Protocol):
    """The standard protocol defining the contract that all messaging provider integrations must follow."""

    async def validate(self, configuration: dict[str, Any], credentials: dict[str, Any]) -> None:
        """Validates configuration parameters and credentials structural correctness.
        
        Raises ValidationException or ValueError on failure.
        """
        ...

    async def health_check(self, configuration: dict[str, Any], credentials: dict[str, Any]) -> bool:
        """Tests if the provider credentials can actively connect to the external API/server."""
        ...

    async def send(
        self,
        recipient: str,
        subject: Optional[str],
        body: str,
        payload: dict[str, Any],
        configuration: dict[str, Any],
        credentials: dict[str, Any]
    ) -> dict[str, Any]:
        """Dispatches the outbound message.
        
        Returns:
            A dictionary containing delivery metadata:
            {
                "provider_message_id": str,
                "status_code": int,
                "provider_latency_ms": int,
                "provider_response": dict,
                "provider_error_code": Optional[str]
            }
        """
        ...

    async def get_delivery_status(self, provider_message_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        """Retrieves active message status updates directly from the provider."""
        ...

    async def cancel(self, provider_message_id: str, credentials: dict[str, Any]) -> bool:
        """Requests cancellation of a scheduled message on the provider's side."""
        ...

    async def parse_webhook(self, webhook_payload: dict[str, Any]) -> dict[str, Any]:
        """Translates incoming provider callbacks into unified delivery log format."""
        ...


class MockProvider(CommunicationProvider):
    """High-fidelity mock provider for unit and integration smoke testing."""

    async def validate(self, configuration: dict[str, Any], credentials: dict[str, Any]) -> None:
        pass

    async def health_check(self, configuration: dict[str, Any], credentials: dict[str, Any]) -> bool:
        return True

    async def send(
        self,
        recipient: str,
        subject: Optional[str],
        body: str,
        payload: dict[str, Any],
        configuration: dict[str, Any],
        credentials: dict[str, Any]
    ) -> dict[str, Any]:
        import time
        start = time.perf_counter()
        # Simulate small network delay
        time.sleep(0.005)
        latency = int((time.perf_counter() - start) * 1000)
        
        # Check if we should simulate a transient/permanent failure for testing retry
        if "simulate_fail" in recipient:
            return {
                "provider_message_id": None,
                "status_code": 500,
                "provider_latency_ms": latency,
                "provider_response": {"error": "Simulated transmission failure"},
                "provider_error_code": "SIMULATED_FAIL"
            }

        msg_id = f"mock_{uuid.uuid4().hex[:12]}"
        return {
            "provider_message_id": msg_id,
            "status_code": 200,
            "provider_latency_ms": latency,
            "provider_response": {"status": "sent", "message_id": msg_id},
            "provider_error_code": None
        }

    async def get_delivery_status(self, provider_message_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        return {"status": "DELIVERED"}

    async def cancel(self, provider_message_id: str, credentials: dict[str, Any]) -> bool:
        return True

    async def parse_webhook(self, webhook_payload: dict[str, Any]) -> dict[str, Any]:
        return {"event": "DELIVERED", "provider_message_id": webhook_payload.get("message_id")}
