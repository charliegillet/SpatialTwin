"""Trace hub and SSE route: replay with Last-Event-ID, durable rows, pings, no thought content, stream mapping."""
import asyncio
import json

import httpx
from fastapi import FastAPI

from backend.app.ai.managed.adapter import ManagedAgentAdapter
from backend.app.ai.managed.door_agent import DoorAgentRunner
from backend.app.ai.managed.ledger import ManagedLedger
from backend.app.ai.managed.trace import StepAccumulator, TraceHub, clean_text, format_sse, steps_from_interaction
from backend.app.state.manager import StateManager
from backend.app.state.service import ScenarioService
from backend.app.state.store import SQLiteStore
from backend.app.venues.agent import build_door_agent_router
from tests.agents.fakes import FIRE, FakeStream, LaneProvider, interaction_id, response, stream_events, submit


def parse_sse(text):
    frames = []
    for block in text.strip().split("\n\n"):
        if block.startswith(":"):
            frames.append({"comment": block})
            continue
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        frames.append({"id": int(fields["id"]), "event": fields["event"], "data": json.loads(fields["data"])})
    return frames


def ledger_hub(tmp_path):
    ledger = ManagedLedger(str(tmp_path / "ledger.sqlite3"))
    hub = TraceHub(durable=lambda i, elapsed, record: ledger.event(i, elapsed, "trace", record),
                   loader=ledger.trace_events)
    return ledger, hub


async def collect(agen):
    return [frame async for frame in agen]


async def test_publish_replay_and_last_event_id(tmp_path):
    ledger, hub = ledger_hub(tmp_path)
    hub.open("t1")
    await hub.publish("t1", "deadline", {"deadline_at_ms": 1})
    await hub.publish("t1", "delta", {"text": "print(1)"}, lane="robustness")
    await hub.publish("t1", "step", {"step_type": "code_execution_call", "text": "print(1)"}, lane="robustness")
    await hub.publish("t1", "not-an-event", {})            # unknown names are dropped
    await hub.close("t1")
    frames = parse_sse("".join(await collect(hub.events("t1"))))
    assert [(f["id"], f["event"]) for f in frames] == [(1, "deadline"), (2, "delta"), (3, "step")]
    assert frames[1]["data"]["lane"] == "robustness" and frames[2]["data"]["seq"] == 3
    after = parse_sse("".join(await collect(hub.events("t1", "2"))))
    assert [f["id"] for f in after] == [3]
    # Durable rows: every event except transient deltas, each carrying its seq.
    assert [r["seq"] for r in ledger.trace_events("t1")] == [1, 3]
    assert [e["phase"] for e in ledger.events("t1")] == []  # trace rows never flood the progress receipts


async def test_replay_from_durable_rows_after_the_hub_forgot_the_run(tmp_path):
    ledger, hub = ledger_hub(tmp_path)
    hub.open("t2")
    for i in range(3):
        await hub.publish("t2", "tool", {"function_name": "verify_candidates", "n": i})
    await hub.close("t2")
    restarted = TraceHub(loader=ledger.trace_events)          # a new process: nothing in memory
    frames = parse_sse("".join(await collect(restarted.events("t2", "1"))))
    assert [f["id"] for f in frames] == [2, 3] and frames[0]["data"]["n"] == 1


async def test_live_subscriber_gets_pings_then_events_then_ends():
    hub = TraceHub()
    hub.open("t3")
    received = []

    async def reader():
        async for frame in hub.events("t3", ping_seconds=0.02):
            received.append(frame)
    task = asyncio.create_task(reader())
    await asyncio.sleep(0.07)
    await hub.publish("t3", "lane", {"status": "started"}, lane="strategist")
    await hub.publish("t3", "done", {"team_status": "finished"})
    await hub.close("t3")
    await asyncio.wait_for(task, 2)
    assert received[0] == ": ping\n\n"
    events = [f for f in received if not f.startswith(":")]
    assert [parse_sse(f)[0]["event"] for f in events] == ["lane", "done"]


def test_accumulator_never_carries_thought_content():
    acc = StepAccumulator()
    acc.start({"index": 0, "step": {"type": "thought"}})
    assert acc.delta({"index": 0, "delta": {"type": "thought_summary", "content": {"text": "secret"}}}) is None
    stop = acc.stop({"index": 0, "usage": {"total_tokens": 9}})
    assert stop == {"kind": "step", "index": 0, "step_type": "thought", "chars": 0, "usage": {"total_tokens": 9}}
    acc.start({"index": 1, "step": {"type": "code_execution_call", "arguments": {"code": "", "language": "python"}}})
    delta = acc.delta({"index": 1, "delta": {"type": "code_execution_call", "arguments": {"code": "x = 1\x07"}}})
    assert delta["text"] == "x = 1" and delta["step_type"] == "code_execution_call"
    assert acc.stop({"index": 1})["text"] == "x = 1"
    acc.start({"index": 2, "step": {"type": "function_call", "id": "c", "name": "submit_recommendation"}})
    assert acc.delta({"index": 2, "delta": {"type": "arguments_delta", "arguments": "{\"a\": 1}"}}) is None
    assert acc.stop({"index": 2}) == {"kind": "step", "index": 2, "step_type": "function_call", "chars": 8,
                                      "name": "submit_recommendation"}


def test_a_code_result_that_arrives_whole_in_its_start_event_keeps_its_text():
    """Live stream shape (probe P9): step.start:code_execution_result carries the result, with no delta or stop."""
    acc = StepAccumulator()
    started = acc.start({"index": 3, "step": {"type": "code_execution_result", "result": "suggested_claims [[\"baseline\", 125]]\n",
                                              "is_error": False}})
    assert "text" not in started and "complete" not in started
    assert acc.steps[3]["complete"] is True
    record = acc.stop({"index": 3})
    assert record["step_type"] == "code_execution_result" and "125" in record["text"] and record["is_error"] is False
    acc.start({"index": 4, "step": {"type": "code_execution_result"}})
    assert "complete" not in acc.steps[4], "an empty start still accumulates deltas as before"


def test_polled_steps_and_text_cleaning():
    interaction = response("requires_action", [
        {"type": "thought", "signature": "abc"},
        {"type": "code_execution_call", "id": "x", "arguments": {"code": "print(2)"}},
        {"type": "code_execution_result", "call_id": "x", "result": "2\n", "is_error": False},
        submit("call_1")])
    records = steps_from_interaction(interaction)
    assert [r["step_type"] for r in records] == ["thought", "code_execution_call", "code_execution_result",
                                                 "function_call"]
    assert "text" not in records[0] and records[1]["text"] == "print(2)" and records[3]["name"] == "submit_recommendation"
    assert steps_from_interaction(interaction, 3)[0]["index"] == 3
    assert clean_text("a" * 10, 5) == "aaaa…" and clean_text(None) == ""
    assert format_sse({"seq": 7, "event": "step", "x": 1}).startswith("id: 7\nevent: step\ndata: {")


async def test_route_serves_the_team_trace_with_replay(tmp_path):
    service = ScenarioService(StateManager(SQLiteStore(str(tmp_path / "state.sqlite3"))))
    steps = [{"type": "model_output", "text": "Submitting."},
             {"type": "function_call", "id": "call_1001", "name": "submit_recommendation"}]
    provider = LaneProvider({"strategist": {
        "creates": [FakeStream(stream_events(interaction_id(1), "requires_action", steps))],
        "gets": [response("requires_action", [submit("call_1001")], identifier=interaction_id(1))],
        "acks": [response("in_progress", identifier=interaction_id(2))], "streams": []}})
    adapter = ManagedAgentAdapter(service, api_key="", client=provider, poll_interval=0.001)
    runner = DoorAgentRunner(adapter, retry_base=0.001)
    app = FastAPI()
    app.include_router(build_door_agent_router(adapter, asyncio.Semaphore(2), lambda: True, runner=runner,
                                               ping_seconds=0.05))
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    started = (await client.post("/api/venues/building-v2/investigate",
                                 json={"hazards": [FIRE], "mode": "live"})).json()
    for _ in range(500):
        body = (await client.get(f"/api/venues/building-v2/investigations/{started['investigation_id']}")).json()
        if body["team_status"] != "running":
            break
        await asyncio.sleep(0.01)
    url = started["trace_url"]
    full = await client.get(url)
    assert full.status_code == 200 and full.headers["content-type"].startswith("text/event-stream")
    frames = parse_sse(full.text)
    events = [f["event"] for f in frames]
    assert events[0] == "deadline" and events[-1] == "done"
    assert {"lane", "step", "verification", "result", "usage"} <= set(events)
    step_texts = [f["data"].get("text") for f in frames if f["event"] == "step"]
    assert "Submitting." in step_texts
    result = next(f for f in frames if f["event"] == "result")["data"]
    assert result["lane"] == "strategist" and result["status"] == "completed"
    assert result["verification"]["source"] == "agent"
    ids = [f["id"] for f in frames]
    assert ids == sorted(ids) and len(set(ids)) == len(ids)
    tail = parse_sse((await client.get(url, headers={"Last-Event-ID": str(ids[-3])})).text)
    assert [f["id"] for f in tail] == ids[-2:]
    assert [f["id"] for f in parse_sse((await client.get(url + f"?after={ids[-2]}")).text)] == ids[-1:]
    assert (await client.get("/api/venues/building-v2/investigations/nope/trace")).status_code == 404
