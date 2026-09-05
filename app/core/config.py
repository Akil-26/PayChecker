"""Production-grade application configuration.

All runtime configuration is loaded from environment variables / .env file.
No component reads os.environ directly — everything comes through Settings.

Monetary values are in MINOR CURRENCY UNITS (paise for INR) throughout.
"""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.enums import ActionType, FailureReason

# ---------------------------------------------------------------------------
# Default cost/probability tables
# ---------------------------------------------------------------------------

DEFAULT_INTERVENTION_COST_MINOR: dict[str, int] = {
    ActionType.RETRY_NOW.value:              500,
    ActionType.RETRY_LATER.value:          2_000,
    ActionType.SEND_PAYMENT_LINK.value:    3_000,
    ActionType.CHANGE_PAYMENT_METHOD.value: 3_000,
    ActionType.SEND_REMINDER.value:        1_000,
    ActionType.ESCALATE_HUMAN.value:      50_000,
    ActionType.STOP.value:                     0,
}

DEFAULT_FRICTION_PENALTY_MINOR: dict[str, int] = {
    ActionType.RETRY_NOW.value:              2_000,
    ActionType.RETRY_LATER.value:           10_000,
    ActionType.SEND_PAYMENT_LINK.value:     15_000,
    ActionType.CHANGE_PAYMENT_METHOD.value: 20_000,
    ActionType.SEND_REMINDER.value:          8_000,
    ActionType.ESCALATE_HUMAN.value:             0,
    ActionType.STOP.value:                       0,
}

DEFAULT_SIMULATOR_SUCCESS_PROBABILITY: dict[str, float] = {
    f"{FailureReason.BANK_TIMEOUT.value}:{ActionType.RETRY_NOW.value}":              0.35,
    f"{FailureReason.BANK_TIMEOUT.value}:{ActionType.SEND_PAYMENT_LINK.value}":      0.55,
    f"{FailureReason.NETWORK_ERROR.value}:{ActionType.RETRY_NOW.value}":             0.60,
    f"{FailureReason.NETWORK_ERROR.value}:{ActionType.RETRY_LATER.value}":           0.75,
    f"{FailureReason.INSUFFICIENT_FUNDS.value}:{ActionType.SEND_PAYMENT_LINK.value}": 0.40,
    f"{FailureReason.INSUFFICIENT_FUNDS.value}:{ActionType.SEND_REMINDER.value}":    0.35,
    f"{FailureReason.EXPIRED_CARD.value}:{ActionType.SEND_PAYMENT_LINK.value}":      0.58,
    f"{FailureReason.CHECKOUT_ABANDONMENT.value}:{ActionType.SEND_REMINDER.value}":  0.30,
    f"{FailureReason.CHECKOUT_ABANDONMENT.value}:{ActionType.SEND_PAYMENT_LINK.value}": 0.45,
    f"{FailureReason.SUBSCRIPTION_FAILURE.value}:{ActionType.RETRY_LATER.value}":    0.62,
    f"{FailureReason.SUBSCRIPTION_FAILURE.value}:{ActionType.SEND_REMINDER.value}":  0.35,
    f"{FailureReason.SUBSCRIPTION_FAILURE.value}:{ActionType.SEND_PAYMENT_LINK.value}": 0.48,
}

DEFAULT_SIMULATOR_FALLBACK_PROBABILITY = 0.30


class Settings(BaseSettings):
    """Runtime configuration — production and development."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application metadata ────────────────────────────────────────────
    app_name: str = "Paychecker API"
    app_description: str = (
        "Autonomous AI revenue recovery for merchants. "
        "Detects failed payments, diagnoses root causes, selects the optimal "
        "recovery action, and executes it — with a complete audit trail."
    )
    version: str = "1.0.0"
    environment: str = "development"
    api_prefix: str = "/api"
    log_level: str = "INFO"

    # ── Database ────────────────────────────────────────────────────────
    # SQLite for development; PostgreSQL for production.
    # Example production value:
    #   postgresql+psycopg2://user:pass@host:5432/paychecker
    database_url: str = "sqlite:///./paychecker.db"
    db_echo: bool = False
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30

    # ── Security ────────────────────────────────────────────────────────
    # API key for authenticating dashboard / internal service calls.
    # Generate with: python -c "import secrets; print(secrets.token_hex(32))"
    api_key_secret: str = ""

    # When True, the /docs and /redoc endpoints are disabled in production.
    # Set to False in development for interactive testing.
    disable_docs_in_production: bool = True

    # ── CORS ────────────────────────────────────────────────────────────
    backend_cors_origins: str = "http://localhost:8501"

    # ── Razorpay integration ─────────────────────────────────────────────
    # Leave blank to use the payment simulator (development/test mode).
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""

    # ── Multi-tenancy ───────────────────────────────────────────────────
    # Default merchant identifier used when no merchant context is supplied.
    default_merchant_id: str = "merch_default"
    default_currency: str = "INR"

    # ── Recovery policy ─────────────────────────────────────────────────
    max_automatic_retries: int = 2
    repeated_failure_limit: int = 3
    high_value_escalation_threshold: int = 5_000_000   # paise = INR 50,000
    allow_human_escalation: bool = True

    # ── Expected recovery value (minor units) ───────────────────────────
    intervention_cost_minor: dict[str, int] = Field(
        default_factory=lambda: dict(DEFAULT_INTERVENTION_COST_MINOR)
    )
    friction_penalty_minor: dict[str, int] = Field(
        default_factory=lambda: dict(DEFAULT_FRICTION_PENALTY_MINOR)
    )

    # ── Simulator (development / CI only) ───────────────────────────────
    simulator_success_probability: dict[str, float] = Field(
        default_factory=lambda: dict(DEFAULT_SIMULATOR_SUCCESS_PROBABILITY)
    )
    simulator_fallback_probability: float = DEFAULT_SIMULATOR_FALLBACK_PROBABILITY

    # ── Pluggable component implementations ─────────────────────────────
    # diagnosis_engine_impl: "rule_based"
    # recovery_predictor_impl: "deterministic"
    # action_executor_impl: "razorpay" | "simulator"
    diagnosis_engine_impl: str = "rule_based"
    recovery_predictor_impl: str = "deterministic"
    action_executor_impl: str = "simulator"   # overridden to "razorpay" in production

    # ── Development virtual clock ────────────────────────────────────────
    # Only used when ENVIRONMENT != production.
    simulation_seed: int = 20260101
    virtual_clock_start: datetime = datetime(2026, 1, 1, 13, 0, 0)
    virtual_clock_state_path: str = "./.paychecker_clock.json"
    retry_later_delay_minutes: int = 15

    # ── Validators ──────────────────────────────────────────────────────
    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def _production_safety_checks(self) -> "Settings":
        env = (self.environment or "").strip().lower()
        if env == "production":
            if not self.api_key_secret:
                raise ValueError(
                    "API_KEY_SECRET must be set in production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
                )
            if not self.razorpay_key_id or not self.razorpay_key_secret:
                # Warn but do not hard-block — allows running in production
                # with simulator if explicitly configured.
                import warnings
                warnings.warn(
                    "RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are not set. "
                    "Recovery actions will use the payment simulator.",
                    UserWarning,
                    stacklevel=2,
                )
        return self

    # ── Derived properties ───────────────────────────────────────────────
    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.backend_cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return (self.environment or "").strip().lower() == "production"

    @property
    def is_development(self) -> bool:
        return (self.environment or "").strip().lower() in {
            "development", "dev", "local", "test", "demo"
        }

    @property
    def razorpay_configured(self) -> bool:
        return bool(self.razorpay_key_id and self.razorpay_key_secret)

    @property
    def docs_url(self) -> str | None:
        if self.is_production and self.disable_docs_in_production:
            return None
        return "/docs"

    @property
    def redoc_url(self) -> str | None:
        if self.is_production and self.disable_docs_in_production:
            return None
        return "/redoc"

    @property
    def openapi_url(self) -> str | None:
        if self.is_production and self.disable_docs_in_production:
            return None
        return "/openapi.json"

    def intervention_cost(self, action: ActionType) -> int:
        return int(self.intervention_cost_minor.get(
            action.value, DEFAULT_INTERVENTION_COST_MINOR.get(action.value, 0)
        ))

    def friction_penalty(self, action: ActionType) -> int:
        return int(self.friction_penalty_minor.get(
            action.value, DEFAULT_FRICTION_PENALTY_MINOR.get(action.value, 0)
        ))

    def scenario_success_probability(self, reason: FailureReason, action: ActionType) -> float:
        key = f"{reason.value}:{action.value}"
        return float(self.simulator_success_probability.get(key, self.simulator_fallback_probability))


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
