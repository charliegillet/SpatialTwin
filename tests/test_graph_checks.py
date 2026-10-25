from walktwin.contracts import Evidence, Hazard, Scenario, VenueGraph
from walktwin.graph_checks import check_graph, has_errors, reachable_zones


def _codes(findings, code):
    return [f for f in findings if f.code == code]


def _with_door(g: VenueGraph, door_id: str, **update) -> VenueGraph:
    doors = [d.model_copy(update=update) if d.id == door_id else d for d in g.doors]
    return g.model_copy(update={"doors": doors})


def test_fixture_clean(office_graph):
    assert check_graph(office_graph, 90.0) == []


def test_door_off_boundary(office_graph):
    g = _with_door(office_graph, "D1", position=(5.0, 4.0))
    found = _codes(check_graph(g, 90.0), "DOOR_OFF_BOUNDARY")
    assert [f.element_id for f in found] == ["D1"]
    assert len(check_graph(g, 90.0)) == 1


def test_overlap(office_graph):
    z2 = office_graph.zones[1]
    # Z2 [0,0,3,8] widened to w=3.125 overlaps Z1 [3,0,12,8] by 0.125*8 = 1 m2
    zones = list(office_graph.zones)
    zones[1] = z2.model_copy(update={"rect": (0, 0, 3.125, 8)})
    g = office_graph.model_copy(update={"zones": zones})
    found = _codes(check_graph(g, 90.0), "ZONE_OVERLAP")
    assert len(found) == 1
    assert found[0].severity == "error"


def test_no_exit(office_graph):
    doors = [d for d in office_graph.doors if d.b != "OUTSIDE"]
    g = office_graph.model_copy(update={"doors": doors})
    findings = check_graph(g, 90.0)
    assert _codes(findings, "NO_EXIT")
    assert has_errors(findings)


def test_evidence_out_of_range(office_graph):
    zones = list(office_graph.zones)
    zones[0] = zones[0].model_copy(
        update={"evidence": [Evidence(start_s=0, end_s=200, note="late")]}
    )
    g = office_graph.model_copy(update={"zones": zones})
    found = _codes(check_graph(g, 90.0), "EVIDENCE_OUT_OF_RANGE")
    assert found and found[0].element_id == "Z1"


def test_unreachable_zone_warning(office_graph):
    g = _with_door(office_graph, "D6", state="locked")
    findings = check_graph(g, 90.0)
    unreachable = _codes(findings, "UNREACHABLE_ZONE")
    assert [f.element_id for f in unreachable] == ["Z4"]
    assert unreachable[0].severity == "warning"
    assert not has_errors(findings)


def test_duplicate_and_unknown_refs(office_graph):
    doors = list(office_graph.doors)
    doors.append(doors[0].model_copy(update={"b": "Z9"}))
    g = office_graph.model_copy(update={"doors": doors})
    findings = check_graph(g, 90.0)
    assert _codes(findings, "DUPLICATE_ID")
    assert _codes(findings, "UNKNOWN_ZONE_REF")


def test_keyframe_unknown_zone_and_unknown_state(office_graph):
    kfs = list(office_graph.keyframes)
    kfs[0] = kfs[0].model_copy(update={"zone_id": "Z9"})
    g = office_graph.model_copy(update={"keyframes": kfs})
    g = _with_door(g, "D3", state="unknown")
    findings = check_graph(g, 90.0)
    assert _codes(findings, "KEYFRAME_UNKNOWN_ZONE")
    assert [f.element_id for f in _codes(findings, "UNKNOWN_DOOR_STATE")] == ["D3"]


def test_reachable_with_scenario(office_graph):
    assert reachable_zones(office_graph) == {"Z1", "Z2", "Z3", "Z4"}
    # D5 locked; opening it by intervention is fine, a hazard closes it again.
    g = _with_door(office_graph, "D6", state="closed")
    assert "Z4" not in reachable_zones(g)
    assert "Z4" in reachable_zones(g, Scenario(interventions=["OPEN:D6"]))
    sc = Scenario(interventions=["OPEN:D6"], hazards=[Hazard(door_id="D6", kind="fire", from_s=30)])
    assert "Z4" not in reachable_zones(g, sc)
