import pytest
from backend.app.ai.managed.adapter import ManagedAgentAdapter
from backend.app.contracts import AlternativeId, InvestigationStatus
from backend.app.state.manager import StateManager
from backend.app.state.service import ScenarioService


@pytest.fixture
def state_manager():
    return StateManager()


@pytest.fixture
def scenario_service(state_manager):
    return ScenarioService(state_manager)


@pytest.fixture
def managed_adapter(scenario_service):
    return ManagedAgentAdapter(scenario_service, api_key="none")


@pytest.mark.asyncio
async def test_managed_investigation_tool_loop(state_manager, managed_adapter):
    ctx = state_manager.get_current_context()
    result = await managed_adapter.investigate_scenario(ctx)

    assert result.status == InvestigationStatus.COMPLETED
    assert len(result.tool_ledger) >= 3
    # Check that tools were actually executed locally
    executed_tools = [e.function_name for e in result.tool_ledger if e.status == "executed"]
    assert "get_reviewed_scenario" in executed_tools
    assert "evaluate_allowed_alternative" in executed_tools
    assert "get_checked_comparison" in executed_tools

    # Baseline: both KEEP_CURRENT and OPEN_P3 should have 120 completed
    assert result.recommended_alternative == AlternativeId.KEEP_CURRENT
