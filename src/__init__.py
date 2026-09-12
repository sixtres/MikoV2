# YAMA Y-353: Global mutable state forbidden - no module-level mutable globals, DI via Dependencies dataclass
# YAMA FAZ0-SRC-STRUCTURE: 38 file skeleton, single responsibility, 10 faz

"""
MikoV2 package root.

Provides package metadata only. No runtime state creation here.
All runtime objects must be constructed via src.config.di.Dependencies (Y-353).
"""

__version__ = "2.0.0-REV5"
__all__ = ["__version__"]