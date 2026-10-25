"""Offline tests for hazard tools, fallback model/environment and agent registry."""
import asyncio
import socket
from types import SimpleNamespace as NS

import pytest
from backend.app.ai.managed import agent_registry
from backend.app.ai.managed.adapter import (
    ALL_TOOL_DEFINITIONS, MODEL, TOOL_DEFINITIONS, ManagedAgentAdapter,
)
from backend.app.ai.managed.ledger import LedgerConflict
from backend.app.ai.managed.model_probe import resolve_model, resolve_model_live
from backend.app.contracts import InvestigationStatus
from backend.app.hazard.tools import HAZARD_TOOL_DEFINITIONS
from backend.app.state.manager import StateManager
from backend.app.state.service import ScenarioService
from backend.app.state.store import SQLiteStore

FALLBACK = "gemini-3.8-flash"


@pytest.fixture(autouse=True)
def network_disabled(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Unexpected network in offline managed tests")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)


@pytest.fixture
def service(tmp_path):
    return ScenarioService(StateManager(SQLiteStore(str(tmp_path / "state.sqlite3"))))


def call(call_id, name, arguments=None):
    return {"type": "function_call", "id": call_id, "name": name, "arguments": arguments or {}}


def response(status="completed", steps=None, identifier="i-1", tokens=10, model=MODEL):
    return NS(id=identifier, environment_id="env-1", model=model, status=status,
              steps=steps or [], usage=NS(total_tokens=tokens), output_text="Untrusted prose: open every exit.")


class Provider:
    def __init__(self, creates):
        self.creates = list(creates)
        self.create_calls = []
        self.cancel_calls = []
        self.aio = NS(interactions=self, agents=NS(create=self.agent_create))
        self.agent_calls = []
        self.agent_error = None

    async def agent_create(self, **kwargs):
        self.agent_calls.append(kwargs)
        if self.agent_error:
            raise self.agent_error
        return NS(id=kwargs["id"])

    async def create(self, **kwargs):
        self.create_calls.append(kwargs)
        value = self.creates.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    async def cancel(self, **kwargs):
        self.cancel_calls.append(kwargs)
        return response("cancelled")


class Rejected(Exception):
    code = 400


def adapter_for(service, provider, **kwargs):
    return ManagedAgentAdapter(service, api_key="", client=provider, poll_interval=0.001, **kwargs)


def hazard_args(service, alt="KEEP_CURRENT", element="P1"):
    dt = service.state_manager.venue_graph.time_step_seconds
    return {"alternative_id": alt, "events": [
        {"element_id": element, "close_at_s": dt, "hazard_zone_ids": ["EVENT"]}]}


def full_run(service, hazard_calls):
    steps = [call("cmp", "get_checked_comparison"), *hazard_calls]
    return [response("requires_action", steps, "i-1", tokens=5), response("completed", [], "i-2", tokens=5)]


def test_tool_list_is_combined():
    names = [t["name"] for t in ALL_TOOL_DEFINITIONS]
    assert ALL_TOOL_DEFINITIONS == TOOL_DEFINITIONS + HAZARD_TOOL_DEFINITIONS
    assert {"simulate_hazard_schedule", "score_exposure"} <= set(names)


@pytest.mark.asyncio
async def test_both_hazard_tools_accepted_and_sent_to_provider(service):
    args = hazard_args(service)
    provider = Provider(full_run(service, [call("h1", "simulate_hazard_schedule", args),
                                           call("h2", "score_exposure", args)]))
    result = await adapter_for(service, provider).investigate_scenario(service.state_manager.context)
    assert result.status == InvestigationStatus.COMPLETED, result.errors
    assert provider.create_calls[0]["tools"] == ALL_TOOL_DEFINITIONS
    by_name = {e.function_name: e for e in result.tool_ledger}
    assert by_name["score_exposure"].result["modeled_exposure_people_seconds"] is not None
    assert by_name["simulate_hazard_schedule"].result["modeled_exposure_people_seconds"] is None
    assert by_name["score_exposure"].status == "executed"


@pytest.mark.asyncio
@pytest.mark.parametrize("name,arguments,code", [
    ("set_servo", {}, "tool_not_allowed"),
    ("score_exposure", {**{"alternative_id": "KEEP_CURRENT", "events": []}, "extra": 1}, "invalid_tool_arguments"),
    ("simulate_hazard_schedule", {"alternative_id": "KEEP_CURRENT"}, "invalid_tool_arguments"),
])
async def test_unknown_tool_and_extra_arguments_rejected(service, name, arguments, code):
    provider = Provider([response("requires_action", [call("x", name, arguments)])])
    result = await adapter_for(service, provider).investigate_scenario(service.state_manager.context)
    assert result.status == InvestigationStatus.FAILED
    assert code in result.errors
    assert result.recommended_alternative is None


@pytest.mark.asyncio
async def test_invalid_hazard_event_fails_with_fixed_code(service):
    bad = hazard_args(service, element="NOPE")
    provider = Provider([response("requires_action", [call("x", "score_exposure", bad)])])
    result = await adapter_for(service, provider).investigate_scenario(service.state_manager.context)
    assert result.status == InvestigationStatus.FAILED
    assert "invalid_arguments" in result.errors


@pytest.mark.asyncio
async def test_cap_of_six_per_hazard_tool_and_duplicates_idempotent(service):
    args = hazard_args(service)
    calls = [call(f"h{i}", "score_exposure", args) for i in range(8)]
    provider = Provider([response("requires_action", calls)])
    result = await adapter_for(service, provider).investigate_scenario(service.state_manager.context)
    assert "tool_call_limit" in result.errors
    assert len(result.tool_ledger) == 6

    ledger = adapter_for(service, Provider([])).ledger
    for i in range(6):
        assert ledger.claim("inv", f"c{i}", "score_exposure", args, 6) is None
        ledger.finish_call("inv", f"c{i}", {"call_id": f"c{i}"})
    assert ledger.claim("inv", "c0", "score_exposure", args, 6) == {"call_id": "c0"}
    with pytest.raises(LedgerConflict, match="tool_call_limit"):
        ledger.claim("inv", "c6", "score_exposure", args, 6)


@pytest.mark.asyncio
async def test_duplicate_hazard_call_id_is_idempotent(service):
    args = hazard_args(service)
    steps = [call("cmp", "get_checked_comparison"), call("h", "score_exposure", args)]
    first = response("requires_action", steps, "i-1")
    provider = Provider([first, response("completed", [], "i-2")])
    result = await adapter_for(service, provider).investigate_scenario(service.state_manager.context)
    assert result.status == InvestigationStatus.COMPLETED
    adapter = adapter_for(service, Provider([]))
    inv = result.investigation_id
    again = await adapter._execute_local_tool("score_exposure", args, service.state_manager.context, "h", inv)
    assert again.status == "duplicate"
    assert again.result == next(e.result for e in result.tool_ledger if e.call_id == "h")


@pytest.mark.asyncio
async def test_token_budget_exhaustion_gives_local_only_result(service):
    provider = Provider([response("requires_action", [call("cmp", "get_checked_comparison")], tokens=20_001)])
    result = await adapter_for(service, provider).investigate_scenario(service.state_manager.context)
    assert result.status == InvestigationStatus.FAILED
    assert "token_budget_exhausted" in result.errors
    assert result.recommended_alternative is None


@pytest.mark.asyncio
async def test_model_fallback_is_recorded_and_label_is_fallback(service):
    provider = Provider(full_run(service, []))
    provider.creates = [response("requires_action", [call("cmp", "get_checked_comparison")], model=FALLBACK),
                        response("completed", [], "i-2", model=FALLBACK)]
    adapter = adapter_for(service, provider, model=FALLBACK)
    result = await adapter.investigate_scenario(service.state_manager.context)
    assert result.status == InvestigationStatus.COMPLETED, result.errors
    assert result.provider_model == result.configured_model == FALLBACK
    assert provider.create_calls[0]["agent_config"]["model"] == FALLBACK
    assert any(e["phase"] == "model_fallback" for e in result.provider_progress)


@pytest.mark.asyncio
async def test_model_mismatch_still_fails(service):
    provider = Provider([response("completed", model="some-other-model")])
    result = await adapter_for(service, provider, model=FALLBACK).investigate_scenario(service.state_manager.context)
    assert result.status == InvestigationStatus.FAILED
    assert "provider_model_mismatch" in result.errors


def test_resolve_model_offline_cache(tmp_path):
    cache = str(tmp_path / "m.json")
    assert resolve_model(cache_path=cache) is None

    async def run(accept):
        return await resolve_model_live(accept, cache_path=cache)
    fallback = asyncio.run(run(lambda m: _async(m == FALLBACK)))
    assert fallback.model == FALLBACK and fallback.provenance == "live (fallback model)"
    assert resolve_model(cache_path=cache) == fallback
    first = asyncio.run(run(lambda m: _async(True)))
    assert first.model == MODEL and first.provenance == "live"
    assert asyncio.run(run(lambda m: _async(False))) is None


async def _async(value):
    return value


@pytest.mark.asyncio
async def test_recommendation_text_uses_only_checked_fields(service):
    args = hazard_args(service)
    provider = Provider(full_run(service, [call("h", "score_exposure", args)]))
    result = await adapter_for(service, provider).investigate_scenario(service.state_manager.context)
    keep = next(c for c in result.candidate_envelopes if c.alternative_id.value == "KEEP_CURRENT")
    opened = next(c for c in result.candidate_envelopes if c.alternative_id.value == "OPEN_P3")
    gain = opened.completed_crossings - keep.completed_crossings
    assert f"{gain:+d}" in result.agent_explanation
    assert "Untrusted" not in result.agent_explanation and "open every exit" not in result.agent_explanation


@pytest.mark.asyncio
async def test_cancelled_investigation_does_not_write_ledger(service):
    started = asyncio.Event()

    async def slow(**kwargs):
        started.set()
        await asyncio.sleep(10)
    provider = Provider([])
    provider.create = slow
    adapter = adapter_for(service, provider)
    task = asyncio.create_task(adapter.investigate_scenario(service.state_manager.context, "cancel-run"))
    await started.wait()
    task.cancel()
    result = await task
    assert result.status == InvestigationStatus.CANCELLED
    assert result.tool_ledger == []
    assert adapter.ledger.calls("cancel-run") == []


@pytest.mark.asyncio
async def test_ensure_agent_makes_no_call_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv(agent_registry.ENABLE_ENV, raising=False)
    provider = Provider([])
    assert await agent_registry.ensure_agent(provider, cache_path=str(tmp_path / "a.json")) is None
    assert provider.agent_calls == []


@pytest.mark.asyncio
async def test_ensure_agent_creates_once_caches_and_falls_back_on_error(tmp_path):
    cache = str(tmp_path / "agent.json")
    failing = Provider([])
    failing.agent_error = Rejected()
    assert await agent_registry.ensure_agent(failing, enabled=True, cache_path=cache) is None
    ok = Provider([])
    ref = await agent_registry.ensure_agent(ok, enabled=True, cache_path=cache)
    assert ref.agent_id == "spatialtwin-evac-v1" and ref.created
    assert ok.agent_calls[0]["base_agent"] == "antigravity-preview-09-2026"
    assert "AI proposes" in ok.agent_calls[0]["system_instruction"]
    again = await agent_registry.ensure_agent(ok, enabled=True, cache_path=cache)
    assert again.agent_id == ref.agent_id and len(ok.agent_calls) == 1


@pytest.mark.asyncio
async def test_agent_ref_used_for_create(service):
    provider = Provider([response("completed", [])])
    ref = agent_registry.AgentRef("spatialtwin-evac-v1")
    await adapter_for(service, provider, agent_ref=ref).investigate_scenario(service.state_manager.context)
    assert provider.create_calls[0]["agent"] == "spatialtwin-evac-v1"


def test_build_environment_shape():
    assert agent_registry.build_environment(False) == "remote"
    assert agent_registry.build_environment(True) == {"type": "remote", "network": "disabled"}


@pytest.mark.asyncio
async def test_network_deny_rejection_fails_without_downgrading_to_remote(service):
    env = agent_registry.build_environment(True)
    provider = Provider([Rejected(), response("completed", [])])
    result = await adapter_for(service, provider, environment=env).investigate_scenario(service.state_manager.context)
    assert len(provider.create_calls) == 1 and provider.create_calls[0]["environment"] == env
    assert result.status == InvestigationStatus.FAILED
    assert result.errors == ["network_deny_rejected"]
    assert not any(e["phase"] == "environment_fallback" for e in result.provider_progress)


@pytest.mark.asyncio
async def test_plain_remote_rejection_keeps_generic_code(service):
    provider = Provider([Rejected()])
    result = await adapter_for(service, provider).investigate_scenario(service.state_manager.context)
    assert result.errors == ["provider_request_rejected"]


@pytest.mark.asyncio
async def test_named_agent_run_sends_no_model_override(service):
    # Regression (P5): the provider refuses an interaction-time model override on a named agent.
    provider = Provider([response("completed", [])])
    ref = agent_registry.AgentRef("spatialtwin-evac-v1")
    await adapter_for(service, provider, agent_ref=ref).investigate_scenario(service.state_manager.context)
    assert "agent_config" not in provider.create_calls[0]


@pytest.mark.asyncio
async def test_base_agent_run_still_sends_model_and_budget(service):
    provider = Provider([response("completed", [])])
    await adapter_for(service, provider).investigate_scenario(service.state_manager.context)
    config = provider.create_calls[0]["agent_config"]
    assert config["model"] == "gemini-4-argon" and config["max_total_tokens"] > 0


def test_resolution_reads_the_key_the_live_probe_writes(tmp_path):
    # Regression: the probe writes resolved_managed_model; the reader used to look for "model" only,
    # so the app never reported the resolved model after a passing P1.
    from backend.app.ai.managed import model_probe
    cache = tmp_path / "model_resolution.json"
    cache.write_text('{"managed_available": true, "resolved_managed_model": "gemini-4-argon"}')
    resolution = model_probe.resolve_model(cache_path=str(cache))
    assert resolution is not None and resolution.model == "gemini-4-argon" and not resolution.is_fallback


# ---- review-finding regressions -------------------------------------------------------------


def test_hazard_context_carries_live_state_and_baseline_reason(service, monkeypatch):
    from backend.app.ai.managed import adapter as adapter_mod
    seen = {}

    def spy(name, arguments, ctx):
        seen["ctx"] = ctx
        return {"tool": name}
    monkeypatch.setattr(adapter_mod, "execute_hazard_tool", spy)
    manager = service.state_manager
    manager.blocked_portals.add("P2")
    manager.blocked_boundaries.add("B1")
    adapter = adapter_for(service, Provider([]))
    result = adapter._hazard_result("inv-live", "score_exposure", hazard_args(service), manager.context)
    assert seen["ctx"].blocked_portals == frozenset({"P2"})
    assert seen["ctx"].blocked_boundaries == frozenset({"B1"})
    assert seen["ctx"].p3_physical_open is False
    assert "baseline_unavailable_reason" not in result

    def broken(_investigation_id):
        raise RuntimeError("db down")
    monkeypatch.setattr(adapter.ledger, "calls", broken)
    result = adapter._hazard_result("inv-live", "score_exposure", hazard_args(service), manager.context)
    assert result["baseline_unavailable_reason"] == "baseline_load_failed"


def test_tool_payload_missing_context_is_explicit(service):
    from backend.app.ai.managed.adapter import InvestigationError
    from backend.app.contracts import ToolCallLedgerEntry
    entry = ToolCallLedgerEntry(call_id="c", function_name="get_checked_comparison", arguments={},
                                status="executed", result={"keep_current": {}, "open_p3": {}},
                                execution_time_ms=0.0)
    with pytest.raises(InvestigationError, match="invalid_comparison_result"):
        ManagedAgentAdapter._tool_payload(entry)


def test_finish_call_failure_becomes_terminal_call_error(service, monkeypatch):
    adapter = adapter_for(service, Provider([]))
    ctx = service.state_manager.context
    adapter.ledger.claim("inv-fc", "c1", "get_reviewed_scenario", {}, 4)
    real = adapter.ledger.finish_call
    calls = []

    def flaky(*a):
        calls.append(a)
        if len(calls) == 1:
            raise RuntimeError("disk")
        return real(*a)
    monkeypatch.setattr(adapter.ledger, "finish_call", flaky)
    entry = adapter._worker("inv-fc", "c1", "get_reviewed_scenario", {}, ctx)
    assert entry.status == "failed" and entry.error == "call_finalization_failed"
    assert adapter.ledger.calls("inv-fc")[0]["status"] == "failed"


@pytest.mark.asyncio
async def test_result_construction_failure_still_finalizes_owner_row(service, monkeypatch):
    from backend.app.ai.managed import adapter as adapter_mod
    real = adapter_mod.InvestigationResult

    class Flaky(real):
        def __init__(self, **kwargs):
            if "candidate_envelopes" in kwargs:
                raise ValueError("boom")
            super().__init__(**kwargs)
    monkeypatch.setattr(adapter_mod, "InvestigationResult", Flaky)
    adapter = adapter_for(service, Provider([]))
    result = await adapter.investigate_scenario(service.state_manager.context, "inv-rc", mode="local")
    assert result.status == InvestigationStatus.FAILED and "result_construction_failed" in result.errors
    with adapter.ledger._lock:
        state = adapter.ledger._connection.execute(
            "SELECT state FROM managed_runs_v1 WHERE investigation_id='inv-rc'").fetchone()[0]
    assert state == "finished"


@pytest.mark.asyncio
async def test_unpublishable_owner_row_is_aborted_not_running(service, monkeypatch):
    adapter = adapter_for(service, Provider([]))

    def explode(*a, **k):
        raise RuntimeError("publish bug")
    monkeypatch.setattr(adapter, "_publish_result", explode)
    with pytest.raises(RuntimeError):
        await adapter.investigate_scenario(service.state_manager.context, "inv-ab", mode="local")
    with adapter.ledger._lock:
        state = adapter.ledger._connection.execute(
            "SELECT state FROM managed_runs_v1 WHERE investigation_id='inv-ab'").fetchone()[0]
    assert state == "aborted"


def test_ledger_maps_sqlite_errors_to_fixed_codes(service, monkeypatch):
    import sqlite3
    from backend.app.ai.managed import ledger as ledger_mod
    adapter = adapter_for(service, Provider([]))
    path = service.state_manager.store.db_path
    other = sqlite3.connect(path, isolation_level=None)
    other.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(LedgerConflict) as claim_error:
            adapter.ledger.claim("inv-l", "c", "get_reviewed_scenario", {}, 4)
        assert str(claim_error.value) == "tool_storage_busy"
        monkeypatch.setattr(ledger_mod, "PUBLISH_BUSY_TIMEOUT_MS", 50)
        adapter.ledger._connection.rollback()
        with pytest.raises(LedgerConflict) as publish_error:
            adapter.ledger.publish("inv-l", "{}")
        assert str(publish_error.value) == "result_persistence_busy"
    finally:
        other.execute("ROLLBACK")
        other.close()
    assert ledger_mod.PUBLISH_BUSY_TIMEOUT_MS != 0
    assert ledger_mod._storage_code(sqlite3.OperationalError("x"), "busy", "failed") == "failed"


@pytest.mark.asyncio
async def test_agent_created_is_returned_even_if_cache_write_fails(tmp_path):
    provider = Provider([])
    blocker = tmp_path / "file"
    blocker.write_text("x")
    ref = await agent_registry.ensure_agent(provider, enabled=True, cache_path=str(blocker / "sub" / "a.json"))
    assert ref is not None and ref.created is True and len(provider.agent_calls) == 1


def test_default_caches_are_anchored_to_repo_root():
    from pathlib import Path
    from backend.app.ai.managed import model_probe
    root = Path(agent_registry.__file__).resolve().parents[4]
    assert (root / "backend").is_dir()
    for default in (agent_registry.DEFAULT_CACHE, model_probe.DEFAULT_CACHE):
        assert Path(default).is_absolute() and Path(default).is_relative_to(root)


def test_model_probe_does_not_cache_fallback_on_transient_error(tmp_path):
    cache = tmp_path / "m.json"

    async def transient(model):
        raise TimeoutError()
    assert asyncio.run(resolve_model_live(transient, cache_path=str(cache))) is None
    assert not cache.exists()

    async def rejected_then_ok(model):
        if model == MODEL:
            raise Rejected()
        return True
    resolution = asyncio.run(resolve_model_live(rejected_then_ok, cache_path=str(cache)))
    assert resolution.model == FALLBACK and resolution.is_fallback
    assert resolve_model(cache_path=str(cache)) == resolution


def test_resolve_model_reads_legacy_model_key(tmp_path):
    cache = tmp_path / "m.json"
    cache.write_text('{"model": "gemini-3.8-flash"}')
    assert resolve_model(cache_path=str(cache)).model == FALLBACK
    cache.write_text('{"resolved_managed_model": "gemini-4-argon", "model": "gemini-3.8-flash"}')
    assert resolve_model(cache_path=str(cache)).model == MODEL
