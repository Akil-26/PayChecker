"""API key authentication logic — framework-free.

Domain/core modules must not depend on FastAPI (Requirement 27.8), so this module
holds only the pure decision of whether a request's API key is acceptable. The
FastAPI wiring (the ``Security``/``HTTPException`` dependency actually used by
routes) lives in ``app.api.deps``, which is free to import FastAPI.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings


@dataclass(frozen=True)
class AuthDecision:
    """The result of checking an API key against settings.

    ``status`` is one of:
      - "ok"              — request is authenticated (or auth is bypassed in dev)
      - "unauthorized"     — key missing or does not match
      - "misconfigured"    — production with no API_KEY_SECRET set; fail closed
    """

    status: str
    key: str | None = None

    @property
    def allowed(self) -> bool:
        return self.status == "ok"


def check_api_key(settings: Settings, api_key: str | None) -> AuthDecision:
    """Decide whether ``api_key`` is acceptable under ``settings``.

    - Development/demo/test: any key (or no key) is accepted.
    - Production with no API_KEY_SECRET configured: fail closed ("misconfigured").
    - Production otherwise: the key must match API_KEY_SECRET exactly.
    """
    if not settings.is_production:
        return AuthDecision(status="ok", key=api_key or "dev-mode")

    if not settings.api_key_secret:
        return AuthDecision(status="misconfigured", key=api_key)

    if not api_key or api_key != settings.api_key_secret:
        return AuthDecision(status="unauthorized", key=api_key)

    return AuthDecision(status="ok", key=api_key)


__all__ = ["AuthDecision", "check_api_key"]
