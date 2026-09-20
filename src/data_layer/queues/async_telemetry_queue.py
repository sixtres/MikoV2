# YAMA Y-276: telemetry DROP_OLDEST 1000, put_nowait DROP (state DROP_NEVER)
# YAMA Y-329: mp.Queue bridge for process-boundary telemetry
# YAMA Y-353: Stateless - no global mutable, instance via DI

"""
Telemetry queue - true DROP_OLDEST across process boundary.

Architecture (Solution F):
  producer (async) -> collections.deque(maxlen=N) under Lock
                   -> daemon bridge thread -> mp.Queue
                   -> consumer (separate process) reads mp.Queue only.

put_nowait is sync and non-blocking; deque append is O(1), atomically
evicts oldest when full. Bridge thread forwards to mp_queue without
blocking the event loop.

threaded_bridge=False enables synchronous forwarding (unit tests only):
put_nowait pushes directly into mp_queue on the caller's thread, no daemon
bridge thread.

CAVEAT: regardless of threaded_bridge, mp.Queue itself owns an internal
feeder thread. put_nowait returns after enqueueing to mp.Queue's buffer,
NOT after data reaches the pipe. get_nowait reads from the pipe only and
may therefore return None immediately after a successful put_nowait.
Consumers MUST poll (or sleep briefly) rather than assume synchronous
put→get ordering.
"""

from __future__ import annotations

import multiprocessing as mp
import queue
import threading
from collections import deque
from typing import Any


class AsyncTelemetryQueue:
    """
    Telemetry queue with true DROP_OLDEST (Y-276).

    Y-276: telemetry DROP_OLDEST 1000, put_nowait DROP
    Y-329: mp.Queue bridge for process-boundary telemetry
    Y-353: instance via DI

    Async semantics (mp.Queue):
      - put_nowait: enqueues to mp.Queue buffer, returns immediately.
      - get_nowait: reads pipe; may return None even when put_nowait
        has just succeeded (feeder thread has not flushed yet).
      - Producers must not assume synchronous put→get ordering.
        Consumers poll or wait between get_nowait calls.
    """

    def __init__(
        self,
        maxsize: int = 1000,
        threaded_bridge: bool = True,
    ) -> None:
        self._maxsize = maxsize
        self._q: mp.Queue = mp.Queue(maxsize=maxsize)
        # Non-blocking exit: producer process must not hang waiting for
        # the mp.Queue feeder thread at interpreter shutdown.
        try:
            self._q.cancel_join_thread()
        except Exception:
            pass

        self._dropped: int = 0
        self._lock = threading.Lock()
        self._deque: deque = deque(maxlen=maxsize)
        self._threaded_bridge = threaded_bridge
        self._stop_event = threading.Event()
        self._bridge_thread: threading.Thread | None = None

        if threaded_bridge:
            self._bridge_thread = threading.Thread(
                target=self._bridge_loop,
                name="telemetry-bridge",
                daemon=True,
            )
            self._bridge_thread.start()

    # --- public API ---

    def put_nowait(self, item: Any) -> None:
        """
        Non-blocking put with DROP_OLDEST (Y-276).

        threaded_bridge=True: enqueue to local deque; bridge thread forwards.
        threaded_bridge=False: forward directly to mp_queue on caller thread.
        """
        if not self._threaded_bridge:
            # synchronous test mode
            try:
                self._q.put_nowait(item)
                return
            except queue.Full:
                pass

            evicted = False
            try:
                self._q.get_nowait()
                evicted = True
            except queue.Empty:
                pass

            try:
                self._q.put_nowait(item)
                if evicted:
                    with self._lock:
                        self._dropped += 1
            except queue.Full:
                with self._lock:
                    self._dropped += 1
            return

        # production: local deque with lock
        dropped = False
        with self._lock:
            if len(self._deque) == self._deque.maxlen:
                dropped = True
            self._deque.append(item)
            if dropped:
                self._dropped += 1

    def get_nowait(self) -> Any:
        """Consumer reads only from mp.Queue (Option A)."""
        try:
            return self._q.get_nowait()
        except queue.Empty:
            return None

    def qsize(self) -> int:
        """Approximate size: mp_queue current + local deque backlog."""
        try:
            base = self._q.qsize()
        except Exception:
            base = 0
        if self._threaded_bridge:
            with self._lock:
                base += len(self._deque)
        return base

    def dropped_count(self) -> int:
        with self._lock:
            return self._dropped

    def close(self) -> None:
        """Stop bridge thread, drain remaining, close mp_queue."""
        self._stop_event.set()
        if self._bridge_thread is not None:
            self._bridge_thread.join(timeout=2.0)
            self._bridge_thread = None

        # best-effort flush remaining deque items before close
        try:
            while True:
                with self._lock:
                    if not self._deque:
                        break
                    item = self._deque.popleft()
                try:
                    self._q.put_nowait(item)
                except queue.Full:
                    with self._lock:
                        self._dropped += 1
                    break
        except Exception:
            pass

        try:
            self._q.cancel_join_thread()
        except Exception:
            pass
        try:
            self._q.close()
        except Exception:
            pass

    @property
    def maxsize(self) -> int:
        return self._maxsize

    # --- internals ---

    def _bridge_loop(self) -> None:
        """Daemon bridge: deque -> mp_queue. Handles BrokenPipe/EOF safely."""
        while not self._stop_event.is_set():
            item = None
            with self._lock:
                if self._deque:
                    item = self._deque.popleft()
            if item is None:
                # brief yield, keep CPU low
                self._stop_event.wait(timeout=0.005)
                continue
            try:
                self._q.put(item, timeout=0.5)
            except queue.Full:
                # mp_queue stalled; put back and retry
                with self._lock:
                    self._deque.appendleft(item)
                    if len(self._deque) == self._deque.maxlen:
                        # deque.appendleft already evicted the newest; count it
                        self._dropped += 1
                self._stop_event.wait(timeout=0.05)
            except (BrokenPipeError, EOFError, OSError):
                # consumer gone; drop item and continue
                with self._lock:
                    self._dropped += 1
            except Exception:
                with self._lock:
                    self._dropped += 1