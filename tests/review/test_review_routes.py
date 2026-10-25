"""The review route is read-only for scenario state and records escalations locally only."""
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.planner.flow_solver import FlowPlanner
from backend.app.review.routes import build_review_router
from tests.review.review_helpers import authoritative, block, local_investigation


@pytest.fixture
def api(manager):
    app = FastAPI()
    app.include_router(build_review_router(manager, lambda: "simulator"))
    return TestClient(app)


def forbid_solving(monkeypatch):
    monkeypatch.setattr(FlowPlanner, "solve", lambda *args, **kwargs: pytest.fail("A review must not compute a new run"))


def scenario_tables(manager):
    with sqlite3.connect(manager.store.db_path) as connection:
        return [line for line in connection.iterdump() if "review_escalations_v1" not in line]


def escalation_rows(manager):
    with sqlite3.connect(manager.store.db_path) as connection:
        return connection.execute("SELECT count(*) FROM review_escalations_v1").fetchone()[0]


def post(api, manager, **extra):
    return api.post("/api/scenarios/facility-demo/review",
                    json={"expected_context": manager.get_current_context().model_dump(mode="json"), **extra})


def test_escalated_review_returns_watch_verification_and_one_idempotent_local_record(api, manager, monkeypatch):
    block(manager, "portal", "P2", "route-p2")
    forbid_solving(monkeypatch)
    before_state, before_tables = authoritative(manager), scenario_tables(manager)

    first = post(api, manager)
    assert first.status_code == 200
    body = first.json()
    assert body["provenance"] == "local_review"
    assert body["run_id"] == manager.current_plan.run_id == body["watch"]["run_id"] == body["verification"]["run_id"]
    assert body["watch"]["escalation"] == "escalated"
    assert body["watch"]["next_step"] == "compare_alternatives"
    assert body["verification"]["verdict"] == "verified_within_model"
    record = body["escalation_record"]
    assert record["delivery"] == "local_record_only" and "No message" in record["notice"]
    assert record["reasons"] == ["zone:EVENT:RESIDUAL_HOLDING", "passage:P2:PASSAGE_UNAVAILABLE"]

    second = post(api, manager).json()["escalation_record"]
    assert (second["record_id"], second["created_at_iso"]) == (record["record_id"], record["created_at_iso"])
    assert escalation_rows(manager) == 1
    assert authoritative(manager) == before_state
    assert scenario_tables(manager) == before_tables


def test_nominal_review_creates_no_escalation_record(api, manager, monkeypatch):
    forbid_solving(monkeypatch)
    body = post(api, manager).json()
    assert body["watch"]["escalation"] == "nominal"
    assert body["escalation_record"] is None
    assert escalation_rows(manager) == 0


def test_saved_investigation_is_compared_only_when_supplied(api, manager):
    block(manager, "portal", "P2", "route-compare")
    investigation = local_investigation(manager, "inv-route")
    manager.store.save_investigation(investigation.investigation_id, "completed",
                                     investigation.model_dump_json(), "2026-10-24T00:00:00+00:00")
    items = {item["requirement_id"]: item for item in post(api, manager, investigation_id="inv-route").json()["verification"]["requirements"]}
    assert (items["comparison_equal_conditions"]["status"], items["comparison_equal_conditions"]["value"]) == ("pass", 57)
    missing = {item["requirement_id"]: item for item in post(api, manager, investigation_id="inv-missing").json()["verification"]["requirements"]}
    assert missing["comparison_equal_conditions"]["status"] == "not_run"


def test_stale_unknown_malformed_and_unreviewable_requests_fail_closed(api, manager):
    old = manager.get_current_context().model_dump(mode="json")
    block(manager, "portal", "P1", "route-stale")
    assert api.post("/api/scenarios/facility-demo/review", json={"expected_context": old}).status_code == 409
    assert api.post("/api/scenarios/other/review", json={"expected_context": old}).status_code == 404
    current = manager.get_current_context().model_dump(mode="json")
    assert api.post("/api/scenarios/facility-demo/review", json={"expected_context": current, "mode": "live"}).status_code == 422
    assert api.post("/api/scenarios/facility-demo/review", json={"expected_context": current, "investigation_id": "../x"}).status_code == 422
    manager.current_plan = None
    response = post(api, manager)
    assert response.status_code == 409 and "no_checked_plan" in response.json()["detail"]
