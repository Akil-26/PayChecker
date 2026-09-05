"""Production clock — real UTC wall-clock time.

Kept in its own module, separate from ``app.core.clock``, so that module can be
mechanically verified to derive time only from persisted simulation state
(Requirement 18.2). ``WallClock`` is the one legitimate exception: production
needs real time, and that necessarily means reading ``datetime.now()``.
"""

from __future__ import annotations

from datetime import datetime, timezone


class WallClock:
    """Real UTC wall clock — used in production."""

    def now(self) -> datetime:
        return datetime.now(tz=timezone.utc).replace(tzinfo=None)

    def is_due(self, moment: datetime | None) -> bool:
        if moment is None:
            return True
        return self.now() >= moment

    # Stub methods so routes that call advance/reset don't crash when
    # they are accidentally reached in production (they are gated by
    # ENVIRONMENT checks in the route layer, but defence-in-depth).
    def advance(self, *, minutes: int = 0, hours: int = 0) -> datetime:  # noqa: ARG002
        return self.now()

    def reset(self, to: datetime | None = None) -> datetime:  # noqa: ARG002
        return self.now()


__all__ = ["WallClock"]
