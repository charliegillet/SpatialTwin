"""Capabilities are receipt-gated, read local files only and never call a provider."""
import json

import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.ai.grounding import video as video_mod


@pytest.fixture
def api(tmp_path, monkeypatch):
    probes = tmp_path / "runtime" / "probes"
    probes.mkdir(parents=True)
    monkeypatch.setattr(video_mod, "VIDEO_PROBE_DIR", probes)
    monkeypatch.chdir(tmp_path)

    async def forbidden(*args, **kwargs):
        pytest.fail("capabilities must not call a provider")

    monkeypatch.setattr(main.grounding_adapter, "interpret_capture", forbidden)
    monkeypatch.setattr(main.managed_agent_adapter, "investigate_scenario", forbidden)
    return TestClient(main.app), probes


def test_everything_disabled_without_receipts(api):
    client, _ = api
    response = client.get("/api/ai/capabilities")
    assert response.status_code == 200
    assert response.json() == {"video_static": False, "video_agentic": False, "managed_model": None,
                               "managed_model_fallback": False, "receipts_source": "runtime/probes"}


def test_receipts_gate_each_mode(api):
    client, probes = api
    (probes / "P3.json").write_text(json.dumps({"pass": True}))
    (probes / "P4.json").write_text(json.dumps({"pass": False}))
    body = client.get("/api/ai/capabilities").json()
    assert body["video_static"] is True and body["video_agentic"] is False
    (probes / "P4.json").write_text("garbage")
    assert client.get("/api/ai/capabilities").json()["video_agentic"] is False


def test_managed_model_from_offline_cache(api):
    client, probes = api
    (probes / "model_resolution.json").write_text(json.dumps({"model": "gemini-3.8-flash"}))
    body = client.get("/api/ai/capabilities").json()
    assert body["managed_model"] == "gemini-3.8-flash" and body["managed_model_fallback"] is True
    (probes / "model_resolution.json").write_text(json.dumps({"model": "gemini-4-argon"}))
    body = client.get("/api/ai/capabilities").json()
    assert body["managed_model"] == "gemini-4-argon" and body["managed_model_fallback"] is False
