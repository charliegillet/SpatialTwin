"""Managed-agent sweep: offline tests with FakeClient (no key, R2)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from fakes import FakeClient, code_execution_step, function_call_step, text_step
from walktwin import agent, flow
from walktwin.contracts import FlowParams, Hazard, Scenario, VenueGraph

REPO = Path(__file__).resolve().parents[1]
FIRE_D2 = Scenario(hazards=[Hazard(door_id="D2", kind="fire")])
# Horizon 60 s on the 58-person variant: fire on D2 leaves 40 reaching a modeled
# exit; OPEN:D5 lets all 58 reach one (reached == total, so any max-flow schedule
# gives the same figure).
P60 = FlowParams(horizon_s=60)


@pytest.fixture
def graph58(office_graph: VenueGraph) -> VenueGraph:
    zones = [z.model_copy(update={"occupants": {"Z1": 48, "Z4": 10}.get(z.id, z.occupants)})
             for z in office_graph.zones]
    return office_graph.model_copy(update={"zones": zones})


@pytest.fixture
def png(tmp_path: Path) -> Path:
    p = tmp_path / "view_top.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\nfake-top-down")
    return p


def requires_action(*steps, env="env-1"):
    return {"status": "requires_action", "environment_id": env, "steps": list(steps),
            "agent_config": {"type": "antigravity", "model": "gemini-4-argon"}}


def completed(env="env-1"):
    return {"status": "completed", "environment_id": env, "steps": [text_step("done")],
            "agent_config": {"type": "antigravity", "model": "gemini-4-argon"}}


def evaluate(ids, id="fc-eval"):
    return function_call_step("evaluate_interventions", {"ids": ids}, id=id)


def submit(iid, claimed, id="fc-sub"):
    return function_call_step("submit_recommendation", {
        "intervention_id": iid, "claimed_reached_exit": claimed,
        "rationale": "Argon proposed opening D5; sandbox runs, unverified.",
        "caveats": ["declared parameters"]}, id=id)


async def run(client, graph, scenario, png, tmp_path, params=P60, **kw):
    return await agent.investigate(
        client, graph, scenario, params, environment_id="env-1", topdown_png=png,
        poll_s=0.001, sessions_dir=tmp_path / "sessions", **kw)


def sent_results(client, i):
    return {r["call_id"]: r for r in client.requests[i]["input"]}


# --- sanity of the figures the tests rely on ---------------------------------


def test_fixture_figures(graph58):
    cur = flow.solve(graph58, FIRE_D2, P60)
    d5 = flow.solve(graph58, FIRE_D2.model_copy(update={"interventions": ["OPEN:D5"]}), P60)
    assert (cur.reached_exit, d5.reached_exit, d5.total) == (40, 58, 58)


def test_allowed_interventions(office_graph):
    assert agent.allowed_interventions(office_graph, Scenario()) == ["OPEN:D5"]
    # A hazard on the locked door removes it.
    hz = Scenario(hazards=[Hazard(door_id="D5", kind="fire")])
    assert agent.allowed_interventions(office_graph, hz) == []
    doors = [d.model_copy(update={"id": f"D{i}", "state": s, "position": d.position})
             for i, s in zip(range(1, 14), ["open", "closed", "locked", "unknown"] * 4)
             for d in [office_graph.doors[0]]]
    g = office_graph.model_copy(update={"doors": doors})
    out = agent.allowed_interventions(g, Scenario())
    assert out == ["OPEN:D2", "OPEN:D3", "OPEN:D4", "OPEN:D6", "OPEN:D7", "OPEN:D8"]
    assert len(out) <= 6


def test_limiting_doors(office_graph):
    params = FlowParams()
    d1 = next(d for d in office_graph.doors if d.id == "D1")
    caps = [flow.door_capacity_at_step(d1, k, params) for k in range(4)]
    run_ = SimpleNamespace(door_flows={
        "D1": [caps[0], caps[1], 1, 0] + [0] * 56,   # at cap 2 of 3 flowing steps
        "D3": [1, 1, 0, 0] + [0] * 56,                # never at cap
        "D6": [0] * 60})
    assert caps[0] > 1
    assert agent.limiting_doors(office_graph, run_, params) == ["D1"]


# --- investigate ----------------------------------------------------------------


async def test_happy_path_sweep_then_verify(graph58, png, tmp_path):
    client = FakeClient(
        ["in_progress", requires_action(code_execution_step("ce1"), code_execution_step("ce2"),
                                        code_execution_step("ce3"), evaluate(["OPEN:D5"]))],
        [requires_action(submit("OPEN:D5", 58))],
        [completed()],
    )
    inv = await run(client, graph58, FIRE_D2, png, tmp_path)
    assert inv.status == "completed"
    assert inv.sandbox_runs == 3
    evals = [e for e in inv.ledger if e.kind == "client_function"
             and e.name == "evaluate_interventions"]
    assert len(evals) == 1
    assert inv.best is not None and inv.best.intervention_id == "OPEN:D5"
    assert inv.best.reached_exit == 58 and inv.best.delta_vs_current == 18
    assert inv.best.check_ok is True
    assert inv.recommendation.claimed_reached_exit == 58
    assert inv.disagreement is None
    assert inv.receipt.provider_model == "gemini-4-argon"
    # Compact payload back to the agent: ids and integers, no arrays of flows.
    res = sent_results(client, 1)["fc-eval"]
    assert res["name"] == "evaluate_interventions"
    (entry,) = res["result"]["results"]
    assert entry["reached_exit"] == 58 and entry["delta_vs_current"] == 18
    assert set(entry) <= {"intervention_id", "run_id", "reached_exit", "total",
                          "delta_vs_current", "check_ok", "limiting_doors"}
    # Continuation shape.
    req2 = client.requests[1]
    assert req2["previous_interaction_id"] == "int-1"
    assert req2["environment"] == "env-1"
    # Ledger persisted.
    ledger = json.loads((tmp_path / "sessions" / inv.investigation_id / "ledger.json")
                        .read_text())
    assert [e["call_id"] for e in ledger if e["kind"] == "client_function"] == [
        "fc-eval", "fc-sub"]


async def test_disagreement_flagged(graph58, png, tmp_path):
    client = FakeClient(
        [requires_action(evaluate(["OPEN:D5"]))],
        [requires_action(submit("OPEN:D5", 70))],
        [completed()],
    )
    inv = await run(client, graph58, FIRE_D2, png, tmp_path)
    assert inv.disagreement is not None
    assert "70" in inv.disagreement and "58" in inv.disagreement
    assert inv.best.intervention_id == "OPEN:D5" and inv.best.reached_exit == 58


async def test_unknown_function_not_executed(graph58, png, tmp_path, monkeypatch):
    calls = []
    real = flow.solve
    monkeypatch.setattr(flow, "solve", lambda *a, **k: calls.append(a) or real(*a, **k))
    wf = function_call_step("write_file", {"path": "/workspace/x.py", "content": "x"}, id="fs1")
    client = FakeClient([requires_action(wf, submit(None, None))], [completed()])
    inv = await run(client, graph58, FIRE_D2, png, tmp_path)
    (entry,) = [e for e in inv.ledger if e.call_id == "fs1"]
    assert entry.kind == "sandbox_step" and entry.name == "write_file"
    assert entry.result is None
    # Only the baseline solve ran; no result was sent back for the sandbox tool.
    assert len(calls) == 1
    assert "fs1" not in sent_results(client, 1)


async def test_duplicate_call_id_not_reexecuted(graph58, png, tmp_path, monkeypatch):
    calls = []
    real = flow.solve

    def counting(graph, scenario, params):
        if scenario.interventions:
            calls.append(scenario.interventions)
        return real(graph, scenario, params)

    monkeypatch.setattr(flow, "solve", counting)
    client = FakeClient(
        [requires_action(evaluate(["OPEN:D5"], id="fc-dup"))],
        [requires_action(evaluate(["OPEN:D5"], id="fc-dup"))],  # re-emitted call
        [completed()],
    )
    inv = await run(client, graph58, FIRE_D2, png, tmp_path)
    assert len(calls) == 1
    assert sent_results(client, 1)["fc-dup"] == sent_results(client, 2)["fc-dup"]
    assert len([e for e in inv.ledger if e.call_id == "fc-dup"]) == 1


async def test_not_allowed_id(graph58, png, tmp_path):
    client = FakeClient([requires_action(evaluate(["OPEN:D1", "OPEN:D5"]))], [completed()])
    inv = await run(client, graph58, FIRE_D2, png, tmp_path)
    by_id = {r["intervention_id"]: r for r in
             sent_results(client, 1)["fc-eval"]["result"]["results"]}
    assert by_id["OPEN:D1"]["error"] == "not_allowed"
    assert by_id["OPEN:D5"]["reached_exit"] == 58
    assert [r.intervention_id for r in inv.results] == ["OPEN:D5"]


async def test_bad_arguments_rejected(graph58, png, tmp_path):
    ids = ["OPEN:D5"] * 5
    client = FakeClient([requires_action(evaluate(ids))], [completed()])
    await run(client, graph58, FIRE_D2, png, tmp_path)
    assert sent_results(client, 1)["fc-eval"]["result"]["error"] == "bad_arguments"


async def test_no_improvement_best_none(graph58, png, tmp_path):
    client = FakeClient(
        [requires_action(evaluate(["OPEN:D5"]))],
        [requires_action(submit("OPEN:D5", 58))],
        [completed()],
    )
    inv = await run(client, graph58, Scenario(), png, tmp_path, params=FlowParams())
    assert inv.results[0].delta_vs_current == 0
    assert inv.best is None
    assert inv.verdict == "No allowed change improves this case"
    assert inv.status == "completed"


async def test_incomplete_resumes_once(graph58, png, tmp_path):
    client = FakeClient([{"status": "incomplete", "environment_id": "env-1"}],
                        [{"status": "incomplete", "environment_id": "env-1"}],
                        [completed()])
    inv = await run(client, graph58, FIRE_D2, png, tmp_path)
    assert inv.status == "incomplete"
    assert len(client.requests) == 2
    assert client.requests[1]["previous_interaction_id"] == "int-1"
    assert client.requests[1]["environment"] == "env-1"
    assert client.requests[1]["agent_config"]["max_total_tokens"] == 300000


async def test_incomplete_then_completed(graph58, png, tmp_path):
    client = FakeClient([{"status": "incomplete", "environment_id": "env-1"}], [completed()])
    inv = await run(client, graph58, FIRE_D2, png, tmp_path)
    assert inv.status == "completed"


async def test_request_shape(graph58, png, tmp_path):
    client = FakeClient([completed()])
    await run(client, graph58, FIRE_D2, png, tmp_path)
    req = client.requests[0]
    assert req["agent"] == "antigravity-preview-09-2026"
    assert req["agent_config"] == {"type": "antigravity", "model": "gemini-4-argon",
                                   "max_total_tokens": 300000}
    assert req["agent_config"]["model"] == "gemini-4-argon"
    types_ = [t["type"] for t in req["tools"]]
    names = {t.get("name") for t in req["tools"] if t["type"] == "function"}
    assert "code_execution" in types_
    assert names == {"evaluate_interventions", "submit_recommendation"}
    assert "google_search" not in types_ and "url_context" not in types_
    images = [p for p in req["input"] if p["type"] == "image"]
    assert len(images) == 1 and images[0]["mime_type"] == "image/png" and images[0]["data"]
    text = next(p["text"] for p in req["input"] if p["type"] == "text")
    assert "40/58" in text and "OPEN:D5" in text and "D2" in text
    env = req["environment"]
    assert env["environment_id"] == "env-1" and env["network"] == "disabled"
    targets = {s["target"]: s for s in env["sources"]}
    scen = json.loads(targets["/workspace/scenario.json"]["content"])
    assert scen["hazards"][0]["door_id"] == "D2"
    assert "/workspace/accepted_graph.json" in targets


async def test_deadline_cancels(graph58, png, tmp_path):
    client = FakeClient(["in_progress"])
    inv = await run(client, graph58, FIRE_D2, png, tmp_path, deadline_s=0.05)
    assert inv.status == "timeout"
    assert client.cancel_calls == ["int-1"]
    assert inv.interaction_id == "int-1"


async def test_resume_reuses_persisted_ledger(graph58, png, tmp_path, monkeypatch):
    first = FakeClient([requires_action(evaluate(["OPEN:D5"]))], [{"status": "failed"}])
    inv1 = await run(first, graph58, FIRE_D2, png, tmp_path)
    calls = []
    real = flow.solve
    monkeypatch.setattr(flow, "solve", lambda g, sc, p: (
        calls.append(sc.interventions) if sc.interventions else None) or real(g, sc, p))
    again = FakeClient([requires_action(evaluate(["OPEN:D5"]))], [completed()])
    inv2 = await run(again, graph58, FIRE_D2, png, tmp_path,
                     investigation_id=inv1.investigation_id)
    assert calls == []  # stored result reused, solver not re-run
    assert inv2.best.intervention_id == "OPEN:D5"


async def test_max_rounds_stops(graph58, png, tmp_path):
    scripts = [[requires_action(evaluate(["OPEN:D5"], id=f"fc{i}"))] for i in range(5)]
    client = FakeClient(*scripts)
    inv = await run(client, graph58, FIRE_D2, png, tmp_path, max_rounds=2)
    assert len(client.requests) == 2
    assert inv.status == "incomplete"


async def test_failed_status(graph58, png, tmp_path):
    client = FakeClient([{"status": "failed"}])
    inv = await run(client, graph58, FIRE_D2, png, tmp_path)
    assert inv.status == "failed" and inv.best is None


async def test_hook_denials_counted(graph58, png, tmp_path):
    denied = {"type": "code_execution_result", "call_id": "ce1", "is_error": True,
              "result": f"{agent.HOOK_DENY_MARKER}: accepted graph is read-only"}
    client = FakeClient([{**completed(), "steps": [code_execution_step("ce1"), denied]}])
    inv = await run(client, graph58, FIRE_D2, png, tmp_path)
    assert inv.hook_denials == 1
    assert inv.sandbox_runs == 1


# --- environment ------------------------------------------------------------------


async def test_prepare_environment_caches(tmp_path):
    client = FakeClient([{"status": "completed", "environment_id": "env-prep",
                          "steps": [text_step("installed")]}])
    cache = tmp_path / "agent_env.json"
    env_id = await agent.prepare_environment(client, cache_path=cache, poll_s=0.001)
    assert env_id == "env-prep"
    req = client.requests[0]
    env = req["environment"]
    assert env["type"] == "remote" and env["network"] != "disabled"
    targets = {s["target"] for s in env["sources"]}
    assert {"/workspace/walktwin/flow.py", "/workspace/walktwin/contracts.py",
            "/workspace/walktwin/graph_checks.py", ".agents/AGENTS.md",
            ".agents/skills/sweep/SKILL.md", ".agents/skills/ada/SKILL.md",
            ".agents/hooks.json", ".agents/hooks-scripts/pre_tool_execution.py"} <= targets
    assert sum(len(s["content"].encode()) for s in env["sources"]) < 2_000_000
    assert "pip install networkx pydantic" in req["input"]
    assert req["agent_config"]["model"] == "gemini-4-argon"
    # Cached: second call makes no request.
    again = await agent.prepare_environment(FakeClient(), cache_path=cache)
    assert again == "env-prep"


# --- audit hook -------------------------------------------------------------------


def _hook():
    path = REPO / "agent_env" / "hooks" / "pre_tool_execution.py"
    spec = importlib.util.spec_from_file_location("walktwin_hook", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("payload, decision", [
    ({"tool_call": {"name": "write_to_file",
                    "args": {"path": "/workspace/accepted_graph.json", "content": "{}"}}}, "deny"),
    ({"tool_call": {"name": "replace_file_content",
                    "args": {"TargetFile": "accepted_graph.json"}}}, "deny"),
    ({"tool_call": {"name": "code_execution", "args": {
        "code": "json.dump(g, open('/workspace/accepted_graph.json', 'w'))"}}}, "deny"),
    ({"tool_call": {"name": "code_execution", "args": {
        "code": "echo {} > /workspace/accepted_graph.json", "language": "bash"}}}, "deny"),
    ({"tool_call": {"name": "view_file", "args": {"path": "/workspace/accepted_graph.json"}}},
     "allow"),
    ({"tool_call": {"name": "code_execution", "args": {
        "code": "g = json.load(open('/workspace/accepted_graph.json'))"}}}, "allow"),
    ({"tool_call": {"name": "write_to_file", "args": {"path": "/workspace/sweep.py"}}}, "allow"),
    ({"tool_call": {"name": "code_execution", "args": {
        "code": "cp /workspace/accepted_graph.json /workspace/work/graph.json"}}}, "allow"),
    ({"tool_call": {"name": "code_execution", "args": {
        "code": "cp /workspace/work/graph.json /workspace/accepted_graph.json"}}}, "deny"),
    ({"tool_call": {"name": "code_execution", "args": {
        "code": "rm /.agents/hooks.json"}}}, "deny"),
    ({"tool_call": {"name": "write_to_file", "args": {"path": "/.agents/hooks.json"}}}, "deny"),
    ({"unexpected": True}, "allow"),
    ("not a dict", "allow"),
])
def test_hook_decision(payload, decision):
    out = _hook().decide(payload)
    assert out["decision"] == decision
    if decision == "deny":
        assert out["reason"].startswith(agent.HOOK_DENY_MARKER)
