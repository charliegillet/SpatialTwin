"""Live event stream: broadcasts from worker threads are delivered safely; slow clients keep the newest state."""
import asyncio
import threading

import pytest

from backend.app.state import manager as manager_module
from backend.app.state.manager import StateManager


@pytest.mark.asyncio
async def test_broadcast_from_worker_thread_reaches_loop_subscriber():
    manager = StateManager()
    stream = manager.subscribe()
    assert (await stream.__anext__()).startswith("event: snapshot")
    worker = threading.Thread(target=manager.broadcast_event, args=("probe", {"n": 1}))
    worker.start()
    worker.join()
    message = await asyncio.wait_for(stream.__anext__(), timeout=1)
    assert message.startswith("event: probe") and '"n": 1' in message
    await stream.aclose()


@pytest.mark.asyncio
async def test_full_queue_drops_oldest_and_keeps_newest(monkeypatch):
    monkeypatch.setattr(manager_module, "SUBSCRIBER_QUEUE_LIMIT", 2)
    manager = StateManager()
    stream = manager.subscribe()
    await stream.__anext__()
    for n in range(5):
        manager.broadcast_event("tick", {"n": n})
    first = await asyncio.wait_for(stream.__anext__(), timeout=1)
    second = await asyncio.wait_for(stream.__anext__(), timeout=1)
    assert '"n": 3' in first and '"n": 4' in second
    await stream.aclose()
