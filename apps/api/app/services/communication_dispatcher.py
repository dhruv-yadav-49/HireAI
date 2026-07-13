import time
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationException
from app.models.enums import (
    CommunicationStatus,
    DeliveryEvent,
)
from app.models.communication import Communication
from app.models.communication_provider import CommunicationProvider
from app.services.provider_registry import ProviderRegistry
from app.services.delivery_tracker import DeliveryTracker

logger = logging.getLogger(__name__)


class CommunicationDispatcher:
    """Dispatches queued communications by resolving providers, capabilities, and recording delivery metrics."""

    @staticmethod
    async def dispatch(db: AsyncSession, communication: Communication) -> bool:
        """Resolves the default provider for a communication channel and executes transmission."""
        
        # 1. Resolve configured provider for organization & channel
        stmt = select(CommunicationProvider).where(
            CommunicationProvider.organization_id == communication.organization_id,
            CommunicationProvider.channel == communication.channel,
            CommunicationProvider.enabled == True
        )
        res = await db.execute(stmt)
        providers = res.scalars().all()

        if not providers:
            # Fallback to system mock provider row or throw error
            # For testing/MVP convenience, look up a global mock or create fallback details
            raise ValidationException(
                f"No enabled provider configured for channel '{communication.channel.value}' on organization '{communication.organization_id}'."
            )

        # Prefer default provider, otherwise pick the first enabled
        provider = next((p for p in providers if p.is_default), providers[0])

        # 2. Verify capabilities
        if communication.attachments_json:
            supports_attachments = provider.capabilities_json.get("supports_attachments", False)
            if not supports_attachments:
                raise ValidationException(
                    f"Resolved provider '{provider.display_name}' does not support attachments."
                )

        # 3. Transition to PROCESSING state
        communication.status = CommunicationStatus.PROCESSING
        communication.provider_id = provider.id
        db.add(communication)
        await db.flush()

        await DeliveryTracker.log_delivery_event(
            db,
            communication,
            DeliveryEvent.PROCESSING,
            provider_message_id=None
        )

        # 4. Resolve provider class from registry
        provider_client = ProviderRegistry.get_provider(provider.provider_type, provider.channel.value)

        # 5. Dispatch actual send API call
        start_time = time.perf_counter()
        
        try:
            payload = {
                "is_html": communication.channel == "EMAIL",
                "attachments": communication.attachments_json,
                "priority": communication.priority.value
            }
            
            # Send message
            result = await provider_client.send(
                recipient=communication.recipient,
                subject=communication.rendered_subject or communication.subject,
                body=communication.rendered_body or communication.body,
                payload=payload,
                configuration=provider.configuration_json,
                credentials=provider.credentials_json
            )

            # Resolve timing
            latency = result.get("provider_latency_ms") or int((time.perf_counter() - start_time) * 1000)
            status_code = result.get("status_code", 200)
            msg_id = result.get("provider_message_id")
            err_code = result.get("provider_error_code")

            if status_code >= 400 or err_code is not None or msg_id is None:
                # Trigger failure path
                raise RuntimeError(
                    f"Provider transmission failure (status={status_code}, error_code={err_code})"
                )

            # Mark SUCCESS / SENT
            communication.status = CommunicationStatus.SENT
            communication.sent_at = datetime.now(timezone.utc)
            db.add(communication)
            await db.flush()

            await DeliveryTracker.log_delivery_event(
                db,
                communication,
                DeliveryEvent.SENT,
                provider_message_id=msg_id,
                provider_latency_ms=latency,
                provider_status_code=status_code,
                provider_error_code=None,
                provider_response=result.get("provider_response")
            )

            return True

        except Exception as exc:
            latency = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"Failed to dispatch communication {communication.id}: {exc}")
            
            # Re-raise to trigger retries in caller background processor
            await DeliveryTracker.log_delivery_event(
                db,
                communication,
                DeliveryEvent.FAILED,
                provider_message_id=None,
                provider_latency_ms=latency,
                provider_status_code=500,
                provider_error_code="TRANSMISSION_FAILED",
                provider_response={"error": str(exc)},
                error_message=str(exc)
            )
            
            raise exc
