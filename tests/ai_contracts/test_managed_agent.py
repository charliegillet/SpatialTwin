import pytest
from backend.app.ai.managed.adapter import ManagedAgentAdapter
from backend.app.contracts import AlternativeId, InvestigationStatus
from backend.app.state.manager import StateManager
from backend.app.state.service import ScenarioService
from backend.app.state.store import SQLiteStore


@pytest.mark.asyncio
@pytest.mark.parametrize("blocked_boundary,expected", [(False, AlternativeId.OPEN_P3), (True, AlternativeId.KEEP_CURRENT)])
async def test_explicit_local_investigation_uses_checked_numerical_tools(tmp_path, blocked_boundary, expected):
    state = StateManager(SQLiteStore(str(tmp_path / "state.sqlite3")))
    state.blocked_portals = {"P2"}
    state.blocked_boundaries = {"B2"} if blocked_boundary else set()
    adapter = ManagedAgentAdapter(ScenarioService(state), api_key="")
    result = await adapter.investigate_scenario(state.get_current_context(), mode="local")
    assert result.status == InvestigationStatus.COMPLETED
    assert result.provenance == "local"
    assert result.token_usage == {}
    assert result.recommended_alternative == expected
    assert len(result.candidate_envelopes) == 2
    assert all(candidate.is_publishable for candidate in result.candidate_envelopes)
    assert all(entry.status == "executed" for entry in result.tool_ledger)
    await adapter.aclose()
