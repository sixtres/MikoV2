# YAMA Y-353: Global mutable state forbidden - no module-level secret cache, secrets loaded via function DI
# YAMA SECRET-MASK: Docker secrets /run/secrets, logs must mask secrets

"""
Secrets module.

Handles Docker secrets and API key loading.
All secrets are loaded from /run/secrets or env, never hard-coded.
Logs must mask secrets (SECRET-MASK).
No global mutable cache (Y-353).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

SECRETS_DIR: Final[Path] = Path("/run/secrets")
MASK_PLACEHOLDER: Final[str] = "***MASKED***"
MIN_MASK_LEN: Final[int] = 4

@dataclass(frozen=True, slots=True)
class Secrets:
    """Immutable container for secrets - no global mutable state."""

    api_key: str
    api_secret: str

def get_secret_path(name: str) -> Path:
    """Return path for secret file under /run/secrets."""
    raise NotImplementedError("FAZ 1")

def load_secret(name: str) -> str:
    """
    Load secret by name from Docker secrets or env fallback.

    - Tries /run/secrets/<name> first
    - Falls back to env var uppercased
    - FATAL if not found
    """
    raise NotImplementedError("FAZ 1")

def load_api_keys() -> Secrets:
    """
    Load API key and secret via DI.

    Trade-only key, FATAL if missing.
    """
    raise NotImplementedError("FAZ 1")

def mask_secret(value: str) -> str:
    """
    Mask secret for logging.

    Returns ***MASKED*** with last 4 chars visible if len > 4.
    Must be used in all log statements.
    """
    raise NotImplementedError("FAZ 1")

def assert_no_secret_in_logs(message: str) -> None:
    """Assert no raw secret appears in log message - FATAL if leak detected."""
    raise NotImplementedError("FAZ 1")