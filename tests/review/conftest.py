"""Review tests start from an observed CLOSED reserve on an isolated store."""
import pytest

from backend.app.contracts import GateObservedState
from backend.app.state.manager import StateManager
from backend.app.state.store import SQLiteStore


@pytest.fixture
def manager(tmp_path):
    state = StateManager(SQLiteStore(str(tmp_path / "review.sqlite3")))
    state.update_physical_observation(GateObservedState.CLOSED, "boot-review", 1, 1)
    return state
