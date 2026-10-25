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
async def test_network_deny_rejection_falls_back_to_remote(service):
    env = agent_registry.build_environment(True)
    provider = Provider([Rejected(), response("completed", [])])
    result = await adapter_for(service, provider, environment=env).investigate_scenario(service.state_manager.context)
    assert provider.create_calls[0]["environment"] == env
    assert provider.create_calls[1]["environment"] == "remote"
    assert any(e["phase"] == "environment_fallback" and e["used"] == "remote" for e in result.provider_progress)
