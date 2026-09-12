# YAMA Y-357: deadlock fix - mp.Queue + to_thread + Semaphore(8) FORBIDDEN, asyncio.Queue(200) bridge + single writer MANDATORY
# YAMA Y-353: Stateless - no global mutable, instance via DI, no module-level queue
# YAMA Y-358: asyncio.Lock for state, threading.Lock FORBIDDEN

"""
Async state queue - deadlock safe bridge.

Y-357: multiprocessing queue bridge must use asyncio.Queue(200) + single writer task.
mp.Queue + asyncio.to_thread + Semaphore(8) pattern causes deadlock - FORBIDDEN.
"""

from __future__ import annotations

import asyncio
import multiprocessing as mp
from typing import Any

class AsyncStateQueue:
    """
    Async state queue bridge.

    Single writer pattern:
    - async side: asyncio.Queue(maxsize=200) (Y-357)
    - sync side: mp.Queue
    - single asyncio.Task drains async queue -> mp.Queue
    - No Semaphore(8), no to_thread (Y-357)

    Y-357: asyncio.Queue(200) bridge + single writer
    Y-353: instance via DI
    Y-358: asyncio.Lock for lifecycle
    """

    def __init__(self, mp_queue: mp.Queue, maxsize: int = 200) -> None:
        self._mp_queue: mp.Queue = mp_queue
        self._maxsize: int = maxsize
        self._async_queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=maxsize)
        self._writer_task: asyncio.Task | None = None
        self._lock: asyncio.Lock = asyncio.Lock()
        self._running: bool = False

    async def start(self) -> None:
        """
        Start single writer task.

        Idempotent: if already running, returns without creating second writer.
        Y-357: single writer pattern, multiple writers FORBIDDEN.
        """
        raise NotImplementedError("FAZ 3")

    async def stop(self) -> None:
        """
        Stop writer task with drain (Y-337).

        Sequence:
        1. Set running=False to exit writer loop gracefully
        2. Await writer task with timeout
        3. Drain remaining mp.Queue items (SIGTERM grace period)
        4. Y-266: tasks pop in done_callback try/finally
        5. Y-311: no task leak

        drain() is MANDATORY on SIGTERM (Y-337) - state_queue DROP_NEVER.
        """
        raise NotImplementedError("FAZ 3")

    async def put(self, item: Any) -> None:
        """
        Put item into async bridge.

        Bounded 200 (Y-357). DROP_NEVER - if full, blocks until space.
        Never drops items (Y-276 state_queue DROP_NEVER).
        """
        raise NotImplementedError("FAZ 3")

    async def _writer_loop(self) -> None:
        """
        Single writer loop: asyncio.Queue -> mp.Queue.

        Only place where mp.Queue.put occurs.
        No Semaphore, no to_thread (Y-357).
        """
        raise NotImplementedError("FAZ 3")

    def qsize_async(self) -> int:
        """Return async queue size."""
        raise NotImplementedError("FAZ 3")

    @property
    def maxsize(self) -> int:
        return self._maxsize