from __future__ import annotations
import logging
from app.models.enums import AIJobStatus

logger = logging.getLogger(__name__)


class JobStateMachine:
    """Restricts and validates execution state machine transitions.

    CTO refinement #1: Explicit DISPATCHED transition check.
    """

    _VALID_TRANSITIONS = {
        AIJobStatus.QUEUED: [AIJobStatus.DISPATCHED, AIJobStatus.CANCELLED],
        AIJobStatus.DISPATCHED: [AIJobStatus.RUNNING, AIJobStatus.CANCELLED, AIJobStatus.FAILED],
        AIJobStatus.RUNNING: [AIJobStatus.COMPLETED, AIJobStatus.FAILED, AIJobStatus.CANCELLED],
        AIJobStatus.FAILED: [AIJobStatus.RETRYING, AIJobStatus.DEAD_LETTER],
        AIJobStatus.RETRYING: [AIJobStatus.QUEUED, AIJobStatus.DEAD_LETTER],
        AIJobStatus.CANCELLED: [],
        AIJobStatus.COMPLETED: [],
        AIJobStatus.DEAD_LETTER: [AIJobStatus.QUEUED]  # Replays re-enter QUEUED state
    }

    @classmethod
    def validate_transition(cls, current: AIJobStatus, target: AIJobStatus) -> bool:
        """Returns True if the transition is allowed, False otherwise."""
        if current == target:
            return True

        allowed = cls._VALID_TRANSITIONS.get(current, [])
        is_valid = target in allowed
        if not is_valid:
            logger.warning(f"Invalid job state machine transition attempted: {current.value} -> {target.value}")
        return is_valid
