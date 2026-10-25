"""Leaving a doorless room out at Accept: posted maps often draw tenant rooms with no door, which the graph checks
(rightly) call unreachable. The operator may leave such a room out of the walkable floor; it is said in provenance."""
from fastapi.testclient import TestClient

from backend.app.ai.real2sim.fixtures import FIXTURES_DIR_ENV
from backend.app.venues.registry import venue_registry
from tests.real2sim.test_critique import home_draft
from tests.real2sim.test_drafts import write_saved_run
from tests.real2sim.test_routes_real2sim import _ready_fixture, build


def doorless_flat():
    draft = home_draft()
    draft["doors"] = [door for door in draft["doors"] if "BED_2" not in door["between"]]
    return draft


def test_a_doorless_room_blocks_accept_until_the_operator_leaves_it_out(tmp_path, monkeypatch):
    root = tmp_path / "fixtures"
    write_saved_run(root, "doorless-flat", draft=doorless_flat())
    monkeypatch.setenv(FIXTURES_DIR_ENV, str(root))
    app, _, _ = build(tmp_path, real_compiler=True)
    with TestClient(app) as client:
        draft_id, view = _ready_fixture(client, "doorless-flat")
        assert "room_unreachable" in view["accept_blockers"]
        assert view["unreachable_rooms"] == [{"key": "BED_2", "name": "Bedroom 2"}]
        url = f"/api/real2sim/drafts/{draft_id}/accept"
        blocked = client.post(url, json={"expected_revision": view["revision"]})
        assert blocked.status_code == 422 and blocked.json()["detail"]["code"] == "graph_check_errors"
        unknown = client.post(url, json={"expected_revision": view["revision"], "left_out_rooms": ["NOPE"]})
        assert unknown.status_code == 422 and unknown.json()["detail"]["code"] == "unknown_room"
        everything = client.post(url, json={"expected_revision": view["revision"],
                                            "left_out_rooms": ["LIVING", "KITCHEN", "HALL", "BED_1", "BED_2"]})
        assert everything.status_code == 422 and everything.json()["detail"]["code"] == "no_room_left"
        accepted = client.post(url, json={"expected_revision": view["revision"], "left_out_rooms": ["BED_2"]})
        assert accepted.status_code == 200, accepted.json()
        venue_id = accepted.json()["venue_id"]
    stored = venue_registry().accepted_venue(venue_id)
    assert "Bedroom 2" not in {zone.name for zone in stored.zones}
    assert "Operator left out Bedroom 2 (drawn with no door) from the walkable floor." in stored.provenance
    assert venue_registry().venue_record(venue_id)["left_out_rooms"] == ["BED_2"]
