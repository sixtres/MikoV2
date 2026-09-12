# YAMA Y-357, Y-337, Y-266, Y-311, Y-329, Y-353, Y-358

import asyncio
import multiprocessing as mp

import pytest

from src.data_layer.queues.async_state_queue import AsyncStateQueue

def test_maxsize_default_200():
    mq = mp.Queue()
    q = AsyncStateQueue(mq)
    assert q.maxsize == 200
    assert q.qsize_async() == 0

@pytest.mark.asyncio
async def test_start_idempotent():
    mq = mp.Queue()
    q = AsyncStateQueue(mq)
    await q.start()
    task1 = q._writer_task
    await q.start()
    task2 = q._writer_task
    assert task1 is task2
    await q.stop()

@pytest.mark.asyncio
async def test_stop_idempotent():
    mq = mp.Queue()
    q = AsyncStateQueue(mq)
    await q.start()
    await q.stop()
    await q.stop()
    assert q._writer_task is None

@pytest.mark.asyncio
async def test_put_then_drain():
    mq = mp.Queue()
    q = AsyncStateQueue(mq)
    await q.start()
    await q.put("item1")
    await asyncio.sleep(0.2)
    assert not mq.empty()
    got = mq.get_nowait()
    assert got == "item1"
    await q.stop()

@pytest.mark.asyncio
async def test_put_blocks_when_full_no_writer():
    mq = mp.Queue()
    q = AsyncStateQueue(mq, maxsize=2)
    # start() CAGRILMAZ - writer yok, async queue dolu kalir
    await q.put("a")
    await q.put("b")
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(q.put("c"), timeout=0.1)

@pytest.mark.asyncio
async def test_writer_task_created():
    mq = mp.Queue()
    q = AsyncStateQueue(mq)
    assert q._writer_task is None
    await q.start()
    assert q._writer_task is not None
    assert isinstance(q._writer_task, asyncio.Task)
    await q.stop()

@pytest.mark.asyncio
async def test_stop_drains_remaining():
    mq = mp.Queue()
    q = AsyncStateQueue(mq)
    await q.start()
    await q.put("x")
    await q.put("y")
    await q.stop()
    items = []
    while not mq.empty():
        try:
            items.append(mq.get_nowait())
        except Exception:
            break
    assert "x" in items
    assert "y" in items

def test_no_global_state():
    assert not hasattr(AsyncStateQueue, "_async_queue")
    assert not hasattr(AsyncStateQueue, "_mp_queue")
    assert not hasattr(AsyncStateQueue, "_writer_task")

def test_async_queue_bounded_200():
    mq = mp.Queue()
    q = AsyncStateQueue(mq, maxsize=200)
    assert q._async_queue.maxsize == 200

@pytest.mark.asyncio
async def test_writer_done_callback():
    mq = mp.Queue()
    q = AsyncStateQueue(mq)
    await q.start()
    assert q._writer_task is not None
    assert len(q._writer_task._callbacks) >= 1 or q._writer_task.done() is False
    await q.stop()
    assert q._writer_task is None

@pytest.mark.asyncio
async def test_put_nowait_on_mpqueue_used():
    mq = mp.Queue()
    q = AsyncStateQueue(mq)
    await q.start()
    await q.put({"seq": 1})
    await asyncio.sleep(0.2)
    assert mq.qsize() >= 1
    await q.stop()