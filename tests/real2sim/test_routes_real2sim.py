"""Real2Sim HTTP surface (Contract 3): drafts, SSE replay, images, Accept with compare-and-set, saved runs."""
import base64
import threading
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.ai.real2sim.critique import hash_identifier
from backend.app.ai.real2sim.drafts import Real2SimService
from backend.app.ai.real2sim.extract import DraftExtractor
from backend.app.ai.real2sim.fixtures import FIXTURES_DIR_ENV, fixtures_dir, list_saved_runs
from backend.app.ai.real2sim.routes import build_real2sim_router
from backend.app.venues.model import get_venue
from backend.app.venues.registry import RegistryConflict, venue_registry
from tests.real2sim.test_critique import FakeInteractions, fake_adapter, fake_compile, home_draft, script
from tests.real2sim.test_drafts import png_bytes, write_saved_run

REAL_FIXTURES = fixtures_dir()


@pytest.fixture
def saved_dir(tmp_path, monkeypatch):
    root = tmp_path / "fixtures"
    write_saved_run(root, "test-flat")
    write_saved_run(root, "broken-flat", draft=home_draft(doors=3))
    monkeypatch.setenv(FIXTURES_DIR_ENV, str(root))
    return root


def build(tmp_path, *responses, gate=None, enabled=True, critique_rounds=1, registry_fn=None, real_compiler=False):
    fake = FakeInteractions(*responses, gate=gate)
    adapter = fake_adapter(fake)
    options = {} if real_compiler else {"compile_fn": fake_compile, "overlay_fn": lambda *a: png_bytes(8, 8),
                                        "topdown_fn": lambda venue: png_bytes(9, 9)}
    if registry_fn is not None:
        options["registry_fn"] = registry_fn
    service = Real2SimService(adapter, runtime_dir=tmp_path / "runtime", extractor=DraftExtractor(adapter, stream=True),
                              critique_rounds=critique_rounds, ping_seconds=0.05, **options)
    flag = {"enabled": enabled}
    app = FastAPI()
    app.include_router(build_real2sim_router(adapter, lambda: flag["enabled"], service=service))
    return app, fake, flag


def wait_done(client, draft_id, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        view = client.get(f"/api/real2sim/drafts/{draft_id}").json()
        if view["status"] in ("ready", "failed"):
            return view
        time.sleep(0.01)
    raise AssertionError("draft did not finish")


def read_sse(client, draft_id, headers=None, params=None):
    with client.stream("GET", f"/api/real2sim/drafts/{draft_id}/events", headers=headers or {},
                       params=params or {}) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        text = "".join(response.iter_text())
    events = []
    for block in text.split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line and not line.startswith(":"))
        if "id" in fields:
            events.append((int(fields["id"]), fields["event"], fields["data"]))
    return events


def live_body(**extra):
    return {"mode": "live", "image_base64": base64.b64encode(png_bytes()).decode(), "mime_type": "image/png",
            "source_kind": "photo", **extra}


def test_fixture_mode_is_labelled_replayable_and_serves_images(tmp_path, saved_dir):
    app, fake, _ = build(tmp_path)
    with TestClient(app) as client:
        saved = client.get("/api/real2sim/saved").json()
        assert saved["fixtures_enabled"] and [s["fixture_id"] for s in saved["saved"]] == ["broken-flat", "test-flat"]
        created = client.post("/api/real2sim/drafts", json={"mode": "fixture", "fixture_id": "test-flat"})
        assert created.status_code == 200 and created.json()["status"] == "extracting"
        draft_id = created.json()["draft_id"]
        view = wait_done(client, draft_id)
        assert view["status"] == "ready" and view["provenance"] == "synthetic" and view["mode"] == "fixture"
        assert "not a Gemini reading" in view["provenance_label"]
        assert view["fixture"]["fixture_id"] == "test-flat" and fake.calls == []
        assert {c["key"] for c in view["controllable_door_candidates"]} == {"KD1", "KD2", "KD3", "KD4", "KD5"}
        events = read_sse(client, draft_id)
        assert events[0][0] == 1 and events[0][1] == "status" and events[-1][1] == "done"
        assert [e[0] for e in events] == sorted(e[0] for e in events)
        replay = read_sse(client, draft_id, headers={"Last-Event-ID": "2"})
        assert replay and all(event_id > 2 for event_id, _, _ in replay) and replay[-1][1] == "done"
        by_query = read_sse(client, draft_id, params={"last_event_id": str(events[-2][0])})
        assert [e[1] for e in by_query] == ["done"]
        for name in ("overlay.png", "topdown.png"):
            image = client.get(f"/api/real2sim/drafts/{draft_id}/{name}")
            assert image.status_code == 200 and image.headers["content-type"] == "image/png"
            assert image.content.startswith(b"\x89PNG")


def test_fixtures_disabled_are_403_and_hidden(tmp_path, saved_dir):
    app, _, _ = build(tmp_path, enabled=False)
    with TestClient(app) as client:
        response = client.post("/api/real2sim/drafts", json={"mode": "fixture", "fixture_id": "test-flat"})
        assert response.status_code == 403 and response.json() == {"detail": {"code": "fixtures_disabled"}}
        assert client.get("/api/real2sim/saved").json() == {"fixtures_enabled": False, "saved": [], "invalid": []}


def test_live_draft_streams_thoughts_critiques_once_and_hashes_receipts(tmp_path):
    app, fake, _ = build(tmp_path, script(home_draft(doors=3), interaction_id="v1_read", thoughts=("Walls.", "Exits.")),
                         script(home_draft(doors=5), interaction_id="v1_fix"))
    with TestClient(app) as client:
        created = client.post("/api/real2sim/drafts", json=live_body(name="Judge sketch"))
        assert created.status_code == 200, created.json()
        draft_id = created.json()["draft_id"]
        view = wait_done(client, draft_id)
        assert view["status"] == "ready" and view["provenance"] == "live" and view["name"] == "Judge sketch"
        assert [t["text"] for t in view["thoughts"]][:2] == ["Walls.", "Exits."]
        assert view["rounds"][0]["accepted"] and view["checks"]["errors"] == 0
        assert view["receipts"][0]["interaction_id_hash"] == hash_identifier("v1_read")
        assert "v1_read" not in str(view) and view["source"]["mime_type"] == "image/png"
        assert fake.calls[1]["previous_interaction_id"] == "v1_read"
        kinds = [event for _, event, _ in read_sse(client, draft_id)]
        assert kinds.count("thought") == 3 and "round" in kinds and kinds[-1] == "done"
        assert kinds.index("draft") < kinds.index("checks") < kinds.index("round")


def test_busy_live_slot_returns_429(tmp_path):
    gate = threading.Event()
    app, _, _ = build(tmp_path, script(home_draft()), gate=gate)
    with TestClient(app) as client:
        first = client.post("/api/real2sim/drafts", json=live_body())
        assert first.status_code == 200
        second = client.post("/api/real2sim/drafts", json=live_body())
        assert second.status_code == 429 and second.json() == {"detail": {"code": "real2sim_busy"}}
        gate.set()
        assert wait_done(client, first.json()["draft_id"])["status"] == "ready"


def test_unconfigured_live_and_bad_requests_have_codes(tmp_path, saved_dir):
    app, fake, _ = build(tmp_path)
    with TestClient(app) as client:
        cases = [
            (live_body(mime_type="image/heic"), 415, "unsupported_mime_type"),
            (live_body(mime_type="image/jpeg"), 422, "source_mime_mismatch"),
            (live_body(source_kind="pdf"), 422, "source_kind_mismatch"),
            (live_body(fixture_id="test-flat"), 422, "live_request_with_fixture_id"),
            ({"mode": "fixture", "fixture_id": "test-flat", "image_base64": "AAAA"}, 422, "fixture_with_image"),
            ({"mode": "fixture"}, 422, "fixture_id_required"),
            ({"mode": "fixture", "fixture_id": "no-such-run"}, 404, "unknown_fixture"),
        ]
        for body, status, code in cases:
            response = client.post("/api/real2sim/drafts", json=body)
            assert (response.status_code, response.json()["detail"]["code"]) == (status, code), body
        assert client.post("/api/real2sim/drafts", json={**live_body(), "extra": 1}).status_code == 422
    adapter = fake_adapter(FakeInteractions())
    adapter.client = None
    plain = FastAPI()
    plain.include_router(build_real2sim_router(adapter, lambda: True,
                                               service=Real2SimService(adapter, runtime_dir=tmp_path / "rt")))
    with TestClient(plain) as client:
        response = client.post("/api/real2sim/drafts", json=live_body())
        assert response.status_code == 503 and response.json() == {"detail": {"code": "configuration_missing"}}
    assert fake.calls == []


@pytest.mark.parametrize("fixture_id", ["../etc", "..", "a/../../b", "%2e%2e", "UPPER", "evac-office/../../x"])
def test_fixture_id_traversal_is_rejected(tmp_path, saved_dir, fixture_id):
    app, _, _ = build(tmp_path)
    with TestClient(app) as client:
        response = client.post("/api/real2sim/drafts", json={"mode": "fixture", "fixture_id": fixture_id})
        assert response.status_code == 422 and response.json() == {"detail": {"code": "invalid_fixture_id"}}


@pytest.mark.parametrize("draft_id", ["..%2F..%2Fetc%2Fpasswd", "r2s-..", "r2s-" + "g" * 24, "R2S-" + "a" * 24,
                                      "%2e%2e", "r2s-" + "a" * 23])
def test_draft_id_traversal_is_rejected(tmp_path, draft_id):
    app, _, _ = build(tmp_path)
    with TestClient(app) as client:
        for suffix in ("", "/overlay.png", "/topdown.png", "/events"):
            response = client.get(f"/api/real2sim/drafts/{draft_id}{suffix}")
            assert response.status_code == 404, (draft_id, suffix)
        accept = client.post(f"/api/real2sim/drafts/{draft_id}/accept", json={"expected_revision": 1})
        assert accept.status_code == 404


def _ready_fixture(client, fixture_id="test-flat"):
    draft_id = client.post("/api/real2sim/drafts", json={"mode": "fixture", "fixture_id": fixture_id}).json()["draft_id"]
    return draft_id, wait_done(client, draft_id)


def test_accept_stores_activates_and_closes_the_draft(tmp_path, saved_dir):
    app, _, _ = build(tmp_path)
    with TestClient(app) as client:
        draft_id, view = _ready_fixture(client)
        response = client.post(f"/api/real2sim/drafts/{draft_id}/accept", json={
            "expected_revision": view["revision"], "controllable_doors": ["KD5"], "headcount": 12})
        assert response.status_code == 200, response.json()
        accepted = response.json()
        venue_id = accepted["venue_id"]
        assert venue_id.startswith("test-flat-synthetic-") and venue_id != "building-v2"
        assert accepted["venue_revision"] == 1 and accepted["active_revision"] == 1
        assert venue_registry().active() == {"venue_id": venue_id, "revision": 1}
        door = next(d for d in get_venue(venue_id).doors if d.id == "D5")
        assert door.planner_can_open and door.default_state == "closed"
        record = venue_registry().venue_record(venue_id)
        assert record["provenance"] == "synthetic" and record["controllable_doors"] == ["KD5"]
        assert record["draft_id"] == draft_id and record["headcount"] == 12
        after = client.get(f"/api/real2sim/drafts/{draft_id}").json()
        assert after["status"] == "accepted" and after["accepted"]["venue_id"] == venue_id
        again = client.post(f"/api/real2sim/drafts/{draft_id}/accept", json={"expected_revision": after["revision"]})
        assert again.status_code == 409 and again.json()["detail"]["code"] == "draft_not_ready"


def test_accept_with_a_stale_revision_is_409(tmp_path, saved_dir):
    app, _, _ = build(tmp_path)
    with TestClient(app) as client:
        draft_id, view = _ready_fixture(client)
        response = client.post(f"/api/real2sim/drafts/{draft_id}/accept",
                               json={"expected_revision": view["revision"] - 1})
        assert response.status_code == 409
        assert response.json()["detail"] == {"code": "stale_draft_revision", "revision": view["revision"]}
        assert venue_registry().active()["venue_id"] == "building-v2"


def test_registry_conflicts_surface_as_409(tmp_path, saved_dir):
    class Conflicting:
        def __init__(self, inner):
            self.inner = inner

        def __getattr__(self, name):
            return getattr(self.inner, name)

        def accept_draft(self, *args, **kwargs):
            raise RegistryConflict("stale_draft_revision")

    app, _, _ = build(tmp_path, registry_fn=lambda: Conflicting(venue_registry()))
    with TestClient(app) as client:
        draft_id, view = _ready_fixture(client)
        response = client.post(f"/api/real2sim/drafts/{draft_id}/accept", json={"expected_revision": view["revision"]})
        assert response.status_code == 409 and response.json() == {"detail": {"code": "stale_draft_revision"}}


def test_accept_with_graph_errors_is_422_with_issues(tmp_path, saved_dir):
    app, _, _ = build(tmp_path)
    with TestClient(app) as client:
        draft_id, view = _ready_fixture(client, "broken-flat")
        assert view["checks"]["errors"] == 2 and "over_capacity" in view["accept_blockers"]
        response = client.post(f"/api/real2sim/drafts/{draft_id}/accept", json={"expected_revision": view["revision"]})
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["code"] == "graph_check_errors" and {i["code"] for i in detail["issues"]} == {"over_capacity"}
        assert client.get(f"/api/real2sim/drafts/{draft_id}").json()["status"] == "ready"


@pytest.mark.parametrize("doors, code", [(["KD1", "KD2", "KD3", "KD4"], "too_many_controllable_doors"),
                                         (["KD1", "NOPE"], "unknown_controllable_door"),
                                         (["KD1", "KD1"], "duplicate_controllable_door")])
def test_controllable_doors_are_validated(tmp_path, saved_dir, doors, code):
    app, _, _ = build(tmp_path)
    with TestClient(app) as client:
        draft_id, view = _ready_fixture(client)
        response = client.post(f"/api/real2sim/drafts/{draft_id}/accept",
                               json={"expected_revision": view["revision"], "controllable_doors": doors})
        assert response.status_code == 422 and response.json()["detail"]["code"] == code
        builtin = client.post(f"/api/real2sim/drafts/{draft_id}/accept",
                              json={"expected_revision": view["revision"], "venue_id": "building-v2"})
        assert builtin.status_code == 422 and builtin.json()["detail"]["code"] == "invalid_venue_id"


@pytest.mark.skipif(not any(entry["fixture_id"] == "sketch-home" for entry in list_saved_runs(REAL_FIXTURES)["saved"]),
                    reason="the compiler teammate's saved runs are not generated")
def test_real_saved_run_through_the_real_compiler_overlay_and_accept(tmp_path, monkeypatch):
    monkeypatch.setenv(FIXTURES_DIR_ENV, str(REAL_FIXTURES))
    app, _, _ = build(tmp_path, real_compiler=True)
    with TestClient(app) as client:
        draft_id, view = _ready_fixture(client, "sketch-home")
        assert view["status"] == "ready" and view["provenance"] == "synthetic", view["errors"]
        assert view["overlay_available"] and view["topdown_available"]
        assert view["checks"]["errors"] == 0, view["checks"]
        response = client.post(f"/api/real2sim/drafts/{draft_id}/accept", json={"expected_revision": view["revision"]})
        assert response.status_code == 200, response.json()
        venue = get_venue(response.json()["venue_id"])
        assert venue is not None and "synthetic" in venue.provenance
