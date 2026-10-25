import json

import pytest
from pydantic import ValidationError

from walktwin.contracts import (
    Anchor,
    Door,
    Evidence,
    FlowParams,
    Hazard,
    Keyframe,
    Measure,
    Scenario,
    VenueGraph,
    Zone,
    apply_anchor,
)


def _graph_dict() -> dict:
    return {
        "schema_version": "1",
        "video_sha256": "abc",
        "anchor": None,
        "zones": [
            {"id": "Z1", "name": "A", "rect": [0, 0, 5, 5], "occupants": 3,
             "furniture_seen": False, "evidence": [{"start_s": 0, "end_s": 1, "note": "n"}]},
        ],
        "doors": [
            {"id": "D1", "a": "Z1", "b": "OUTSIDE", "kind": "exit", "state": "open",
             "clear_width": {"low_m": 0.9, "high_m": 1.1, "basis": "estimated"},
             "position": [0, 2], "evidence": []},
            {"id": "D2", "a": "Z1", "b": "OUTSIDE", "kind": "exit", "state": "open",
             "clear_width": {"low_m": 1.8, "high_m": 2.2, "basis": "estimated"},
             "position": [5, 2], "evidence": []},
        ],
        "keyframes": [{"t_s": 1, "zone_id": "Z1", "x": 1, "y": 1, "heading_deg": 90}],
    }


def _reorder(d):
    if isinstance(d, dict):
        return {k: _reorder(d[k]) for k in reversed(list(d))}
    if isinstance(d, list):
        return [_reorder(x) for x in d]
    return d


def test_revision_stable_under_key_order():
    d = _graph_dict()
    g1 = VenueGraph.model_validate(d)
    g2 = VenueGraph.model_validate_json(json.dumps(_reorder(d)))
    assert g1.revision == g2.revision
    assert g1.revision.startswith("g-") and len(g1.revision) == 18


def test_revision_changes_on_width():
    d = _graph_dict()
    g1 = VenueGraph.model_validate(d)
    d["doors"][0]["clear_width"]["low_m"] = 0.91
    g2 = VenueGraph.model_validate(d)
    assert g1.revision != g2.revision


def test_rejects_bad_ids():
    d = _graph_dict()
    d["zones"][0]["id"] = "room1"
    with pytest.raises(ValidationError):
        VenueGraph.model_validate(d)


def test_apply_anchor_scales_and_bands():
    g = VenueGraph.model_validate(_graph_dict())
    out = apply_anchor(g, Anchor(door_id="D1", measured_width_m=0.85))
    d1, d2 = out.doors
    assert d1.clear_width == Measure(low_m=0.85, high_m=0.85, basis="anchor_measured")
    assert d2.clear_width.low_m == pytest.approx(1.36)
    assert d2.clear_width.high_m == pytest.approx(2.04)
    assert d2.clear_width.basis == "estimated"
    f = 0.85 / 1.0
    assert out.zones[0].rect == pytest.approx((0, 0, 5 * f, 5 * f))
    assert out.doors[1].position == pytest.approx((5 * f, 2 * f))
    assert out.anchor == Anchor(door_id="D1", measured_width_m=0.85)
    assert g.anchor is None  # original untouched


def test_assumed_basis_kept_and_models_frozen():
    d = _graph_dict()
    d["doors"][1]["clear_width"]["basis"] = "assumed"
    out = apply_anchor(VenueGraph.model_validate(d), Anchor(door_id="D1", measured_width_m=0.85))
    assert out.doors[1].clear_width.basis == "assumed"
    with pytest.raises(ValidationError):
        out.doors[0].state = "closed"


def test_scenario_hash_and_defaults():
    s = Scenario(hazards=[Hazard(door_id="D1", kind="fire")], interventions=["OPEN:D3"])
    assert s.hash.startswith("s-") and len(s.hash) == 14
    assert s.hash == Scenario(hazards=[Hazard(door_id="D1", kind="fire", from_s=0)],
                              interventions=["OPEN:D3"]).hash
    assert Scenario().hash != s.hash
    p = FlowParams()
    assert (p.dt_s, p.horizon_s, p.specific_flow_p_per_m_s, p.boundary_layer_m, p.walk_speed_m_s) == (2, 120, 1.3, 0.15, 1.2)


def test_bounds():
    with pytest.raises(ValidationError):
        Measure(low_m=1.0, high_m=0.5, basis="estimated")
    with pytest.raises(ValidationError):
        Evidence(start_s=5, end_s=1, note="x")
    with pytest.raises(ValidationError):
        Keyframe(t_s=0, zone_id="Z1", x=0, y=0, heading_deg=360)


def test_office_fixture(office_graph):
    g = office_graph
    assert len(g.zones) == 4 and len(g.doors) == 6 and len(g.keyframes) == 5
    assert sum(1 for d in g.doors if d.kind == "exit") == 3
    zones = {z.id: z for z in g.zones}
    assert sum(z.occupants for z in g.zones) == 130
    for k in g.keyframes:
        x, y, w, h = zones[k.zone_id].rect
        assert x <= k.x <= x + w and y <= k.y <= y + h
    ids = {z.id for z in g.zones} | {"OUTSIDE"}
    assert all(d.a in ids and d.b in ids for d in g.doors)
    assert len(g.zones[0].evidence) == 1


def test_fixture_evidence_within_video(office_graph):
    for item in [*office_graph.zones, *office_graph.doors]:
        assert item.evidence
        assert all(0 <= e.start_s <= e.end_s <= 60 for e in item.evidence)
