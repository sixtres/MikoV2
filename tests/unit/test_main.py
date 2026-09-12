import asyncio

import pytest

from src.main import async_main


@pytest.mark.asyncio
async def test_async_main_runs():
    await async_main()