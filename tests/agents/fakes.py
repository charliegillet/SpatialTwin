"""Fake Interactions provider with recorded shapes (ids, statuses, usage and stream events).

Shapes follow runtime/live-checks-2026-10-25/door-agent-live*.json (interaction ids "v1_...", 32-hex environment ids,
"call_<digits>" function-call ids, usage with total/input/output/thought/cached tokens) and the SSE event shapes in
CLAUDE_BUILD_HANDOFF/reference/google/streaming.md (interaction.created, interaction.status_update, step.start/
delta/stop with index, step.stop usage, interaction.completed, error) plus the SDK 2.33 models (event_id on every
event, code_execution_call arguments {code, language}, code_execution_result {result, is_error}).
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace as NS
from typing import Any, Dict, Iterable, List, Optional

MODEL = "gemini-4-argon"
ENV_ID = "a0d1d8c123fe848e00f9b7e2c0c506ea"
BEST = {"D4": "closed", "D9": "open"}            # checker's best for FIRE in the lobby: 125 of 125
ROBUST = {"D4": "open", "D9": "open"}            # ties it at 125 and holds every single failure
FIRE = {"id": "h0", "type": "FIRE", "position": {"x": 20, "y": 4}, "source": "simulated"}
GAS = {"id": "g0", "type": "GAS", "position": {"x": 20, "y": 14}, "source": "simulated"}


def interaction_id(n: int) -> str:
    return f"v1_ChdKM1RkYXBxVks3bjl2X2dQNUo2UG1RMBIX{n:05d}"


def usage(total: int = 5333, cached: int = 0) -> NS:
    output, thought = min(16, total // 4), min(13, total // 4)
    return NS(total_tokens=total, total_input_tokens=total - output - thought, total_output_tokens=output,
              total_thought_tokens=thought, total_cached_tokens=cached, total_tool_use_tokens=0)


def call(call_id: str, name: str, arguments: Optional[dict] = None) -> dict:
    return {"type": "function_call", "id": call_id, "name": name, "arguments": arguments or {}}


def submit(call_id: str = "call_1111214", states: Optional[dict] = None, fallback: Optional[dict] = None,
           claims: Iterable[dict] = (), rationale: str = "D9 open gives every modeled crossing.") -> dict:
    return call(call_id, "submit_recommendation", {
        "door_states": dict(states or BEST), "fallback_if_jammed": dict(fallback or {"D4": "open", "D9": "closed"}),
        "claims": list(claims), "rationale": rationale})


def response(status: str = "completed", steps: Optional[list] = None, identifier: Optional[str] = None,
             tokens: int = 5333, model: str = MODEL, text: str = "", environment: str = ENV_ID) -> NS:
    return NS(id=identifier or interaction_id(1), environment_id=environment, model=model, status=status,
              steps=steps or [], usage=usage(tokens), output_text=text)


def final(text: str, identifier: Optional[str] = None) -> NS:
    return response(identifier=identifier or interaction_id(2), text=text)


class FakeStream:
    """Async iterator of recorded-shape SSE events; ``drop_after`` raises a connection error mid-stream."""

    def __init__(self, events: List[dict], drop_after: Optional[int] = None):
        self.events, self.drop_after, self.closed = list(events), drop_after, False

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for index, event in enumerate(self.events):
            if self.drop_after is not None and index >= self.drop_after:
                raise ConnectionResetError("stream dropped")
            await asyncio.sleep(0)
            yield event

    async def close(self):
        self.closed = True


def stream_events(identifier: str, final_status: str, steps: Iterable[dict] = (), start_id: int = 1) -> List[dict]:
    """created -> per step start/delta/stop -> status_update(final_status)."""
    n = start_id
    out: List[dict] = []

    def add(event: dict) -> None:
        nonlocal n
        out.append({**event, "event_id": f"evt-{n}"})
        n += 1

    add({"event_type": "interaction.created", "interaction": {"id": identifier, "status": "in_progress",
                                                             "model": MODEL, "agent": "antigravity-preview-09-2026"}})
    add({"event_type": "interaction.status_update", "interaction_id": identifier, "status": "in_progress"})
    for index, step in enumerate(steps):
        kind = step["type"]
        if kind == "code_execution_call":
            add({"event_type": "step.start", "index": index,
                 "step": {"type": kind, "id": f"ce_{index}", "arguments": {"code": "", "language": "python"}}})
            add({"event_type": "step.delta", "index": index,
                 "delta": {"type": "code_execution_call", "arguments": {"code": step["code"], "language": "python"}}})
        elif kind == "code_execution_result":
            add({"event_type": "step.start", "index": index, "step": {"type": kind, "call_id": f"ce_{index - 1}",
                                                                     "result": ""}})
            add({"event_type": "step.delta", "index": index,
                 "delta": {"type": "code_execution_result", "result": step["result"]}})
        elif kind == "thought":
            add({"event_type": "step.start", "index": index, "step": {"type": "thought"}})
            add({"event_type": "step.delta", "index": index, "delta": {"type": "thought_signature", "signature": "x"}})
        elif kind == "model_output":
            add({"event_type": "step.start", "index": index, "step": {"type": "model_output"}})
            add({"event_type": "step.delta", "index": index, "delta": {"type": "text", "text": step["text"]}})
        elif kind == "function_call":
            add({"event_type": "step.start", "index": index,
                 "step": {"type": "function_call", "id": step["id"], "name": step["name"], "arguments": {}}})
            add({"event_type": "step.delta", "index": index,
                 "delta": {"type": "arguments_delta", "arguments": "{\"door_states\": {}}"}})
        add({"event_type": "step.stop", "index": index,
             "usage": {"total_tokens": 4650, "total_input_tokens": 3577, "total_output_tokens": 305,
                       "total_cached_tokens": 0},
             "step_usage": {"total_tokens": 303, "total_input_tokens": 31, "total_output_tokens": 3}})
    add({"event_type": "interaction.status_update", "interaction_id": identifier, "status": final_status})
    return out


class Provider:
    """``creates``/``gets``/``get_streams`` are consumed in order; a callable entry is awaited (to hang or raise)."""

    def __init__(self, creates: Iterable[Any] = (), gets: Iterable[Any] = (), get_streams: Iterable[Any] = ()):
        self.creates, self.gets, self.get_streams = list(creates), list(gets), list(get_streams)
        self.create_calls: List[dict] = []
        self.get_calls: List[dict] = []
        self.cancel_calls: List[dict] = []
        self.aio = NS(interactions=self)

    async def _value(self, queue: list) -> Any:
        value = queue.pop(0)
        if callable(value):
            return await value()
        if isinstance(value, BaseException):
            raise value
        return value

    async def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return await self._value(self.creates)

    async def get(self, **kwargs):
        self.get_calls.append(kwargs)
        if kwargs.get("stream"):
            return await self._value(self.get_streams)
        return await self._value(self.gets)

    async def cancel(self, **kwargs):
        self.cancel_calls.append(kwargs)
        return response("cancelled")


class LaneProvider:
    """Routes each call to a per-lane script. A first create is routed by its tools (code_execution means the
    robustness or follow-up lane), a continuation or get by the interaction id it names."""

    def __init__(self, scripts: Dict[str, Dict[str, list]]):
        self.scripts = {lane: {k: list(v) for k, v in script.items()} for lane, script in scripts.items()}
        self.owner: Dict[str, str] = {}
        self.calls: List[tuple] = []
        self.cancel_calls: List[dict] = []
        self.aio = NS(interactions=self)

    def _lane_of(self, kwargs: dict) -> str:
        ref = kwargs.get("previous_interaction_id") or kwargs.get("id")
        if ref in self.owner:
            return self.owner[ref]
        tools = kwargs.get("tools") or []
        if any(t.get("type") == "code_execution" for t in tools):
            return "followup" if kwargs.get("previous_interaction_id") else "robustness"
        return "strategist"

    async def _next(self, lane: str, queue: str) -> Any:
        value = self.scripts[lane][queue].pop(0)
        if callable(value):
            value = await value()
        if isinstance(value, BaseException):
            raise value
        identifier = getattr(value, "id", None) or (value.events[0].get("interaction", {}).get("id")
                                                    if isinstance(value, FakeStream) and value.events else None)
        if identifier:
            self.owner[identifier] = lane
        return value

    async def create(self, **kwargs):
        lane = self._lane_of(kwargs)
        self.calls.append((lane, "create", kwargs))
        items = kwargs.get("input") if isinstance(kwargs.get("input"), list) else []
        is_ack = (kwargs.get("previous_interaction_id") in self.owner and "acks" in self.scripts[lane] and items
                  and all(i.get("type") == "function_result" for i in items)
                  and any(i.get("name") == "submit_recommendation" for i in items))
        queue = "acks" if is_ack else "creates"
        return await self._next(lane, queue)

    async def get(self, **kwargs):
        lane = self._lane_of(kwargs)
        self.calls.append((lane, "get", kwargs))
        return await self._next(lane, "streams" if kwargs.get("stream") else "gets")

    async def cancel(self, **kwargs):
        self.cancel_calls.append(kwargs)
        return response("cancelled", identifier=kwargs.get("id"))

    def lane_calls(self, lane: str, method: str = "create") -> List[dict]:
        return [kwargs for owner, name, kwargs in self.calls if owner == lane and name == method]


class HttpError(Exception):
    """Typed HTTP metadata only, as the SDK's errors carry (provider_error_code reads status_code)."""

    def __init__(self, status_code: int):
        super().__init__("provider error")
        self.status_code = status_code


def claims_for(evaluator, states: Dict[str, str], scenarios: Iterable[str], tamper: Optional[int] = None) -> List[dict]:
    """Claims exactly as the local checker computes them; ``tamper`` adds +1 crossing to that claim index."""
    out = []
    for index, label in enumerate(scenarios):
        local = evaluator.evaluate(states, label)
        out.append({"scenario": local["scenario"], "completed_crossings": local["completed_crossings"]
                    + (1 if tamper == index else 0), "candidate_hash": local["candidate_hash"]})
    return out
