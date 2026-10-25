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
