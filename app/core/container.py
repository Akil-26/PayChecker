"""Component resolution — production and development.

Swappable components are resolved from configuration here.
Adding a new implementation only requires registering it in the registry dict
and setting the corresponding env var — no other code changes.

Production resolver order for action_executor:
  1. If RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are set → RazorpayExecutor
  2. Otherwise → PaymentSimulatorExecutor (with a warning)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import Settings, get_settings

if TYPE_CHECKING:
    from app.core.clock import VirtualClock
    from app.integrations.action_executor import ActionExecutor
    from app.ml.predictor import RecoveryPredictor
    from app.services.diagnosis_engine import DiagnosisEngine


class UnknownImplementation(RuntimeError):
    def __init__(self, kind: str, name: str, available: tuple[str, ...]) -> None:
        super().__init__(
            f"Unknown {kind} implementation '{name}'. Available: {', '.join(available)}."
        )


def get_clock(settings: Settings | None = None) -> "VirtualClock":
    """Return the appropriate clock for the current environment."""
    from app.core.clock import VirtualClock, build_clock
    from app.core.wall_clock import WallClock

    if settings is None:
        return build_clock()

    env = (settings.environment or "production").strip().lower()
    if env == "production":
        return WallClock()

    return VirtualClock(
        state_path=settings.virtual_clock_state_path,
        start=settings.virtual_clock_start,
    )


def get_diagnosis_engine(settings: Settings | None = None) -> "DiagnosisEngine":
    from app.services.diagnosis_engine import RuleBasedDiagnosisEngine

    resolved = settings or get_settings()
    registry = {"rule_based": RuleBasedDiagnosisEngine}

    try:
        return registry[resolved.diagnosis_engine_impl]()
    except KeyError:
        raise UnknownImplementation(
            "diagnosis engine", resolved.diagnosis_engine_impl, tuple(registry)
        ) from None


def get_recovery_predictor(settings: Settings | None = None) -> "RecoveryPredictor":
    from app.ml.deterministic_scorer import DeterministicRecoveryScorer

    resolved = settings or get_settings()
    registry = {"deterministic": DeterministicRecoveryScorer}

    try:
        return registry[resolved.recovery_predictor_impl]()
    except KeyError:
        raise UnknownImplementation(
            "recovery predictor", resolved.recovery_predictor_impl, tuple(registry)
        ) from None


def get_action_executor(
    session,
    settings: Settings | None = None,
    clock=None,
) -> "ActionExecutor":
    """Resolve the action executor.

    Production with Razorpay credentials → RazorpayExecutor.
    Otherwise → PaymentSimulatorExecutor.
    """
    from app.core.logging import get_logger
    logger = get_logger("container")

    resolved = settings or get_settings()
    resolved_clock = clock or get_clock(resolved)

    # Auto-select Razorpay if credentials are present,
    # regardless of what action_executor_impl says.
    if resolved.razorpay_configured:
        try:
            from app.integrations.razorpay_executor import RazorpayExecutor
            executor = RazorpayExecutor(
                session=session,
                settings=resolved,
                clock=resolved_clock,
            )
            logger.info("action executor: RazorpayExecutor (live)")
            return executor
        except ImportError as exc:
            logger.warning(
                "razorpay package not installed or failed to import (%s); "
                "falling back to simulator. Run: pip install razorpay",
                exc,
            )
        except Exception as exc:
            logger.exception(
                "RazorpayExecutor failed to initialize (%s: %s); falling back to simulator.",
                type(exc).__name__,
                exc,
            )

    if resolved.action_executor_impl == "razorpay" and not resolved.razorpay_configured:
        logger.warning(
            "action_executor_impl=razorpay but RAZORPAY credentials are missing; "
            "falling back to simulator."
        )

    from app.integrations.payment_simulator import PaymentSimulatorExecutor
    logger.info("action executor: PaymentSimulatorExecutor (simulation)")
    return PaymentSimulatorExecutor(
        session=session,
        settings=resolved,
        clock=resolved_clock,
    )
