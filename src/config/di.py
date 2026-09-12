# YAMA Y-353: Dependencies dataclass - global mutable instance forbidden, all runtime objects via DI, no module-level mutable state

"""
DI module.

Provides Dependencies dataclass that holds all runtime singletons.
No global mutable state allowed (Y-353).
All modules receive dependencies via constructor injection.
Utils are stateless and not part of DI - they are imported directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True, slots=True)
class Dependencies:
    """
    Immutable container for all runtime dependencies (Y-353).

    All fields are injected, no global instance creation.
    Future faz will fill None placeholders.
    """

    # Config
    settings: Any  # Settings from .settings - Any to avoid circular import in skeleton
    secrets: Any = None

    # Data layer (FAZ 2)
    l2_buffer: Any = None
    seq_tracker: Any = None
    token_bucket: Any = None
    async_state_queue: Any = None
    async_telemetry_queue: Any = None

    # WS manager (FAZ 2)
    ws_manager: Any = None
    snapshot_handler: Any = None
    funding_scheduler: Any = None

    # Execution (FAZ 3-4)
    pacer: Any = None
    rest_gateway: Any = None
    order_manager: Any = None
    flush_controller: Any = None

    # Storage (FAZ 4)
    sqlite_writer: Any = None
    orderbook_store: Any = None
    sealed_store: Any = None
    archiver: Any = None

    # Emergency (FAZ 4)
    emergency_close: Any = None
    emergency_persist: Any = None
    emergency_journal: Any = None

    # Risk (FAZ 4)
    portfolio_risk: Any = None
    whale_radar: Any = None
    funding_risk: Any = None

def create_dependencies(settings: Any) -> Dependencies:
    """
    Create Dependencies from Settings via DI (Y-353).

    No global state, returns new immutable Dependencies.
    """
    raise NotImplementedError("FAZ 1")

def validate_dependencies(deps: Dependencies) -> None:
    """
    Validate Dependencies - all required fields for current FAZ must be set.
    Raises FATAL if global ref used or required dep missing (Y-353).
    """
    raise NotImplementedError("FAZ 1")

def get_empty_dependencies() -> Dependencies:
    """
    Return empty Dependencies for testing - no global state.
    """
    raise NotImplementedError("FAZ 1")