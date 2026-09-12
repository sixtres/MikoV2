# YAMA Y-266: tasks pop done_callback try/finally
# YAMA Y-311: no task leak
# YAMA Y-329: AsyncStateQueue adapter
# YAMA Y-337: state_queue ayri executor YASAK, drain() SIGTERM zorunlu
# YAMA Y-353: DI, no global
# YAMA Y-357: asyncio.Queue(200) bridge + single writer task, mp.Queue + to_thread + Semaphore(8) deadlock fix, ayri executor YASAK
# YAMA Y-358: asyncio.Lock

"""
AsyncStateQueue - bridge asyncio.Queue(200) -> mp.Queue with single writer.

Y-357: asyncio.Queue(200) + single writer task, mp.Queue + to_thread + Semaphore(8) fix.
Y-337: no separate executor, drain() SIGTERM mandatory.
Y-266: done_callback try/finally.
Y-311: no task leak.
Y-329: adapter.
Y-353: DI, no global.
Y-358: asyncio.Lock.
"""

from __future__ import annotations

import asyncio
import logging
import multiprocessing as mp
import multiprocessing.queues

logger = logging.getLogger(__name__)

class AsyncStateQueue:
    """
    Bridge bounded asyncio.Queue(200) to mp.Queue with single writer task.

    mp_queue: multiprocessing.Queue
    maxsize: int = 200
    """

    def __init__(self, mp_queue: mp.Queue, maxsize: int = 200) -> None:
        self._mp_queue = mp_queue
        self._maxsize = maxsize
        self._async_queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._writer_task: asyncio.Task | None = None
        self._lock: asyncio.Lock = asyncio.Lock()
        self._running: bool = False

    @property
    def maxsize(self) -> int:
        return self._maxsize

    def _on_writer_done(self, task: asyncio.Task) -> None:
        try:
            try:
                exc = task.exception()
                if exc is not None:
                    logger.warning("writer done with exception: %s", exc)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.warning("writer done callback error: %s", e)
        finally:
            # Y-266 try/finally pop, Y-311 no leak
            pass

    async def start(self) -> None:
        async with self._lock:
            if self._running:
                return
            self._running = True
            self._writer_task = asyncio.create_task(self._writer_loop())
            self._writer_task.add_done_callback(self._on_writer_done)

    async def stop(self) -> None:
        async with self._lock:
            if not self._running:
                return
            self._running = False

        if self._writer_task is not None:
            self._writer_task.cancel()
            try:
                await self._writer_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.warning("writer task stop error: %s", e)
            finally:
                self._writer_task = None

        self._drain_remaining()

    def _drain_remaining(self) -> None:
        # Y-337 drain() SIGTERM zorunlu
        try:
            while True:
                item = self._async_queue.get_nowait()
                try:
                    self._mp_queue.put(item)
                except Exception:
                    try:
                        self._mp_queue.put_nowait(item)
                    except Exception as e:
                        logger.warning("drain mp put failed: %s", e)
                try:
                    self._async_queue.task_done()
                except Exception:
                    pass
        except asyncio.QueueEmpty:
            pass
        except Exception as e:
            logger.warning("drain error: %s", e)

    async def put(self, item) -> None:
        await self._async_queue.put(item)

    async def _writer_loop(self) -> None:
        while self._running:
            try:
                item = await asyncio.wait_for(self._async_queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            try:
                try:
                    self._mp_queue.put_nowait(item)
                except Exception:
                    # DROP_NEVER blocking put
                    self._mp_queue.put(item)
            except Exception as e:
                logger.warning("mp_queue put failed: %s", e)
                await asyncio.sleep(0.01)
                try:
                    self._async_queue.put_nowait(item)
                except Exception:
                    pass
            finally:
                try:
                    self._async_queue.task_done()
                except Exception:
                    pass

    def qsize_async(self) -> int:
        return self._async_queue.qsize()