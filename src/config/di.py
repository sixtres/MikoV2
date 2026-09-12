"""Dependency Injection container for MikoV2.

Y-353: All dependencies must be injected via this dataclass.
Global state is PROHIBITED. No module-level mutable state allowed.

All leaf modules receive Dependencies as constructor parameter.
"""

from dataclasses import dataclass
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from src.storage.sqlite_writer import SqliteWriter
    from src.alerting.agent import AlertingAgent


@dataclass(frozen=True)
class Dependencies:
    """Dependency Injection container.
    
    Y-353: All modules must receive this via __init__, never access
    global state. All fields are required and validated.
    
    Fields:
        db: SqliteWriter instance (Y-341 WAL).
        alerting_agent: AlertingAgent instance (Y-345 bypass).
        compute_obi: Callable for orderbook imbalance (Y-344 active len).
        write_emergency_journal: Callable for emergency logging (Y-341).
        _numba_cvd: Callable for Numba CVD warmup (Y-272).
    """
    
    db: "SqliteWriter"
    alerting_agent: "AlertingAgent"
    compute_obi: Callable[..., int]  # Y-344: returns active len
    write_emergency_journal: Callable[..., None]  # Y-341: fallback writer
    _numba_cvd: Callable[..., None]  # Y-272: warmup function
    
    def validate(self) -> None:
        """Validate all dependencies are properly set.
        
        Raises:
            ValueError: If any dependency is None or invalid.
        """
        if self.db is None:
            raise ValueError("Dependencies.db cannot be None (Y-353)")
        
        if self.alerting_agent is None:
            raise ValueError("Dependencies.alerting_agent cannot be None (Y-353)")
        
        if not callable(self.compute_obi):
            raise ValueError("Dependencies.compute_obi must be callable (Y-353)")
        
        if not callable(self.write_emergency_journal):
            raise ValueError(
                "Dependencies.write_emergency_journal must be callable (Y-353)"
            )
        
        if not callable(self._numba_cvd):
            raise ValueError("Dependencies._numba_cvd must be callable (Y-353)")


def create_dependencies(
    db: "SqliteWriter",
    alerting_agent: "AlertingAgent",
    compute_obi: Callable[..., int],
    write_emergency_journal: Callable[..., None],
    numba_cvd: Callable[..., None],
) -> Dependencies:
    """Create validated Dependencies instance.
    
    Args:
        db: SqliteWriter instance.
        alerting_agent: AlertingAgent instance.
        compute_obi: OBI computation callable.
        write_emergency_journal: Emergency journal writer.
        numba_cvd: Numba CVD warmup callable.
        
    Returns:
        Dependencies: Validated DI container.
        
    Raises:
        ValueError: If any dependency is invalid.
    """
    deps = Dependencies(
        db=db,
        alerting_agent=alerting_agent,
        compute_obi=compute_obi,
        write_emergency_journal=write_emergency_journal,
        _numba_cvd=numba_cvd,
    )
    deps.validate()
    return deps
