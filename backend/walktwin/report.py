"""Verification report, self-contained HTML export and the drafted note to security.

The report states a verdict from measured, checker and model-reported rows:

* ``verified_within_model``: an accepted, checked run exists, the checker passed
  and no requirement row failed.
* ``failed``: an accepted, checked run exists and the checker or any row failed.
* ``incomplete``: no checked run for the accepted graph and current scenario.

``cannot_measure`` and ``not_run`` rows never pass or fail the verdict; every
``cannot_measure`` row becomes a hand-check to-do line naming its door, zone or
"venue". Declared parameters are model assumptions, never measurements.

Copy rules: never claim people are out of danger or that a venue meets code.
Say "reach a modeled exit in 120 s", "meets ADA §… within measured range" (a
tape-measured width), "… within the model's estimated range (model-reported)"
(any other width) or "cannot measure".

Loop iterations are read as JSON dicts with ``kind`` ("baseline", "round" or
"accepted"; a missing kind is "round"). Geometry rows score the iteration for
the accepted revision (an "accepted" one first, then a "round") against the
"baseline" scored before the loop under the same alignment.

The note to security is a local markdown draft. Nothing here sends anything.
"""
from __future__ import annotations

import dataclasses
import html
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from .checker import check_run
from .contracts import Door, FlowParams, Scenario, VenueGraph
from .egress_rules import ALWAYS_CANNOT_MEASURE, RuleResult, evaluate_rules
from .flow import solve
from .graph_checks import check_graph
from .sessions import Approval, Session

DRAFT_HEADER = "# DRAFT — not sent"
OUTSIDE = "OUTSIDE"
CSP_META = ("<meta http-equiv=\"Content-Security-Policy\" "
            "content=\"default-src 'none'; style-src 'unsafe-inline'\">")

# Declared, not measured (global constraints).
NON_ANCHOR_UNCERTAINTY = 0.20
EYE_HEIGHT_DECLARED = "1.5±0.1"
ROUTING_DECLARED = ("system-optimal (earliest arrival); "
                    "real crowds tend to use the way they came in")
GEOMETRY_DOOR_TOLERANCE_M = 0.5
GEOMETRY_WALL_BAND_M = 0.15
GEOMETRY_EDGE_PX = 5

Method = Literal["measured", "checker", "model_reported", "outside_model"]
ReqStatus = Literal["pass", "fail", "cannot_measure", "not_run"]
Verdict = Literal["verified_within_model", "failed", "incomplete"]

_ALWAYS_CITATION = {
    "ADA-404.2.5": "2010 ADA Standards §404.2.5",
    "ADA-404.2.7": "2010 ADA Standards §404.2.7",
    "ADA-404.2.9": "2010 ADA Standards §404.2.9",
    "ADA-405.2": "2010 ADA Standards §405.2",
    "ADA-SIGNAGE": "2010 ADA Standards §216, §703",
    "IBC/NFPA-OCCUPANT-LOAD": "IBC §1004, NFPA 101 §7.3; section numbers only",
}
_ALWAYS_TODO = {
    "ADA-404.2.5": "Check threshold height at every door in the venue",
    "ADA-404.2.7": "Check door hardware at every door in the venue",
    "ADA-404.2.9": "Check door opening force at every door in the venue",
    "ADA-405.2": "Check ramp slope on every ramp in the venue",
    "ADA-SIGNAGE": "Check exit and accessibility signage in the venue",
    "IBC/NFPA-OCCUPANT-LOAD": "Check the posted occupant load for the venue",
}


class Requirement(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    statement: str
    method: Method
    status: ReqStatus
    value: str | None
    evidence: str


class Report(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str
    graph_revision: str  # "" without an accepted graph (the UI parser expects a string)
    scenario_hash: str
    run_id: str  # the accepted, checked run's id; "" without one
    verdict: Verdict
    requirements: list[Requirement]
    rules: list[RuleResult]
    hand_checks: list[str]
    declared_parameters: dict
    provenance: list[str]
    security_note: str | None = None  # latest approval's drafted note (Ruling R24)


# --- small helpers -----------------------------------------------------------------


def _g(obj: Any, key: str, default: Any = None) -> Any:
    """Read a field from a JSON dict or an object (iterations, investigations)."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v)


def _mmss(seconds: float) -> str:
    s = max(0, int(seconds))
    return f"{s // 60:02d}:{s % 60:02d}"


def _hhmm(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%H:%M")
    except (TypeError, ValueError):
        return str(iso)


def _door_key(door_id: str) -> tuple[int, str]:
    m = re.search(r"(\d+)$", door_id)
    return (int(m.group(1)) if m else 10**6, door_id)


def _one_line(text: Any, n: int = 200) -> str:
    s = " ".join(str(text).split())
    return s if len(s) <= n else s[: n - 1] + "…"


def _is_exit(d: Door) -> bool:
    return OUTSIDE in (d.a, d.b)


def _first_evidence_t(d: Door) -> str:
    return _mmss(d.evidence[0].start_s) if d.evidence else "none (no video evidence)"


def _params(session: Session) -> FlowParams:
    run = session.current_run
    return run.params if run is not None else FlowParams()


def _accepted_run(session: Session):
    """(graph, run, check) when a checked run matches the accepted graph and scenario."""
    graph, run, check = session.accepted_graph, session.current_run, session.current_check
    if graph is None or run is None or check is None:
        return None
    if run.graph_revision != graph.revision or run.scenario_hash != session.scenario.hash:
        return None
    if check.run_id != run.run_id:
        return None
    return graph, run, check


def _kind(it: Any) -> str:
    """An iteration's kind; old data without one is a critique round."""
    k = _g(it, "kind")
    return k if k in ("baseline", "round", "accepted") else "round"


def _applied_anchor(graph: VenueGraph | None):
    """The graph's anchor only when ``apply_anchor`` ran (the door is tape-measured)."""
    if graph is None or graph.anchor is None:
        return None
    door = next((d for d in graph.doors if d.id == graph.anchor.door_id), None)
    if door is None or door.clear_width.basis != "anchor_measured":
        return None
    return graph.anchor


def _unanchored_alignment(session: Session) -> dict | None:
    """The pre-anchor alignment when the session alignment is the anchored one, else None.

    ``alignment_unanchored`` is added by the session API fix; read it defensively.
    """
    un = getattr(session, "alignment_unanchored", None)
    cur = session.alignment
    if not isinstance(un, dict) or not isinstance(cur, dict):
        return None
    return un if un.get("hash") != cur.get("hash") else None


def _alignment(d: dict | None):
    if not isinstance(d, dict):
        return None
    from . import sfm
    names = {f.name for f in dataclasses.fields(sfm.Alignment)}
    data = {k: v for k, v in d.items() if k in names}
    if "floor_normal" in data:
        data["floor_normal"] = tuple(data["floor_normal"])
    try:
        return sfm.Alignment(**data)
    except TypeError:
        return None


# --- requirement rows ----------------------------------------------------------------


def _req(id: str, statement: str, method: Method, status: ReqStatus,
         value: str | None, evidence: str) -> Requirement:
    return Requirement(id=id, statement=statement, method=method, status=status,
                       value=value, evidence=evidence)


def _population_row(graph: VenueGraph | None, run) -> Requirement:
    stmt = ("Population is conserved: people in zones, in transit and at a modeled exit "
            "add up to the total at every step")
    if graph is None or run is None:
        return _req("population_conserved", stmt, "measured", "not_run", None, "no solver run")
    total = sum(z.occupants for z in graph.zones)
    steps = len(run.zone_occupancy)
    bad = []
    if run.total != total:
        bad.append(f"run total {run.total} != sum of occupants {total}")
    if len(run.transit_by_step) != steps or len(run.reached_by_step) != steps:
        bad.append("step arrays differ in length")
    else:
        for k in range(steps):
            occ = run.zone_occupancy[k]
            s = sum(occ.values()) + run.transit_by_step[k] + run.reached_by_step[k]
            if s != total or any(v < 0 for v in occ.values()):
                bad.append(f"step {k}: zones + transit + reached = {s}, total {total}")
                break
    if bad:
        return _req("population_conserved", stmt, "measured", "fail", None, "; ".join(bad))
    return _req("population_conserved", stmt, "measured", "pass",
                f"{total} people at all {steps} steps",
                f"recomputed from run {run.run_id} arrays")


def _checker_row(run, check) -> Requirement:
    stmt = "Independent checker verifies the solver run (capacity, closures, conservation)"
    if run is None or check is None:
        return _req("checker", stmt, "checker", "not_run", None, "no checked run")
    if check.ok:
        return _req("checker", stmt, "checker", "pass", f"checker verified {run.run_id}",
                    "check_run recomputed capacity, travel and conservation without the solver")
    v = list(check.violations)
    return _req("checker", stmt, "checker", "fail", f"{len(v)} violations",
                "; ".join(_one_line(x, 160) for x in v[:3]))


def _graph_row(session: Session, graph: VenueGraph | None) -> Requirement:
    stmt = "Accepted graph has zero validation errors"
    if graph is None:
        return _req("graph_zero_errors", stmt, "measured", "not_run", None, "no accepted graph")
    findings = check_graph(graph, session.video.duration_s)
    errors = [f for f in findings if f.severity == "error"]
    warnings = len(findings) - len(errors)
    value = f"{len(errors)} errors, {warnings} warnings"
    if errors:
        ev = "; ".join(f"{f.code} {f.element_id or ''}".strip() for f in errors[:5])
        return _req("graph_zero_errors", stmt, "measured", "fail", value, ev)
    return _req("graph_zero_errors", stmt, "measured", "pass", value,
                f"check_graph on {graph.revision}")


def _exit_row(graph: VenueGraph | None) -> Requirement:
    stmt = "Every exit has video evidence"
    if graph is None:
        return _req("exit_video_evidence", stmt, "measured", "not_run", None, "no accepted graph")
    exits = sorted((d for d in graph.doors if _is_exit(d)), key=lambda d: _door_key(d.id))
    if not exits:
        return _req("exit_video_evidence", stmt, "measured", "fail", "0 exits",
                    "no door leads to OUTSIDE")
    missing = [d.id for d in exits if not d.evidence]
    value = ", ".join(f"{d.id} t={_first_evidence_t(d)}" for d in exits if d.evidence) or None
    if missing:
        return _req("exit_video_evidence", stmt, "measured", "fail", value,
                    "no video evidence for " + ", ".join(missing))
    return _req("exit_video_evidence", stmt, "measured", "pass", value,
                f"{len(exits)} exits, each with a video time range")


def _geometry_unavailable(session: Session) -> tuple[str, str] | None:
    """(reason, system to-do) when measured geometry is unavailable (R30/R31), else None.

    A "disagrees" scale badge or ``geometry_unavailable_reason`` on the session makes
    the scale and geometry rows ``cannot_measure``; it never fails the verdict.
    """
    al = _alignment(session.alignment)
    anchor = _applied_anchor(session.accepted_graph) or session.anchor
    if al is not None:
        from .sfm import scale_badge
        if scale_badge(al) == "disagrees":
            reason = (f"scale badge disagrees (residual {al.residual_m:.2f} m, "
                      f"eye height {al.eye_height_m:.2f} m)")
            if anchor is None:
                return reason, ("Tape-measure one door as the anchor and re-capture the "
                                f"venue walkthrough; {reason}")
            return reason, (f"Re-tape the anchor door {anchor.door_id} and re-capture the "
                            f"venue walkthrough; {reason}")
    # Field added by the session API fix (R30); read defensively until it is merged.
    raw = getattr(session, "geometry_unavailable_reason", None)
    if raw:
        reason = _one_line(raw, 300)
        if reason.startswith("sfm failed"):
            return reason, f"Re-run SfM on a new capture of the venue walkthrough; {reason}"
        return reason, (f"Re-run SfM and the alignment fit, then refine the venue twin "
                        f"again; {reason}")
    return None


def _geometry_rows(session: Session, unavailable: tuple[str, str] | None,
                   todos: dict[str, str]) -> list[Requirement]:
    stmts = {
        "geometry_illegal_crossings":
            "Final illegal crossings of the walker's SfM path through modeled walls",
        "geometry_wall_support": "Final wall support of SfM points (no measured regression)",
        "geometry_edge_alignment":
            "Final held-out edge alignment of the twin to video frames (no measured regression)",
    }

    def same(status: ReqStatus, why: str, todo: str | None = None) -> list[Requirement]:
        if todo:
            todos.update(dict.fromkeys(stmts, todo))
        return [_req(rid, s, "measured", status, None, why) for rid, s in stmts.items()]

    graph = session.accepted_graph
    if graph is None:
        return same("not_run", "no accepted graph")
    if unavailable is not None:
        return same("cannot_measure", f"geometry unavailable: {unavailable[0]}", unavailable[1])
    its = list(session.iterations)
    scored = [i for i, it in enumerate(its) if isinstance(_g(it, "geometry"), dict)]
    matches = [i for i in scored if _g(its[i], "graph_revision") == graph.revision]
    final_i = next((i for kind in ("accepted", "round", "baseline")
                    for i in reversed(matches) if _kind(its[i]) == kind), None)
    if final_i is None:
        return same("not_run", "no geometry score for the accepted graph")
    final = _g(its[final_i], "geometry")
    ahash = final.get("alignment_hash")
    al = _alignment(session.alignment)
    if al is not None and ahash != al.hash:
        return same("not_run", f"geometry was scored under alignment {ahash}; "
                               f"the current alignment is {al.hash}")
    final_kind = _kind(its[final_i])
    if final_kind == "accepted":
        where = f"accepted graph {graph.revision} rescored at accept, alignment {ahash}"
    elif final_kind == "baseline":
        where = f"baseline before the loop, graph {graph.revision}, alignment {ahash}"
    else:
        where = (f"loop round {_g(its[final_i], 'index', final_i)}, graph {graph.revision}, "
                 f"alignment {ahash}")
    # Baseline: the "baseline" iteration recorded before the loop that led to the final
    # score. Old data without kinds: the first round scored under the same alignment.
    base: dict = {}
    no_base = "single measured round; no baseline to compare"
    baselines = [i for i in range(final_i + 1) if _kind(its[i]) == "baseline"]
    if baselines:
        base_i, base_label = baselines[-1], "baseline before the loop"
        bgeom = _g(its[base_i], "geometry")
        if base_i == final_i:
            pass
        elif not isinstance(bgeom, dict):
            no_base = "the baseline before the loop has no measured geometry; not compared"
        elif bgeom.get("alignment_hash") != ahash:
            no_base = (f"the baseline before the loop was scored under alignment "
                       f"{bgeom.get('alignment_hash')}; not compared")
        else:
            base = bgeom
    else:
        base_i = next((i for i in scored if _kind(its[i]) == "round"
                       and _g(its[i], "geometry").get("alignment_hash") == ahash), final_i)
        base_label = f"baseline loop round {_g(its[base_i], 'index', base_i)} (same alignment)"
        if base_i != final_i:
            base = _g(its[base_i], "geometry")
    single = not base
    rows = []

    crossings = final.get("illegal_crossings")
    if isinstance(crossings, list):
        n = len(crossings)
        times = ", ".join(f"t={_mmss(_num(_g(c, 't_s')) or 0)} {_g(c, 'edge', '')}".strip()
                          for c in crossings[:3])
        ev = (f"{where}; path segments crossing a wall more than {GEOMETRY_DOOR_TOLERANCE_M} m "
              f"(declared) from any door" + (f"; {times}" if times else ""))
        rows.append(_req("geometry_illegal_crossings", stmts["geometry_illegal_crossings"],
                         "measured", "pass" if n == 0 else "fail", str(n), ev))
    else:
        rows.append(_req("geometry_illegal_crossings", stmts["geometry_illegal_crossings"],
                         "measured", "not_run", None, f"{where}; no crossings recorded"))

    ws, ws0 = _num(final.get("wall_support")), _num(base.get("wall_support"))
    if ws is None:
        rows.append(_req("geometry_wall_support", stmts["geometry_wall_support"], "measured",
                         "not_run", None, f"{where}; no wall support recorded"))
    else:
        ev = (f"{where}; share of SfM points 0.5-2.0 m above the floor within "
              f"{GEOMETRY_WALL_BAND_M} m (declared) of a modeled wall")
        status: ReqStatus = "pass"
        if single or ws0 is None:
            ev += f"; {no_base}"
        else:
            from .geometry_score import REGRESSION_WALL_SUPPORT
            ev += f"; {base_label} {ws0:.2f}"
            if ws < ws0 - REGRESSION_WALL_SUPPORT:
                status = "fail"
                ev += f"; dropped more than {REGRESSION_WALL_SUPPORT}"
        rows.append(_req("geometry_wall_support", stmts["geometry_wall_support"], "measured",
                         status, f"{ws:.2f}", ev))

    e, e0 = _num(final.get("edge_within_5px")), _num(base.get("edge_within_5px"))
    if e is None:
        rows.append(_req("geometry_edge_alignment", stmts["geometry_edge_alignment"],
                         "measured", "not_run", None, f"{where}; no held-out frames were scored"))
    else:
        px = _num(final.get("edge_chamfer_px"))
        value = f"{e:.0%} within {GEOMETRY_EDGE_PX} px" + (
            f"; mean distance {px:.1f} px" if px is not None else "")
        ev = (f"{where}; projected floor-wall lines and jambs against Canny edges on "
              "held-out frames")
        status = "pass"
        if single or e0 is None:
            ev += f"; {no_base}"
        else:
            from .geometry_score import REGRESSION_EDGE_WITHIN
            ev += f"; {base_label} {e0:.0%}"
            if e < e0 - REGRESSION_EDGE_WITHIN:
                status = "fail"
                ev += f"; dropped more than {REGRESSION_EDGE_WITHIN:.0%}"
        rows.append(_req("geometry_edge_alignment", stmts["geometry_edge_alignment"],
                         "measured", status, value, ev))
    return rows


def _scale_row(session: Session, unavailable: tuple[str, str] | None,
               todos: dict[str, str]) -> Requirement:
    stmt = ("SfM alignment scale is consistent with the declared 1.5 ± 0.1 m eye height "
            "(scale badge)")
    al = _alignment(session.alignment)
    if unavailable is not None:
        todos["alignment_scale"] = unavailable[1]
    if al is None:
        if unavailable is not None:
            return _req("alignment_scale", stmt, "measured", "cannot_measure", None,
                        unavailable[0])
        why = session.alignment_error or "no SfM alignment"
        return _req("alignment_scale", stmt, "measured", "not_run", None, _one_line(why))
    from .sfm import scale_badge
    badge = scale_badge(al)
    value = (f"residual {al.residual_m:.2f} m; eye height {al.eye_height_m:.2f} m; "
             f"scale badge {badge}")
    ev = (f"alignment {al.hash}; the badge agrees when eye height is within "
          f"{EYE_HEIGHT_DECLARED} m (declared) and the residual is at most 0.5 m")
    unanchored = _unanchored_alignment(session)
    if unanchored is not None:  # the anchor is mentioned only for the anchored alignment
        anchor = _applied_anchor(session.accepted_graph)
        door = (f" {anchor.door_id} ({anchor.measured_width_m:.3f} m)"
                if anchor is not None else "")
        ev += (f"; rescaled at accept to the tape-measured anchor{door} from the "
               f"pre-anchor alignment {unanchored.get('hash')}")
    if unavailable is not None:
        return _req("alignment_scale", stmt, "measured", "cannot_measure", value,
                    f"{unavailable[0]}; {ev}")
    return _req("alignment_scale", stmt, "measured", "pass", value, ev)


def _described_revision(its: list, i: int) -> str | None:
    """Graph revision that round ``i``'s critique looked at.

    A round's ``graph_revision`` is the graph after the round. When nothing was
    kept that is also the graph it critiqued; when a patch was kept, the critiqued
    graph is the previous round's ``graph_revision``.
    """
    it = its[i]
    if not (_g(it, "applied") or []):
        return _g(it, "graph_revision")
    if i > 0:
        idx, prev_idx = _g(it, "index"), _g(its[i - 1], "index")
        if isinstance(idx, int) and isinstance(prev_idx, int) and idx == prev_idx + 1:
            return _g(its[i - 1], "graph_revision")
    return None


def _discrepancy_row(session: Session, todos: dict[str, str]) -> Requirement:
    stmt = "Final loop discrepancy count (Argon's critique of renders against video)"
    graph = session.accepted_graph
    if graph is None:
        return _req("loop_discrepancies", stmt, "model_reported", "not_run", None,
                    "no accepted graph")
    its = list(session.iterations)
    match = None
    for i, it in enumerate(its):
        if _kind(it) != "round":  # the baseline and the accepted rescore carry no critique
            continue
        if _g(it, "stop_reason") == "provider_failed":  # its count of 0 is not a critique
            continue
        if _described_revision(its, i) == graph.revision:
            match = it
    if match is None:
        return _req("loop_discrepancies", stmt, "model_reported", "not_run", None,
                    "no critique round for the accepted graph")
    n = _g(match, "discrepancy_count")
    idx = _g(match, "index", "?")
    if not isinstance(n, int) or isinstance(n, bool):
        return _req("loop_discrepancies", stmt, "model_reported", "not_run", None,
                    f"loop round {idx} has no count")
    ev = f"loop round {idx} on graph {graph.revision}; model-reported, not a measurement"
    if n == 0:
        return _req("loop_discrepancies", stmt, "model_reported", "pass", "0", ev)
    todos["loop_discrepancies"] = (f"Review the {n} model-reported discrepancies from loop "
                                   f"round {idx} against the video and correct the venue twin")
    return _req("loop_discrepancies", stmt, "model_reported", "cannot_measure", str(n), ev)


def _rule_row(r: RuleResult) -> Requirement:
    m = r.measured
    method: Method = "measured" if m is not None and m.basis == "anchor_measured" else "model_reported"
    value = f"{m.low_m:.2f}-{m.high_m:.2f} m ({m.basis})" if m is not None else None
    ev = f"{r.citation}; threshold {r.threshold_m:.3f} m" + (f"; {r.reason}" if r.reason else "")
    return _req(f"{r.rule_id}:{r.element_id}", r.statement, method, r.status, value, ev)


def _always_rows() -> list[Requirement]:
    return [_req(rid, text, "outside_model", "cannot_measure", None,
                 _ALWAYS_CITATION.get(rid, rid)) for rid, text in ALWAYS_CANNOT_MEASURE]


# --- hand checks -----------------------------------------------------------------------


def _rule_todo(r: RuleResult) -> str:
    el, cite = r.element_id, r.citation
    if r.rule_id == "ADA-404.2.3":
        if r.reason == "basis assumed":
            return f"Tape-measure the clear width at {el}; the model width is assumed ({cite})"
        return f"Measure the clear width and doorway depth at {el} ({cite})"
    if r.rule_id == "ADA-403.5.1":
        return f"Measure the route width at {el} ({cite})"
    if r.rule_id == "ADA-304.3.1":
        if r.reason == "furniture seen":
            return f"Check the 1.524 m turning circle in {el} around the furniture ({cite})"
        return f"Measure the turning space in {el} ({cite})"
    return f"Check {r.rule_id} at {el} ({cite})"


def _hand_checks(rules: list[RuleResult], rows: list[Requirement],
                 todos: dict[str, str]) -> list[str]:
    out = [_rule_todo(r) for r in rules if r.status == "cannot_measure"]
    rule_ids = {f"{r.rule_id}:{r.element_id}" for r in rules}
    always = {rid for rid, _ in ALWAYS_CANNOT_MEASURE}
    groups: dict[str, list[str]] = {}  # system to-do -> the rows it resolves
    for row in rows:
        if row.status != "cannot_measure" or row.id in rule_ids or row.id in always:
            continue
        todo = todos.get(row.id) or f"Resolve {row.id}: {row.statement}"
        groups.setdefault(todo, []).append(row.id)
    out += [f"{todo} ({', '.join(ids)})" for todo, ids in groups.items()]
    for rid, text in ALWAYS_CANNOT_MEASURE:
        todo = _ALWAYS_TODO.get(rid, f"Check in the venue: {text}")
        out.append(f"{todo} ({_ALWAYS_CITATION.get(rid, rid)})")
    return out


# --- report ------------------------------------------------------------------------------


def _declared(session: Session) -> dict:
    return {**_params(session).model_dump(mode="json"),
            "non_anchor_uncertainty": NON_ANCHOR_UNCERTAINTY,
            "eye_height_m": EYE_HEIGHT_DECLARED,
            "geometry_door_tolerance_m": GEOMETRY_DOOR_TOLERANCE_M,
            "geometry_wall_band_m": GEOMETRY_WALL_BAND_M,
            "geometry_edge_px": GEOMETRY_EDGE_PX,
            "routing": ROUTING_DECLARED}


def _receipt_text(rec: Any) -> str | None:
    iid = _g(rec, "interaction_id")
    if not iid:
        return None
    model, status = _g(rec, "provider_model"), _g(rec, "status")
    extra = ", ".join(str(x) for x in (model, status) if x)
    return f"interaction {iid}" + (f" ({extra})" if extra else "")


def _provenance(session: Session, accepted) -> list[str]:
    out = [f"video sha256 {session.video.sha256}"]
    graph = session.accepted_graph
    if graph is not None:
        out.append(f"graph {graph.revision} (you accepted)")
        anchor = _applied_anchor(graph)  # "tape-measured" only when apply_anchor ran
        if anchor is not None:
            out.append(f"anchor {anchor.door_id} tape-measured at "
                       f"{anchor.measured_width_m:.3f} m (applied at accept)")
    out.append(f"scenario {session.scenario.hash}")
    if session.current_run is not None:
        verified = accepted is not None and accepted[2].ok
        out.append(f"run {session.current_run.run_id} "
                   f"({'checker verified' if verified else 'not checker verified'})")
    al = _alignment(session.alignment)
    if al is not None:
        out.append(f"alignment {al.hash} (geometry measured)")
    ex = session.extraction
    if ex is not None:
        rec = _receipt_text(ex.receipt) or (f"interaction {ex.interaction_id}"
                                            if ex.interaction_id else None)
        out.append(f"extraction: Argon proposed the draft graph ({ex.status}, mode {ex.mode})"
                   + (f"; {rec}" if rec else ""))
    for n, it in enumerate(session.iterations):
        rev, kind = _g(it, "graph_revision", "?"), _kind(it)
        geom = _g(it, "geometry")
        scored = (f"geometry measured, alignment {geom.get('alignment_hash')}"
                  if isinstance(geom, dict) else "geometry unavailable")
        if kind == "baseline":
            out.append(f"loop baseline (before round 1): graph {rev}; {scored}")
            continue
        if kind == "accepted":
            out.append(f"accepted graph rescored at accept: graph {rev}; {scored}")
            continue
        rec = _receipt_text(_g(it, "receipt"))
        out.append(f"loop round {_g(it, 'index', n)}: graph {rev}"
                   + (f"; {rec}" if rec else ""))
    for inv in session.investigations:
        rec = _receipt_text(_g(inv, "receipt")) or (
            f"interaction {_g(inv, 'interaction_id')}" if _g(inv, "interaction_id") else None)
        out.append(f"investigation {_g(inv, 'investigation_id', '?')} "
                   f"({_g(inv, 'status', '?')})" + (f"; {rec}" if rec else ""))
    for a in session.approvals:
        out.append(f"you approved {a.intervention_id} at {a.approved_at} (run {a.run_id})")
    return out


def _latest_note(session: Session) -> str | None:
    if not session.approvals:
        return None
    try:
        return Path(session.approvals[-1].note_path).read_text(encoding="utf-8")
    except OSError:
        return None


def build_report(session: Session) -> Report:
    accepted = _accepted_run(session)
    graph = session.accepted_graph
    run = accepted[1] if accepted else None
    check = accepted[2] if accepted else None
    rules = evaluate_rules(graph) if graph is not None else []
    unavailable = _geometry_unavailable(session)
    todos: dict[str, str] = {}

    rows: list[Requirement] = [
        _population_row(graph, run),
        _checker_row(run, check),
        _graph_row(session, graph),
        _exit_row(graph),
        *_geometry_rows(session, unavailable, todos),
        _scale_row(session, unavailable, todos),
        _discrepancy_row(session, todos),
        *(_rule_row(r) for r in rules),
        *_always_rows(),
    ]

    if accepted is None:
        verdict: Verdict = "incomplete"
    elif check.ok and not any(r.status == "fail" for r in rows):
        verdict = "verified_within_model"
    else:
        verdict = "failed"

    return Report(
        session_id=session.id,
        graph_revision=graph.revision if graph is not None else "",
        scenario_hash=session.scenario.hash,
        run_id=run.run_id if run is not None else "",  # the accepted run only
        verdict=verdict,
        requirements=rows,
        rules=rules,
        hand_checks=_hand_checks(rules, rows, todos),
        declared_parameters=_declared(session),
        provenance=_provenance(session, accepted),
        security_note=_latest_note(session),
    )


# --- HTML ------------------------------------------------------------------------------------

_VERDICT_TEXT = {
    "verified_within_model": "Verified within the model: checker verified, no requirement failed",
    "failed": "Failed: the checker or at least one requirement failed",
    "incomplete": "Incomplete: no checked run for the accepted graph and scenario",
}

_STYLE = """
:root{color-scheme:light dark;--fg:#1d1d1f;--bg:#fff;--mut:#666;--line:#ddd;
--pass:#1a7f37;--fail:#c62828;--cm:#9a6700;--nr:#666}
@media (prefers-color-scheme:dark){:root{--fg:#eee;--bg:#161618;--mut:#aaa;--line:#333;
--pass:#56d364;--fail:#ff7b72;--cm:#e3b341;--nr:#999}}
body{font:14px/1.45 system-ui,sans-serif;color:var(--fg);background:var(--bg);
margin:0 auto;max-width:1100px;padding:16px}
h1{font-size:22px}h2{font-size:17px;margin-top:28px}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{border-bottom:1px solid var(--line);padding:4px 6px;text-align:left;vertical-align:top}
.mut{color:var(--mut)}.pass{color:var(--pass)}.fail{color:var(--fail)}
.cannot_measure{color:var(--cm)}.not_run{color:var(--nr)}
.verdict{font-size:16px;font-weight:600;padding:8px 10px;border:1px solid var(--line)}
.wrap{overflow-x:auto}pre{white-space:pre-wrap;border:1px solid var(--line);padding:8px}
"""


def _e(v: Any) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def render_html(report: Report) -> str:
    """Self-contained page: no scripts, no external URLs, all text escaped."""
    r = report
    status_cls = {"verified_within_model": "pass", "failed": "fail", "incomplete": "not_run"}
    parts = [
        "<!doctype html>", '<html lang="en"><head>', '<meta charset="utf-8">', CSP_META,
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>WalkTwin verification report</title>", f"<style>{_STYLE}</style>",
        "</head><body>", "<h1>WalkTwin verification report</h1>",
        f'<p class="verdict {status_cls[r.verdict]}">{_e(_VERDICT_TEXT[r.verdict])} '
        f'<span class="mut">({_e(r.verdict)})</span></p>',
        '<table><tbody>',
        f"<tr><th>Session</th><td>{_e(r.session_id)}</td></tr>",
        f"<tr><th>Graph revision</th><td>{_e(r.graph_revision or 'none')}</td></tr>",
        f"<tr><th>Scenario</th><td>{_e(r.scenario_hash)}</td></tr>",
        f"<tr><th>Run</th><td>{_e(r.run_id or 'none')}</td></tr>",
        "</tbody></table>",
        "<h2>Requirements</h2>", '<div class="wrap"><table><thead><tr><th>Id</th>'
        "<th>Statement</th><th>Method</th><th>Status</th><th>Value</th><th>Evidence</th>"
        "</tr></thead><tbody>",
    ]
    for q in r.requirements:
        parts.append(
            f"<tr><td>{_e(q.id)}</td><td>{_e(q.statement)}</td>"
            f"<td>{_e(q.method.replace('_', '-'))}</td>"
            f'<td class="{_e(q.status)}">{_e(q.status)}</td>'
            f"<td>{_e(q.value or '')}</td><td>{_e(q.evidence)}</td></tr>")
    parts += ["</tbody></table></div>", "<h2>ADA rules</h2>",
              '<div class="wrap"><table><thead><tr><th>Rule</th><th>Element</th>'
              "<th>Statement</th><th>Status</th><th>Citation</th></tr></thead><tbody>"]
    for rule in r.rules:
        parts.append(
            f"<tr><td>{_e(rule.rule_id)}</td><td>{_e(rule.element_id)}</td>"
            f"<td>{_e(rule.statement)}</td>"
            f'<td class="{_e(rule.status)}">{_e(rule.status)}</td>'
            f"<td>{_e(rule.citation)}</td></tr>")
    if not r.rules:
        parts.append('<tr><td colspan="5" class="mut">no accepted graph</td></tr>')
    parts += ["</tbody></table></div>", "<h2>Hand checks (cannot measure from video)</h2>",
              "<ul>", *(f"<li>[ ] {_e(h)}</li>" for h in r.hand_checks), "</ul>",
              "<h2>Declared parameters</h2>",
              '<p class="mut">Model assumptions, not measurements.</p>',
              "<table><tbody>",
              *(f"<tr><th>{_e(k)}</th><td>{_e(v)} <span class=\"mut\">declared</span></td></tr>"
                for k, v in r.declared_parameters.items()),
              "</tbody></table>", "<h2>Provenance</h2>", "<ul>",
              *(f"<li>{_e(p)}</li>" for p in r.provenance), "</ul>"]
    if r.security_note:
        parts += ["<h2>Note to security (draft, not sent)</h2>", f"<pre>{_e(r.security_note)}</pre>"]
    parts += ["</body></html>", ""]
    return "\n".join(parts)


# --- note to security --------------------------------------------------------------------------


def _approval_scenarios(session: Session, approval: Approval) -> tuple[Scenario, Scenario] | None:
    """(before, after) scenarios for the approval, or None if the scenario has moved on."""
    after = session.scenario
    if after.hash != approval.scenario_hash:
        return None
    ivs = list(after.interventions)
    if approval.intervention_id in ivs:
        i = len(ivs) - 1 - ivs[::-1].index(approval.intervention_id)
        ivs.pop(i)
    return Scenario(hazards=list(after.hazards), interventions=ivs), after


def _checked(graph: VenueGraph, scenario: Scenario, params: FlowParams, session: Session):
    """A checker-verified run for ``scenario``, or None."""
    run, check = session.current_run, session.current_check
    if (run is None or check is None or run.scenario_hash != scenario.hash
            or run.graph_revision != graph.revision or check.run_id != run.run_id):
        run = solve(graph, scenario, params)
        check = check_run(graph, scenario, params, run)
    return run if check.ok else None


def _limiting(session: Session, approval: Approval, graph: VenueGraph, run,
              params: FlowParams) -> list[str] | None:
    inv = next((i for i in session.investigations
                if _g(i, "investigation_id") == approval.investigation_id), None)
    res = next((x for x in (_g(inv, "results") or [])
                if _g(x, "intervention_id") == approval.intervention_id), None)
    lim = _g(res, "limiting_doors")
    if isinstance(lim, list) and _g(res, "check_ok") is True:
        return [str(x) for x in lim]
    if run is None:
        return None
    try:
        from .agent import limiting_doors
    except ImportError:
        return None
    return limiting_doors(graph, run, params)


def _door_line(d: Door, opened: set[str], hazards: set[str], hhmm: str) -> str:
    if d.id in hazards:
        text = f"{d.id} is blocked by the modeled fire; direct people to the other exits"
    elif d.state == "open" or d.id in opened:
        text = f"{d.id} must stay unlocked and clear"
    else:
        text = f"{d.id} is {d.state} in the model and is not counted as an exit route"
    return f"- {text}; checked {hhmm}; video t={_first_evidence_t(d)}"


def draft_security_note(session: Session, approval: Approval) -> str:
    """Local markdown draft for the venue's security team. Nothing is sent."""
    graph = session.accepted_graph
    params = _params(session)
    hhmm = _hhmm(approval.approved_at)
    lines = [DRAFT_HEADER, "",
             "To: Security",
             "From: venue operations (drafted by WalkTwin from a change you approved)",
             f"Re: {approval.intervention_id}, approved at {hhmm}", "",
             "This draft has not been sent. Review it, then send it yourself.", ""]

    lines.append("## Doors")
    if graph is None:
        lines.append("- no accepted graph; video t=none")
    else:
        if graph.revision != approval.graph_revision:
            lines.append(f"- note: the accepted graph is now {graph.revision}, "
                         f"not {approval.graph_revision} from the approval")
        doors = {d.id: d for d in graph.doors}
        approved = approval.intervention_id.partition(":")[2]
        opened = {i.split(":", 1)[1] for i in session.scenario.interventions
                  if i.startswith("OPEN:")}
        hazards = {h.door_id for h in session.scenario.hazards}
        order = [approved] if approved in doors else []
        order += [d.id for d in sorted(graph.doors, key=lambda d: _door_key(d.id))
                  if _is_exit(d) and d.id not in order]
        lines += [_door_line(doors[i], opened, hazards, hhmm) for i in order]
    lines.append("")

    lines.append("## Hazard")
    hz = [f"- {h.kind} at {h.door_id} from {h.from_s:g} s" for h in session.scenario.hazards]
    lines += hz or ["- none modeled"]
    lines.append("")

    lines.append("## Modeled outcome (checker-verified runs only)")
    scen = _approval_scenarios(session, approval) if graph is not None else None
    after_run = None
    if scen is None:
        lines.append("- not available: the scenario has changed since this approval")
    else:
        before_s, after_s = scen
        before_run = _checked(graph, before_s, params, session)
        after_run = _checked(graph, after_s, params, session)
        for label, run in ((f"Before {approval.intervention_id}", before_run),
                           (f"After {approval.intervention_id}", after_run)):
            if run is None:
                lines.append(f"- {label}: the checker did not verify this run; not reported")
            else:
                lines.append(f"- {label}: {run.reached_exit}/{run.total} reach a modeled exit "
                             f"in {params.horizon_s} s (run {run.run_id})")
    lim = _limiting(session, approval, graph, after_run, params) if graph is not None else None
    lines.append("- Limiting doors: " + (", ".join(lim) if lim else
                                          "none" if lim is not None else "not available"))
    lines.append("")

    lines.append("## Receipts")
    lines.append(f"- Approval: {approval.intervention_id} at {approval.approved_at}; graph "
                 f"{approval.graph_revision}; scenario {approval.scenario_hash}; "
                 f"run {approval.run_id}")
    inv = next((i for i in session.investigations
                if _g(i, "investigation_id") == approval.investigation_id), None)
    if inv is not None:
        rec = _receipt_text(_g(inv, "receipt")) or (
            f"interaction {_g(inv, 'interaction_id')}" if _g(inv, "interaction_id") else
            "no receipt")
        lines.append(f"- Investigation {approval.investigation_id}: {rec}")
    if session.extraction is not None:
        rec = _receipt_text(session.extraction.receipt)
        if rec:
            lines.append(f"- Extraction: {rec}")
    lines.append("")

    lines.append("## Hand checks (cannot measure from video)")
    lines += [f"- [ ] {h}" for h in build_report(session).hand_checks]
    return "\n".join(lines)
