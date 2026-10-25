from pathlib import Path

import pytest

from walktwin.contracts import VenueGraph

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def office_graph() -> VenueGraph:
    return VenueGraph.model_validate_json((FIXTURES / "office_graph.json").read_text())
