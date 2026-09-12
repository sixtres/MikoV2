# YAMA Y-327: Pacer.pop recursion YASAK, while loop zorunlu
# YAMA Y-328: Pacer.enqueue heapq.heappush, heapify YASAK
# YAMA Y-330: Pacer min-spacing CRITICAL 2ms NORMAL 20ms REBUILD 50ms
# YAMA Y-353: Stateless - no global mutable, DI

"""
Execution package.

Order flow:
  OrderQueue -> Pacer (rate limiter) -> RestGateway

Y-327: Pacer.pop recursion forbidden, while loop mandatory
Y-330: Pacer min-spacing CRITICAL 2ms NORMAL 20ms REBUILD 50ms
Y-353: DI, no global state
"""

from __future__ import annotations

from .pacer import Pacer, PacerConfig
from .rest_gateway import RestGateway, RestGatewayConfig

__all__ = [
    "Pacer",
    "PacerConfig",
    "RestGateway",
    "RestGatewayConfig",
]