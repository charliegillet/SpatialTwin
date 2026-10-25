import pytest

from backend.app.venues.model import load_building_v2
from backend.app.venues.schemas import DoorPlanRequest


@pytest.fixture(scope="session")
def venue():
    return load_building_v2()


def make_request(hazards, **extra):
    return DoorPlanRequest(hazards=[
        {"id": f"h{i}", "type": t, "position": {"x": x, "y": y}, "source": "simulated", **opts}
        for i, (t, x, y, *rest) in enumerate(hazards) for opts in [rest[0] if rest else {}]
    ], **extra)
