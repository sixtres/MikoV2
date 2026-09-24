"""Observation package.

B3.5 Mod 2: observation_state migration public API.
"""

from .migration import (
    OBSERVATION_SCHEMA_VERSION,
    migrate_observation,
)

__all__ = [
    "OBSERVATION_SCHEMA_VERSION",
    "migrate_observation",
]