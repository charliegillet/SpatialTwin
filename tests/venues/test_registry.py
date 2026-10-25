"""Accepted venues, drafts and the active pointer change only under compare-and-set revisions."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.hazard.door_planner import plan_doors
from backend.app.venues.model import VenueV2, get_venue
from backend.app.venues.registry import RegistryConflict, VenueRegistry, venue_registry
from backend.app.venues.schemas import DoorPlanRequest

HOME = json.loads((Path(__file__).parent / "fixtures" / "home_flat.json").read_text())


@pytest.fixture
def home() -> VenueV2:
    return VenueV2.model_validate(HOME)


def test_builtin_is_listed_active_and_read_only(home):
    registry = venue_registry()
    assert registry.active() == {"venue_id": "building-v2", "revision": 0}
    assert [v["venue_id"] for v in registry.list_venues()] == ["building-v2"]
    with pytest.raises(RegistryConflict, match="builtin_venue_read_only"):
        registry.save_venue(VenueV2.model_validate({**HOME, "venue_id": "building-v2"}), {})


def test_saved_venue_resolves_and_revisions_grow(home):
    registry = venue_registry()
    assert get_venue("home-flat") is None
    assert registry.save_venue(home, {"name": "Test flat", "source_kind": "hand_written"}) == 1
    assert get_venue("home-flat") == home
    assert registry.save_venue(home, {"name": "Test flat"}) == 2
    listed = registry.list_venues()[1]
    assert listed["venue_id"] == "home-flat" and listed["revision"] == 2 and listed["name"] == "Test flat"
    assert registry.venue_record("home-flat")["revision"] == 2


def test_active_pointer_compare_and_set(home):
    registry = venue_registry()
    with pytest.raises(RegistryConflict, match="unknown_venue"):
        registry.set_active("home-flat", 0)
    registry.save_venue(home, {})
    assert registry.set_active("home-flat", 0) == {"venue_id": "home-flat", "revision": 1}
    with pytest.raises(RegistryConflict, match="stale_active_revision"):
        registry.set_active("building-v2", 0)
    assert registry.set_active("building-v2", 1)["revision"] == 2


def test_drafts_reject_stale_and_closed_updates(home):
    registry = venue_registry()
    assert registry.create_draft("dr-1", "extracting", {"source_kind": "photo"}) == 1
    assert registry.update_draft("dr-1", 1, "ready", {"source_kind": "photo", "compiled": True}) == 2
    with pytest.raises(RegistryConflict, match="stale_draft_revision"):
        registry.update_draft("dr-1", 1, "ready", {})
    with pytest.raises(RegistryConflict, match="stale_draft_revision"):
        registry.accept_draft("dr-1", 1, home, {}, {})
    accepted = registry.accept_draft("dr-1", 2, home, {"name": "Flat"}, {"compiled": True})
    assert accepted == {"venue_id": "home-flat", "venue_revision": 1, "draft_revision": 3, "active_revision": 1}
    assert registry.draft("dr-1")["status"] == "accepted"
    assert registry.active()["venue_id"] == "home-flat"
    with pytest.raises(RegistryConflict, match="draft_not_ready"):
        registry.accept_draft("dr-1", 3, home, {}, {})


def test_failed_accept_changes_nothing(home):
    registry = venue_registry()
    registry.create_draft("dr-2", "extracting", {})
    with pytest.raises(RegistryConflict, match="draft_not_ready"):
        registry.accept_draft("dr-2", 1, home, {}, {})
    assert get_venue("home-flat") is None and registry.active()["venue_id"] == "building-v2"


def test_registry_persists_across_instances(home):
    first = venue_registry()
    first.save_venue(home, {})
    first.set_active("home-flat", None)
    second = VenueRegistry(first.db_path)
    assert second.accepted_venue("home-flat") == home and second.active()["venue_id"] == "home-flat"


def test_planner_runs_on_a_second_venue(home):
    plan = plan_doors(home, DoorPlanRequest(hazards=[{"id": "h1", "type": "FIRE", "position": {"x": 3, "y": 2},
                                                       "source": "simulated"}]))
    assert plan.venue_id == "home-flat" and plan.chosen.validator_report.is_valid
    assert len(plan.lights.px) == 24
    assert plan.model_assumptions[0].startswith("home-flat model: Hand-written test venue")
    assert plan.chosen.initial_population == 7


def test_routes_list_activate_plan_and_check(home):
    client = TestClient(main.app)
    venue_registry().save_venue(home, {"name": "Test flat"})
    listed = client.get("/api/venues").json()
    assert [v["venue_id"] for v in listed["venues"]] == ["building-v2", "home-flat"]
    assert listed["active"] == {"venue_id": "building-v2", "revision": 0}
    assert client.put("/api/venues/active", json={"venue_id": "home-flat", "expected_revision": 5}).status_code == 409
    assert client.put("/api/venues/active", json={"venue_id": "missing-venue"}).status_code == 404
    assert client.put("/api/venues/active", json={"venue_id": "home-flat", "expected_revision": 0}).json()["revision"] == 1
    assert client.get("/api/venues/active").json() == {"venue_id": "home-flat", "revision": 1}
    assert client.get("/api/venues/home-flat").json() == home.to_json()
    checks = client.get("/api/venues/home-flat/checks").json()
    assert checks["errors"] == 0 and checks["issues"] == []
    plan = client.post("/api/venues/home-flat/door-plan",
                       json={"hazards": [{"id": "h1", "type": "SMOKE", "position": {"x": 9, "y": 8}, "source": "simulated"}]})
    assert plan.status_code == 200 and plan.json()["venue_id"] == "home-flat"
    # The camera twin calibrates against the printed building-v2 sheet only.
    assert client.post("/api/venues/home-flat/camera/calibration", json={}).status_code in (404, 422)
    assert client.get("/api/venues/Bad_Id").status_code == 404
