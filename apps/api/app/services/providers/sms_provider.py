from typing import Any, Optional
import uuid
import time
import logging

from app.services.providers.base_provider import CommunicationProvider
from app.core.exceptions import ValidationException

logger = logging.getLogger(__name__)


class TwilioSMSProvider(CommunicationProvider):
    """Twilio SMS integration provider."""

    async def validate(self, configuration: dict[str, Any], credentials: dict[str, Any]) -> None:
        if not credentials.get("account_sid"):
            raise ValidationException("Twilio requires 'account_sid'")
        if not credentials.get("auth_token"):
            raise ValidationException("Twilio requires 'auth_token'")

    async def health_check(self, configuration: dict[str, Any], credentials: dict[str, Any]) -> bool:
        await self.validate(configuration, credentials)
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
        await self.validate(configuration, credentials)
        start = time.perf_counter()
        
        time.sleep(0.01)
        latency = int((time.perf_counter() - start) * 1000)
        msg_id = f"twilio_sms_{uuid.uuid4().hex[:12]}"
        
        logger.info(f"[TWILIO SMS SEND] Recipient={recipient}, MsgId={msg_id}, Body='{body}'")
        return {
            "provider_message_id": msg_id,
            "status_code": 201,
            "provider_latency_ms": latency,
            "provider_response": {"sid": msg_id, "status": "sent"},
            "provider_error_code": None
        }

    async def get_delivery_status(self, provider_message_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        return {"status": "DELIVERED"}

    async def cancel(self, provider_message_id: str, credentials: dict[str, Any]) -> bool:
        return True

    async def parse_webhook(self, webhook_payload: dict[str, Any]) -> dict[str, Any]:
        return {}


class Msg91SMSProvider(CommunicationProvider):
    """MSG91 SMS integration provider."""

    async def validate(self, configuration: dict[str, Any], credentials: dict[str, Any]) -> None:
        if not credentials.get("auth_key"):
            raise ValidationException("MSG91 requires 'auth_key'")

    async def health_check(self, configuration: dict[str, Any], credentials: dict[str, Any]) -> bool:
        await self.validate(configuration, credentials)
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
        await self.validate(configuration, credentials)
        start = time.perf_counter()
        
        time.sleep(0.01)
        latency = int((time.perf_counter() - start) * 1000)
        msg_id = f"msg91_{uuid.uuid4().hex[:12]}"
        
        logger.info(f"[MSG91 SMS SEND] Recipient={recipient}, MsgId={msg_id}, Body='{body}'")
        return {
            "provider_message_id": msg_id,
            "status_code": 200,
            "provider_latency_ms": latency,
            "provider_response": {"request_id": msg_id, "type": "success"},
            "provider_error_code": None
        }

    async def get_delivery_status(self, provider_message_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        return {"status": "DELIVERED"}

    async def cancel(self, provider_message_id: str, credentials: dict[str, Any]) -> bool:
        return False

    async def parse_webhook(self, webhook_payload: dict[str, Any]) -> dict[str, Any]:
        return {}
