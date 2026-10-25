from walktwin.contracts import Door, Measure, VenueGraph, Zone
from walktwin.egress_rules import ALWAYS_CANNOT_MEASURE, evaluate_rules

BANNED = ("compliant", "safe", "survive")


def _door(lo, hi, basis="estimated", kind="door", did="D1"):
    return Door(id=did, a="Z1", b="OUTSIDE", kind=kind, state="open",
                clear_width=Measure(low_m=lo, high_m=hi, basis=basis),
                position=(0.0, 0.0), evidence=[])


def _zone(w, h, furniture=False):
    return Zone(id="Z1", name="r", rect=(0, 0, w, h), occupants=0,
                furniture_seen=furniture, evidence=[])


def _graph(doors=(), zones=()):
    return VenueGraph(schema_version="1", video_sha256="x", anchor=None,
                      zones=list(zones), doors=list(doors), keyframes=[])


def _one(g):
    r = evaluate_rules(g)
    assert len(r) == 1
    return r[0]


def test_door_pass():
    assert _one(_graph([_door(0.95, 0.95, "anchor_measured")])).status == "pass"


def test_door_32_to_36_cannot_measure():
    r = _one(_graph([_door(0.85, 0.85, "anchor_measured")]))
    assert r.status == "cannot_measure" and r.reason == "doorway depth unknown"


def test_door_fail():
    assert _one(_graph([_door(0.70, 0.78)])).status == "fail"


def test_door_band_straddles():
    assert _one(_graph([_door(0.75, 0.90)])).status == "cannot_measure"


def test_opening_route():
    assert _one(_graph([_door(0.95, 1.0, kind="opening")])).rule_id == "ADA-403.5.1"
    assert _one(_graph([_door(0.7, 0.8, kind="opening")])).status == "fail"
    assert _one(_graph([_door(0.8, 1.0, kind="opening")])).status == "cannot_measure"


def test_stair_skipped():
    assert evaluate_rules(_graph([_door(0.9, 1.0, kind="stair")])) == []


def test_turning_furniture_cannot_measure():
    r = _one(_graph(zones=[_zone(5, 5, furniture=True)]))
    assert r.status == "cannot_measure" and r.reason == "furniture seen"
    assert "room footprint only" in r.statement


def test_turning_pass_fail():
    assert _one(_graph(zones=[_zone(5, 6)])).status == "pass"
    assert _one(_graph(zones=[_zone(1.0, 6)])).status == "fail"


def test_assumed_is_cannot_measure():
    r = _one(_graph([_door(1.0, 1.0, "assumed")]))
    assert r.status == "cannot_measure" and r.reason == "basis assumed"
    r = _one(_graph([_door(1.0, 1.0, "assumed", kind="opening")]))
    assert r.status == "cannot_measure"


def test_citations_present():
    g = _graph([_door(0.95, 0.95), _door(0.9, 1.0, kind="opening", did="D2")],
               [_zone(5, 5)])
    rs = evaluate_rules(g)
    assert len(rs) == 3
    for r in rs:
        assert r.citation.startswith("2010 ADA Standards §")
        assert not any(b in r.statement.lower() for b in BANNED)


def test_always_cannot_measure():
    ids = [i for i, _ in ALWAYS_CANNOT_MEASURE]
    assert "ADA-404.2.5" in ids and "ADA-405.2" in ids
    assert any(s.startswith("IBC/NFPA occupant load: copyrighted model code") for _, s in ALWAYS_CANNOT_MEASURE)


def test_office_graph_smoke(office_graph):
    rs = evaluate_rules(office_graph)
    doors = [d for d in office_graph.doors if d.kind in ("door", "exit")]
    assert len([r for r in rs if r.rule_id == "ADA-404.2.3"]) == len(doors)
    assert len([r for r in rs if r.rule_id == "ADA-304.3.1"]) == len(office_graph.zones)


# --- I7: model-reported wording unless the width is tape-measured ------------------

MODEL = "within the model's estimated range (model-reported)"


def test_estimated_pass_and_fail_say_model_reported():
    for kind, lo, hi in (("door", 0.95, 1.0), ("opening", 0.95, 1.0)):
        r = _one(_graph([_door(lo, hi, kind=kind)]))
        assert r.status == "pass" and MODEL in r.statement, r.statement
        assert "within measured range" not in r.statement
    for kind in ("door", "opening"):
        r = _one(_graph([_door(0.6, 0.7, kind=kind)]))
        assert r.status == "fail" and MODEL in r.statement, r.statement
    assert "§404.2.3" in _one(_graph([_door(0.95, 1.0)])).statement
    assert "§403.5.1" in _one(_graph([_door(0.6, 0.7, kind="opening")])).statement


def test_anchor_measured_pass_and_fail_say_measured():
    r = _one(_graph([_door(0.95, 0.95, "anchor_measured")]))
    assert r.status == "pass" and "within measured range" in r.statement
    assert "model-reported" not in r.statement
    r = _one(_graph([_door(0.70, 0.70, "anchor_measured")]))
    assert r.status == "fail" and "tape-measured" in r.statement
    assert "model-reported" not in r.statement and "§404.2.3" in r.statement


def test_turning_circle_is_always_model_reported():
    r = _one(_graph(zones=[_zone(5, 6)]))
    assert r.status == "pass" and MODEL in r.statement and "§304.3.1" in r.statement
    r = _one(_graph(zones=[_zone(1.0, 6)]))
    assert r.status == "fail" and MODEL in r.statement
    assert r.citation == "2010 ADA Standards §304.3.1"
