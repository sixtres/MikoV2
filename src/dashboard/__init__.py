# YAMA Y-353: DI, re-export only

"""
Dashboard package - re-export only.

Y-353: DI
"""

from __future__ import annotations

from .app import DashboardApp, DashboardConfig
from .routes import DashboardRoutes, RoutesConfig

__all__ = [
    "DashboardApp",
    "DashboardConfig",
    "DashboardRoutes",
    "RoutesConfig",
]