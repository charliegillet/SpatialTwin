import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.venues import schemas
from backend.app.venues.model import VENUE_FILE, VenueV2, VenueDoor, VenueExit, VenueZone, HazardDefaults

TYPES_TS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "twin" / "types.ts"


@pytest.fixture
def client():
    return TestClient(main.app)


def body(hazards, **extra):
    return {"hazards": [{"id": f"h{i}", "type": t, "position": {"x": x, "y": y}, "source": "simulated"}
                        for i, (t, x, y) in enumerate(hazards)], **extra}


def test_get_venue_returns_file(client):
    response = client.get("/api/venues/building-v2")
    assert response.status_code == 200
    assert response.json() == json.loads(VENUE_FILE.read_text())


def test_unknown_venue_404(client):
    for response in (client.get("/api/venues/nope"), client.post("/api/venues/tabletop-v1/door-plan", json=body([]))):
        assert response.status_code == 404 and response.json() == {"detail": {"code": "unknown_venue"}}


def test_post_door_plan_ok(client):
    response = client.post("/api/venues/building-v2/door-plan", json=body([("FIRE", 20, 4)]))
    assert response.status_code == 200
    data = response.json()
    assert data["provenance"] == "local_door_planner_v1" and data["hypothetical"] is True
    assert data["chosen"]["completed_crossings"] == 125 and data["baseline"]["completed_crossings"] == 96
    assert data["timings_ms"] > 0


@pytest.mark.parametrize("payload, code", [
    (body([("FIRE", 20, 4)] * 7), "too_many_hazards"),
    (body([("FIRE", 20, 4)], horizon_seconds=7), "invalid_horizon"),
    (body([("FIRE", 99, 99)]), "outside_building"),
    ({"hazards": [{"id": "a", "type": "FIRE", "position": {"x": 20, "y": 4}, "source": "simulated", "zone_id": "HALL"}]}, "zone_mismatch"),
    ({"hazards": [{"id": "a", "type": "FIRE", "position": {"x": 20, "y": 4}, "source": "simulated", "untenable_s": 7}]}, "invalid_untenable_time"),
    ({"hazards": [{"id": "a", "type": "FIRE", "position": {"x": 20, "y": 4}, "source": "simulated"},
                  {"id": "a", "type": "GAS", "position": {"x": 20, "y": 14}, "source": "simulated"}]}, "duplicate_hazard_id"),
])
def test_422_codes(client, payload, code):
    response = client.post("/api/venues/building-v2/door-plan", json=payload)
    assert response.status_code == 422 and response.json() == {"detail": {"code": code}}


@pytest.mark.parametrize("payload", [
    {"hazards": [{"id": "a", "type": "LAVA", "position": {"x": 1, "y": 1}, "source": "simulated"}]},
    {"hazards": [{"id": "a", "type": "FIRE", "position": {"x": 1}, "source": "simulated"}]},
    {"hazards": [], "surprise": 1},
    {},
])
def test_malformed_body_uses_app_wide_422(client, payload):
    response = client.post("/api/venues/building-v2/door-plan", json=payload)
    assert response.status_code == 422 and response.json()["detail"] == "Invalid request"


def interface_fields(name):
    text = TYPES_TS.read_text()
    match = re.search(rf"export interface {name}(?: extends \w+)? \{{(.*?)\n\}}", text, re.S)
    assert match, name
    inherited = re.search(rf"export interface {name} extends (\w+)", text)
    fields = set(re.findall(r"^\s{2}(\w+)\??:", match.group(1), re.M))
    return fields | (interface_fields(inherited.group(1)) if inherited else set())


@pytest.mark.parametrize("ts_name, model", [
    ("VenueV2", VenueV2), ("VenueZone", VenueZone), ("VenueDoor", VenueDoor), ("VenueExit", VenueExit),
    ("HazardDefaults", HazardDefaults),
    ("HazardInput", schemas.HazardInput), ("DoorPlanRequest", schemas.DoorPlanRequest),
    ("HazardEcho", schemas.HazardEcho), ("PlanDoor", schemas.PlanDoor), ("PlanExit", schemas.PlanExit),
    ("PlanZone", schemas.PlanZone), ("PlanRoute", schemas.PlanRoute), ("TimelineFrameV2", schemas.TimelineFrameV2),
    ("ValidatorReportV2", schemas.ValidatorReportV2), ("PlanOutcome", schemas.PlanOutcome),
    ("PlanAlternative", schemas.PlanAlternative), ("LightSegment", schemas.LightSegment),
    ("PlanLights", schemas.PlanLights), ("DoorPlanResponse", schemas.DoorPlanResponse),
])
def test_models_match_types_ts_field_names(ts_name, model):
    assert set(model.model_fields) == interface_fields(ts_name), ts_name


def test_baseline_shape_matches_inline_ts_type():
    assert set(schemas.Baseline.model_fields) == {"completed_crossings", "run_id"}
