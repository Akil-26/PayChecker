"""Route aggregation — production grade.

GET /health is mounted at root (no prefix) for probes.
Webhooks are mounted at root (/webhooks/razorpay).
Everything else sits under API_PREFIX.

Demo and simulate routes are included always but gated inside their
own handlers — they refuse to run outside dev/demo environments.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    analytics,
    command_center,
    demo,
    health,
    payments,
    recovery,
    simulate,
    webhooks,
)

# Mounted at the application root (no prefix)
root_router = APIRouter()
root_router.include_router(health.router)
root_router.include_router(webhooks.router)

# Mounted under the configured API prefix
api_router = APIRouter()
api_router.include_router(command_center.router)   # /recovery/overview etc.
api_router.include_router(payments.router)
api_router.include_router(recovery.router)
api_router.include_router(simulate.router)
api_router.include_router(analytics.router)
api_router.include_router(demo.router)
