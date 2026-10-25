"""The review router is mounted on the application."""
from fastapi.testclient import TestClient

from backend.app import main


def test_review_route_is_mounted():
    assert "/api/scenarios/{scenario_id}/review" in main.app.openapi()["paths"]
    response = TestClient(main.app).post(
        "/api/scenarios/unknown/review",
        json={"expected_context": main.state_manager.get_current_context().model_dump()})
    assert response.status_code == 404
