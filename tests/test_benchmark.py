from walktwin.benchmark import AnswerKey, BenchmarkScore, KeyDoor, score
from walktwin.contracts import Door, Evidence, Measure


def _door(did, kind, ev, width=(1.0, 1.0)):
    return Door(
        id=did, a="Z1", b="OUTSIDE" if kind == "exit" else "Z2", kind=kind, state="open",
        clear_width=Measure(low_m=width[0], high_m=width[1], basis="estimated"),
        position=(0.0, 0.0),
        evidence=[Evidence(start_s=s, end_s=e, note="x") for s, e in ev],
    )


def _graph(base, doors):
    return base.model_copy(update={"doors": doors})


def _key(doors):
    return AnswerKey(venue="v", video_sha256="0" * 64, source="tape", doors=doors)


def test_perfect_match(office_graph):
    g = _graph(office_graph, [_door("D1", "door", [(9, 11)]), _door("D2", "door", [(19, 21)]),
                              _door("D3", "exit", [(29, 31)])])
    key = _key([KeyDoor(t_s=10, kind="door", measured_width_m=None),
                KeyDoor(t_s=20, kind="door", measured_width_m=None),
                KeyDoor(t_s=30, kind="exit", measured_width_m=None)])
    s = score(g, key)
    assert isinstance(s, BenchmarkScore)
    assert (s.door_precision, s.door_recall, s.door_f1, s.exit_recall) == (1.0, 1.0, 1.0, 1.0)
    assert sorted(s.matched) == [("D1", 0), ("D2", 1), ("D3", 2)]
    assert s.width_mae_m is None


def test_kind_mismatch_not_matched(office_graph):
    g = _graph(office_graph, [_door("D1", "door", [(9, 11)])])
    s = score(g, _key([KeyDoor(t_s=10, kind="exit", measured_width_m=None)]))
    assert s.matched == [] and s.door_f1 == 0.0 and s.exit_recall == 0.0
    # opening is compatible with door
    s2 = score(g, _key([KeyDoor(t_s=10, kind="opening", measured_width_m=None)]))
    assert s2.matched == [("D1", 0)]


def test_tolerance(office_graph):
    g = _graph(office_graph, [_door("D1", "door", [(12.5, 13)])])
    key = _key([KeyDoor(t_s=15, kind="door", measured_width_m=None)])
    assert score(g, key, tolerance_s=2.0).matched == [("D1", 0)]
    assert score(g, key, tolerance_s=1.0).matched == []


def test_width_mae(office_graph):
    g = _graph(office_graph, [_door("D1", "door", [(9, 11)], (0.9, 0.9)),
                              _door("D2", "door", [(19, 21)], (1.0, 1.2))])
    key = _key([KeyDoor(t_s=10, kind="door", measured_width_m=0.85),
                KeyDoor(t_s=20, kind="door", measured_width_m=0.95)])
    assert abs(score(g, key).width_mae_m - 0.10) < 1e-9


def test_empty_never_divides_by_zero(office_graph):
    g = _graph(office_graph, [])
    s = score(g, _key([]))
    assert (s.door_precision, s.door_recall, s.door_f1, s.exit_recall) == (0.0, 0.0, 0.0, 0.0)


def test_greedy_one_to_one_tie_break(office_graph):
    # D1 and D2 both cover key 0 at the same distance; D1 wins by id; D2 stays unmatched.
    g = _graph(office_graph, [_door("D2", "door", [(9, 11)]), _door("D1", "door", [(9, 11)])])
    s = score(g, _key([KeyDoor(t_s=10, kind="door", measured_width_m=None)]))
    assert s.matched == [("D1", 0)]
    assert s.door_precision == 0.5 and s.door_recall == 1.0
