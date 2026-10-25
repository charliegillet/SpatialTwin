import pytest
from pydantic import TypeAdapter, ValidationError

from walktwin.contracts import Door, Evidence, Measure, VenueGraph
from walktwin.graph_checks import check_graph, has_errors
from walktwin.patch import (AddDoor, PatchOp, PatchOutcome, RemoveDoor, RemoveZone,
                            UpdateDoor, UpdateZone, apply_patch)

DUR = 60.0
OPS = TypeAdapter(list[PatchOp])


def _door(graph: VenueGraph, ident: str) -> Door:
    return next(d for d in graph.doors if d.id == ident)


def _d7() -> Door:
    return Door(id="D7", a="Z4", b="OUTSIDE", kind="exit", state="open",
                clear_width=Measure(low_m=0.9, high_m=1.0, basis="estimated"),
                position=(3.0, 9.5),
                evidence=[Evidence(start_s=20, end_s=22, note="fire exit at back of green room")])


# --- brief tests ----------------------------------------------------------------


def test_patch_rejects_unknown_and_breaking_ops(office_graph):
    d1 = _door(office_graph, "D1")
    assert _door(office_graph, "D2").state == "open"
    office = office_graph.model_copy(update={"doors": [
        d.model_copy(update={"state": "closed"}) if d.id == "D2" else d
        for d in office_graph.doors]})
    ops = OPS.validate_python([
        {"op": "update_door", "id": "D9", "state": "open", "cite_t_s": 10, "reason": "x"},
        {"op": "update_door", "id": "D1", "position": [d1.position[0] + 3, d1.position[1]],
         "cite_t_s": 31, "reason": "door looks further east"},
        {"op": "update_door", "id": "D2", "state": "open", "cite_t_s": 36,
         "reason": "exit propped open at 0:36"},
    ])
    out = apply_patch(office, ops, DUR)
    assert isinstance(out, PatchOutcome)
    assert out.applied == [2]
    reasons = dict(out.rejected)
    assert sorted(reasons) == [0, 1]
    assert "unknown id" in reasons[0]
    assert "DOOR_OFF_BOUNDARY" in reasons[1]
    assert _door(out.graph, "D2").state == "open"
    assert _door(out.graph, "D1").position == d1.position  # reverted
    assert _door(office, "D2").state == "closed"  # input untouched


def test_patch_add_door_then_check(office_graph):
    op = AddDoor(op="add_door", door=_d7(), cite_t_s=21, reason="exit sign over door")
    out = apply_patch(office_graph, [op], DUR)
    assert out.applied == [0] and out.rejected == []
    assert _door(out.graph, "D7").b == "OUTSIDE"
    assert not has_errors(check_graph(out.graph, DUR))
    assert out.graph.revision != office_graph.revision


# --- extra coverage ---------------------------------------------------------------


def test_patch_op_is_discriminated_union():
    ops = OPS.validate_python([
        {"op": "remove_door", "id": "D3", "cite_t_s": 1, "reason": "r"},
        {"op": "update_zone", "id": "Z1", "name": "Hall", "cite_t_s": 1, "reason": "r"},
        {"op": "remove_zone", "id": "Z4", "cite_t_s": 1, "reason": "r"},
    ])
    assert [type(o) for o in ops] == [RemoveDoor, UpdateZone, RemoveZone]
    with pytest.raises(ValidationError):
        OPS.validate_python([{"op": "teleport", "id": "D1", "cite_t_s": 1, "reason": "r"}])
    with pytest.raises(ValidationError):
        OPS.validate_python([{"op": "remove_door", "id": "D1", "reason": "no cite"}])
    with pytest.raises(ValidationError):
        OPS.validate_python([{"op": "remove_door", "id": "D1", "cite_t_s": 1, "reason": "r" * 201}])


def test_patch_add_duplicate_door_rejected(office_graph):
    dup = _d7().model_copy(update={"id": "D1"})
    out = apply_patch(office_graph, [AddDoor(op="add_door", door=dup, cite_t_s=1, reason="r")], DUR)
    assert out.applied == []
    assert "DUPLICATE_ID" in out.rejected[0][1]
    assert out.graph == office_graph


def test_patch_remove_zone_with_doors_rejected(office_graph):
    out = apply_patch(office_graph, [RemoveZone(op="remove_zone", id="Z4", cite_t_s=1, reason="r")], DUR)
    assert out.applied == []
    assert "UNKNOWN_ZONE_REF" in out.rejected[0][1]


def test_patch_invalid_rect_rejected(office_graph):
    op = UpdateZone(op="update_zone", id="Z1", rect=(3, 0, -2, 8), cite_t_s=1, reason="r")
    out = apply_patch(office_graph, [op], DUR)
    assert out.applied == [] and out.rejected[0][1].startswith("invalid")


def test_patch_cite_outside_video_rejected(office_graph):
    op = UpdateDoor(op="update_door", id="D2", state="closed", cite_t_s=DUR + 5, reason="r")
    out = apply_patch(office_graph, [op], DUR)
    assert out.applied == [] and "cite_t_s" in out.rejected[0][1]


def test_patch_preexisting_error_does_not_block(office_graph):
    # D6 placed off-boundary before the patch; an unrelated fix still applies.
    broken = office_graph.model_copy(update={"doors": [
        d.model_copy(update={"position": (5.0, 3.0)}) if d.id == "D6" else d
        for d in office_graph.doors]})
    assert has_errors(check_graph(broken, DUR))
    op = UpdateDoor(op="update_door", id="D5", state="open", cite_t_s=55, reason="r")
    out = apply_patch(broken, [op], DUR)
    assert out.applied == [0]
    fix = UpdateDoor(op="update_door", id="D6", position=(5.0, 8.0), cite_t_s=57, reason="r")
    assert not has_errors(check_graph(apply_patch(broken, [fix], DUR).graph, DUR))
