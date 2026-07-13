from typing import Any, Optional
import uuid
import time

from app.services.providers.base_provider import CommunicationProvider


class GmailProvider(CommunicationProvider):
    """Placeholder Gmail API provider using OAuth / Google client services."""

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
        start = time.perf_counter()
        # Mock transmission
        time.sleep(0.01)
        latency = int((time.perf_counter() - start) * 1000)
        return {
            "provider_message_id": f"gmail_mock_{uuid.uuid4().hex[:12]}",
            "status_code": 200,
            "provider_latency_ms": latency,
            "provider_response": {"message": "Mock Gmail API call succeeded"},
            "provider_error_code": None
        }

    async def get_delivery_status(self, provider_message_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        return {"status": "DELIVERED"}

    async def cancel(self, provider_message_id: str, credentials: dict[str, Any]) -> bool:
        return False

    async def parse_webhook(self, webhook_payload: dict[str, Any]) -> dict[str, Any]:
        return {}
