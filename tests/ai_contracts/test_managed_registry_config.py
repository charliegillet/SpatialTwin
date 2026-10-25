"""Saved managed agent: model pinned at creation, verified from its definition, used only when a run echoes no model."""
import socket
from types import SimpleNamespace as NS

import pytest

from backend.app.ai.managed import agent_registry
from backend.app.ai.managed.adapter import MODEL, ManagedAgentAdapter
from backend.app.ai.managed.agent_registry import AgentRef
from backend.app.contracts import InvestigationStatus
from backend.app.state.manager import StateManager
from backend.app.state.service import ScenarioService
from backend.app.state.store import SQLiteStore


@pytest.fixture(autouse=True)
def network_disabled(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Unexpected network in offline managed tests")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)


@pytest.fixture
def service(tmp_path):
    return ScenarioService(StateManager(SQLiteStore(str(tmp_path / "state.sqlite3"))))


class AgentClient:
    def __init__(self, definition=None):
        self.definition = definition
        self.agent_calls = []
        self.aio = NS(agents=NS(create=self.create))

    async def create(self, **kwargs):
        self.agent_calls.append(kwargs)
        return NS(id=kwargs["id"], agent_config=self.definition)


def function(call_id="comparison"):
    return {"type": "function_call", "id": call_id, "name": "get_checked_comparison", "arguments": {}}


def response(status="completed", steps=None, identifier="i-1", model=MODEL, agent_config=None):
    return NS(id=identifier, environment_id="env-1", model=model, agent_config=agent_config, status=status,
              steps=steps or [], usage=NS(total_tokens=10), output_text="")


class Provider:
    def __init__(self, creates):
        self.creates = list(creates)
        self.aio = NS(interactions=self)

    async def create(self, **kwargs):
        return self.creates.pop(0)

    async def get(self, **kwargs):
        raise AssertionError("no polling expected")

    async def cancel(self, **kwargs):
        return response("cancelled")


def named_run(service, creates, verified):
    ref = AgentRef(agent_registry.AGENT_ID, created=True, verified_model=verified)
    adapter = ManagedAgentAdapter(service, api_key="", client=Provider(creates), poll_interval=0.001, agent_ref=ref)
    return adapter.investigate_scenario(service.state_manager.context)


def echo_none_run(identifier="i-2"):
    # Named-agent run whose interaction echoes neither model nor agent_config.
    return [response("requires_action", [function()], identifier="i-1", model=None),
            response("completed", identifier=identifier, model=None, agent_config=None)]


def test_registry_model_matches_adapter_model():
    assert agent_registry.AGENT_MODEL == MODEL


@pytest.mark.asyncio
async def test_saved_agent_is_created_with_pinned_model_and_verified(tmp_path):
    client = AgentClient(definition=NS(model=MODEL))
    ref = await agent_registry.ensure_agent(client, enabled=True, cache_path=str(tmp_path / "agent.json"))
    assert ref is not None and ref.created
    assert client.agent_calls[0]["agent_config"] == {"type": "antigravity", "model": MODEL}
    assert client.agent_calls[0]["base_agent"] == agent_registry.BASE_AGENT
    assert ref.verified_model == MODEL
    again = await agent_registry.ensure_agent(client, enabled=True, cache_path=str(tmp_path / "agent.json"))
    assert again.verified_model == MODEL and len(client.agent_calls) == 1


@pytest.mark.asyncio
async def test_unverified_when_creation_response_has_no_model(tmp_path):
    client = AgentClient(definition=None)
    ref = await agent_registry.ensure_agent(client, enabled=True, cache_path=str(tmp_path / "agent.json"))
    assert ref.created and ref.verified_model is None


@pytest.mark.asyncio
async def test_run_uses_verified_definition_model_only_when_echo_is_absent(service):
    result = await named_run(service, echo_none_run(), verified=MODEL)
    assert result.status == InvestigationStatus.COMPLETED, result.errors
    assert result.provider_model == MODEL
    assert any(e.get("phase") == "model_from_agent_definition" for e in result.provider_progress)


@pytest.mark.asyncio
async def test_echo_absent_without_verified_definition_fails_closed(service):
    result = await named_run(service, echo_none_run(), verified=None)
    assert result.status != InvestigationStatus.COMPLETED
    assert "provider_model_unverified" in result.errors
    assert not any(e.get("phase") == "model_from_agent_definition" for e in result.provider_progress)


@pytest.mark.asyncio
async def test_mismatched_echo_still_fails_even_with_verified_definition(service):
    creates = [response("requires_action", [function()], identifier="i-1", model=None),
               response("completed", identifier="i-2", model="gemini-3.8-flash")]
    result = await named_run(service, creates, verified=MODEL)
    assert "provider_model_mismatch" in result.errors
    assert result.status != InvestigationStatus.COMPLETED


@pytest.mark.asyncio
async def test_cached_reference_keeps_verified_model(tmp_path):
    client = AgentClient(definition=NS(model=MODEL))
    cache = str(tmp_path / "agent.json")
    await agent_registry.ensure_agent(client, enabled=True, cache_path=cache)
    cached = agent_registry._read_cache(tmp_path / "agent.json")
    assert cached.verified_model == MODEL
