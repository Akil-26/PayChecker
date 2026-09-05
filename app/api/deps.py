"""FastAPI dependencies.

Route handlers receive fully constructed collaborators from here, which keeps the
handlers themselves limited to validation, delegation, and serialization
(Requirement 1.9).
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Query, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from app.core.auth import check_api_key
from app.core.clock import VirtualClock
from app.core.config import Settings, get_settings
from app.core.container import get_clock
from app.core.logging import get_logger
from app.db.session import get_session

logger = get_logger("auth")


def settings_dep() -> Settings:
    return get_settings()


_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(
    settings: Annotated[Settings, Depends(settings_dep)],
    api_key: Annotated[str | None, Security(_API_KEY_HEADER)] = None,
) -> str:
    """FastAPI dependency validating the X-API-Key header.

    Delegates the actual decision to ``app.core.auth.check_api_key`` so that logic
    stays framework-free and independently testable; this function only translates
    the decision into HTTP responses.
    """
    decision = check_api_key(settings, api_key)

    if decision.status == "misconfigured":
        logger.error("API_KEY_SECRET is not set in production; rejecting all requests.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is not configured correctly. Contact the administrator.",
        )

    if decision.status == "unauthorized":
        logger.warning("Rejected request with invalid or missing API key.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Include X-API-Key in your request headers.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return decision.key or "dev-mode"


# FastAPI dependency alias — add to any route to require authentication.
AuthDep = Annotated[str, Depends(verify_api_key)]


def clock_dep(settings: Annotated[Settings, Depends(settings_dep)]) -> VirtualClock:
    return get_clock(settings)


SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(settings_dep)]
ClockDep = Annotated[VirtualClock, Depends(clock_dep)]


class Pagination:
    """Shared list pagination parameters."""

    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=200, description="Maximum records to return.")] = 50,
        offset: Annotated[int, Query(ge=0, description="Records to skip.")] = 0,
    ) -> None:
        self.limit = limit
        self.offset = offset


PaginationDep = Annotated[Pagination, Depends(Pagination)]
