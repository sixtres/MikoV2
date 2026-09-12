# YAMA Y-353: Global mutable state forbidden - config must be injected via DI, no module-level instances
# YAMA Y-269: _ms fields whitelist enforced in settings.py, FATAL on violation

"""
Config package.

Re-exports settings, validation, di and secrets modules.
No global instance is created here (Y-353).
"""

from . import di as di
from . import secrets as secrets
from . import settings as settings
from . import validation as validation

__all__ = [
    "settings",
    "validation",
    "di",
    "secrets",
]