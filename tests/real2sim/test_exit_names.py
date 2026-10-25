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


def test_a_specific_label_is_kept():
    raw = home_raw()
    raw["exits"][0]["label"] = "Garden door"
    assert compile_raw(raw, building_width_m=12).venue.exits[0].name == "Garden door"
