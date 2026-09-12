# YAMA Y-266: SIGTERM 30s grace
# YAMA Y-331: funding_scheduler ayri task
# YAMA Y-353: DI
# YAMA Y-358: asyncio.Lock DI

"""
Entry point - FAZ 9 SON DOSYA.

Y-353: DI
Y-266: SIGTERM 30s grace supervisor uzerinden
Y-331: funding_scheduler ayri task
Y-358: asyncio.Lock DI

Sadece bu dosyada if __name__ == "__main__" olur.
src/ icinde oldugu icin tek nokta import.
"""

from __future__ import annotations

import asyncio
import sys

from .config.di import create_dependencies
from .config.secrets import load_api_keys
from .config.settings import load_settings
from .supervisor import Supervisor

async def async_main() -> None:
    """
    Main async entry.

    - Settings yukle, validate_fatal cagir (FATAL ise cikis)
    - Secrets yukle (load_api_keys)
    - Dependencies olustur (create_dependencies)
    - Supervisor olustur ve run() cagir
    - SIGTERM/SIGINT handle supervisor uzerinden
    """
    raise NotImplementedError("FAZ 9")

def main() -> None:
    """Sync entry - asyncio.run(async_main)."""
    raise NotImplementedError("FAZ 9")

if __name__ == "__main__":
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        sys.exit(0)