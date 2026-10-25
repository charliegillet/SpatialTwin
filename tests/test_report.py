"""Verification report, HTML export and the drafted note to security (Task 15)."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from walktwin import report as rp
from walktwin.checker import check_run
from walktwin.contracts import FlowParams, Hazard, Measure, Scenario, VenueGraph
from walktwin.egress_rules import ALWAYS_CANNOT_MEASURE
from walktwin.flow import solve
from walktwin.media import PreparedVideo
from walktwin.sessions import Approval, Session, to_jsonable

FIXTURES = Path(__file__).parent / "fixtures"
PARAMS = FlowParams()
BANNED = ("safe", "compliant", "survive", "evacuated")
CSP = ("<meta http-equiv=\"Content-Security-Policy\" "
       "content=\"default-src 'none'; style-src 'unsafe-inline'\">")


def _office() -> VenueGraph:
    return VenueGraph.model_validate_json((FIXTURES / "office_graph.json").read_text())


def _geometry(crossings: int = 0, wall: float = 0.9, edge: float | None = 0.8) -> dict:
    return {"alignment_hash": "a-1", "illegal_crossings": [
                {"t_s": 3.0 + i, "x": 1.0, "y": 2.0, "edge": "Z1.north"} for i in range(crossings)],
            "wall_support": wall, "unexplained_points": 0.05,
            "edge_chamfer_px": 2.5 if edge is not None else None,
            "edge_within_5px": edge, "heldout_t_s": [4.0, 9.0] if edge is not None else []}


def _iteration(index: int, rev: str, geometry: dict | None, discrepancies: int = 0) -> dict:
    return {"index": index, "graph_revision": rev, "discrepancy_count": discrepancies,
            "applied": [], "rejected": [], "findings": [], "geometry": geometry,
            "renders": [], "receipt": {"interaction_id": f"crit-{index}",
                                       "provider_model": "gemini-4-argon", "status": "completed",
                                       "usage": {}, "elapsed_ms": 10, "processing_calls": 0},
            "stop_reason": None if index == 0 else "no_discrepancies"}


def _alignment(eye: float = 1.52, residual: float = 0.12) -> dict:
    return {"scale": 1.0, "yaw_rad": 0.0, "tx": 0.0, "ty": 0.0, "floor_normal": [0.0, 0.0, 1.0],
            "floor_offset": 0.0, "residual_m": residual, "eye_height_m": eye, "hash": "a-1",
            "_reflected": False}


def _session(graph: VenueGraph | None = None, *, sfm: bool = True, hazard: str = "D2",
             interventions: tuple[str, ...] = (), run: bool = True) -> Session:
    graph = graph or _office()
    scenario = Scenario(hazards=[Hazard(door_id=hazard, kind="fire")],
                        interventions=list(interventions))
    s = Session(id="0123456789ab",
                video=PreparedVideo(path=Path("/nonexistent/walk.mp4"), sha256="b" * 64,
                                    duration_s=90.0, width=640, height=360),
                draft_graph=graph, accepted_graph=graph, scenario=scenario)
    if run:
        r = solve(graph, scenario, PARAMS)
        s.current_run, s.current_check = r, check_run(graph, scenario, PARAMS, r)
    if sfm:
        s.alignment = _alignment()
        s.iterations = [_iteration(0, graph.revision, _geometry(crossings=1, wall=0.85), 3),
                        _iteration(1, graph.revision, _geometry(crossings=0, wall=0.9), 0)]
    else:
        s.iterations = [_iteration(0, graph.revision, None, 0)]
    return s


def _approved(tmp_path: Path) -> tuple[Session, Approval]:
    s = _session(hazard="D2")
    graph = s.accepted_graph
    scenario = Scenario(hazards=list(s.scenario.hazards), interventions=["OPEN:D5"])
    before = solve(graph, s.scenario, PARAMS)
    after = solve(graph, scenario, PARAMS)
    s.investigations = [{
        "investigation_id": "inv-0", "graph_revision": graph.revision,
        "scenario_hash": s.scenario.hash, "status": "completed", "interaction_id": "int-0",
        "environment_id": "env-1", "ledger": [], "sandbox_runs": 0,
        "results": [{"intervention_id": "OPEN:D5", "run_id": after.run_id,
                     "reached_exit": after.reached_exit, "total": after.total,
                     "delta_vs_current": after.reached_exit - before.reached_exit,
                     "check_ok": True, "limiting_doors": ["D5"]}],
        "recommendation": None, "best": None, "disagreement": None, "hook_denials": 0,
        "receipt": {"interaction_id": "int-0", "provider_model": "antigravity-preview-09-2026",
                    "status": "completed", "usage": {}, "elapsed_ms": 1000,
                    "processing_calls": 0}}]
    s.scenario = scenario
    s.current_run, s.current_check = after, check_run(graph, scenario, PARAMS, after)
    approved_at = datetime(2026, 10, 25, 18, 42, tzinfo=timezone.utc).isoformat()
    approval = Approval(intervention_id="OPEN:D5", investigation_id="inv-0",
                        graph_revision=graph.revision, scenario_hash=scenario.hash,
                        run_id=after.run_id, note_path=str(tmp_path / "approval-1.md"),
                        approved_at=approved_at)
    s.approvals = [approval]
    return s, approval


def _req(report, rid: str):
    return next(r for r in report.requirements if r.id == rid)


# --- brief tests ----------------------------------------------------------------


def test_verdict_verified():
    s = _session()
    assert s.current_check.ok
    report = rp.build_report(s)
    assert report.verdict == "verified_within_model"
    assert report.session_id == s.id and report.run_id == s.current_run.run_id
    assert report.graph_revision == s.accepted_graph.revision
    assert report.scenario_hash == s.scenario.hash
    assert not [r for r in report.requirements if r.status == "fail"]
    assert _req(report, "checker").status == "pass" and _req(report, "checker").method == "checker"
    assert _req(report, "population_conserved").status == "pass"
    assert _req(report, "graph_zero_errors").status == "pass"
    assert _req(report, "exit_video_evidence").status == "pass"
    scale = _req(report, "alignment_scale")
    assert scale.method == "measured" and scale.status == "pass" and "agrees" in scale.value
    disc = _req(report, "loop_discrepancies")
    assert disc.method == "model_reported" and disc.value == "0"
    # every RuleResult is mirrored, with its citation
    assert len(report.rules) == 10
    for rule in report.rules:
        row = _req(report, f"{rule.rule_id}:{rule.element_id}")
        assert row.status == rule.status and rule.citation in row.evidence
    for rule_id, _ in ALWAYS_CANNOT_MEASURE:
        row = _req(report, rule_id)
        assert row.method == "outside_model" and row.status == "cannot_measure"
    assert report.declared_parameters["horizon_s"] == 120
    assert any(s.video.sha256 in p for p in report.provenance)


def test_incomplete_without_accepted_run():
    s = _session(run=False)
    assert rp.build_report(s).verdict == "incomplete"
    s = _session()
    s.accepted_graph = None
    assert rp.build_report(s).verdict == "incomplete"
    s = _session()  # run belongs to another scenario
    s.scenario = Scenario(hazards=[Hazard(door_id="D4", kind="fire")])
    assert rp.build_report(s).verdict == "incomplete"


def test_failed_rule_fails_verdict():
    g = _office()
    narrow = Measure(low_m=0.5, high_m=0.6, basis="estimated")
    g = g.model_copy(update={"doors": [d.model_copy(update={"clear_width": narrow})
                                       if d.id == "D6" else d for d in g.doors]})
    report = rp.build_report(_session(g))
    row = _req(report, "ADA-404.2.3:D6")
    assert row.status == "fail" and "§404.2.3" in row.evidence
    assert _req(report, "checker").status == "pass"
    assert report.verdict == "failed"


def test_failed_checker_fails_verdict():
    s = _session()
    s.current_check = type(s.current_check)(ok=False, run_id=s.current_run.run_id,
                                            violations=["door D2: capacity exceeded"])
    report = rp.build_report(s)
    assert _req(report, "checker").status == "fail"
    assert report.verdict == "failed"


def test_geometry_rows_measured_or_not_run():
    ids = ("geometry_illegal_crossings", "geometry_wall_support", "geometry_edge_alignment")
    report = rp.build_report(_session(sfm=True))
    for rid in ids:
        row = _req(report, rid)
        assert row.method == "measured" and row.status == "pass", row
    assert _req(report, "geometry_illegal_crossings").value == "0"
    assert _req(report, "geometry_wall_support").value == "0.90"

    s = _session(sfm=True)
    s.iterations[-1]["geometry"] = _geometry(crossings=2, wall=0.5, edge=0.2)
    report = rp.build_report(s)
    for rid in ids:
        assert _req(report, rid).status == "fail", rid
    assert report.verdict == "failed"

    s = _session(sfm=True)
    s.iterations[-1]["geometry"] = _geometry(edge=None)
    assert _req(rp.build_report(s), "geometry_edge_alignment").status == "not_run"

    report = rp.build_report(_session(sfm=False))
    for rid in (*ids, "alignment_scale"):
        assert _req(report, rid).status == "not_run", rid
    assert report.verdict == "verified_within_model"


GEOM_IDS = ("geometry_illegal_crossings", "geometry_wall_support", "geometry_edge_alignment")


def _with_reason(s: Session, reason: str) -> Session:
    """Set geometry_unavailable_reason (R30), whether or not the field is merged yet."""
    if "geometry_unavailable_reason" in Session.model_fields:
        s.geometry_unavailable_reason = reason
        return s
    return s.model_copy(update={"geometry_unavailable_reason": reason})


def test_scale_badge_disagrees_is_cannot_measure_not_failed():
    s = _session()
    s.alignment = _alignment(eye=2.4)
    report = rp.build_report(s)
    assert report.verdict == "verified_within_model"  # R31: the badge never fails the verdict
    row = _req(report, "alignment_scale")
    assert row.status == "cannot_measure" and "disagrees" in row.value
    assert "scale badge disagrees" in row.evidence
    for rid in GEOM_IDS:
        row = _req(report, rid)
        assert row.status == "cannot_measure" and "scale badge disagrees" in row.evidence, rid
    todo = [h for h in report.hand_checks if h.startswith("Re-tape the anchor door")]
    assert len(todo) == 1 and "re-capture the venue walkthrough" in todo[0]
    assert "alignment_scale" in todo[0] and all(rid in todo[0] for rid in GEOM_IDS)


def test_geometry_unavailable_reason_is_cannot_measure_not_failed():
    s = _with_reason(_session(sfm=False), "sfm failed: no_floor_plane")
    report = rp.build_report(s)
    assert report.verdict == "verified_within_model"
    for rid in (*GEOM_IDS, "alignment_scale"):
        row = _req(report, rid)
        assert row.status == "cannot_measure" and "no_floor_plane" in row.evidence, rid
    todo = [h for h in report.hand_checks if h.startswith("Re-run SfM")]
    assert len(todo) == 1 and "no_floor_plane" in todo[0] and "venue" in todo[0]
    # a reason other than SfM failure still asks for SfM and alignment again
    s = _with_reason(_session(), "scale badge unavailable: TypeError: boom")
    report = rp.build_report(s)
    assert report.verdict == "verified_within_model"
    assert any(h.startswith("Re-run SfM and the alignment fit") for h in report.hand_checks)


def test_geometry_rows_use_accepted_revision():
    s = _session(sfm=True)
    rev = s.accepted_graph.revision
    # the final scored round describes another graph: it must not be reported
    s.iterations.append(_iteration(2, "g-other", _geometry(crossings=5, wall=0.1, edge=0.1), 4))
    s.iterations[-1]["applied"] = [0]
    report = rp.build_report(s)
    assert _req(report, "geometry_illegal_crossings").value == "0"
    assert rev in _req(report, "geometry_wall_support").evidence
    assert report.verdict == "verified_within_model"
    # no scored round for the accepted graph at all
    s = _session(sfm=True)
    for it in s.iterations:
        it["graph_revision"] = "g-other"
    report = rp.build_report(s)
    for rid in GEOM_IDS:
        row = _req(report, rid)
        assert row.status == "not_run"
        assert row.evidence == "no geometry score for the accepted graph"
    disc = _req(report, "loop_discrepancies")
    assert disc.status == "not_run" and "accepted graph" in disc.evidence
    # scored under a different alignment from the persisted one
    s = _session(sfm=True)
    s.alignment = {**_alignment(), "hash": "a-2"}
    assert _req(rp.build_report(s), "geometry_wall_support").status == "not_run"


def test_baseline_same_alignment_and_single_round():
    s = _session(sfm=True)
    s.iterations = [s.iterations[-1]]
    report = rp.build_report(s)
    for rid in ("geometry_wall_support", "geometry_edge_alignment"):
        row = _req(report, rid)
        assert row.status == "pass" and "single measured round; no baseline to compare" in row.evidence
    # an earlier round under another alignment is not a baseline
    s = _session(sfm=True)
    s.iterations[0]["geometry"] = {**_geometry(wall=0.99, edge=0.99), "alignment_hash": "a-0"}
    row = _req(rp.build_report(s), "geometry_wall_support")
    assert row.status == "pass" and "single measured round" in row.evidence


def test_discrepancy_row_uses_round_that_critiqued_accepted_graph():
    s = _session(sfm=False)
    rev = s.accepted_graph.revision
    # round 0 critiqued an earlier graph and patched it into the accepted one
    s.iterations = [{**_iteration(0, rev, None, 3), "applied": [0, 1]}]
    s.iterations[0]["stop_reason"] = "max_iterations"
    row = _req(rp.build_report(s), "loop_discrepancies")
    assert row.status == "not_run" and "accepted graph" in row.evidence
    # round 1 critiqued the accepted graph and reported 2
    s.iterations.append({**_iteration(1, "g-next", None, 2), "applied": [0]})
    report = rp.build_report(s)
    row = _req(report, "loop_discrepancies")
    assert row.status == "cannot_measure" and row.value == "2" and "round 1" in row.evidence
    todo = [h for h in report.hand_checks if "loop_discrepancies" in h]
    assert len(todo) == 1 and todo[0].startswith("Review the 2 model-reported discrepancies")
    # a provider failure's count of 0 is not a critique
    s.iterations.append({**_iteration(2, rev, None, 0), "stop_reason": "provider_failed"})
    assert _req(rp.build_report(s), "loop_discrepancies").value == "2"


def test_run_id_is_accepted_run_only():
    s = _session()
    s.scenario = Scenario(hazards=[Hazard(door_id="D4", kind="fire")])  # run is now stale
    report = rp.build_report(s)
    assert report.verdict == "incomplete" and report.run_id == ""


def test_hand_checks_cover_cannot_measure():
    report = rp.build_report(_session())
    assert len(report.hand_checks) >= 6
    ids = {d.id for d in _office().doors} | {z.id for z in _office().zones}
    for line in report.hand_checks:
        assert "venue" in line or any(re.search(rf"\b{i}\b", line) for i in ids), line
    cm = [r for r in report.rules if r.status == "cannot_measure"]
    assert cm, "fixture should have cannot_measure rules (D4, D6)"
    for r in cm:
        assert any(re.search(rf"\b{r.element_id}\b", line) for line in report.hand_checks)
    assert sum("venue" in line for line in report.hand_checks) >= len(ALWAYS_CANNOT_MEASURE)
    assert len(report.hand_checks) >= len(cm) + len(ALWAYS_CANNOT_MEASURE)


def test_html_has_no_script_or_external():
    s = _session(sfm=False)
    s.alignment = None
    s.alignment_error = "<script>alert(1)</script> & \"x\""  # reaches the alignment_scale row
    report = rp.build_report(s)
    assert "<script>" in _req(report, "alignment_scale").evidence
    page = rp.render_html(report)
    assert CSP in page
    assert "<script" not in page.lower()
    assert "&lt;script&gt;alert(1)&lt;/script&gt; &amp; &quot;x&quot;" in page
    assert "http://" not in page and "https://" not in page
    assert "http" not in page.replace(CSP, "")  # the CSP meta is the only "http" (http-equiv)
    assert not re.search(r"\b(src|href)\s*=", page, re.I)
    assert "verified_within_model" in page


def test_security_note_header_and_timestamp(tmp_path):
    s, approval = _approved(tmp_path)
    note = rp.draft_security_note(s, approval)
    lines = note.splitlines()
    assert lines[0] == "# DRAFT — not sent"
    assert "video t=" in note
    assert re.search(r"(?i)\bto: security\b", note)
    hhmm = datetime.fromisoformat(approval.approved_at).astimezone().strftime("%H:%M")
    # the approved door: D5 evidence starts at 50 s
    assert f"D5 must stay unlocked and clear; checked {hhmm}; video t=00:50" in note
    for exit_id in ("D2", "D4"):  # every exit appears
        assert re.search(rf"^- {exit_id} .*checked {hhmm}; video t=\d\d:\d\d", note, re.M)
    assert "fire at D2" in note
    before = solve(s.accepted_graph, Scenario(hazards=list(s.scenario.hazards)), PARAMS)
    assert f"{before.reached_exit}/{before.total}" in note
    assert f"{s.current_run.reached_exit}/{s.current_run.total}" in note
    assert "int-0" in note and approval.run_id in note
    assert "Limiting doors" in note
    todo = [ln for ln in lines if ln.startswith("- [ ] ")]
    assert len(todo) == len(rp.build_report(s).hand_checks) >= 6
    assert lines[-1].startswith("- [ ] ")


def test_report_security_note_is_latest_approval(tmp_path):
    s, approval = _approved(tmp_path)
    assert rp.build_report(s).security_note is None  # not written yet
    Path(approval.note_path).write_text("# DRAFT — not sent\n\nhello\n", encoding="utf-8")
    assert rp.build_report(s).security_note.startswith("# DRAFT — not sent")
    s.approvals = []
    assert rp.build_report(s).security_note is None


def test_no_banned_words_in_generated_text(tmp_path):
    texts = []
    disagree = _session()
    disagree.alignment = _alignment(eye=2.4)
    for sess in (_session(), _session(sfm=False), _session(run=False), disagree,
                 _with_reason(_session(sfm=False), "sfm failed: no_floor_plane")):
        rep = rp.build_report(sess)
        texts += [json.dumps(to_jsonable(rep)), rp.render_html(rep)]
    g = _office()
    narrow = Measure(low_m=0.5, high_m=0.6, basis="estimated")
    g = g.model_copy(update={"doors": [d.model_copy(update={"clear_width": narrow})
                                       if d.id == "D6" else d for d in g.doors]})
    rep = rp.build_report(_session(g))
    texts += [json.dumps(to_jsonable(rep)), rp.render_html(rep)]
    s, approval = _approved(tmp_path)
    texts.append(rp.draft_security_note(s, approval))
    blob = "\n".join(texts).replace(CSP, "")  # 'unsafe-inline' is CSP syntax, not copy
    for word in BANNED:
        assert not re.search(word, blob, re.I), word


def test_report_json_round_trips():
    rep = rp.build_report(_session())
    data = to_jsonable(rep)
    for key in ("session_id", "graph_revision", "scenario_hash", "run_id", "verdict",
                "requirements", "rules", "hand_checks", "declared_parameters", "provenance",
                "security_note"):
        assert key in data
    assert isinstance(data["graph_revision"], str) and isinstance(data["run_id"], str)
    incomplete = to_jsonable(rp.build_report(_session(run=False)))
    assert isinstance(incomplete["run_id"], str)  # the UI parser expects strings
