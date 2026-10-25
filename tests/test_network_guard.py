"""Network exposure: non-loopback peers need X-API-Token; loopback is unchanged."""
import pytest
from fastapi.testclient import TestClient

from backend.app import main

REMOTE = ("203.0.113.9", 4000)


def call(client, path="/health", **kwargs):
    return TestClient(main.app, client=client).get(path, **kwargs)


def test_remote_is_rejected_without_a_configured_token(monkeypatch):
    monkeypatch.delenv("SPATIALTWIN_API_TOKEN", raising=False)
    response = call(REMOTE)
    assert response.status_code == 403
    assert response.json() == {"detail": "remote_access_denied"}
    # An unset variable must not accept an empty header either.
    assert call(REMOTE, headers={"X-API-Token": ""}).status_code == 403


def test_remote_with_matching_token_is_served(monkeypatch):
    monkeypatch.setenv("SPATIALTWIN_API_TOKEN", "s3cret-token")
    assert call(REMOTE, headers={"X-API-Token": "s3cret-token"}).status_code == 200
    assert call(REMOTE, headers={"X-API-Token": "wrong"}).status_code == 403
    assert call(REMOTE).status_code == 403


def test_remote_is_rejected_on_every_route_including_events(monkeypatch):
    monkeypatch.delenv("SPATIALTWIN_API_TOKEN", raising=False)
    client = TestClient(main.app, client=REMOTE)
    assert client.get("/api/scenarios/facility-demo").status_code == 403
    assert client.post("/api/hardware/stop").status_code == 403
    assert client.get("/api/scenarios/facility-demo/events").status_code == 403


@pytest.mark.parametrize("host", ["127.0.0.1", "127.8.9.10", "::1", "::ffff:127.0.0.1"])
def test_loopback_needs_no_token(monkeypatch, host):
    monkeypatch.delenv("SPATIALTWIN_API_TOKEN", raising=False)
    assert call((host, 5000)).status_code == 200


@pytest.mark.parametrize("host", ["testclient", "", "10.0.0.5", "::2"])
def test_non_loopback_and_unparseable_peers_are_not_loopback(host):
    assert main.is_loopback_client(host) is False


def test_health_does_not_disclose_device_path_or_sdk_version(monkeypatch):
    monkeypatch.setattr(main.hardware_bridge, "port", "/dev/cu.usbmodem-SECRET")
    monkeypatch.setattr(main.hardware_bridge, "is_simulator", False)
    body = TestClient(main.app, client=("127.0.0.1", 1)).get("/health").json()
    assert "usbmodem" not in str(body)
    assert "sdk_version" not in body["ai"]
    assert body["hardware_mode"] == "physical_serial"
    assert {"status", "live_api_configured", "current_context", "physical_gate_state", "ai"} <= set(body)
