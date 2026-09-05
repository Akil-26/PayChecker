"""Health endpoint — production grade.

Reports service status with a live database ping.
Served outside API_PREFIX so load balancers and k8s probes never need the mount path.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import ClockDep, SettingsDep
from app.db.session import ping_db
from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service liveness and dependency health",
)
def health(settings: SettingsDep, clock: ClockDep) -> HealthResponse:
    db_ok = ping_db()
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        app_name=settings.app_name,
        version=settings.version,
        environment=settings.environment,
        virtual_clock_time=clock.now(),
        db_status="ok" if db_ok else "unreachable",
    )
