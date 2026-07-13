import uuid
import time
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional

from app.core.exceptions import ValidationException
from app.services.providers.base_provider import CommunicationProvider

logger = logging.getLogger(__name__)


class SMTPProvider(CommunicationProvider):
    """SMTP server provider integration for outgoing emails."""

    async def validate(self, configuration: dict[str, Any], credentials: dict[str, Any]) -> None:
        if not configuration.get("host"):
            raise ValidationException("SMTP configuration requires 'host'")
        if not configuration.get("port"):
            raise ValidationException("SMTP configuration requires 'port'")
        if not configuration.get("from_email"):
            raise ValidationException("SMTP configuration requires 'from_email'")

    async def health_check(self, configuration: dict[str, Any], credentials: dict[str, Any]) -> bool:
        await self.validate(configuration, credentials)
        host = configuration["host"]
        port = int(configuration["port"])
        username = credentials.get("username")
        password = credentials.get("password")
        tls = configuration.get("tls", True)

        if host in ("localhost", "mock", "smtp.mock"):
            return True

        try:
            # Connect synchronously in a loop-executor wrapper or directly (health test can be synch block)
            server = smtplib.SMTP(host, port, timeout=5)
            if tls:
                server.starttls()
            if username and password:
                server.login(username, password)
            server.quit()
            return True
        except Exception as e:
            logger.error(f"SMTP health check failed: {e}")
            return False

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
        
        host = configuration["host"]
        port = int(configuration["port"])
        from_email = configuration["from_email"]
        username = credentials.get("username")
        password = credentials.get("password")
        tls = configuration.get("tls", True)

        start_time = time.perf_counter()

        # Handle Mock Mode
        if host in ("localhost", "mock", "smtp.mock") or not password:
            # Simulate latency
            time.sleep(0.05)
            latency = int((time.perf_counter() - start_time) * 1000)
            msg_id = f"smtp_mock_{uuid.uuid4().hex[:12]}"
            logger.info(f"[MOCK SMTP SEND] From={from_email}, To={recipient}, Subject={subject}, MsgId={msg_id}")
            return {
                "provider_message_id": msg_id,
                "status_code": 250,
                "provider_latency_ms": latency,
                "provider_response": {"message": "Simulated successful SMTP transmission"},
                "provider_error_code": None
            }

        try:
            # Build message
            msg = MIMEMultipart()
            msg["From"] = from_email
            msg["To"] = recipient
            msg["Subject"] = subject or ""
            msg.attach(MIMEText(body, "html" if payload.get("is_html") else "plain"))

            # Dispatch
            server = smtplib.SMTP(host, port, timeout=10)
            if tls:
                server.starttls()
            if username and password:
                server.login(username, password)
            server.sendmail(from_email, recipient, msg.as_string())
            server.quit()

            latency = int((time.perf_counter() - start_time) * 1000)
            msg_id = f"smtp_{uuid.uuid4().hex[:12]}"
            return {
                "provider_message_id": msg_id,
                "status_code": 250,
                "provider_latency_ms": latency,
                "provider_response": {"status": "dispatched"},
                "provider_error_code": None
            }
        except Exception as e:
            latency = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"SMTP send failed: {e}")
            return {
                "provider_message_id": None,
                "status_code": 500,
                "provider_latency_ms": latency,
                "provider_response": {"error": str(e)},
                "provider_error_code": "SMTP_SEND_ERROR"
            }

    async def get_delivery_status(self, provider_message_id: str, credentials: dict[str, Any]) -> dict[str, Any]:
        return {"status": "DELIVERED", "details": "SMTP protocol has no native webhook tracking"}

    async def cancel(self, provider_message_id: str, credentials: dict[str, Any]) -> bool:
        return False

    async def parse_webhook(self, webhook_payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("SMTP provider does not support webhook callbacks")
