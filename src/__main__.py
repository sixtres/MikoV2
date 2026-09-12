from __future__ import annotations

import asyncio

from .main import async_main


if __name__ == "__main__":
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass