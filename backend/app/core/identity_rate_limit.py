"""Per-identity (not per-IP) rate limiting. `slowapi` (see rate_limit.py)
keys on remote address, which doesn't stop the same identity (e.g. one
mobile number) being hammered from many rotating IPs — a real gap for a
public, unauthenticated endpoint like donation initiation. Deliberately a
tiny in-memory sliding-window counter, not a new infra dependency — matches
the same "single-instance, in-memory is fine at this scale" call already
made for slowapi itself (see docs/06-deployment-security.md §6.3); promote
both together if multi-instance deployment ever requires a shared store.
"""

import threading
import time
from collections import defaultdict, deque


class IdentityRateLimiter:
    """Generic sliding-window counter, keyed by an arbitrary identity string.
    `max_requests` is passed per-call (not fixed at construction) so callers
    can source the threshold from `Settings` without needing a second
    process-wide singleton per config value."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, identity: str, *, max_requests: int, window_seconds: int) -> bool:
        """Returns False (and does NOT record a hit) if `identity` is already
        at its limit within the current window; otherwise records the hit
        and returns True."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[identity]
            while hits and now - hits[0] > window_seconds:
                hits.popleft()
            if len(hits) >= max_requests:
                return False
            hits.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


donation_identity_limiter = IdentityRateLimiter()
