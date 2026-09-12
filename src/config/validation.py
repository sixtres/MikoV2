# YAMA Y-353: DI validation - no global refs, all checks via injected Settings, global mutable state forbidden
# YAMA Y-269: _ms whitelist REJECT - minutes suffix forbidden, only whitelist int fields, FATAL
# YAMA Y-38: target_leverage set_leverage startup required, FATAL if None or <=0
# YAMA FATAL-CHECKS: Full AnaYasa REV5 validation matrix - FATAL vs WARNING separation

"""
Validation module.

Minimal validation logic per AnaYasa REV5.
- FATAL: raises RuntimeError with FATAL prefix
- WARNING: logs warning but does not raise (rate-limited trim etc)
All functions receive Settings via DI, no global state (Y-353).
"""

from __future__ import annotations

from typing import Final, Mapping, List, Tuple

# _MS_WHITELIST used by validate_ms_int - import for re-export
from .settings import Settings, _MS_WHITELIST

# Expected constants (AnaYasa)
EXPECTED_MAX_BUFFER: Final[int] = 5000
EXPECTED_LOW_WATER: Final[int] = 4000
EXPECTED_PER_IP: Final[int] = 15
EXPECTED_PER_SYMBOL: Final[int] = 2
EXPECTED_SEM_EMERGENCY: Final[int] = 3
EXPECTED_SEM_NORMAL: Final[int] = 9
EXPECTED_ACQUIRE_TIMEOUT_MS: Final[int] = 2000
EXPECTED_OUTER_TIMEOUT_MS: Final[int] = 3500
EXPECTED_PACER_CRITICAL_MS: Final[int] = 2
EXPECTED_PACER_MAX_CRITICAL_MS: Final[int] = 5

def _raise_fatal(message: str) -> None:
    """Raise FATAL RuntimeError."""
    raise NotImplementedError("FAZ 1")

def _log_warning(code: str, **kwargs: object) -> None:
    """Log WARNING - rate-limited where required (Y-348)."""
    raise NotImplementedError("FAZ 1")

def validate_ms_int(settings_dict: Mapping[str, object]) -> None:
    """
    Validate all *_ms fields are int and in whitelist (Y-269).
    FATAL if not int or not in _MS_WHITELIST.
    """
    raise NotImplementedError("FAZ 1")

def validate_no_minutes_suffix(settings_dict: Mapping[str, object]) -> None:
    """
    Validate no field ends with _minutes or contains minutes (Y-269).
    FATAL if found - use _ms only.
    """
    raise NotImplementedError("FAZ 1")

def validate_position_mode(mode: str) -> None:
    """Validate position_mode ONE_WAY|HEDGE required FATAL."""
    raise NotImplementedError("FAZ 1")

def validate_margin_mode(mode: str) -> None:
    """Validate margin_mode ISOLATED default else FATAL."""
    raise NotImplementedError("FAZ 1")

def validate_environment(env: str) -> None:
    """Validate environment TEST|PROD else FATAL."""
    raise NotImplementedError("FAZ 1")

def validate_leverage(leverage: int) -> None:
    """
    target_leverage must be set (>0). 5 is default. FATAL if None or <=0.
    set_leverage startup zorunlu (Y-38).
    """
    raise NotImplementedError("FAZ 1")

def validate_api_urls(api_url: str, ws_url: str) -> None:
    """Validate DNS not IP hardcode, trade only key - FATAL on IP literal."""
    raise NotImplementedError("FAZ 1")

def validate_buffer_constants(max_buffer: int, low_water: int) -> None:
    """
    Validate buffer hard cap 5000 and low-water 4000.
    WARNING if not, FATAL if Python loop / list.sort used (checked elsewhere).
    """
    raise NotImplementedError("FAZ 1")

def validate_lock_hierarchy(hierarchy: List[str]) -> None:
    """
    Validate lock hierarchy buffer>fill>sqlite>pacer>flush>telemetry (Y-339).
    FATAL if order reversed or sealed_lock not separate.
    """
    raise NotImplementedError("FAZ 1")

def validate_pacer_config(
    critical_ms: int, normal_ms: int, rebuild_ms: int, is_priority_queue: bool
) -> None:
    """
    Validate pacer PriorityQueue, min-spacing CRITICAL 2ms NORMAL 20ms REBUILD 50ms (Y-330).
    FATAL if pacer_min_delay[0] >5ms, WARNING if not PriorityQueue.
    """
    raise NotImplementedError("FAZ 1")

def validate_rest_gateway(
    per_ip: int, per_symbol: int, sem_emergency: int, sem_normal: int
) -> None:
    """
    Validate REST gateway SINGLE GLOBAL bucket rate 8 burst 15, per-IP 15, per-symbol 2,
    sem_emergency 3 sem_normal 9 distinct (Y-342), acquire 2.0s outer 3.5s (Y-359).
    """
    raise NotImplementedError("FAZ 1")

def validate_emergency_config(
    max_retry: int, reduce_only: bool, slippage_pct: float
) -> None:
    """Validate emergency MAX_RETRY 1, reduce_only True else FATAL, slippage leverage adjusted."""
    raise NotImplementedError("FAZ 1")

def validate_time_source(is_exchange_timestamp: bool, has_monotonic: bool) -> None:
    """Validate time_source exchange_timestamp and monotonic fallback (Y-257)."""
    raise NotImplementedError("FAZ 1")

def validate_storage_config(
    is_wal: bool, is_drop_never_state: bool, is_drop_oldest_telemetry: bool
) -> None:
    """Validate SQLite WAL, state_queue DROP_NEVER, telemetry DROP_OLDEST - FATAL otherwise."""
    raise NotImplementedError("FAZ 1")

def validate_fatal_config(settings: Settings) -> None:
    """
    Run all FATAL validations on Settings (Y-353 DI).
    Calls sub-validators, raises FATAL on violation.
    """
    raise NotImplementedError("FAZ 1")

def validate_warning_config(settings: Settings) -> None:
    """
    Run all WARNING validations - logs warnings for non-critical mismatches.
    """
    raise NotImplementedError("FAZ 1")