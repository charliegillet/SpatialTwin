"""Hazard route: local-only, strict arguments, deterministic."""
import pytest
from fastapi.testclient import TestClient

from backend.app import main

KEYS = {"tool", "alternative_id", "is_valid", "reasons", "status", "completed_crossings",
        "remaining_population", "boundary_breakdown", "baseline_completed_crossings", "modeled_exposure_people_seconds",
        "exposure_label"}
BODY = {"alternative_id": "KEEP_CURRENT", "events": [{"element_id": "P1", "close_at_s": 0}]}


@pytest.fixture
def client(monkeypatch):
    async def forbidden(*args, **kwargs):
        pytest.fail("hazard simulation must not call a provider")

    monkeypatch.setattr(main.grounding_adapter, "interpret_capture", forbidden)
    monkeypatch.setattr(main.managed_agent_adapter, "investigate_scenario", forbidden)
    return TestClient(main.app)


def test_shape_and_determinism(client):
    first = client.post("/api/hazard/simulate", json=BODY)
    assert first.status_code == 200
    assert set(first.json()) == KEYS
    assert first.json()["alternative_id"] == "KEEP_CURRENT"
    assert client.post("/api/hazard/simulate", json=BODY).json() == first.json()


def test_extra_field_is_422_without_echo(client):
    for bad in ({**BODY, "note": "SECRET-TEXT"},
                {**BODY, "events": [{"element_id": "P1", "close_at_s": 0, "x": "SECRET-TEXT"}]}):
        response = client.post("/api/hazard/simulate", json=bad)
        assert response.status_code == 422
        assert response.json() == {"detail": {"code": "invalid_arguments"}}


def test_unknown_element_and_bad_time_are_422(client):
    for events in ([{"element_id": "SECRET-X", "close_at_s": 0}],
                   [{"element_id": "P1", "close_at_s": -1}],
                   [{"element_id": "P1", "close_at_s": 10 ** 6}],
                   [],
                   [{"element_id": "P1", "close_at_s": 0}, {"element_id": "P1", "close_at_s": 0}]):
        response = client.post("/api/hazard/simulate", json={**BODY, "events": events})
        assert response.status_code == 422
        assert response.json() == {"detail": {"code": "invalid_arguments"}}
        assert "SECRET" not in response.text


def test_repeated_calls_keep_baseline_and_exposure(client):
    # Regression: a fixed baseline evaluation id was rejected on repeat calls
    # ("reused with different inputs") and silently left baseline and exposure null.
    body = {"alternative_id": "KEEP_CURRENT", "events": [{"element_id": "P2", "close_at_s": 12}]}
    for _ in range(3):
        response = client.post("/api/hazard/simulate", json=body)
        assert response.status_code == 200
        payload = response.json()
        assert payload["baseline_completed_crossings"] is not None
        assert payload["modeled_exposure_people_seconds"] is not None
        assert payload["exposure_label"].startswith("modeled")


def test_default_zones_make_closure_exposure_nonzero(client):
    # Regression: the UI sends no hazard zones, so exposure was always 0.
    body = {"alternative_id": "KEEP_CURRENT", "events": [{"element_id": "P1", "close_at_s": 12}]}
    payload = client.post("/api/hazard/simulate", json=body).json()
    assert payload["modeled_exposure_people_seconds"] > 0


def test_boundary_breakdown_sums_to_completed_crossings(client):
    payload = client.post("/api/hazard/simulate", json=BODY).json()
    breakdown = payload["boundary_breakdown"]
    assert set(breakdown) == {"B1", "B2"}
    assert all(type(v) is int and v >= 0 for v in breakdown.values())
    assert sum(breakdown.values()) == payload["completed_crossings"]


def test_odd_close_time_has_distinct_code(client):
    response = client.post("/api/hazard/simulate", json={**BODY, "events": [{"element_id": "P1", "close_at_s": 7}]})
    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "invalid_close_time"}}
