"""Demo/seed endpoint — development and test environments only.

Blocked in production. Used for local development and Buildathon demos.
Drops and recreates all tables — never permitted in production.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import ClockDep, SessionDep, SettingsDep
from app.api.routes.command_center import scenario_reads
from app.core.errors import DemoResetForbidden
from app.core.logging import get_logger
from app.schemas.product import DemoResetRequest, DemoResetResponse
from app.services.scenario_generator import ScenarioGenerator

logger = get_logger("demo")

router = APIRouter(prefix="/demo", tags=["demo"])

DEV_ENVIRONMENTS = frozenset({"development", "dev", "local", "test", "demo"})


def _require_dev(settings) -> None:
    env = (settings.environment or "").strip().lower()
    if env not in DEV_ENVIRONMENTS:
        raise DemoResetForbidden(settings.environment, tuple(DEV_ENVIRONMENTS))


@router.post(
    "/reset",
    response_model=DemoResetResponse,
    summary="[DEV ONLY] Reset synthetic data and virtual clock",
)
def reset_demo(
    request: DemoResetRequest,
    session: SessionDep,
    clock: ClockDep,
    settings: SettingsDep,
) -> DemoResetResponse:
    """Restore the deterministic starting state. Blocked in production."""
    _require_dev(settings)

    from app.db.base import Base

    environment = (settings.environment or "").strip().lower()
    bind = session.get_bind()

    logger.warning(
        "demo reset | env=%s | db=%s",
        environment,
        bind.url if hasattr(bind, "url") else bind,
    )

    session.rollback()
    session.expunge_all()
    Base.metadata.drop_all(bind=bind)
    Base.metadata.create_all(bind=bind)

    clock.reset()

    generator = ScenarioGenerator(session=session, clock=clock, settings=settings)
    summary = generator.generate(background_customers=request.background_customers)
    session.commit()

    logger.info(
        "demo reset complete | customers=%s payments=%s cases=%s",
        summary.customers, summary.payments, summary.cases,
    )

    return DemoResetResponse(
        customers=summary.customers,
        payments=summary.payments,
        cases=summary.cases,
        scenarios=scenario_reads(session),
        virtual_clock_time=clock.now(),
        message=(
            f"Dataset reseeded from seed {settings.simulation_seed}. "
            f"Clock reset to {clock.now().isoformat()}."
        ),
    )
