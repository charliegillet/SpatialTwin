"""Video grounding route falls back to the image path when receipts do not enable video."""
import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.ai.grounding import video as video_mod


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(video_mod, "VIDEO_PROBE_DIR", tmp_path)
    called = []

    async def forbidden(*args, **kwargs):
        called.append(1)
        pytest.fail("no provider call when video is disabled")

    monkeypatch.setattr(main.grounding_adapter, "interpret_capture", forbidden)
    monkeypatch.setattr(main, "ground_video", forbidden)
    return TestClient(main.app)


@pytest.mark.parametrize("mode", ["static", "agentic"])
def test_video_disabled_falls_back(client, mode):
    context = main.state_manager.get_current_context().model_dump()
    body = {"capture_id": f"clip-{mode}", "timestamp_iso": "2026-10-24T00:00:00+00:00",
            "source_context": context, "media_kind": "video", "video_mode": mode,
            "video_base64": "AAAA"}
    response = client.post("/api/scenarios/facility-demo/grounding", json=body)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unavailable" and data["errors"] == ["video_disabled_use_image_path"]
    assert data["proposal"] is None and data["provenance"] == "unavailable"


def test_live_video_proposal_can_be_applied_after_review(tmp_path, monkeypatch):
    """A reviewed live video proposal is applied like a still: the capture record now exists."""
    from datetime import datetime, timezone
    from uuid import uuid4
    from backend.app.contracts import GroundingProposalV1, GroundingResult, GroundingStatus, EntityType

    monkeypatch.setattr(main, "video_enabled", lambda mode: True)
    seen = {}

    async def fake_ground_video(clip, mime, ctx, mode, **kwargs):
        seen["clip"] = clip
        proposal = GroundingProposalV1(
            capture_id="unused", source_context=ctx, status=GroundingStatus.MATCHED,
            candidate_ids=["portal:P2"], selected_entity_type=EntityType.PORTAL, selected_entity_id="P2",
            evidence="Token on the east pad throughout the clip.", thinking_level="low")
        return GroundingResult(proposal=proposal, provenance="live", status="completed", errors=[])

    monkeypatch.setattr(main, "ground_video", fake_ground_video)
    client = TestClient(main.app)
    context = main.state_manager.get_current_context().model_dump()
    capture_id = f"clip-{uuid4().hex[:8]}"
    body = {"capture_id": capture_id, "timestamp_iso": datetime.now(timezone.utc).isoformat(),
            "source_context": context, "media_kind": "video", "video_mode": "agentic", "video_base64": "AAAA"}
    grounded = client.post("/api/scenarios/facility-demo/grounding", json=body)
    assert grounded.status_code == 200, grounded.text
    proposal_id = grounded.json()["proposal_id"]
    stored = main.state_manager.store.get_capture(capture_id)
    assert stored["media_kind"] == "video" and len(stored["video_sha256"]) == 64 and "video_base64" not in stored

    again = client.post("/api/scenarios/facility-demo/grounding", json=body)
    assert again.status_code == 409

    applied = client.post("/api/scenarios/facility-demo/commands", json={
        "type": "APPLY_BLOCKAGE", "expected_context": context, "expected_scenario_revision": context["scenario_revision"],
        "idempotency_key": f"video-apply-{uuid4().hex}", "target_type": "portal", "target_id": "P2",
        "source": "grounding_proposal", "proposal_id": proposal_id, "reviewed": True})
    assert applied.status_code == 200, applied.text
    assert "P2" in applied.json()["snapshot"]["blocked_portals"]
    ctx = main.state_manager.get_current_context().model_dump()
    reset = client.post("/api/scenarios/facility-demo/commands", json={
        "type": "RESET_SCENARIO", "expected_context": ctx, "expected_scenario_revision": ctx["scenario_revision"],
        "idempotency_key": f"video-reset-{uuid4().hex}"})
    assert reset.status_code == 200


def test_video_request_cannot_claim_a_fixture_source(client):
    context = main.state_manager.get_current_context().model_dump()
    body = {"capture_id": "clip-fixture-kind", "timestamp_iso": "2026-10-24T00:00:00+00:00",
            "source_context": context, "media_kind": "video", "video_mode": "agentic",
            "source_kind": "fixture", "video_base64": "AAAA"}
    response = client.post("/api/scenarios/facility-demo/grounding", json=body)
    assert response.status_code == 422
