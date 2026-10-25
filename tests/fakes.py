"""Offline stand-in for ``genai.Client`` (async surface only).

Mimics ``client.aio.interactions.{create,get,cancel}`` and
``client.aio.files.{upload,get}`` and returns *real* SDK ``Interaction`` /
``File`` models, so code under test sees the same shapes as production.

Each positional argument to ``FakeClient`` is one *script*: the list of states
a single interaction goes through. ``create()`` consumes the next script and
returns its first state; every later ``get(id)`` for that interaction returns the
next state (the last state repeats). A state is a status string or a dict with
``status`` plus optional ``steps``, ``id``, ``environment_id``, ``model``,
``usage``, ``agent_config``.

Example::

    client = FakeClient(
        ["in_progress", "in_progress", {"status": "completed", "steps": [text_step("hi")]}],
        # a second create() (e.g. answering a function call) gets this script:
        [{"status": "requires_action",
          "steps": [function_call_step("echo_number", {"n": 3}, id="fc1")]}],
    )
    interaction = await client.aio.interactions.create(model="m", input="x")
    client.requests[0]          # captured create kwargs
    client.get_calls            # ids passed to get()
    client.cancel_calls         # ids passed to cancel()

Files: ``FakeClient(file_states=["PROCESSING", "ACTIVE"])`` makes ``files.upload``
return the first state and each ``files.get`` the next; ``client.uploads`` captures
upload kwargs.
"""
from __future__ import annotations

from typing import Any

from google.genai import types
from google.genai._gaos.types.interactions.createagentinteraction import (
    CreateAgentInteractionParam)
from google.genai._gaos.types.interactions.createmodelinteraction import (
    CreateModelInteractionParam)
from google.genai._gaos.types.interactions.interaction import Interaction

# Body keys the real google-genai 2.33.0 ``interactions.create`` accepts
# (union of the model and agent request TypedDicts) plus its transport kwargs.
ALLOWED_CREATE_KWARGS = (
    set(CreateModelInteractionParam.__annotations__)
    | set(CreateAgentInteractionParam.__annotations__)
    | {"request", "api_version", "extra_headers", "extra_query", "extra_body", "timeout"}
)


def text_step(text: str) -> dict:
    return {"type": "model_output", "content": [{"type": "text", "text": text}]}


def processing_call_step(id: str = "pc1") -> dict:
    return {"type": "processing_call", "id": id}


def function_call_step(name: str, arguments: dict, id: str = "fc1") -> dict:
    return {"type": "function_call", "id": id, "name": name, "arguments": arguments}


def code_execution_step(id: str = "ce1", code: str = "print(1)") -> dict:
    # Real SDK step type is "code_execution_call".
    return {"type": "code_execution_call", "id": id,
            "arguments": {"language": "python", "code": code}}


class _Interactions:
    def __init__(self, owner: "FakeClient") -> None:
        self._o = owner

    async def create(self, **kwargs: Any) -> Interaction:
        o = self._o
        unknown = set(kwargs) - ALLOWED_CREATE_KWARGS
        if unknown:
            raise TypeError(f"FakeClient: unknown create() kwargs {sorted(unknown)}")
        inp = kwargs.get("input")
        if isinstance(inp, list):
            for item in inp:
                if not isinstance(item, dict) or "type" not in item:
                    raise TypeError(f"FakeClient: input item needs a 'type': {item!r}")
        o.requests.append(kwargs)
        if not o._scripts:
            raise AssertionError("FakeClient: create() called with no script left")
        script = o._scripts.pop(0)
        iid = None
        states = [dict(s) if isinstance(s, dict) else {"status": s} for s in script]
        iid = states[0].get("id") or f"int-{len(o._by_id) + 1}"
        for s in states:
            s.setdefault("id", iid)
        o._by_id[iid] = {"states": states, "pos": 0}
        return self._build(states[0])

    async def get(self, id: str, **kwargs: Any) -> Interaction:
        o = self._o
        o.get_calls.append(id)
        entry = o._by_id[id]
        entry["pos"] = min(entry["pos"] + 1, len(entry["states"]) - 1)
        return self._build(entry["states"][entry["pos"]])

    async def cancel(self, id: str, **kwargs: Any) -> Interaction:
        self._o.cancel_calls.append(id)
        entry = self._o._by_id[id]
        cancelled = {**entry["states"][entry["pos"]], "status": "cancelled"}
        entry["states"] = [cancelled]
        entry["pos"] = 0
        return self._build(cancelled)

    @staticmethod
    def _build(state: dict) -> Interaction:
        return Interaction.model_validate(state)


class _Files:
    def __init__(self, owner: "FakeClient") -> None:
        self._o = owner

    def _file(self, state: str) -> types.File:
        return types.File(name="files/fake123", uri="https://fake.test/files/fake123",
                          mime_type="video/mp4", state=state)

    async def upload(self, **kwargs: Any) -> types.File:
        self._o.uploads.append(kwargs)
        self._o._file_pos = 0
        return self._file(self._o._file_states[0])

    async def get(self, *, name: str, **kwargs: Any) -> types.File:
        self._o.file_get_calls.append(name)
        o = self._o
        o._file_pos = min(o._file_pos + 1, len(o._file_states) - 1)
        return self._file(o._file_states[o._file_pos])


    async def delete(self, *, name: str, **kwargs: Any) -> None:
        self._o.file_deletes.append(name)


class _Agents:
    def __init__(self, owner: "FakeClient") -> None:
        self._o = owner

    async def create(self, **kwargs: Any) -> Any:
        from types import SimpleNamespace
        self._o.agents_created.append(kwargs)
        self._o._agents[kwargs["id"]] = kwargs
        return SimpleNamespace(**kwargs)

    async def get(self, *, id: str, **kwargs: Any) -> Any:
        from types import SimpleNamespace
        return SimpleNamespace(**self._o._agents[id])

    async def delete(self, *, id: str, **kwargs: Any) -> None:
        self._o._agents.pop(id)
        self._o.agents_deleted.append(id)


class _Aio:
    def __init__(self, owner: "FakeClient") -> None:
        self.interactions = _Interactions(owner)
        self.files = _Files(owner)
        self.agents = _Agents(owner)


class FakeClient:
    def __init__(self, *scripts: list, file_states: list[str] | None = None) -> None:
        self._scripts = [list(s) for s in scripts]
        self._by_id: dict[str, dict] = {}
        self._file_states = file_states or ["ACTIVE"]
        self._file_pos = 0
        self.requests: list[dict] = []
        self.get_calls: list[str] = []
        self.cancel_calls: list[str] = []
        self.uploads: list[dict] = []
        self.file_get_calls: list[str] = []
        self.file_deletes: list[str] = []
        self._agents: dict[str, dict] = {}
        self.agents_created: list[dict] = []
        self.agents_deleted: list[str] = []
        self.aio = _Aio(self)
