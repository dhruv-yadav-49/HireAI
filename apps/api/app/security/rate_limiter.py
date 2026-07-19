"""
app/security/rate_limiter.py

Sliding-window rate limiter with a pluggable backend interface.

CTO refinement #9: RateLimiterBackend interface documents the Memory → Redis
→ Distributed upgrade path. Swapping backends requires zero application code
changes.

ADR-021: Pluggable Security — rate limiting backend is independently replaceable.
"""
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from threading import Lock
from typing import Dict, Optional


@dataclass(frozen=True)
class RateLimitResult:
    """Result of a rate limit check."""
    allowed: bool
    remaining: int
    retry_after_seconds: Optional[float]   # None when allowed
    limit: int
    window_seconds: int


# ── Backend interface (CTO refinement #9) ─────────────────────────────────────

class RateLimiterBackend(ABC):
    """Abstract backend for rate limit state storage.

    Upgrade path:
        MemoryRateLimiterBackend    — in-process, single instance (MVP)
        RedisRateLimiterBackend     — shared across workers, Redis ZRANGEBYSCORE
        DistributedRateLimiterBackend — token bucket via distributed coordination
    """

    @abstractmethod
    def check_and_record(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        """Check whether key is within limit for the window.

        Atomically records the request if allowed.
        """
        ...

    @abstractmethod
    def reset(self, key: str) -> None:
        """Reset the counter for a key (for testing or admin override)."""
        ...


class MemoryRateLimiterBackend(RateLimiterBackend):
    """In-process sliding-window backend using deque.

    Thread-safe per-key locking. Suitable for single-instance deployments.
    """

    def __init__(self) -> None:
        # key → deque of request timestamps (monotonic seconds)
        self._windows: Dict[str, deque] = {}
        self._lock = Lock()

    def check_and_record(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        now = time.monotonic()
        cutoff = now - window_seconds

        with self._lock:
            if key not in self._windows:
                self._windows[key] = deque()

            window = self._windows[key]

            # Evict expired timestamps
            while window and window[0] < cutoff:
                window.popleft()

            count = len(window)

            if count >= limit:
                # Oldest timestamp + window gives retry-after
                oldest = window[0]
                retry_after = (oldest + window_seconds) - now
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    retry_after_seconds=max(0.0, retry_after),
                    limit=limit,
                    window_seconds=window_seconds,
                )

            window.append(now)
            return RateLimitResult(
                allowed=True,
                remaining=limit - count - 1,
                retry_after_seconds=None,
                limit=limit,
                window_seconds=window_seconds,
            )

    def reset(self, key: str) -> None:
        with self._lock:
            self._windows.pop(key, None)


# ── Rate limiter facade ────────────────────────────────────────────────────────

class RateLimiter:
    """Rate limiter facade. Configure once, use across the application.

    Default key patterns:
        org:{org_id}:{endpoint}     — per-org per-endpoint
        ip:{ip_address}:{endpoint}  — per-IP per-endpoint (unauthenticated)
        global:{endpoint}           — global endpoint cap
    """

    def __init__(
        self,
        limit: int = 1000,
        window_seconds: int = 60,
        backend: Optional[RateLimiterBackend] = None,
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._backend: RateLimiterBackend = backend or MemoryRateLimiterBackend()

    def check(self, key: str) -> RateLimitResult:
        """Check and record a request for the given key."""
        return self._backend.check_and_record(key, self.limit, self.window_seconds)

    def check_org(self, org_id: str, endpoint: str = "*") -> RateLimitResult:
        return self.check(f"org:{org_id}:{endpoint}")

    def check_ip(self, ip_address: str, endpoint: str = "*") -> RateLimitResult:
        return self.check(f"ip:{ip_address}:{endpoint}")

    def reset(self, key: str) -> None:
        self._backend.reset(key)


# ── Default singleton (shared across the application) ─────────────────────────
_default_limiter = RateLimiter(limit=1000, window_seconds=60)


def get_rate_limiter() -> RateLimiter:
    """Return the application-wide rate limiter instance."""
    return _default_limiter


def configure_rate_limiter(limit: int, window_seconds: int, backend: Optional[RateLimiterBackend] = None) -> None:
    """Reconfigure the application-wide rate limiter (call during startup)."""
    global _default_limiter
    _default_limiter = RateLimiter(limit=limit, window_seconds=window_seconds, backend=backend)
