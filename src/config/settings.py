"""Settings module with FATAL validation checks.

Y-269: _ms whitelist for millisecond-based settings only.
All settings validated at startup; invalid config causes FATAL exit.
No global state (Y-353).
"""

from dataclasses import dataclass, field
from typing import Final


# Y-269: Whitelist of allowed _ms suffix settings
_MS_WHITELIST: Final[set[str]] = frozenset({
    "flush_interval_ms",
    "telemetry_interval_ms",
    "pacer_min_spacing_ms",
})


@dataclass(frozen=True)
class Settings:
    """Application settings with FATAL validation.
    
    All fields validated on __post_init__. Invalid values raise
    SystemExit with FATAL prefix.
    """
    
    # Exchange settings
    exchange_name: str = "binance"
    testnet: bool = True
    
    # Position settings
    position_mode: str = "ONE_WAY"  # ONE_WAY or BOTH_SIDES
    margin_mode: str = "ISOLATED"   # ISOLATED or CROSS
    target_leverage: int = 5
    
    # Timing settings
    flush_interval_ms: int = 2000
    telemetry_interval_ms: int = 1000
    pacer_min_spacing_ms: int = 2
    
    # Risk limits
    max_position_size_usd: float = 100_000.0
    daily_loss_limit_usd: float = 5_000.0
    
    # Queue settings
    state_queue_capacity: int = 200
    telemetry_queue_capacity: int = 1000
    
    _validated: bool = field(default=False, init=False)
    
    def __post_init__(self) -> None:
        """Validate all settings with FATAL checks."""
        if self._validated:
            return
        
        # Y-269: Validate _ms whitelist
        for attr_name, attr_value in self.__dict__.items():
            if attr_name.endswith("_ms") and attr_name not in _MS_WHITELIST:
                raise SystemExit(
                    f"FATAL: Setting '{attr_name}' not in _ms whitelist (Y-269)"
                )
        
        # Validate position_mode
        if self.position_mode not in ("ONE_WAY", "BOTH_SIDES"):
            raise SystemExit(
                f"FATAL: position_mode must be ONE_WAY or BOTH_SIDES, got {self.position_mode}"
            )
        
        # Validate margin_mode
        if self.margin_mode not in ("ISOLATED", "CROSS"):
            raise SystemExit(
                f"FATAL: margin_mode must be ISOLATED or CROSS, got {self.margin_mode}"
            )
        
        # Validate leverage
        if not (1 <= self.target_leverage <= 125):
            raise SystemExit(
                f"FATAL: target_leverage must be 1-125, got {self.target_leverage}"
            )
        
        # Validate timing (must be positive)
        if self.flush_interval_ms <= 0:
            raise SystemExit(
                f"FATAL: flush_interval_ms must be > 0, got {self.flush_interval_ms}"
            )
        
        if self.telemetry_interval_ms <= 0:
            raise SystemExit(
                f"FATAL: telemetry_interval_ms must be > 0, got {self.telemetry_interval_ms}"
            )
        
        if self.pacer_min_spacing_ms <= 0:
            raise SystemExit(
                f"FATAL: pacer_min_spacing_ms must be > 0, got {self.pacer_min_spacing_ms}"
            )
        
        object.__setattr__(self, "_validated", True)


def create_settings() -> Settings:
    """Create validated Settings instance.
    
    Returns:
        Settings: Validated configuration.
        
    Raises:
        SystemExit: On invalid configuration (FATAL).
    """
    return Settings()
