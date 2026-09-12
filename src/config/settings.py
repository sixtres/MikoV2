# YAMA Y-269: _ms whitelist extended to 35 fields - minutes suffix forbidden, only _ms int allowed, FATAL on violation
# YAMA Y-353: Global mutable state forbidden - no module-level mutable Settings instance, DI via Dependencies
# YAMA Y-260: emergency_slippage_pct = min(3%, 10%/lev) leverage adjusted
# YAMA FATAL-CHECKS: DNS not IP, TZ=UTC, API trade only, position_mode ONE_WAY|HEDGE required, margin_mode ISOLATED, target_leverage 5, environment TEST|PROD required

"""
Settings module.

Loads and validates all runtime configuration.
All time values are *_ms and validated against whitelist (Y-269).
Minutes suffix is forbidden - FATAL (Y-269).
Environment TEST|PROD determines risk properties.
All FATAL conditions raise RuntimeError with FATAL prefix.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, FrozenSet, Tuple

# Whitelisted _ms fields - only these allowed (Y-269) - 35 entries
_MS_WHITELIST: Final[FrozenSet[str]] = frozenset(
    {
        "ws_ping_interval_ms",
        "ws_pong_timeout_ms",
        "ws_reconnect_jitter_ms",
        "rest_acquire_timeout_ms",
        "rest_outer_timeout_ms",
        "emergency_acquire_timeout_ms",
        "pacer_critical_delay_ms",
        "pacer_normal_delay_ms",
        "pacer_rebuild_delay_ms",
        "flush_suspend_check_ms",
        "sqlite_timeout_ms",
        "snapshot_stale_ms",
        "funding_interval_ms",
        "next_candle_fallback_ms",
        "archiver_interval_ms",
        "health_check_interval_ms",
        "symbol_status_check_ms",
        "breach_ms",
        "micro_candle_ms",
        "spoof_timeout_ms",
        "real_min_lifetime_ms",
        "hard_deadline_ms",
        "quarantine_ms",
        "seal_ttl_ms",
        "correlation_window_ms",
        "fvg_timeout_ms",
        "mss_timeout_ms",
        "cooldown_ms",
        "limit_ioc_timeout_ms",
        "emergency_timeout_ms",
        "hysteresis_ms",
        "max_pending_ms",
        "max_daily_loss_window_ms",
        "archiver_orphan_ms",
        "archiver_deleted_ms",
    }
)

# FATAL constants
POSITION_MODES: Final[Tuple[str,...]] = ("ONE_WAY", "HEDGE")
MARGIN_MODES: Final[Tuple[str,...]] = ("ISOLATED",)
ENVIRONMENTS: Final[Tuple[str,...]] = ("TEST", "PROD")
TARGET_LEVERAGE: Final[int] = 5

@dataclass(frozen=True, slots=True)
class Settings:
    """
    Immutable application settings (Y-353).

    All _ms fields are in _MS_WHITELIST and int (Y-269).
    No _minutes field allowed (Y-269).
    Risk fields are derived properties from environment.
    """

    # Exchange modes - FATAL if missing/invalid
    position_mode: str
    margin_mode: str
    target_leverage: int
    environment: str # TEST | PROD - FATAL otherwise

    # API - trade only, DNS not IP hardcode
    api_base_url: str
    ws_base_url: str

    # Time fields - all must be in _MS_WHITELIST and int (Y-269) - 35 fields
    ws_ping_interval_ms: int
    ws_pong_timeout_ms: int
    ws_reconnect_jitter_ms: int
    rest_acquire_timeout_ms: int
    rest_outer_timeout_ms: int
    emergency_acquire_timeout_ms: int
    pacer_critical_delay_ms: int
    pacer_normal_delay_ms: int
    pacer_rebuild_delay_ms: int
    flush_suspend_check_ms: int
    sqlite_timeout_ms: int
    snapshot_stale_ms: int
    funding_interval_ms: int
    next_candle_fallback_ms: int
    archiver_interval_ms: int
    health_check_interval_ms: int
    symbol_status_check_ms: int
    breach_ms: int
    micro_candle_ms: int
    spoof_timeout_ms: int
    real_min_lifetime_ms: int
    hard_deadline_ms: int
    quarantine_ms: int
    seal_ttl_ms: int
    correlation_window_ms: int
    fvg_timeout_ms: int
    mss_timeout_ms: int
    cooldown_ms: int
    limit_ioc_timeout_ms: int
    emergency_timeout_ms: int
    hysteresis_ms: int
    max_pending_ms: int
    max_daily_loss_window_ms: int
    archiver_orphan_ms: int
    archiver_deleted_ms: int

    # Storage
    sqlite_path: str
    parquet_live_days: int
    parquet_archive_days: int

    # Emergency
    emergency_max_retry: int
    emergency_reduce_only: bool

    # Process
    max_ws_per_process: int
    process_count: int
    flap_threshold: int

    # Derived risk properties - TEST vs PROD
    @property
    def risk_per_trade(self) -> float:
        """Return risk per trade based on environment: TEST 0.008, PROD 0.006."""
        if self.environment == "TEST":
            return 0.008
        if self.environment == "PROD":
            return 0.006
        raise RuntimeError(f"FATAL: invalid environment {self.environment}")

    @property
    def max_daily_loss(self) -> float:
        """Return max daily loss based on environment: TEST -0.04, PROD -0.02."""
        if self.environment == "TEST":
            return -0.04
        if self.environment == "PROD":
            return -0.02
        raise RuntimeError(f"FATAL: invalid environment {self.environment}")

    @property
    def max_positions(self) -> int:
        """Return max positions based on environment: TEST 3, PROD 2."""
        if self.environment == "TEST":
            return 3
        if self.environment == "PROD":
            return 2
        raise RuntimeError(f"FATAL: invalid environment {self.environment}")

    @property
    def emergency_slippage_pct(self) -> float:
        """Leverage adjusted slippage: min(3%, 10%/lev) - Y-260."""
        return min(0.03, 0.10 / float(self.target_leverage))

def _is_ip_literal(value: str) -> bool:
    """Check if value is IP literal - FATAL if DNS expected."""
    raise NotImplementedError("FAZ 1")

def assert_utc_timezone() -> None:
    """Assert TZ=UTC - FATAL if not UTC."""
    raise NotImplementedError("FAZ 1")

def assert_no_ip_hardcode(url: str) -> None:
    """Assert URL does not contain hard-coded IP - FATAL."""
    raise NotImplementedError("FAZ 1")

def validate_ms_whitelist(settings_dict: dict) -> None:
    """
    Validate _ms whitelist (Y-269).

    Only keys in _MS_WHITELIST allowed for *_ms suffix.
    Must be int, minutes suffix forbidden.
    FATAL on violation.
    """
    raise NotImplementedError("FAZ 1")

def validate_fatal(settings: Settings) -> None:
    """
    Validate all FATAL conditions.

    - position_mode in ONE_WAY|HEDGE else FATAL
    - margin_mode ISOLATED else FATAL
    - target_leverage == 5 else FATAL if not set via startup
    - environment in TEST|PROD else FATAL
    - TZ=UTC else FATAL
    - DNS not IP else FATAL
    - _ms whitelist 35 fields (Y-269)
    - api key trade only
    - no _minutes field
    """
    raise NotImplementedError("FAZ 1")

def load_settings() -> Settings:
    """Load settings from env / Docker secrets without creating global mutable state (Y-353)."""
    raise NotImplementedError("FAZ 1")

def from_env(env: dict) -> Settings:
    """Create Settings from dict - used for testing, no global state (Y-353)."""
    raise NotImplementedError("FAZ 1")