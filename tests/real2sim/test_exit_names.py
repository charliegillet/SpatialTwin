"""Exit names: posted maps print "EXIT" or "STAIR" on every exit, so announcements name a bare label after its room."""
import pytest

from tests.real2sim.test_compiler import compile_raw, home_raw


@pytest.mark.parametrize("printed", ["EXIT", "Exit.", "STAIR", "Stairs", "EXIT STAIR", "stairway", ""])
def test_a_bare_exit_or_stair_label_takes_its_room_name(printed):
    raw = home_raw()
    raw["exits"][0]["label"] = printed
    result = compile_raw(raw, building_width_m=12)
    room = result.venue.zones[[z.id for z in result.venue.zones].index(result.venue.exits[0].zone)]
    assert result.venue.exits[0].name == f"{room.name} exit"


def test_a_room_printed_exit_gives_compass_names_to_it_and_its_exit():
    """Ferry Level 3 prints "EXIT" on the stair rooms themselves: "use the exit or exit" names nothing."""
    raw = home_raw()
    raw["rooms"][1]["name"] = "EXIT"                      # KITCHEN, top right of the drawing
    raw["exits"] = [e for e in raw["exits"] if e["room"] == "KITCHEN"] or raw["exits"]
    for item in raw["exits"]:
        item["label"] = "EXIT"
    result = compile_raw(raw, building_width_m=12)
    names = {zone.id: zone.name for zone in result.venue.zones}
    for item in result.venue.exits:
        assert item.name.upper() != "EXIT" and not item.name.startswith("EXIT")
    kitchen = next(zone for zone in result.venue.zones if zone.name != "EXIT" and zone.id == result.report.element_ids["KITCHEN"])
    assert kitchen.name.endswith(("exit", "exit stair", "room")) and "EXIT" not in names.values()
    assert any("printed name 'EXIT'" in edit for edit in result.report.edits)


def test_a_specific_label_is_kept():
    raw = home_raw()
    raw["exits"][0]["label"] = "Garden door"
    assert compile_raw(raw, building_width_m=12).venue.exits[0].name == "Garden door"
