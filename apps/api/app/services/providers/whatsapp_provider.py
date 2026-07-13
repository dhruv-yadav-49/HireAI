from typing import Any, Optional
import uuid
import time
import logging

from app.services.providers.base_provider import CommunicationProvider
from app.core.exceptions import ValidationException

logger = logging.getLogger(__name__)


class MetaWhatsAppProvider(CommunicationProvider):
    """WhatsApp Cloud API integration from Meta."""

    async def validate(self, configuration: dict[str, Any], credentials: dict[str, Any]) -> None:
        if not configuration.get("phone_number_id"):
            raise ValidationException("Meta WhatsApp requires 'phone_number_id'")

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
        
        # Simulate Meta WhatsApp cloud call
        time.sleep(0.02)
        latency = int((time.perf_counter() - start) * 1000)
        msg_id = f"meta_wa_{uuid.uuid4().hex[:12]}"
        
        logger.info(f"[META WHATSAPP SEND] Recipient={recipient}, MsgId={msg_id}, BodyExcerpt='{body[:50]}'")
        return {
            "provider_message_id": msg_id,
            "status_code": 200,
            "provider_latency_ms": latency,
            "provider_response": {"messaging_product": "whatsapp", "contacts": [{"input": recipient, "wa_id": recipient}], "messages": [{"id": msg_id}]},
            "provider_error_code": None
        }

    async def get_delivery_status(self, provider_message_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        return {"status": "DELIVERED"}

    async def cancel(self, provider_message_id: str, credentials: dict[str, Any]) -> bool:
        return False

    async def parse_webhook(self, webhook_payload: dict[str, Any]) -> dict[str, Any]:
        return {}


class TwilioWhatsAppProvider(CommunicationProvider):
    """Twilio WhatsApp messaging integration provider."""

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
        
        # Simulate Twilio messaging API request
        time.sleep(0.02)
        latency = int((time.perf_counter() - start) * 1000)
        msg_id = f"twilio_wa_{uuid.uuid4().hex[:12]}"
        
        logger.info(f"[TWILIO WHATSAPP SEND] Recipient={recipient}, MsgId={msg_id}, BodyExcerpt='{body[:50]}'")
        return {
            "provider_message_id": msg_id,
            "status_code": 201,
            "provider_latency_ms": latency,
            "provider_response": {"sid": msg_id, "status": "queued"},
            "provider_error_code": None
        }

    async def get_delivery_status(self, provider_message_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        return {"status": "DELIVERED"}

    async def cancel(self, provider_message_id: str, credentials: dict[str, Any]) -> bool:
        return True

    async def parse_webhook(self, webhook_payload: dict[str, Any]) -> dict[str, Any]:
        return {}
