"""Razorpay webhook endpoint.

Ingests real payment events from Razorpay and drives the recovery workflow.

Razorpay sends a POST to this endpoint for every payment event.
We verify the signature, parse the event, and either:
  - Open a new recovery case (on payment.failed / payment.captured with prior failure)
  - Mark a case as recovered (on payment.captured after a recovery attempt)
  - Record the event in the audit trail

Webhook URL to register in Razorpay Dashboard:
    https://your-domain.com/webhooks/razorpay

Events subscribed:
  - payment.failed
  - payment.captured
  - payment_link.paid
  - order.paid

Security: every request is verified with HMAC-SHA256 before processing.
"""

from __future__ import annotations

import hashlib
import hmac

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.api.deps import ClockDep, SessionDep, SettingsDep
from app.core.enums import FailureReason, PaymentStatus
from app.core.logging import get_logger
from app.models import Payment, RecoveryCase
from app.services.audit_service import AuditService
from app.services.payment_service import PaymentService
from app.services.risk_detector import RiskDetector

logger = get_logger("webhooks")

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Razorpay failure reason mapping
_RAZORPAY_ERROR_CODE_MAP: dict[str, FailureReason] = {
    "BAD_REQUEST_ERROR":   FailureReason.UNKNOWN,
    "GATEWAY_ERROR":       FailureReason.NETWORK_ERROR,
    "SERVER_ERROR":        FailureReason.BANK_TIMEOUT,
    "INSUFFICIENT_FUNDS":  FailureReason.INSUFFICIENT_FUNDS,
    "CARD_EXPIRED":        FailureReason.EXPIRED_CARD,
    "TIMEOUT":             FailureReason.BANK_TIMEOUT,
    "BANK_TIMEOUT":        FailureReason.BANK_TIMEOUT,
    "NETWORK_ERROR":       FailureReason.NETWORK_ERROR,
}


def _verify_signature(body: bytes, signature: str, secret: str) -> bool:
    """Verify Razorpay webhook HMAC-SHA256 signature."""
    expected = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _map_failure_reason(razorpay_event: dict) -> FailureReason:
    """Map a Razorpay payment event to our internal FailureReason."""
    error = razorpay_event.get("error", {}) or {}
    code  = (error.get("code") or "").upper()
    desc  = (error.get("description") or "").lower()

    if code in _RAZORPAY_ERROR_CODE_MAP:
        return _RAZORPAY_ERROR_CODE_MAP[code]

    # Fallback: scan description for known keywords
    if "insufficient" in desc or "balance" in desc:
        return FailureReason.INSUFFICIENT_FUNDS
    if "expired" in desc or "expir" in desc:
        return FailureReason.EXPIRED_CARD
    if "timeout" in desc or "time out" in desc:
        return FailureReason.BANK_TIMEOUT
    if "network" in desc or "connectivity" in desc:
        return FailureReason.NETWORK_ERROR

    return FailureReason.UNKNOWN


@router.post(
    "/razorpay",
    status_code=status.HTTP_200_OK,
    summary="Ingest Razorpay payment events",
    include_in_schema=False,  # Don't expose in public API docs
)
async def razorpay_webhook(
    request: Request,
    session: SessionDep,
    clock: ClockDep,
    settings: SettingsDep,
    x_razorpay_signature: str = Header(default="", alias="X-Razorpay-Signature"),
) -> dict:
    """Process an incoming Razorpay webhook event.

    1. Verify signature (reject if invalid)
    2. Parse event type and payload
    3. Upsert payment record
    4. Open or update recovery case
    5. Return 200 immediately (Razorpay retries on non-2xx)
    """
    body = await request.body()

    # ── Signature verification ───────────────────────────────────────────
    webhook_secret = settings.razorpay_webhook_secret
    if webhook_secret:
        if not x_razorpay_signature:
            logger.warning("webhook received without signature — rejected")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing X-Razorpay-Signature header.",
            )
        if not _verify_signature(body, x_razorpay_signature, webhook_secret):
            logger.warning("webhook signature mismatch — rejected")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature.",
            )
    else:
        # No secret configured — log a warning and allow in dev
        if settings.is_production:
            logger.error(
                "RAZORPAY_WEBHOOK_SECRET is not set in production — "
                "webhook signature cannot be verified. Configure it immediately."
            )
        else:
            logger.warning(
                "RAZORPAY_WEBHOOK_SECRET not set — skipping signature verification (dev mode)"
            )

    # ── Parse payload ────────────────────────────────────────────────────
    try:
        import json
        payload = json.loads(body)
    except Exception:
        logger.error("webhook: invalid JSON body")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON.")

    event_type = payload.get("event", "")
    entity     = payload.get("payload", {})

    logger.info("razorpay webhook | event=%s", event_type)

    audit  = AuditService(session=session, clock=clock)
    svc    = PaymentService(session=session, clock=clock)
    detector = RiskDetector(session=session, clock=clock, audit=audit)

    # ── payment.failed ───────────────────────────────────────────────────
    if event_type == "payment.failed":
        razorpay_payment = entity.get("payment", {}).get("entity", {})
        _handle_payment_failed(
            razorpay_payment=razorpay_payment,
            session=session,
            clock=clock,
            settings=settings,
            svc=svc,
            detector=detector,
        )

    # ── payment.captured ─────────────────────────────────────────────────
    elif event_type == "payment.captured":
        razorpay_payment = entity.get("payment", {}).get("entity", {})
        _handle_payment_captured(
            razorpay_payment=razorpay_payment,
            session=session,
            clock=clock,
            settings=settings,
            svc=svc,
        )

    # ── payment_link.paid ────────────────────────────────────────────────
    elif event_type == "payment_link.paid":
        link_entity    = entity.get("payment_link", {}).get("entity", {})
        payment_entity = entity.get("payment", {}).get("entity", {})
        reference_id   = link_entity.get("reference_id", "")
        if reference_id:
            # reference_id was set to our payment_id when creating the link
            _handle_payment_captured(
                razorpay_payment={**payment_entity, "notes": {"original_payment_id": reference_id}},
                session=session,
                clock=clock,
                settings=settings,
                svc=svc,
            )

    # ── order.paid ───────────────────────────────────────────────────────
    elif event_type == "order.paid":
        razorpay_payment = entity.get("payment", {}).get("entity", {})
        _handle_payment_captured(
            razorpay_payment=razorpay_payment,
            session=session,
            clock=clock,
            settings=settings,
            svc=svc,
        )

    else:
        logger.debug("webhook: unhandled event type '%s' — ignored", event_type)

    session.commit()
    return {"status": "ok", "event": event_type}


def _handle_payment_failed(
    *,
    razorpay_payment: dict,
    session,
    clock,
    settings,
    svc: PaymentService,
    detector: RiskDetector,
) -> None:
    """Upsert a failed payment and open a recovery case."""
    rz_id       = razorpay_payment.get("id", "")
    amount      = int(razorpay_payment.get("amount", 0))
    currency    = razorpay_payment.get("currency", settings.default_currency)
    customer_id = razorpay_payment.get("customer_id") or razorpay_payment.get("contact", "")
    method_raw  = (razorpay_payment.get("method") or "").upper()
    notes       = razorpay_payment.get("notes", {}) or {}

    from app.core.enums import PaymentMethod
    method_map = {
        "UPI":        PaymentMethod.UPI,
        "CARD":       PaymentMethod.CARD,
        "NETBANKING": PaymentMethod.NETBANKING,
        "WALLET":     PaymentMethod.WALLET,
        "EMI":        PaymentMethod.EMI,
    }
    method = method_map.get(method_raw, PaymentMethod.CARD)

    failure_reason = _map_failure_reason(razorpay_payment)

    # payment_id in our system = Razorpay payment ID
    payment = session.get(Payment, rz_id)

    if payment is None:
        payment = svc.create_payment(
            payment_id=rz_id,
            amount=amount,
            currency=currency,
            payment_method=method,
            status=PaymentStatus.FAILED,
            failure_reason=failure_reason,
            customer_id=customer_id or None,
            merchant_id=notes.get("merchant_id", settings.default_merchant_id),
            metadata={"source": "razorpay_webhook", "razorpay_id": rz_id},
        )
    else:
        # Existing payment — record additional failure attempt
        svc.fail_payment(rz_id, failure_reason)
        payment = session.get(Payment, rz_id)

    detector.detect_and_open_case(payment)
    logger.info(
        "webhook: payment failed | razorpay_id=%s | reason=%s | amount=%s %s",
        rz_id, failure_reason.value, amount, currency,
    )


def _handle_payment_captured(
    *,
    razorpay_payment: dict,
    session,
    clock,
    settings,
    svc: PaymentService,
) -> None:
    """Mark a payment as succeeded and close any open recovery case."""
    rz_id  = razorpay_payment.get("id", "")
    notes  = razorpay_payment.get("notes", {}) or {}

    # The original payment this recovery applies to may be referenced in notes
    original_id = notes.get("original_payment_id") or notes.get("original_payment") or rz_id
    payment = session.get(Payment, original_id)

    if payment is None:
        logger.warning("webhook: captured payment not found | id=%s", original_id)
        return

    # Mark as succeeded
    from app.core.enums import ActionType
    svc.record_recovery_attempt(
        payment=payment,
        status=PaymentStatus.SUCCEEDED,
        action=ActionType.RETRY_NOW,
        provider_response={"razorpay_payment_id": rz_id, "event": "payment.captured"},
    )

    # Find and close open recovery case
    from sqlalchemy import select
    from app.core.enums import CaseState
    stmt = (
        select(RecoveryCase)
        .where(RecoveryCase.payment_id == original_id)
        .where(RecoveryCase.state.not_in(tuple(CaseState.terminal())))
    )
    case = session.execute(stmt).scalars().first()
    if case:
        case.state = CaseState.RECOVERED
        case.updated_at = clock.now()
        session.flush()
        logger.info(
            "webhook: case recovered | case=%s | payment=%s", case.case_id, original_id
        )

    logger.info("webhook: payment captured | razorpay_id=%s | original=%s", rz_id, original_id)
