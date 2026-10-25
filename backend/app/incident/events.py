"""SSE hub for the incident stream: numbered events, bounded replay, `: ping` heartbeat.

Same delivery pattern as backend/app/state/manager.py (per-subscriber bounded queue, slow client loses its oldest
message and never blocks a publisher) plus ids, so a reconnecting EventSource resumes with Last-Event-ID instead of
silently missing a gate transition. The buffer is bounded; a client that is further behind than the buffer gets a
fresh `snapshot` instead of a partial replay.
"""
from __future__ import annotations

import asyncio
import json
from collections import deque
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Callable, Deque, Dict, List, Optional, Tuple

SUBSCRIBER_QUEUE_LIMIT = 256
REPLAY_LIMIT = 256
PING_SECONDS = 10.0


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class EventHub:
    def __init__(self, replay_limit: int = REPLAY_LIMIT, ping_seconds: float = PING_SECONDS):
        self._seq = 0
        self._replay: Deque[Tuple[int, str]] = deque(maxlen=replay_limit)
        self._subscribers: List[Tuple[asyncio.Queue, asyncio.AbstractEventLoop]] = []
        self.ping_seconds = ping_seconds

    @property
    def last_id(self) -> int:
        return self._seq

    @staticmethod
    def _frame(event_id: Optional[int], event: str, data: Dict[str, Any]) -> str:
        head = f"id: {event_id}\n" if event_id is not None else ""
        return f"{head}event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"

    @staticmethod
    def _deliver(queue: asyncio.Queue, payload: str) -> None:
        if queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        queue.put_nowait(payload)

    def publish(self, event: str, payload: Dict[str, Any]) -> int:
        self._seq += 1
        data = {"seq": self._seq, "ts": now_iso(), "type": event, "simulated": True, **payload}
        frame = self._frame(self._seq, event, data)
        self._replay.append((self._seq, frame))
        try:
            current = asyncio.get_running_loop()
        except RuntimeError:
            current = None
        for queue, loop in list(self._subscribers):
            if loop is current:
                self._deliver(queue, frame)
            elif not loop.is_closed():
                loop.call_soon_threadsafe(self._deliver, queue, frame)
        return self._seq

    def events_since(self, last_event_id: int) -> List[Tuple[int, str]]:
        return [(i, f) for i, f in self._replay if i > last_event_id]

    async def stream(self, last_event_id: Optional[int], snapshot: Callable[[], Dict[str, Any]]) -> AsyncGenerator[str, None]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=SUBSCRIBER_QUEUE_LIMIT)
        entry = (queue, asyncio.get_running_loop())
        # Subscribe and compute the replay with no await in between: no event can fall into the gap.
        self._subscribers.append(entry)
        backlog: List[str] = []
        gap = False
        if last_event_id is not None:
            oldest = self._replay[0][0] if self._replay else self._seq + 1
            gap = last_event_id < oldest - 1
            if not gap:
                backlog = [frame for _, frame in self.events_since(last_event_id)]
        try:
            if last_event_id is None or gap:
                # No id on the snapshot: it must not move the client's Last-Event-ID.
                yield self._frame(None, "snapshot", {"type": "snapshot", "last_id": self._seq, **snapshot()})
            for frame in backlog:
                yield frame
            while True:
                try:
                    yield await asyncio.wait_for(queue.get(), timeout=self.ping_seconds)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            if entry in self._subscribers:
                self._subscribers.remove(entry)
