"""Session API tests: FastAPI TestClient with fakes injected via dependency_overrides.

No network, Argon, pycolmap or Playwright is touched: every job runner and the
genai client factory come from ``Services`` built here.
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from walktwin import api
from walktwin.api import Services, create_app, get_services
from walktwin.checker import check_run
from walktwin.contracts import FlowParams, Hazard, Scenario, VenueGraph
from walktwin.extract import ExtractionResult
from walktwin.flow import solve
from walktwin.graph_checks import check_graph
from walktwin.media import PreparedVideo, prepare_video
from walktwin.sessions import SessionStore

FIXTURES = Path(__file__).parent / "fixtures"
SHA = "b" * 64


def _office() -> VenueGraph:
    return VenueGraph.model_validate_json((FIXTURES / "office_graph.json").read_text())


def _fire(*door_ids: str, interventions: tuple[str, ...] = ()) -> Scenario:
    return Scenario(hazards=[Hazard(door_id=d, kind="fire") for d in door_ids],
                    interventions=list(interventions))


class Fakes:
    """Records calls; behaviour knobs are plain attributes."""

    def __init__(self) -> None:
        self.sfm_calls: list[Path] = []
        self.extract_calls: list[str] = []
        self.refine_calls: list[dict] = []
        self.fit_calls = 0
        self.investigate_calls: list[Scenario] = []
        self.active = 0
        self.max_active = 0
        self.check_ok = True
        self.block_extract = threading.Event()
        self.block_extract.set()  # set = do not block
        self.env_calls = 0
        self.notes: list[tuple] = []

    # -- runners ------------------------------------------------------------
    def prepare_video(self, src: Path, out_dir: Path) -> PreparedVideo:
        out_dir.mkdir(parents=True, exist_ok=True)
        dst = out_dir / "prepared.mp4"
        shutil.copyfile(src, dst)
        return PreparedVideo(path=dst, sha256=SHA, duration_s=60.0, width=64, height=64)

    def run_sfm(self, video: PreparedVideo, work_dir: Path) -> dict:
        self.sfm_calls.append(work_dir)
        frames = [{"t_s": t, "center": [t, 1.0, 0.0], "R": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                   "K": [[500, 0, 32], [0, 500, 32], [0, 0, 1]]} for t in (0.0, 0.5, 1.0)]
        return {"status": "completed", "frames": frames, "points": [[0.0, 0.0, 0.0]],
                "registered_fraction": 1.0, "elapsed_ms": 5, "error": None}

    def fit_alignment(self, sfm, graph) -> dict:
        self.fit_calls += 1
        return {"scale": 2.0, "yaw_rad": 0.0, "tx": 1.0, "ty": 0.0,
                "floor_normal": [0.0, 0.0, 1.0], "floor_offset": 0.0,
                "residual_m": 0.1, "eye_height_m": 1.5, "hash": f"al-{self.fit_calls}"}

    @staticmethod
    def to_graph_xy(alignment: dict, p) -> tuple[float, float]:
        return (p[0] * alignment["scale"] + alignment["tx"], p[1] * alignment["scale"])

    async def extract(self, client, video, *, mode, deadline_s, anchor_hint=None):
        self.extract_calls.append(mode)
        while not self.block_extract.is_set():
            await asyncio.sleep(0.01)
        g = _office().model_copy(update={"video_sha256": video.sha256})
        return ExtractionResult(status="completed", graph=g,
                                findings=check_graph(g, video.duration_s), receipt=None,
                                mode=mode, agentic_observed=None,
                                video_uri="https://fake.test/files/x", error=None)

    async def refine(self, client, graph, video, extraction, *, sfm, alignment, base_url,
                     max_iterations=4, deadline_s):
        self.refine_calls.append({"alignment": alignment, "sfm": sfm, "base_url": base_url})
        new = graph.model_copy(update={"zones": [
            z.model_copy(update={"name": z.name + "*"}) if z.id == "Z1" else z
            for z in graph.zones]})
        rdir = video.path.parent / f"renders-{len(self.refine_calls)}"
        rdir.mkdir(parents=True, exist_ok=True)
        renders = []
        for i, (t, kind) in enumerate(((2.0, "perspective"), (None, "top"))):
            p = rdir / f"view{i}.png"
            p.write_bytes(b"\x89PNG\r\n\x1a\n" + bytes([i]) * 16)
            renders.append({"t_s": t, "path": str(p), "kind": kind})
        it = {"index": 0, "graph_revision": new.revision, "discrepancy_count": 1,
              "applied": [0], "rejected": [], "findings": [], "geometry": None,
              "renders": renders, "receipt": None, "stop_reason": "no_discrepancies"}
        return new, [it]

    async def prepare_environment(self, client) -> str:
        self.env_calls += 1
        await asyncio.sleep(0.01)
        return "env-1"

    @staticmethod
    def allowed_interventions(graph: VenueGraph, scenario: Scenario) -> list[str]:
        hazard = {h.door_id for h in scenario.hazards}
        return sorted(f"OPEN:{d.id}" for d in graph.doors
                      if d.state in ("closed", "locked", "unknown") and d.id not in hazard)[:6]

    async def render_topdown(self, graph, out_dir: Path, base_url: str, hazards) -> Path:
        out_dir.mkdir(parents=True, exist_ok=True)
        p = out_dir / "top.png"
        p.write_bytes(b"\x89PNG fake")
        return p

    async def investigate(self, client, graph, scenario, params, *, environment_id,
                          topdown_png, deadline_s=180, max_rounds=4) -> dict:
        self.investigate_calls.append(scenario)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(0.05)
        finally:
            self.active -= 1
        results = []
        for iid in self.allowed_interventions(graph, scenario):
            s2 = scenario.model_copy(update={"interventions": [*scenario.interventions, iid]})
            run = solve(graph, s2, params)
            results.append({"intervention_id": iid, "run_id": run.run_id,
                            "reached_exit": run.reached_exit, "total": run.total,
                            "delta_vs_current": 1, "limiting_doors": [],
                            "check_ok": self.check_ok and check_run(graph, s2, params, run).ok})
        n = len(self.investigate_calls)
        return {"investigation_id": f"inv-{n}", "graph_revision": graph.revision,
                "scenario_hash": scenario.hash, "status": "completed",
                "interaction_id": f"int-{n}", "environment_id": environment_id,
                "ledger": [], "sandbox_runs": 0, "results": results,
                "recommendation": None, "best": results[0] if results else None,
                "disagreement": None, "hook_denials": 0, "receipt": None,
                "topdown_png": str(topdown_png)}

    def draft_note(self, session, approval) -> str:
        self.notes.append((session.scenario.hash, approval.intervention_id))
        return f"# DRAFT — not sent\n\nTo security: {approval.intervention_id}\n"


@pytest.fixture
def fakes() -> Fakes:
    return Fakes()


@pytest.fixture
def services(tmp_path, fakes) -> Services:
    return Services(
        runtime_root=tmp_path / "runtime",
        base_url="http://127.0.0.1:9",
        make_client=lambda: object(),
        prepare_video=fakes.prepare_video,
        run_sfm=fakes.run_sfm,
        fit_alignment=fakes.fit_alignment,
        to_graph_xy=fakes.to_graph_xy,
        extract=fakes.extract,
        refine=fakes.refine,
        prepare_environment=fakes.prepare_environment,
        investigate=fakes.investigate,
        allowed_interventions=fakes.allowed_interventions,
        render_topdown=fakes.render_topdown,
        draft_note=fakes.draft_note,
    )


@pytest.fixture
def client(services):
    api.app.dependency_overrides[get_services] = lambda: services
    try:
        with TestClient(api.app) as c:
            yield c
    finally:
        api.app.dependency_overrides.clear()


# --- helpers --------------------------------------------------------------------


def wait_for(c: TestClient, sid: str, pred, timeout: float = 10.0) -> dict:
    end = time.monotonic() + timeout
    while True:
        snap = c.get(f"/api/sessions/{sid}").json()
        if pred(snap):
            return snap
        if time.monotonic() > end:
            raise AssertionError(f"timed out; jobs={snap.get('jobs')}")
        time.sleep(0.02)


def idle(snap: dict) -> bool:
    return all(j["status"] in ("done", "failed") for j in snap["jobs"].values())


def upload(c: TestClient, path: Path | None = None, **form) -> str:
    data = path.read_bytes() if path else b"not really a video"
    r = c.post("/api/sessions", files={"video": ("walk.mp4", data, "video/mp4")}, data=form)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def with_draft(c: TestClient) -> tuple[str, dict]:
    sid = upload(c)
    r = c.post(f"/api/sessions/{sid}/extract", json={"mode": "static_hifps"})
    assert r.status_code == 202, r.text
    snap = wait_for(c, sid, lambda s: s["draft_revision"] is not None and idle(s))
    return sid, snap


def accepted(c: TestClient) -> tuple[str, dict]:
    sid, snap = with_draft(c)
    r = c.post(f"/api/sessions/{sid}/accept", json={"expected_revision": snap["draft_revision"]})
    assert r.status_code == 200, r.text
    snap = wait_for(c, sid, lambda s: idle(s) and len(s["investigations"]) == 3)
    return sid, snap


def set_fire(c: TestClient, sid: str, snap: dict, *doors: str):
    return c.post(f"/api/sessions/{sid}/scenario", json={
        "expected_revision": snap["accepted_revision"],
        "hazards": [{"door_id": d, "kind": "fire"} for d in doors]})


# --- brief tests ----------------------------------------------------------------


def test_upload_starts_sfm_job(client, services, fakes, tmp_path):
    clip = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc=size=64x48:rate=10:duration=1", "-pix_fmt", "yuv420p",
                    str(clip)], check=True)
    services.prepare_video = lambda src, out: prepare_video(src, out)  # real ffmpeg
    sid = upload(client, clip)
    snap = client.get(f"/api/sessions/{sid}").json()
    assert snap["jobs"]["sfm"]["kind"] == "sfm"
    assert snap["jobs"]["sfm"]["status"] in ("queued", "running", "done")
    snap = wait_for(client, sid, lambda s: s["jobs"]["sfm"]["status"] == "done")
    assert len(fakes.sfm_calls) == 1
    assert snap["sfm"]["status"] == "completed" and snap["sfm"]["frame_count"] == 3
    assert snap["ghost_path"] == []  # no alignment yet
    assert 0.9 < snap["video"]["duration_s"] < 1.2
    assert (services.runtime_root / "sessions" / sid / "session.json").exists()
    v = client.get(f"/api/sessions/{sid}/video")
    assert v.status_code == 200 and v.headers["content-type"] == "video/mp4"
    f = client.get(f"/api/sessions/{sid}/frame", params={"t": 0.5})
    assert f.status_code == 200 and f.headers["content-type"] == "image/jpeg"
    assert client.get(f"/api/sessions/{sid}/frame", params={"t": 99}).status_code == 422


def test_accept_rejects_errors_422(client):
    sid, snap = with_draft(client)
    g = VenueGraph.model_validate(snap["draft_graph"])
    broken = g.model_copy(update={"doors": [d for d in g.doors if d.b != "OUTSIDE"]})
    r = client.put(f"/api/sessions/{sid}/graph", json={
        "expected_revision": snap["draft_revision"], "graph": broken.model_dump(mode="json")})
    assert r.status_code == 200
    rev = r.json()["revision"]
    r = client.post(f"/api/sessions/{sid}/accept", json={"expected_revision": rev})
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "graph_errors"
    assert any(f["code"] == "NO_EXIT" for f in body["findings"])
    snap = client.get(f"/api/sessions/{sid}").json()
    assert snap["accepted_graph"] is None and snap["current_run"] is None


def test_put_graph_stale_409(client):
    sid, snap = with_draft(client)
    g = VenueGraph.model_validate(snap["draft_graph"])
    edited = g.model_copy(update={"doors": [
        d.model_copy(update={"state": "closed"}) if d.id == "D6" else d for d in g.doors]})
    r = client.put(f"/api/sessions/{sid}/graph", json={
        "expected_revision": "g-0000000000000000", "graph": edited.model_dump(mode="json")})
    assert r.status_code == 409
    assert r.json()["error"] == "stale"
    assert r.json()["current"] == snap["draft_revision"]
    r = client.put(f"/api/sessions/{sid}/graph", json={
        "expected_revision": snap["draft_revision"], "graph": edited.model_dump(mode="json")})
    assert r.status_code == 200
    assert r.json()["revision"] == edited.revision
    # the old revision is now stale
    r = client.put(f"/api/sessions/{sid}/graph", json={
        "expected_revision": snap["draft_revision"], "graph": g.model_dump(mode="json")})
    assert r.status_code == 409
    r = client.post(f"/api/sessions/{sid}/accept", json={"expected_revision": snap["draft_revision"]})
    assert r.status_code == 409 and r.json()["error"] == "stale"


def test_scenario_resolve_returns_checked_run(client):
    sid, snap = accepted(client)
    assert snap["current_check"]["ok"] is True
    base_reached = snap["current_run"]["reached_exit"]
    r = set_fire(client, sid, snap, "D2")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["scenario_hash"] == _fire("D2").hash
    assert body["check"]["ok"] is True
    assert body["check"]["run_id"] == body["run"]["run_id"]
    snap = client.get(f"/api/sessions/{sid}").json()
    assert snap["current_check"]["ok"] is True
    assert snap["current_run"]["scenario_hash"] == snap["scenario_hash"] == _fire("D2").hash
    assert snap["current_run"]["reached_exit"] < base_reached
    # stale and unknown-door requests are refused without changing state
    r = client.post(f"/api/sessions/{sid}/scenario", json={
        "expected_revision": "g-stale", "hazards": []})
    assert r.status_code == 409 and r.json()["error"] == "stale"
    r = set_fire(client, sid, snap, "D99")
    assert r.status_code == 422 and r.json()["error"] == "unknown_door"
    assert client.get(f"/api/sessions/{sid}").json()["scenario_hash"] == _fire("D2").hash


def test_accept_starts_three_precomputed_investigations(client, fakes):
    sid, snap = with_draft(client)
    r = client.post(f"/api/sessions/{sid}/accept", json={"expected_revision": snap["draft_revision"]})
    assert r.status_code == 200
    body = r.json()
    assert body["check"]["ok"] is True
    assert len(body["investigation_jobs"]) == 3
    snap = client.get(f"/api/sessions/{sid}").json()
    inv_jobs = [j for j in snap["jobs"].values() if j["kind"] == "investigate"]
    assert len(inv_jobs) == 3
    snap = wait_for(client, sid, lambda s: idle(s) and len(s["investigations"]) == 3)
    rev = snap["accepted_revision"]
    # exits by baseline flow: D2 and D4 carry people, the locked D5 carries none
    expected = {_fire(e).hash for e in ("D2", "D4", "D5")}
    assert {i["scenario_hash"] for i in snap["investigations"]} == expected
    assert all(i["graph_revision"] == rev for i in snap["investigations"])
    assert fakes.max_active <= 3
    assert fakes.env_calls == 1  # environment prepared once and shared
    assert all(j["status"] == "done" for j in snap["jobs"].values() if j["kind"] == "investigate")
    # the current scenario (no hazards) has no precomputed investigation
    assert snap["ready_investigation_id"] is None


def test_precomputed_investigation_matches_hazard(client, fakes):
    sid, snap = accepted(client)
    n_calls = len(fakes.investigate_calls)
    r = set_fire(client, sid, snap, "D2")
    want = next(i for i in snap["investigations"] if i["scenario_hash"] == _fire("D2").hash)
    assert r.json()["ready_investigation_id"] == want["investigation_id"]
    snap = client.get(f"/api/sessions/{sid}").json()
    assert snap["ready_investigation_id"] == want["investigation_id"]
    assert snap["scenario_hash"] == want["scenario_hash"]
    assert len(fakes.investigate_calls) == n_calls  # only the local solve ran
    # D1 is an interior door with no precomputed investigation
    r = set_fire(client, sid, snap, "D1")
    assert r.status_code == 200
    assert r.json()["ready_investigation_id"] is None
    assert client.get(f"/api/sessions/{sid}").json()["ready_investigation_id"] is None


def test_stale_investigation_rejected(client):
    sid, snap = accepted(client)
    set_fire(client, sid, snap, "D2")
    snap = client.get(f"/api/sessions/{sid}").json()
    inv_id = snap["ready_investigation_id"]
    assert inv_id is not None
    r = set_fire(client, sid, snap, "D2", "D4")  # hazards change after the investigation
    assert r.status_code == 200
    snap = client.get(f"/api/sessions/{sid}").json()
    r = client.post(f"/api/sessions/{sid}/approve", json={
        "expected_revision": snap["accepted_revision"],
        "expected_scenario": snap["scenario_hash"],
        "investigation_id": inv_id, "intervention_id": "OPEN:D5"})
    assert r.status_code == 409
    assert r.json()["error"] == "stale_investigation"
    snap2 = client.get(f"/api/sessions/{sid}").json()
    assert snap2["approvals"] == [] and snap2["scenario"]["interventions"] == []


def test_approve_unchecked_intervention_rejected(client, fakes):
    fakes.check_ok = False
    sid, snap = accepted(client)
    set_fire(client, sid, snap, "D2")
    snap = client.get(f"/api/sessions/{sid}").json()
    inv_id = snap["ready_investigation_id"]
    body = {"expected_revision": snap["accepted_revision"],
            "expected_scenario": snap["scenario_hash"], "investigation_id": inv_id}
    r = client.post(f"/api/sessions/{sid}/approve", json={**body, "intervention_id": "OPEN:D5"})
    assert r.status_code == 422 and r.json()["error"] == "intervention_unchecked"
    r = client.post(f"/api/sessions/{sid}/approve", json={**body, "intervention_id": "OPEN:D9"})
    assert r.status_code == 422 and r.json()["error"] == "intervention_unchecked"
    snap = client.get(f"/api/sessions/{sid}").json()
    assert snap["approvals"] == [] and snap["scenario"]["interventions"] == []
    assert fakes.notes == []


def test_static_mount_does_not_shadow_api(tmp_path, services):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>WalkTwin</title>")
    app = create_app(static_dir=dist)
    app.dependency_overrides[get_services] = lambda: services
    with TestClient(app) as c:
        for path in ("/api/sessions/x", "/api/sessions/abcdef123456", "/api/nope"):
            r = c.get(path)
            assert r.status_code == 404, path
            assert r.headers["content-type"].startswith("application/json"), path
            assert r.json()["error"] == "not_found"
        r = c.get("/")
        assert r.status_code == 200 and "WalkTwin" in r.text  # the mount is active
    # the mount is last
    assert type(app.routes[-1]).__name__ == "Mount"


# --- further tests --------------------------------------------------------------


def test_approve_applies_checked_intervention_and_drafts_note(client, fakes, services):
    sid, snap = accepted(client)
    set_fire(client, sid, snap, "D2")
    snap = client.get(f"/api/sessions/{sid}").json()
    inv_id = snap["ready_investigation_id"]
    r = client.post(f"/api/sessions/{sid}/approve", json={
        "expected_revision": snap["accepted_revision"], "expected_scenario": "s-stale",
        "investigation_id": inv_id, "intervention_id": "OPEN:D5"})
    assert r.status_code == 409 and r.json()["error"] == "stale"
    r = client.post(f"/api/sessions/{sid}/approve", json={
        "expected_revision": snap["accepted_revision"],
        "expected_scenario": snap["scenario_hash"],
        "investigation_id": inv_id, "intervention_id": "OPEN:D5"})
    assert r.status_code == 200, r.text
    body = r.json()
    new_hash = _fire("D2", interventions=("OPEN:D5",)).hash
    assert body["scenario_hash"] == new_hash
    assert body["check"]["ok"] is True
    ap = body["approval"]
    assert ap["investigation_id"] == inv_id and ap["run_id"] == body["run"]["run_id"]
    assert ap["graph_revision"] == snap["accepted_revision"] and ap["scenario_hash"] == new_hash
    note = Path(ap["note_path"])
    assert note.read_text().startswith("# DRAFT — not sent")
    assert note.is_relative_to(services.runtime_root / "sessions" / sid)
    assert fakes.notes == [(new_hash, "OPEN:D5")]  # drafted from the post-approval state
    snap = client.get(f"/api/sessions/{sid}").json()
    assert snap["scenario"]["interventions"] == ["OPEN:D5"]
    assert snap["current_run"]["run_id"] == snap["current_check"]["run_id"] == ap["run_id"]
    assert len(snap["approvals"]) == 1


def test_job_running_409(client, fakes):
    sid = upload(client)
    fakes.block_extract.clear()
    assert client.post(f"/api/sessions/{sid}/extract", json={"mode": "static"}).status_code == 202
    r = client.post(f"/api/sessions/{sid}/extract", json={"mode": "static"})
    assert r.status_code == 409 and r.json()["error"] == "job_running"
    assert client.post(f"/api/sessions/{sid}/extract", json={"mode": "bogus"}).status_code == 422
    fakes.block_extract.set()
    snap = wait_for(client, sid, idle)
    assert snap["jobs"]["extract"]["status"] == "done"
    assert fakes.extract_calls == ["static"]


def test_refine_fits_alignment_once_and_ghost_path(client, fakes):
    sid, snap = with_draft(client)
    snap = wait_for(client, sid, lambda s: s["jobs"]["sfm"]["status"] == "done")
    assert snap["ghost_path"] == []
    r = client.post(f"/api/sessions/{sid}/refine", json={"expected_revision": "g-stale"})
    assert r.status_code == 409 and r.json()["error"] == "stale"
    r = client.post(f"/api/sessions/{sid}/refine", json={"expected_revision": snap["draft_revision"]})
    assert r.status_code == 202
    snap = wait_for(client, sid, lambda s: idle(s) and s["jobs"]["refine"]["status"] == "done")
    assert fakes.fit_calls == 1
    assert snap["alignment"]["hash"] == "al-1"
    assert snap["draft_graph"]["zones"][0]["name"].endswith("*")
    assert len(snap["iterations"]) == 1
    assert snap["ghost_path"] == [{"t_s": 0.0, "x": 1.0, "y": 2.0},
                                  {"t_s": 0.5, "x": 2.0, "y": 2.0},
                                  {"t_s": 1.0, "x": 3.0, "y": 2.0}]
    r = client.post(f"/api/sessions/{sid}/refine", json={"expected_revision": snap["draft_revision"]})
    assert r.status_code == 202
    snap = wait_for(client, sid, lambda s: idle(s) and len(s["iterations"]) == 2)
    assert fakes.fit_calls == 1  # frozen
    assert [c["alignment"]["hash"] for c in fakes.refine_calls] == ["al-1", "al-1"]


def test_job_exception_is_captured(client, services):
    def boom(video, work_dir):
        raise RuntimeError("pycolmap exploded")
    services.run_sfm = boom
    sid = upload(client)
    snap = wait_for(client, sid, lambda s: s["jobs"]["sfm"]["status"] == "failed")
    assert "pycolmap exploded" in snap["jobs"]["sfm"]["error"]
    assert client.get(f"/api/sessions/{sid}").status_code == 200  # server still fine


def test_default_report_module_serves_report_and_note(client, services):
    defaults = api.default_services(services.runtime_root)
    services.build_report, services.render_html = defaults.build_report, defaults.render_html
    services.draft_note = defaults.draft_note
    sid = upload(client)
    r = client.get(f"/api/sessions/{sid}/report")
    assert r.status_code == 200 and r.json()["verdict"] == "incomplete"
    sid, snap = accepted(client)
    rep = client.get(f"/api/sessions/{sid}/report").json()
    assert rep["verdict"] in ("verified_within_model", "failed")
    assert rep["run_id"] == snap["current_run"]["run_id"] and rep["security_note"] == ""
    page = client.get(f"/api/sessions/{sid}/report.html")
    assert page.status_code == 200 and "<script" not in page.text
    assert "Content-Security-Policy" in page.text
    set_fire(client, sid, snap, "D2")
    snap = client.get(f"/api/sessions/{sid}").json()
    r = client.post(f"/api/sessions/{sid}/approve", json={
        "expected_revision": snap["accepted_revision"],
        "expected_scenario": snap["scenario_hash"],
        "investigation_id": snap["ready_investigation_id"], "intervention_id": "OPEN:D5"})
    assert r.status_code == 200, r.text
    note = r.json()["note"]
    assert note.splitlines()[0] == "# DRAFT — not sent" and "D5 must stay unlocked" in note
    assert client.get(f"/api/sessions/{sid}/report").json()["security_note"] == note


def test_session_persisted_and_reloaded(client, services):
    sid, snap = accepted(client)
    store = SessionStore(services.runtime_root)
    s = store.get(sid)
    assert s is not None
    assert s.accepted_graph.revision == snap["accepted_revision"]
    assert s.current_check.ok and s.current_check.run_id == s.current_run.run_id
    assert len(s.investigations) == 3
    assert isinstance(s.video, PreparedVideo) and s.video.path.exists()


def test_snapshot_fields_r24(client):
    sid, snap = with_draft(client)
    assert snap["draft_revision"] == VenueGraph.model_validate(snap["draft_graph"]).revision
    assert snap["graph_revision"] is None and snap["allowed_interventions"] == []
    assert snap["scenario_hash"] == Scenario().hash
    g = VenueGraph.model_validate(snap["draft_graph"])
    assert snap["findings"] == [f.model_dump(mode="json") for f in check_graph(g, 60.0)]
    sid, snap = accepted(client)
    assert snap["graph_revision"] == snap["accepted_revision"] is not None
    assert snap["allowed_interventions"] == ["OPEN:D5"]  # D5 is the locked exit
    set_fire(client, sid, snap, "D5")
    snap = client.get(f"/api/sessions/{sid}").json()
    assert snap["allowed_interventions"] == []  # a door under a hazard is not allowed
    assert snap["scenario_hash"] == _fire("D5").hash


def test_allowed_interventions_unavailable_is_empty(client, services):
    def missing(graph, scenario):
        raise ModuleNotFoundError("No module named 'walktwin.agent'")
    services.allowed_interventions = missing
    sid, snap = accepted(client)
    assert snap["allowed_interventions"] == []


def test_render_url_route(client):
    sid, snap = with_draft(client)
    snap = wait_for(client, sid, lambda s: s["jobs"]["sfm"]["status"] == "done")
    client.post(f"/api/sessions/{sid}/refine", json={"expected_revision": snap["draft_revision"]})
    snap = wait_for(client, sid, lambda s: idle(s) and len(s["iterations"]) == 1)
    client.post(f"/api/sessions/{sid}/refine", json={"expected_revision": snap["draft_revision"]})
    snap = wait_for(client, sid, lambda s: idle(s) and len(s["iterations"]) == 2)
    for n, it in enumerate(snap["iterations"]):
        assert [r["url"] for r in it["renders"]] == [
            f"/api/sessions/{sid}/renders/{n}/0.png", f"/api/sessions/{sid}/renders/{n}/1.png"]
    r = client.get(snap["iterations"][1]["renders"][1]["url"])
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert r.content == Path(snap["iterations"][1]["renders"][1]["path"]).read_bytes()
    for bad in ("2/0.png", "0/2.png", "-1/0.png"):
        r = client.get(f"/api/sessions/{sid}/renders/{bad}")
        assert r.status_code == 404 and r.json()["error"] == "not_found", bad


def test_note_route_and_report_security_note(client, services):
    services.build_report = lambda session: {"session_id": session.id, "verdict": "incomplete"}
    sid, snap = accepted(client)
    assert client.get(f"/api/sessions/{sid}/report").json()["security_note"] == ""
    assert client.get(f"/api/sessions/{sid}/approvals/0/note").status_code == 404
    set_fire(client, sid, snap, "D2")
    snap = client.get(f"/api/sessions/{sid}").json()
    r = client.post(f"/api/sessions/{sid}/approve", json={
        "expected_revision": snap["accepted_revision"],
        "expected_scenario": snap["scenario_hash"],
        "investigation_id": snap["ready_investigation_id"], "intervention_id": "OPEN:D5"})
    assert r.status_code == 200
    r = client.get(f"/api/sessions/{sid}/approvals/0/note")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/markdown")
    assert r.text.startswith("# DRAFT — not sent")
    assert client.get(f"/api/sessions/{sid}/report").json()["security_note"] == r.text
