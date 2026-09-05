"""Deterministic simulation clock.

This module derives time exclusively from persisted simulation state — never
from the real wall clock — so recovery timelines stay reproducible in tests
and demos (Requirement 18.2). The production wall clock lives separately in
``app.core.wall_clock`` so that guarantee can be checked mechanically (no
``datetime.now()`` call may appear anywhere in this file).

This module exports a unified Clock protocol so all callers are agnostic
to whether they are running against a real or virtual clock.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Protocol


class Clock(Protocol):
    """Minimal clock interface used throughout the system."""

    def now(self) -> datetime: ...
    def is_due(self, moment: datetime | None) -> bool: ...


_ISO_KEY = "simulation_time"


class VirtualClock:
    """Deterministic clock for development and testing — NOT for production.

    Moves only when explicitly advanced. State is persisted as JSON so the
    API process and CLI scripts share one timeline.
    """

    def __init__(self, state_path: str | Path, start: datetime) -> None:
        self._state_path = Path(state_path)
        self._start = start

    def now(self) -> datetime:
        stored = self._read()
        if stored is None:
            return self._write(self._start)
        return stored

    def is_due(self, moment: datetime | None) -> bool:
        if moment is None:
            return True
        return self.now() >= moment

    def advance(self, *, minutes: int = 0, hours: int = 0) -> datetime:
        from datetime import timedelta
        delta = timedelta(minutes=minutes, hours=hours)
        if delta.total_seconds() < 0:
            raise ValueError("Simulation time cannot move backwards.")
        return self._write(self.now() + delta)

    def reset(self, to: datetime | None = None) -> datetime:
        return self._write(to if to is not None else self._start)

    def _read(self) -> datetime | None:
        try:
            raw = self._state_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        try:
            payload = json.loads(raw)
            return datetime.fromisoformat(payload[_ISO_KEY])
        except (ValueError, KeyError, TypeError):
            return None

    def _write(self, moment: datetime) -> datetime:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(
            json.dumps({_ISO_KEY: moment.isoformat()}, indent=2) + "\n",
            encoding="utf-8",
        )
        return moment


def build_clock():
    """Construct the correct clock from settings.

    Production → WallClock (real UTC time).
    Development / demo / test → VirtualClock (deterministic, advanceable).
    """
    from app.core.config import get_settings
    from app.core.wall_clock import WallClock

    settings = get_settings()
    env = (settings.environment or "production").strip().lower()

    if env == "production":
        return WallClock()

    return VirtualClock(
        state_path=settings.virtual_clock_state_path,
        start=settings.virtual_clock_start,
    )


__all__ = ["Clock", "VirtualClock", "build_clock"]
