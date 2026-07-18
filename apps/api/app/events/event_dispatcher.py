from __future__ import annotations

import uuid
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_event import AIEvent
from app.models.ai_event_subscription import AIEventSubscription
from app.models.ai_event_delivery import AIEventDelivery
from app.models.enums import EventStatus
from app.events.event_registry import EventRegistry

logger = logging.getLogger(__name__)

# Lease duration before a stale delivery is eligible for requeue (CTO refinement #2)
LEASE_DURATION_SECONDS = 120

# Worker identity — unique per process instance
WORKER_ID = f"dispatcher-{uuid.uuid4().hex[:8]}"


class EventDispatcher:
    """Executes subscriber handlers for pending deliveries using
    lease-based ownership and cooperative cancellation.

    ADR-020: At-Least-Once Delivery, Lease-Based Ownership,
    DLQ Metadata (CTO refinements #2, #8, #10).
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ──────────────────────────────────────────────────────────────────────────
    # Public
    # ──────────────────────────────────────────────────────────────────────────

    async def dispatch(self, event: AIEvent) -> None:
        """Dispatches all pending deliveries attached to *event*.

        For each delivery:
        1. Acquires an exclusive lease to prevent concurrent processing.
        2. Calls the registered handler with a per-subscriber timeout.
        3. On success → marks DELIVERED.
        4. On failure → increments attempt counter; moves to RETRYING or DEAD_LETTER.
        """
        stmt = select(AIEventDelivery).where(
            AIEventDelivery.event_id == event.id,
            AIEventDelivery.status.in_([EventStatus.PENDING, EventStatus.RETRYING]),
        )
        result = await self.db.execute(stmt)
        deliveries = list(result.scalars().all())

        if not deliveries:
            return

        for delivery in deliveries:
            await self._process_delivery(event, delivery)

    # ──────────────────────────────────────────────────────────────────────────
    # Internal
    # ──────────────────────────────────────────────────────────────────────────

    async def _acquire_lease(self, delivery: AIEventDelivery) -> bool:
        """Attempts to claim an exclusive processing lease.

        Returns True if the lease was successfully acquired.
        Returns False if another dispatcher already owns it.
        """
        now = datetime.now(timezone.utc)

        # Allow re-claim only if the existing lease has expired (dead worker)
        if delivery.lease_owner and delivery.lease_expires_at:
            # lease_expires_at may be naive UTC from DB; normalise
            lease_exp = delivery.lease_expires_at
            if lease_exp.tzinfo is None:
                lease_exp = lease_exp.replace(tzinfo=timezone.utc)
            if lease_exp > now:
                logger.debug(
                    "EventDispatcher: delivery %s still leased by %s",
                    delivery.id, delivery.lease_owner
                )
                return False

        stmt = (
            update(AIEventDelivery)
            .where(AIEventDelivery.id == delivery.id)
            .values(
                lease_owner=WORKER_ID,
                lease_expires_at=now + timedelta(seconds=LEASE_DURATION_SECONDS),
            )
        )
        await self.db.execute(stmt)
        await self.db.flush()
        # Refresh to verify we actually own it
        await self.db.refresh(delivery)
        return delivery.lease_owner == WORKER_ID

    async def _process_delivery(
        self, event: AIEvent, delivery: AIEventDelivery
    ) -> None:
        """Processes a single delivery record: lease acquisition → handler call
        → outcome recording."""
        # 1. Load subscriber metadata
        sub_stmt = select(AIEventSubscription).where(
            AIEventSubscription.id == delivery.subscriber_id
        )
        sub_result = await self.db.execute(sub_stmt)
        subscription: Optional[AIEventSubscription] = sub_result.scalar_one_or_none()
        if not subscription:
            logger.warning("EventDispatcher: subscriber %s not found, skipping", delivery.subscriber_id)
            return

        # 2. Idempotency check (CTO refinement #5)
        if delivery.processed_event_key and delivery.status == EventStatus.DELIVERED:
            logger.debug(
                "EventDispatcher: delivery %s already processed (idempotent), skipping", delivery.id
            )
            return

        # 3. Acquire lease
        acquired = await self._acquire_lease(delivery)
        if not acquired:
            return

        # 4. Look up handler
        handler = EventRegistry.get_handler(subscription.subscriber_name)
        if not handler:
            logger.warning(
                "EventDispatcher: no handler registered for subscriber '%s'",
                subscription.subscriber_name,
            )
            return

        # 5. Execute handler with timeout (CTO refinement #6)
        timeout = subscription.timeout_seconds or 60
        attempt = (delivery.attempt or 0) + 1

        try:
            await asyncio.wait_for(
                handler(event, self.db),
                timeout=float(timeout),
            )
            # 6. Mark delivered
            await self._mark_delivered(delivery, attempt)
            logger.info(
                "EventDispatcher: ✓ subscriber=%s event=%s attempt=%d",
                subscription.subscriber_name, event.event_key, attempt,
            )

        except asyncio.TimeoutError:
            error_msg = f"Handler '{subscription.subscriber_name}' timed out after {timeout}s"
            logger.warning("EventDispatcher: %s", error_msg)
            await self._handle_failure(delivery, subscription, attempt, error_msg)

        except Exception as exc:
            error_msg = repr(exc)
            logger.exception(
                "EventDispatcher: handler '%s' raised exception: %s",
                subscription.subscriber_name, error_msg,
            )
            await self._handle_failure(delivery, subscription, attempt, error_msg)

    async def _mark_delivered(self, delivery: AIEventDelivery, attempt: int) -> None:
        stmt = (
            update(AIEventDelivery)
            .where(AIEventDelivery.id == delivery.id)
            .values(
                status=EventStatus.DELIVERED,
                attempt=attempt,
                delivered_at=datetime.now(timezone.utc),
                lease_owner=None,
                lease_expires_at=None,
                last_error=None,
            )
        )
        await self.db.execute(stmt)
        await self.db.flush()

    async def _handle_failure(
        self,
        delivery: AIEventDelivery,
        subscription: AIEventSubscription,
        attempt: int,
        error_msg: str,
    ) -> None:
        """Increments attempt counter; moves to RETRYING or DEAD_LETTER based
        on the subscriber's retry_limit (CTO refinement #8)."""
        retry_limit = subscription.retry_limit or 3

        if attempt >= retry_limit:
            # Exhaust retries → Dead Letter Queue
            new_status = EventStatus.DEAD_LETTER
            stmt = (
                update(AIEventDelivery)
                .where(AIEventDelivery.id == delivery.id)
                .values(
                    status=new_status,
                    attempt=attempt,
                    last_error=error_msg,
                    dead_letter_reason=f"Retry limit ({retry_limit}) exhausted",
                    failed_subscriber=subscription.subscriber_name,
                    failed_attempt=attempt,
                    failed_at=datetime.now(timezone.utc),
                    lease_owner=None,
                    lease_expires_at=None,
                )
            )
            logger.warning(
                "EventDispatcher: delivery %s moved to DEAD_LETTER after %d attempts",
                delivery.id, attempt,
            )
        else:
            new_status = EventStatus.RETRYING
            stmt = (
                update(AIEventDelivery)
                .where(AIEventDelivery.id == delivery.id)
                .values(
                    status=new_status,
                    attempt=attempt,
                    last_error=error_msg,
                    lease_owner=None,
                    lease_expires_at=None,
                )
            )
            logger.info(
                "EventDispatcher: delivery %s RETRYING (attempt %d/%d)",
                delivery.id, attempt, retry_limit,
            )

        await self.db.execute(stmt)
        await self.db.flush()
