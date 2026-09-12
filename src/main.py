# YAMA Y-353: DI
# YAMA Y-266: SIGTERM 30s grace supervisor uzerinden

"""
Entry point.
"""

from __future__ import annotations

import asyncio
import logging
import sys

logger = logging.getLogger(__name__)


async def async_main() -> None:
    """
    Async main - placeholder for FAZ 5a.

    Real wiring (settings load, Dependencies create, Supervisor run) 
    implemented in FAZ 5b once all modules are ready.
    """
    logger.warning("async_main stub")


def main() -> None:
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()