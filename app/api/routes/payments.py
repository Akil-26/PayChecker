"""Payment endpoints — production grade.

Real payment ingestion:
  POST /payments/ingest        — ingest a real payment from your platform
  POST /payments/{id}/fail     — record a payment failure + open recovery case
  GET  /payments               — list payments (paginated, filterable)
  GET  /payments/{id}          — payment detail with attempt history

Development-only (gated by ENVIRONMENT):
  POST /payments/simulate      — create a synthetic payment for testing
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import ClockDep, PaginationDep, SessionDep, SettingsDep
from app.core.enums import FailureReason, PaymentMethod, PaymentStatus
from app.schemas.common import Money, Page
from app.schemas.payment import (
    FailPaymentRequest,
    FailPaymentResponse,
    PaymentDetail,
    PaymentRead,
    SimulatePaymentRequest,
)
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["payments"])

DEV_ENVIRONMENTS = frozenset({"development", "dev", "local", "test", "demo"})


# ── Request schemas ──────────────────────────────────────────────────────────

class IngestPaymentRequest(BaseModel):
    """Ingest a real payment event from your platform or Razorpay."""

    payment_id: str = Field(
        description="Your platform or Razorpay payment ID.",
        examples=["pay_RazorpayPaymentId"],
    )
    amount: int = Field(
        gt=0,
        description="Amount in minor units (paise for INR).",
        examples=[100000],
    )
    currency: str = Field(default="INR", examples=["INR"])
    payment_method: PaymentMethod = Field(default=PaymentMethod.CARD)
    status: PaymentStatus = Field(default=PaymentStatus.FAILED)
    failure_reason: FailureReason | None = Field(
        default=None,
        description="Required when status is FAILED or ABANDONED.",
    )
    customer_id: str | None = Field(
        default=None,
        description="Your internal customer identifier.",
    )
    merchant_id: str | None = Field(
        default=None,
        description="Merchant identifier. Defaults to DEFAULT_MERCHANT_ID.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary key-value data from your platform.",
    )
    open_recovery_case: bool = Field(
        default=True,
        description="Automatically open a recovery case if the payment is at risk.",
    )


class IngestPaymentResponse(BaseModel):
    """Result of ingesting a real payment."""

    payment: PaymentRead
    case_id: str | None = None
    case_state: str | None = None
    amount_at_risk: Money | None = None
    recovery_case_opened: bool = False
    message: str = ""


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post(
    "/ingest",
    response_model=IngestPaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a real payment and optionally open a recovery case",
)
def ingest_payment(
    request: IngestPaymentRequest,
    session: SessionDep,
    clock: ClockDep,
    settings: SettingsDep,
) -> IngestPaymentResponse:
    """Primary production endpoint for bringing payments into Paychecker.

    Call this from your platform whenever a payment fails or is abandoned.
    Paychecker will:
      1. Record the payment and its failure details
      2. Assess revenue risk
      3. Open a recovery case if warranted (unless open_recovery_case=false)

    This is idempotent for the same payment_id — calling it twice for the
    same failed payment reuses the existing recovery case.
    """
    from app.services.audit_service import AuditService
    from app.services.risk_detector import RiskDetector

    svc = PaymentService(session, clock)

    # Validate: failed/abandoned payments must have a failure reason
    if request.status in (PaymentStatus.FAILED, PaymentStatus.ABANDONED):
        if request.failure_reason is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="failure_reason is required when status is FAILED or ABANDONED.",
            )

    payment = svc.create_payment(
        payment_id=request.payment_id,
        amount=request.amount,
        currency=request.currency,
        payment_method=request.payment_method,
        status=request.status,
        failure_reason=request.failure_reason,
        customer_id=request.customer_id,
        merchant_id=request.merchant_id or settings.default_merchant_id,
        metadata={**request.metadata, "source": "api_ingest"},
    )

    case = None
    if request.open_recovery_case:
        audit = AuditService(session=session, clock=clock)
        detector = RiskDetector(session=session, clock=clock, audit=audit)
        case = detector.detect_and_open_case(payment)
        session.commit()

    return IngestPaymentResponse(
        payment=PaymentRead.from_model(payment),
        case_id=case.case_id if case else None,
        case_state=case.state.value if case else None,
        amount_at_risk=Money.of(case.amount_at_risk, payment.currency) if case else None,
        recovery_case_opened=case is not None,
        message=(
            f"Payment ingested. Recovery case {case.case_id} opened."
            if case else
            "Payment ingested. No recovery case opened (payment is not at risk or case already exists)."
        ),
    )


@router.get(
    "",
    response_model=Page[PaymentRead],
    summary="List payments",
)
def list_payments(
    session: SessionDep,
    clock: ClockDep,
    pagination: PaginationDep,
    payment_status: Annotated[
        PaymentStatus | None,
        Query(alias="status", description="Filter by payment status."),
    ] = None,
) -> Page[PaymentRead]:
    page = PaymentService(session, clock).list_payments(
        limit=pagination.limit,
        offset=pagination.offset,
        status=payment_status,
    )
    return Page[PaymentRead](
        items=[PaymentRead.from_model(item) for item in page.items],
        total=page.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get(
    "/{payment_id}",
    response_model=PaymentDetail,
    summary="Get one payment with its attempt history",
)
def get_payment(payment_id: str, session: SessionDep, clock: ClockDep) -> PaymentDetail:
    payment = PaymentService(session, clock).get_payment_with_attempts(payment_id)
    return PaymentDetail.from_model(payment)


@router.post(
    "/{payment_id}/fail",
    response_model=FailPaymentResponse,
    summary="Record a payment failure and open a recovery case",
)
def fail_payment(
    payment_id: str,
    request: FailPaymentRequest,
    session: SessionDep,
    clock: ClockDep,
) -> FailPaymentResponse:
    """Record an additional failure on an existing payment and open or reuse a recovery case.

    Use this when a payment that was previously PENDING or CREATED has now failed.
    For ingesting new failed payments, use POST /payments/ingest.
    """
    from app.schemas.common import Money
    from app.services.audit_service import AuditService
    from app.services.risk_detector import RiskDetector

    service = PaymentService(session, clock)
    payment = service.fail_payment(payment_id, request.failure_reason)

    detector = RiskDetector(
        session=session,
        clock=clock,
        audit=AuditService(session=session, clock=clock),
    )
    case = detector.detect_and_open_case(payment)
    session.commit()

    return FailPaymentResponse(
        payment=PaymentRead.from_model(payment),
        case_id=case.case_id if case else None,
        case_state=case.state.value if case else None,
        amount_at_risk=Money.of(case.amount_at_risk, payment.currency) if case else None,
    )


@router.post(
    "/simulate",
    response_model=PaymentRead,
    status_code=status.HTTP_201_CREATED,
    summary="[DEV ONLY] Create a synthetic payment for testing",
)
def simulate_payment(
    request: SimulatePaymentRequest,
    session: SessionDep,
    clock: ClockDep,
    settings: SettingsDep,
) -> PaymentRead:
    """Create a synthetic payment. Only available in non-production environments."""
    env = (settings.environment or "").strip().lower()
    if env not in DEV_ENVIRONMENTS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"POST /payments/simulate is not available in '{settings.environment}' environment. "
                "Use POST /payments/ingest to bring real payments into Paychecker."
            ),
        )

    payment = PaymentService(session, clock).create_payment(
        amount=request.amount,
        currency=request.currency,
        payment_method=request.payment_method,
        status=request.status,
        failure_reason=request.failure_reason,
        customer_id=request.customer_id,
        merchant_id=request.merchant_id,
        metadata=request.metadata,
    )
    return PaymentRead.from_model(payment)
