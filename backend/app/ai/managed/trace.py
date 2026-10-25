"""Live trace of an agent-team investigation: an in-memory hub with durable rows, served as SSE.

What the trace promises: lane lifecycle, provider status, code cells the agent ran in its sandbox, their results,
the agent's visible output text, client function calls (and the local checker's verdicts on them), token usage and
cost. It never carries agent thoughts: ``AntigravityAgentConfig`` has no ``thinking_summaries`` (only the
deep-research config does), and ``thought`` steps are reported as a bare step marker without content.

Every event gets a per-investigation sequence number ``seq`` (the SSE ``id``). Transient events (text and code
deltas) live only in the in-memory ring; durable ones (finished steps, tool calls, verdicts, lane results, the
deadline, done) are also written to the managed ledger as ``phase="trace"`` rows carrying their ``seq``, so a
browser reconnecting with ``Last-Event-ID`` replays them even after the hub forgot the run or the server restarted.
Text from the sandbox is untrusted data: control characters are stripped and every field is truncated.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from collections import OrderedDict, deque
from typing import Any, AsyncIterator, Callable, Deque, Dict, List, Optional

TRACE_BUFFER = 2048
MAX_STREAMS = 32
MAX_TEXT = 4000
DURABLE_TEXT = 2000
PING_SECONDS = 10.0
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
DURABLE_EVENTS = frozenset({"deadline", "lane", "step", "tool", "verification", "result", "usage", "retry",
                            "stream", "fallback", "error", "done", "followup"})
EVENT_NAMES = DURABLE_EVENTS | {"status", "delta"}


def clean_text(value: Any, limit: int = MAX_TEXT) -> str:
    text = _CONTROL.sub("", value if isinstance(value, str) else "")
    return text if len(text) <= limit else text[:limit - 1] + "…"


class _Stream:
    def __init__(self, started: float):
        self.started = started
        self.seq = 0
        self.events: Deque[dict] = deque(maxlen=TRACE_BUFFER)
        self.subscribers: List[asyncio.Queue] = []
        self.closed = False


class TraceHub:
    """One hub per router. ``durable`` writes a trace row (sync, called through ``asyncio.to_thread``)."""

    def __init__(self, durable: Optional[Callable[[str, float, dict], None]] = None,
                 loader: Optional[Callable[[str], List[dict]]] = None):
        self._streams: "OrderedDict[str, _Stream]" = OrderedDict()
        self._durable = durable
        self._loader = loader

    def open(self, investigation_id: str) -> None:
        if investigation_id not in self._streams:
            self._streams[investigation_id] = _Stream(time.monotonic())
            while len(self._streams) > MAX_STREAMS:
                old_id, old = next(iter(self._streams.items()))
                if not old.closed:
                    break  # never forget a live run; the bound applies to finished ones
                self._streams.pop(old_id)

    def known(self, investigation_id: str) -> bool:
        return investigation_id in self._streams

    def closed(self, investigation_id: str) -> bool:
        stream = self._streams.get(investigation_id)
        return stream is None or stream.closed

    async def publish(self, investigation_id: str, event: str, data: Dict[str, Any], *,
                      lane: Optional[str] = None, durable: Optional[bool] = None) -> int:
        """Append one event; returns its seq (0 when the run has no open stream)."""
        stream = self._streams.get(investigation_id)
        if stream is None or stream.closed or event not in EVENT_NAMES:
            return 0
        stream.seq += 1
        elapsed = round((time.monotonic() - stream.started) * 1000, 1)
        record = {"seq": stream.seq, "event": event, "lane": lane, "elapsed_ms": elapsed, **data}
        stream.events.append(record)
        for queue in list(stream.subscribers):
            try:
                queue.put_nowait(record)
            except asyncio.QueueFull:
                pass  # a slow browser loses live deltas; durable rows replay on reconnect
        if (event in DURABLE_EVENTS if durable is None else durable) and self._durable is not None:
            durable_record = {k: (clean_text(v, DURABLE_TEXT) if isinstance(v, str) else v) for k, v in record.items()}
            try:
                await asyncio.to_thread(self._durable, investigation_id, elapsed, durable_record)
            except Exception:
                pass  # the live trace never fails a run
        return stream.seq

    async def close(self, investigation_id: str) -> None:
        stream = self._streams.get(investigation_id)
        if stream is None or stream.closed:
            return
        stream.closed = True
        for queue in list(stream.subscribers):
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                pass

    def buffered(self, investigation_id: str, after: int) -> List[dict]:
        stream = self._streams.get(investigation_id)
        return [e for e in stream.events if e["seq"] > after] if stream else []

    async def durable(self, investigation_id: str, after: int) -> List[dict]:
        if self._loader is None:
            return []
        try:
            rows = await asyncio.to_thread(self._loader, investigation_id)
        except Exception:
            return []
        out = []
        for row in rows:
            record = {k: v for k, v in row.items() if k != "phase"}
            if isinstance(record.get("seq"), int) and record["seq"] > after:
                out.append(record)
        out.sort(key=lambda r: r["seq"])
        return out

    async def events(self, investigation_id: str, last_event_id: Optional[str] = None, *,
                     ping_seconds: float = PING_SECONDS, idle_limit: Optional[float] = None) -> AsyncIterator[str]:
        """SSE text frames: replay after ``last_event_id`` (memory, else durable rows), then live events with a
        ``: ping`` comment every ``ping_seconds``; ends when the run's stream is closed and drained."""
        after = int(last_event_id) if isinstance(last_event_id, str) and last_event_id.isdigit() else 0
        stream = self._streams.get(investigation_id)
        queue: Optional[asyncio.Queue] = None
        if stream is not None and not stream.closed:
            queue = asyncio.Queue(maxsize=TRACE_BUFFER)
            stream.subscribers.append(queue)
        try:
            replay = self.buffered(investigation_id, after) if stream is not None else []
            # A buffer that no longer reaches back to ``after`` (or a forgotten run) replays the durable rows first.
            if stream is None or not replay or replay[0]["seq"] > after + 1:
                durable = await self.durable(investigation_id, after)
                seen = {r["seq"] for r in replay}
                replay = sorted([r for r in durable if r["seq"] not in seen] + replay, key=lambda r: r["seq"])
            for record in replay:
                after = max(after, record["seq"])
                yield format_sse(record)
            if queue is None:
                return
            idle_started = time.monotonic()
            while True:
                try:
                    record = await asyncio.wait_for(queue.get(), timeout=ping_seconds)
                except (asyncio.TimeoutError, TimeoutError):
                    if idle_limit is not None and time.monotonic() - idle_started > idle_limit:
                        return
                    yield ": ping\n\n"
                    continue
                if record is None:
                    return
                idle_started = time.monotonic()
                if record["seq"] <= after:
                    continue
                after = record["seq"]
                yield format_sse(record)
        finally:
            if stream is not None and queue is not None and queue in stream.subscribers:
                stream.subscribers.remove(queue)


def format_sse(record: Dict[str, Any]) -> str:
    payload = json.dumps(record, sort_keys=True, separators=(",", ":"), default=str)
    return f"id: {record['seq']}\nevent: {record['event']}\ndata: {payload}\n\n"


# --- Provider stream events -> trace records -------------------------------------------------------------------

def field(value: Any, key: str, default: Any = None) -> Any:
    return value.get(key, default) if isinstance(value, dict) else getattr(value, key, default)


class StepAccumulator:
    """Accumulates one provider stream's step.start/delta/stop into trace records (no thought content ever)."""

    def __init__(self):
        self.steps: Dict[int, dict] = {}

    def start(self, event: Any) -> Optional[dict]:
        index = field(event, "index")
        step = field(event, "step") or {}
        step_type = str(field(step, "type") or "unknown")[:40]
        if not isinstance(index, int):
            return None
        entry = {"index": index, "step_type": step_type, "text": "", "chars": 0}
        if step_type == "function_call":
            entry["name"] = clean_text(field(step, "name"), 64)
        if step_type == "code_execution_call":
            arguments = field(step, "arguments") or {}
            code = field(arguments, "code")
            if isinstance(code, str):
                entry["text"] = code
            entry["language"] = clean_text(str(field(arguments, "language") or ""), 16)
        self.steps[index] = entry
        return {"kind": "step_start", **{k: v for k, v in entry.items() if k != "text"}}

    def delta(self, event: Any) -> Optional[dict]:
        index = field(event, "index")
        delta = field(event, "delta") or {}
        delta_type = str(field(delta, "type") or "")
        entry = self.steps.get(index) if isinstance(index, int) else None
        if entry is None or delta_type in ("thought_summary", "thought_signature") or entry["step_type"] == "thought":
            return None
        piece = ""
        if delta_type == "text":
            piece = field(delta, "text") or ""
        elif delta_type == "code_execution_call":
            piece = field(field(delta, "arguments") or {}, "code") or ""
        elif delta_type == "code_execution_result":
            piece = field(delta, "result") or ""
            entry["is_error"] = bool(field(delta, "is_error"))
        elif delta_type == "arguments_delta":
            entry["chars"] += len(field(delta, "arguments") or "")
            return None  # function arguments are verified, not echoed: the tool event carries the checked view
        else:
            return None
        if not isinstance(piece, str) or not piece:
            return None
        entry["text"] += piece
        entry["chars"] += len(piece)
        return {"kind": "delta", "index": index, "step_type": entry["step_type"], "delta_type": delta_type,
                "text": clean_text(piece)}

    def stop(self, event: Any) -> Optional[dict]:
        index = field(event, "index")
        entry = self.steps.pop(index, None) if isinstance(index, int) else None
        if entry is None:
            return None
        record = {"kind": "step", "index": index, "step_type": entry["step_type"], "chars": entry["chars"]}
        for key in ("name", "language", "is_error"):
            if key in entry:
                record[key] = entry[key]
        if entry["step_type"] != "thought" and entry["text"]:
            record["text"] = clean_text(entry["text"], DURABLE_TEXT)
        usage = field(event, "usage")
        if usage is not None:
            record["usage"] = {k: v for k in ("total_tokens", "total_input_tokens", "total_output_tokens",
                                              "total_cached_tokens", "total_thought_tokens")
                               if type(v := field(usage, k)) is int}
        return record


def steps_from_interaction(interaction: Any, start: int = 0) -> List[dict]:
    """Trace records for the steps of a polled (non-streamed) interaction, from index ``start``."""
    out = []
    steps = field(interaction, "steps", None) or []
    for index, step in enumerate(steps):
        if index < start:
            continue
        step_type = str(field(step, "type") or "unknown")[:40]
        record: Dict[str, Any] = {"kind": "step", "index": index, "step_type": step_type, "source": "poll"}
        if step_type == "code_execution_call":
            record["text"] = clean_text(field(field(step, "arguments") or {}, "code"), DURABLE_TEXT)
        elif step_type == "code_execution_result":
            record["text"] = clean_text(field(step, "result"), DURABLE_TEXT)
            record["is_error"] = bool(field(step, "is_error"))
        elif step_type == "function_call":
            record["name"] = clean_text(field(step, "name"), 64)
        elif step_type == "function_result":
            record["name"] = clean_text(field(step, "name"), 64)
        elif step_type == "model_output":
            parts = [field(block, "text") for block in (field(step, "content", None) or [])]
            record["text"] = clean_text("".join(p for p in parts if isinstance(p, str)), DURABLE_TEXT)
        out.append(record)
    return out
