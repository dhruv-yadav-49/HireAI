from __future__ import annotations
import time
import uuid
import logging
from typing import Any, Optional
from app.models.enums import QueueType

logger = logging.getLogger(__name__)


class QueueItem:
    def __init__(self, job_id: uuid.UUID, priority: int, data: dict[str, Any], queue_type: QueueType):
        self.job_id = job_id
        self.priority = priority
        self.data = data
        self.queue_type = queue_type
        self.enqueued_at = time.time()
        self.invisible_until: float = 0.0
        self.attempts = 0


class RedisQueue:
    """Manages low-level queue operations.

    ADR-019: Queue Abstraction, Visibility Timeout.
    """
    _memory_queues: dict[str, list[QueueItem]] = {}
    _in_flight: dict[uuid.UUID, QueueItem] = {}

    def __init__(self, queue_name: str = "DEFAULT"):
        self.queue_name = queue_name
        if queue_name not in self._memory_queues:
            self._memory_queues[queue_name] = []

    async def enqueue(self, job_id: uuid.UUID, priority: int, data: dict[str, Any]) -> None:
        """Pushes an item into the queue. Sorted by priority (highest priority first)."""
        queue = self._memory_queues[self.queue_name]
        item = QueueItem(job_id, priority, data, QueueType(self.queue_name))
        queue.append(item)
        # Sort desc by priority, asc by enqueued_at
        queue.sort(key=lambda x: (-x.priority, x.enqueued_at))
        logger.info(f"Enqueued job {job_id} to queue {self.queue_name} (priority {priority})")

    async def dequeue(self, visibility_timeout_sec: int = 60) -> Optional[dict[str, Any]]:
        """Pops the highest priority item. Starts a visibility timeout."""
        queue = self._memory_queues[self.queue_name]
        now = time.time()

        # Find first item that is not invisible
        for item in queue:
            if item.invisible_until <= now:
                queue.remove(item)
                item.invisible_until = now + visibility_timeout_sec
                item.attempts += 1
                self._in_flight[item.job_id] = item
                logger.info(f"Dequeued job {item.job_id} from queue {self.queue_name}. Visibility timeout: {visibility_timeout_sec}s")
                return {
                    "job_id": item.job_id,
                    "priority": item.priority,
                    "data": item.data,
                    "attempts": item.attempts
                }
        return None

    async def acknowledge(self, job_id: uuid.UUID) -> bool:
        """Acknowledges successful processing. Removes job from in-flight tracker."""
        if job_id in self._in_flight:
            del self._in_flight[job_id]
            logger.info(f"Acknowledged and deleted job {job_id} from in-flight tracker")
            return True
        return False

    async def requeue(self, job_id: uuid.UUID, delay_sec: int = 0) -> bool:
        """Re-queues a failed or visibility-timeout expired job."""
        item = None
        if job_id in self._in_flight:
            item = self._in_flight.pop(job_id)
        else:
            # Search in memory queues if it was not in flight
            for q_name, queue in self._memory_queues.items():
                for x in queue:
                    if x.job_id == job_id:
                        queue.remove(x)
                        item = x
                        break
                if item:
                    break

        if item:
            item.invisible_until = time.time() + delay_sec
            queue = self._memory_queues[self.queue_name]
            queue.append(item)
            queue.sort(key=lambda x: (-x.priority, x.enqueued_at))
            logger.info(f"Re-queued job {job_id} into queue {self.queue_name} with delay {delay_sec}s")
            return True
        return False

    async def check_visibility_timeouts(self) -> list[uuid.UUID]:
        """Scans in-flight jobs. If visibility timeout has expired, requeues the job."""
        now = time.time()
        expired_ids = []
        for job_id, item in list(self._in_flight.items()):
            if item.invisible_until <= now:
                expired_ids.append(job_id)
                # Requeue automatically
                await self.requeue(job_id, delay_sec=0)
        return expired_ids

    def get_depth(self) -> int:
        return len(self._memory_queues.get(self.queue_name, []))

    def get_in_flight_count(self) -> int:
        return sum(1 for item in self._in_flight.values() if item.queue_type.value == self.queue_name)

    @classmethod
    def clear_all(cls):
        cls._memory_queues.clear()
        cls._in_flight.clear()
