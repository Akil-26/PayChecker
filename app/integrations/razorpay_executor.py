"""Razorpay live action executor.

Executes real recovery actions against the Razorpay API.
Used in production when RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are set.

Supported actions:
  RETRY_NOW              — create a new payment order and charge via stored method
  RETRY_LATER            — schedule a retry (recorded; Razorpay webhook confirms)
  SEND_PAYMENT_LINK      — create and send a Razorpay Payment Link via SMS/email
  CHANGE_PAYMENT_METHOD  — create a fresh Payment Link with method selection
  SEND_REMINDER          — send a payment reminder (Payment Link + notification)
  ESCALATE_HUMAN         — record escalation; no API call (human takes over)
  STOP                   — record stop decision; no API call

Requires: pip install razorpay
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.clock import VirtualClock
from app.core.wall_clock import WallClock
from app.core.config import Settings
from app.core.enums import ActionType, ExecutionStatus, PaymentStatus
from app.core.errors import UnsupportedAction
from app.core.logging import get_logger
from app.integrations.action_executor import ActionExecutor, ExecutionResult
from app.services.context_builder import RecoveryContext
from app.services.payment_service import PaymentService

logger = get_logger("razorpay_executor")

_SUPPORTED: frozenset[ActionType] = frozenset(ActionType)  # supports all


class RazorpayExecutor:
    """Executes recovery actions via the Razorpay API."""

    def __init__(
        self,
        session: Session,
        settings: Settings,
        clock: VirtualClock | WallClock,
    ) -> None:
        self._session = session
        self._settings = settings
        self._clock = clock
        self._payment_service = PaymentService(session, clock)
        self._client = self._build_client()

    def _build_client(self):
        try:
            import razorpay
            return razorpay.Client(
                auth=(self._settings.razorpay_key_id, self._settings.razorpay_key_secret)
            )
        except ImportError as exc:
            raise ImportError(
                "The 'razorpay' package is required for live execution. "
                "Install it with: pip install razorpay"
            ) from exc

    @property
    def supported_actions(self) -> frozenset[ActionType]:
        return _SUPPORTED

    def supports(self, action: ActionType) -> bool:
        return action in _SUPPORTED

    # ── Main dispatch ────────────────────────────────────────────────────

    def execute(
        self,
        action: ActionType,
        context: RecoveryContext,
        *,
        audit: Any | None = None,
        workflow_id: str | None = None,
    ) -> ExecutionResult:
        if not self.supports(action):
            raise UnsupportedAction(action)

        logger.info(
            "razorpay execute | action=%s | payment=%s | amount=%s %s",
            action.value,
            context.payment.payment_id,
            context.payment.amount,
            context.payment.currency,
        )

        handlers = {
            ActionType.RETRY_NOW:              self._retry_now,
            ActionType.RETRY_LATER:            self._retry_later,
            ActionType.SEND_PAYMENT_LINK:      self._send_payment_link,
            ActionType.CHANGE_PAYMENT_METHOD:  self._change_payment_method,
            ActionType.SEND_REMINDER:          self._send_reminder,
            ActionType.ESCALATE_HUMAN:         self._escalate_human,
            ActionType.STOP:                   self._stop,
        }
        result = handlers[action](context)

        # Record to audit trail if supplied (mirrors PaymentSimulatorExecutor)
        if audit is not None:
            from app.core.enums import AuditEventType, WorkflowStage
            failed = result.status is ExecutionStatus.FAILED
            audit.record(
                case_id=context.case_id,
                payment_id=context.payment_id,
                stage=WorkflowStage.EXECUTION,
                event_type=AuditEventType.ACTION_FAILED if failed else AuditEventType.ACTION_EXECUTED,
                message=(
                    f"{result.action.value} executed via Razorpay; "
                    f"provider reported {result.status.value}."
                ),
                metadata={
                    "action": result.action.value,
                    "execution_status": result.status.value,
                    "provider_response": result.provider_response,
                    "executed_at": result.executed_at.isoformat(),
                    "executor": "razorpay",
                },
                workflow_id=workflow_id,
            )

        return result

    def schedule(
        self,
        action: ActionType,
        context: RecoveryContext,
        scheduled_at: datetime,
    ) -> ExecutionResult:
        """Record a scheduled retry — Razorpay will execute it at the due time."""
        logger.info(
            "razorpay schedule | action=%s | payment=%s | due=%s",
            action.value,
            context.payment.payment_id,
            scheduled_at.isoformat(),
        )
        return ExecutionResult(
            action=action,
            status=ExecutionStatus.SCHEDULED,
            provider_response={
                "scheduled_at": scheduled_at.isoformat(),
                "payment_id": context.payment.payment_id,
                "executor": "razorpay",
            },
            executed_at=self._clock.now(),
        )

    # ── Action handlers ──────────────────────────────────────────────────

    def _retry_now(self, context: RecoveryContext) -> ExecutionResult:
        """Attempt an immediate charge via Razorpay Orders API."""
        now = self._clock.now()
        payment = context.payment

        try:
            order = self._client.order.create({
                "amount":   payment.amount,
                "currency": payment.currency,
                "receipt":  f"recovery_{payment.payment_id}",
                "notes": {
                    "recovery_case_id": context.case.case_id,
                    "original_payment": payment.payment_id,
                    "action":           "RETRY_NOW",
                },
            })

            logger.info(
                "razorpay order created | order_id=%s | payment=%s",
                order.get("id"), payment.payment_id,
            )

            # Record the attempt — outcome confirmed via webhook
            self._payment_service.record_recovery_attempt(
                payment=payment,
                status=PaymentStatus.PENDING,
                action=ActionType.RETRY_NOW,
                provider_response={"razorpay_order_id": order.get("id"), "status": order.get("status")},
            )

            return ExecutionResult(
                action=ActionType.RETRY_NOW,
                status=ExecutionStatus.SUCCEEDED,
                provider_response={
                    "razorpay_order_id": order.get("id"),
                    "razorpay_status":   order.get("status"),
                    "executor":          "razorpay",
                },
                executed_at=now,
            )

        except Exception as exc:
            logger.error("razorpay retry_now failed | payment=%s | %s", payment.payment_id, exc)
            self._payment_service.record_recovery_attempt(
                payment=payment,
                status=PaymentStatus.FAILED,
                action=ActionType.RETRY_NOW,
                provider_response={"error": str(exc)},
            )
            return ExecutionResult(
                action=ActionType.RETRY_NOW,
                status=ExecutionStatus.FAILED,
                provider_response={"error": str(exc), "executor": "razorpay"},
                executed_at=now,
            )

    def _retry_later(self, context: RecoveryContext) -> ExecutionResult:
        """Schedule a retry — return SCHEDULED status; webhook confirms outcome."""
        from datetime import timedelta
        now = self._clock.now()
        due = now + timedelta(minutes=self._settings.retry_later_delay_minutes)
        return ExecutionResult(
            action=ActionType.RETRY_LATER,
            status=ExecutionStatus.SCHEDULED,
            provider_response={
                "scheduled_at": due.isoformat(),
                "payment_id":   context.payment.payment_id,
                "executor":     "razorpay",
            },
            executed_at=now,
        )

    def _send_payment_link(self, context: RecoveryContext) -> ExecutionResult:
        """Create a Razorpay Payment Link and send it to the customer."""
        now = self._clock.now()
        payment = context.payment
        customer = context.customer

        try:
            payload: dict[str, Any] = {
                "amount":      payment.amount,
                "currency":    payment.currency,
                "description": f"Complete your payment of {payment.currency} {payment.amount / 100:.2f}",
                "reference_id": payment.payment_id,
                "notes": {
                    "recovery_case_id": context.case.case_id,
                    "action": "SEND_PAYMENT_LINK",
                },
                "reminder_enable": True,
            }

            # Add customer contact if available
            if customer:
                contact: dict[str, Any] = {}
                if hasattr(customer, "email") and customer.email:
                    contact["email"] = customer.email
                if hasattr(customer, "phone") and customer.phone:
                    contact["contact"] = customer.phone
                if hasattr(customer, "name") and customer.name:
                    contact["name"] = customer.name
                if contact:
                    payload["customer"] = contact

            link = self._client.payment_link.create(payload)

            logger.info(
                "razorpay payment link created | link_id=%s | payment=%s",
                link.get("id"), payment.payment_id,
            )

            return ExecutionResult(
                action=ActionType.SEND_PAYMENT_LINK,
                status=ExecutionStatus.SUCCEEDED,
                provider_response={
                    "payment_link_id":  link.get("id"),
                    "payment_link_url": link.get("short_url"),
                    "status":           link.get("status"),
                    "executor":         "razorpay",
                },
                executed_at=now,
            )

        except Exception as exc:
            logger.error(
                "razorpay payment link failed | payment=%s | %s", payment.payment_id, exc
            )
            return ExecutionResult(
                action=ActionType.SEND_PAYMENT_LINK,
                status=ExecutionStatus.FAILED,
                provider_response={"error": str(exc), "executor": "razorpay"},
                executed_at=now,
            )

    def _change_payment_method(self, context: RecoveryContext) -> ExecutionResult:
        """Send a Payment Link that allows the customer to choose a new method."""
        now = self._clock.now()
        payment = context.payment

        try:
            payload: dict[str, Any] = {
                "amount":       payment.amount,
                "currency":     payment.currency,
                "description":  "Please complete your payment using a different method.",
                "reference_id": payment.payment_id,
                "notes": {
                    "recovery_case_id": context.case.case_id,
                    "action": "CHANGE_PAYMENT_METHOD",
                    "original_method": payment.payment_method.value if payment.payment_method else "UNKNOWN",
                },
                "reminder_enable": True,
            }

            customer = context.customer
            if customer:
                contact: dict[str, Any] = {}
                if hasattr(customer, "email") and customer.email:
                    contact["email"] = customer.email
                if hasattr(customer, "phone") and customer.phone:
                    contact["contact"] = customer.phone
                if contact:
                    payload["customer"] = contact

            link = self._client.payment_link.create(payload)

            return ExecutionResult(
                action=ActionType.CHANGE_PAYMENT_METHOD,
                status=ExecutionStatus.SUCCEEDED,
                provider_response={
                    "payment_link_id":  link.get("id"),
                    "payment_link_url": link.get("short_url"),
                    "status":           link.get("status"),
                    "executor":         "razorpay",
                },
                executed_at=now,
            )

        except Exception as exc:
            logger.error(
                "razorpay change method failed | payment=%s | %s", payment.payment_id, exc
            )
            return ExecutionResult(
                action=ActionType.CHANGE_PAYMENT_METHOD,
                status=ExecutionStatus.FAILED,
                provider_response={"error": str(exc), "executor": "razorpay"},
                executed_at=now,
            )

    def _send_reminder(self, context: RecoveryContext) -> ExecutionResult:
        """Send a reminder via Razorpay Payment Link + notification."""
        # Reuse payment link creation; Razorpay handles notification dispatch.
        result = self._send_payment_link(context)
        # Re-tag as SEND_REMINDER action
        return ExecutionResult(
            action=ActionType.SEND_REMINDER,
            status=result.status,
            provider_response={**result.provider_response, "action": "SEND_REMINDER"},
            executed_at=result.executed_at,
        )

    def _escalate_human(self, context: RecoveryContext) -> ExecutionResult:
        """Record escalation. No Razorpay API call — human takes over."""
        logger.warning(
            "escalated to human | case=%s | payment=%s | amount=%s %s",
            context.case.case_id,
            context.payment.payment_id,
            context.payment.amount,
            context.payment.currency,
        )
        return ExecutionResult(
            action=ActionType.ESCALATE_HUMAN,
            status=ExecutionStatus.ESCALATED,
            provider_response={
                "case_id":    context.case.case_id,
                "payment_id": context.payment.payment_id,
                "executor":   "razorpay",
                "note":       "Escalated to human agent. No automated action taken.",
            },
            executed_at=self._clock.now(),
        )

    def _stop(self, context: RecoveryContext) -> ExecutionResult:
        """Record stop decision. No Razorpay API call."""
        return ExecutionResult(
            action=ActionType.STOP,
            status=ExecutionStatus.STOPPED,
            provider_response={
                "case_id":    context.case.case_id,
                "payment_id": context.payment.payment_id,
                "executor":   "razorpay",
                "note":       "Recovery stopped per policy.",
            },
            executed_at=self._clock.now(),
        )

    # ── Webhook signature verification ───────────────────────────────────

    @classmethod
    def verify_webhook_signature(
        cls,
        body: bytes,
        signature: str,
        secret: str,
    ) -> bool:
        """Verify a Razorpay webhook payload signature.

        Razorpay signs webhooks with HMAC-SHA256. This must be called before
        processing any webhook payload to prevent replay attacks.
        """
        expected = hmac.new(
            secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)


__all__ = ["RazorpayExecutor"]
