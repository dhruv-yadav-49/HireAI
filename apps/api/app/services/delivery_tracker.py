import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import DomainEvent, get_event_publisher
from app.models.enums import DeliveryEvent
from app.models.communication import Communication
from app.models.communication_delivery import CommunicationDelivery


class DeliveryTracker:
    """Manages the delivery event audit timeline, computes sequence numbers, and publishes domain events."""

    @staticmethod
    async def log_delivery_event(
        db: AsyncSession,
        communication: Communication,
        event: DeliveryEvent,
        provider_message_id: Optional[str] = None,
        provider_latency_ms: Optional[int] = None,
        provider_status_code: Optional[int] = None,
        provider_error_code: Optional[str] = None,
        provider_response: Optional[dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> CommunicationDelivery:
        """Appends a new event entry into the communication deliveries audit timeline and triggers domain events."""
        # 1. Resolve sequence number
        stmt = select(func.coalesce(func.max(CommunicationDelivery.sequence_no), 0)).where(
            CommunicationDelivery.communication_id == communication.id
        )
        res = await db.execute(stmt)
        max_seq = res.scalar() or 0
        next_seq = max_seq + 1

        # 2. Persist audit log
        delivery = CommunicationDelivery(
            communication_id=communication.id,
            event=event,
            sequence_no=next_seq,
            provider_message_id=provider_message_id,
            provider_latency_ms=provider_latency_ms,
            provider_status_code=provider_status_code,
            provider_error_code=provider_error_code,
            provider_response=provider_response or {},
            error_message=error_message
        )
        db.add(delivery)
        await db.flush()

        # 3. Publish domain event (e.g. communication.created, communication.sent)
        event_name = f"communication.{event.value.lower()}"
        domain_event = DomainEvent(
            event_name=event_name,
            tenant_id=communication.organization_id,
            actor_id=communication.created_by,
            payload={
                "communication_id": str(communication.id),
                "channel": communication.channel.value,
                "recipient": communication.recipient,
                "recipient_type": communication.recipient_type.value,
                "direction": communication.direction.value,
                "conversation_id": str(communication.conversation_id) if communication.conversation_id else None,
                "status": communication.status.value,
                "priority": communication.priority.value,
                "provider_message_id": provider_message_id,
                "sequence_no": next_seq,
                "error_message": error_message
            }
        )
        
        publisher = get_event_publisher()
        await publisher.publish(domain_event)

        return delivery
