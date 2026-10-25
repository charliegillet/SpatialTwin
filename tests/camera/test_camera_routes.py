from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.ai.grounding.calibration import CORNER_ORDER, apply_homography, load_sheet
from backend.app.venues.camera import CAMERA_STORE, MAPPING_NOTE

SHEET = load_sheet()
IMAGE = (1280, 720)
CAMERA = [[22.0, 4.0, 160.0], [-1.5, -19.0, 640.0], [0.002, 0.004, 1.0]]
BASE = "/api/venues/building-v2"


@pytest.fixture
def client():
    CAMERA_STORE.clear()
    yield TestClient(main.app)
    CAMERA_STORE.clear()


def _px(floor):
    return apply_homography(CAMERA, floor)


def _norm(floor):
    x, y = _px(floor)
    return [round(y / IMAGE[1] * 1000), round(x / IMAGE[0] * 1000)]


def _card(kind, floor, half=(1.2, 0.8)):
    corners = [_px((floor[0] + dx * half[0], floor[1] + dy * half[1])) for dx in (-1, 1) for dy in (-1, 1)]
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    box = [round(min(ys) / IMAGE[1] * 1000), round(min(xs) / IMAGE[0] * 1000),
           round(max(ys) / IMAGE[1] * 1000), round(max(xs) / IMAGE[0] * 1000)]
    return {"type": kind, "point": _norm(floor), "box_2d": box}


def _calibrate(client):
    corners = {label: list(_px(tuple(SHEET["fiducial_floor_m"][label]))) for label in CORNER_ORDER}
    response = client.post(f"{BASE}/camera/calibration", json={"corners_px": corners, "image_size": list(IMAGE)})
    assert response.status_code == 200, response.text
    return response.json()


def _read(client, cards, calibration_id, **extra):
    return client.post(f"{BASE}/camera/hazard-read", json={
        "capture_id": "cap-test", "timestamp_iso": datetime.now(timezone.utc).isoformat(),
        "dimensions": list(IMAGE), "calibration_id": calibration_id, "mode": "fixture",
        "fixture_cards": cards, **extra,
    })


def test_calibration_reports_error_and_rejects_bad_corners(client):
    data = _calibrate(client)
    assert data["source"] == "clicked"
    assert data["reprojection_error_m"] < 1e-6
    bad = client.post(f"{BASE}/camera/calibration", json={"corners_px": {"TL": [1, 1]}, "image_size": list(IMAGE)})
    assert bad.status_code == 422 and bad.json()["detail"]["code"] == "missing_corner"


def test_fixture_read_maps_cards_to_zones_and_flags_bad_cards(client):
    cal = _calibrate(client)
    response = _read(client, [_card("FIRE", (20, 4)), _card("GAS", (20, 14)), _card("WATER", (40.5, 12)),
                              _card("SMOKE", (4, 4))], cal["calibration_id"])
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["provenance"] == "fixture" and data["status"] == "completed"
    assert data["mapping_note"] == MAPPING_NOTE
    by_type = {c["type"]: c for c in data["candidates"]}
    assert by_type["FIRE"]["zone_id"] == "LOBBY" and by_type["FIRE"]["usable"]
    assert abs(by_type["FIRE"]["floor"]["x"] - 20) < 0.05 and abs(by_type["FIRE"]["floor"]["y"] - 4) < 0.05
    assert by_type["GAS"]["zone_id"] == "HALL"
    assert by_type["WATER"]["rejected_reason"] in ("outside_building", "crosses_building_edge")
    assert by_type["SMOKE"]["rejected_reason"] == "outside_building"  # the empty south-west corner
    assert all(c["evidence"].startswith("[FIXTURE]") for c in data["candidates"])


def test_confirmed_camera_hazard_feeds_the_door_planner(client):
    cal = _calibrate(client)
    read = _read(client, [_card("FIRE", (20, 4))], cal["calibration_id"]).json()
    candidate = read["candidates"][0]
    confirm = client.post(f"{BASE}/camera/reads/{read['read_id']}/confirm", json={"candidate_ids": [candidate["candidate_id"]]})
    assert confirm.status_code == 200, confirm.text
    hazards = confirm.json()["hazards"]
    assert hazards[0]["source"] == "camera" and hazards[0]["proposal_id"] == read["read_id"]
    plan = client.post(f"{BASE}/door-plan", json={"hazards": hazards})
    assert plan.status_code == 200, plan.text
    body = plan.json()
    assert body["hazards"][0]["zone_id"] == "LOBBY"
    assert any(exit_["id"] == "E1" and not exit_["safe"] for exit_ in body["exits"])


def test_unconfirmed_or_edited_camera_hazards_are_refused(client):
    cal = _calibrate(client)
    read = _read(client, [_card("FIRE", (20, 4))], cal["calibration_id"]).json()
    candidate = read["candidates"][0]
    forged = {"id": f"cam-{candidate['candidate_id']}", "type": "FIRE", "position": candidate["floor"],
              "source": "camera", "proposal_id": read["read_id"]}
    refused = client.post(f"{BASE}/door-plan", json={"hazards": [forged]})
    assert refused.status_code == 422 and refused.json()["detail"]["code"] == "unconfirmed_camera_hazard"
    client.post(f"{BASE}/camera/reads/{read['read_id']}/confirm", json={"candidate_ids": [candidate["candidate_id"]]})
    moved = {**forged, "position": {"x": 20, "y": 14}}
    mismatch = client.post(f"{BASE}/door-plan", json={"hazards": [moved]})
    assert mismatch.status_code == 422 and mismatch.json()["detail"]["code"] == "camera_hazard_mismatch"
    retyped = {**forged, "type": "WATER"}
    assert client.post(f"{BASE}/door-plan", json={"hazards": [retyped]}).json()["detail"]["code"] == "camera_hazard_mismatch"
    invented = {**forged, "proposal_id": "read-unknown"}
    assert client.post(f"{BASE}/door-plan", json={"hazards": [invented]}).json()["detail"]["code"] == "unconfirmed_camera_hazard"


def test_unusable_candidates_cannot_be_confirmed(client):
    cal = _calibrate(client)
    read = _read(client, [_card("SMOKE", (4, 4))], cal["calibration_id"]).json()
    candidate_id = read["candidates"][0]["candidate_id"]
    response = client.post(f"{BASE}/camera/reads/{read['read_id']}/confirm", json={"candidate_ids": [candidate_id]})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "candidate_not_usable:outside_building"
    unknown = client.post(f"{BASE}/camera/reads/read-nope/confirm", json={"candidate_ids": [candidate_id]})
    assert unknown.status_code == 404


def test_read_without_calibration_marks_cards_unusable(client):
    data = _read(client, [_card("FIRE", (20, 4))], None).json()
    assert data["candidates"][0]["rejected_reason"] == "no_calibration"


def test_fixture_rules_and_production_gate(client, monkeypatch):
    cal = _calibrate(client)
    with_image = _read(client, [_card("FIRE", (20, 4))], cal["calibration_id"], image_base64="AAAA")
    assert with_image.status_code == 422
    live_with_cards = _read(client, [_card("FIRE", (20, 4))], cal["calibration_id"], mode="live")
    assert live_with_cards.status_code == 422
    monkeypatch.setenv("SPATIALTWIN_MODE", "production")
    blocked = _read(client, [_card("FIRE", (20, 4))], cal["calibration_id"])
    assert blocked.status_code == 403 and blocked.json()["detail"]["code"] == "fixtures_disabled"


def test_live_read_without_a_key_is_unavailable_and_unstored(client, monkeypatch):
    # main's adapter is built at import time, possibly from a key exported in the shell; force "no key".
    monkeypatch.setattr(main.grounding_adapter, "client", None)
    response = client.post(f"{BASE}/camera/hazard-read", json={
        "capture_id": "cap-live", "timestamp_iso": datetime.now(timezone.utc).isoformat(),
        "image_base64": "AAAA", "dimensions": list(IMAGE), "mode": "live",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unavailable" and data["errors"] == ["configuration_missing"]
    assert data["read_id"] is None and data["candidates"] == []


def test_calibration_must_match_the_image_size(client):
    cal = _calibrate(client)
    response = client.post(f"{BASE}/camera/hazard-read", json={
        "capture_id": "cap-size", "timestamp_iso": datetime.now(timezone.utc).isoformat(),
        "dimensions": [640, 480], "calibration_id": cal["calibration_id"], "mode": "fixture",
        "fixture_cards": [_card("FIRE", (20, 4))],
    })
    assert response.status_code == 422 and response.json()["detail"]["code"] == "calibration_image_size_mismatch"


def test_corners_too_close_are_refused(client):
    corners = {"TL": [100, 100], "TR": [120, 100], "BR": [120, 115], "BL": [100, 115]}
    response = client.post(f"{BASE}/camera/calibration", json={"corners_px": corners, "image_size": list(IMAGE)})
    assert response.status_code == 422 and response.json()["detail"]["code"] == "corners_too_close"


def test_camera_hazard_keeps_read_provenance_and_refuses_client_timing(client):
    cal = _calibrate(client)
    read = _read(client, [_card("SMOKE", (20, 4))], cal["calibration_id"]).json()
    candidate = read["candidates"][0]
    hazards = client.post(f"{BASE}/camera/reads/{read['read_id']}/confirm",
                          json={"candidate_ids": [candidate["candidate_id"]]}).json()["hazards"]
    plan = client.post(f"{BASE}/door-plan", json={"hazards": hazards})
    assert plan.status_code == 200, plan.text
    assert plan.json()["hazards"][0]["camera_provenance"] == "fixture"
    timed = [{**hazards[0], "untenable_s": 0}]
    refused = client.post(f"{BASE}/door-plan", json={"hazards": timed})
    assert refused.status_code == 422 and refused.json()["detail"]["code"] == "camera_hazard_mismatch"


def test_simulated_hazards_have_no_camera_provenance(client):
    plan = client.post(f"{BASE}/door-plan", json={"hazards": [
        {"id": "s1", "type": "FIRE", "position": {"x": 20, "y": 4}, "source": "simulated"}]}).json()
    assert plan["hazards"][0]["camera_provenance"] is None
