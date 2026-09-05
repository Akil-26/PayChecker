"""Simulation clock endpoint — development only.

These endpoints advance the virtual clock for deterministic testing of
RETRY_LATER scheduling. They are blocked in production — in production,
time is real (WallClock) and cannot be advanced manually.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import ClockDep, SettingsDep
from app.schemas.simulate import AdvanceClockRequest, ClockResponse

router = APIRouter(prefix="/simulate", tags=["simulation"])

DEV_ENVIRONMENTS = frozenset({"development", "dev", "local", "test", "demo"})

_PRODUCTION_BLOCKED = (
    "Clock simulation endpoints are not available in production. "
    "In production, time is real (UTC wall clock) and cannot be advanced manually."
)


def _require_dev(settings) -> None:
    env = (settings.environment or "").strip().lower()
    if env not in DEV_ENVIRONMENTS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_PRODUCTION_BLOCKED,
        )


@router.get(
    "/clock",
    response_model=ClockResponse,
    summary="Read current clock time",
)
def read_clock(clock: ClockDep, settings: SettingsDep) -> ClockResponse:
    """Returns real UTC time in production, virtual time in development."""
    return ClockResponse(virtual_clock_time=clock.now())


@router.post(
    "/advance-clock",
    response_model=ClockResponse,
    summary="[DEV ONLY] Advance simulation time",
)
def advance_clock(
    request: AdvanceClockRequest,
    clock: ClockDep,
    settings: SettingsDep,
) -> ClockResponse:
    """Advance the virtual clock. Blocked in production."""
    _require_dev(settings)

    previous = clock.now()
    current = clock.advance(minutes=request.minutes, hours=request.hours)

    return ClockResponse(
        virtual_clock_time=current,
        advanced_by_minutes=request.minutes + request.hours * 60,
        previous_virtual_clock_time=previous,
    )
