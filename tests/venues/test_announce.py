from backend.app.hazard.announce import build_announcement
from backend.app.hazard.door_planner import plan_doors
from tests.venues.conftest import make_request


def test_no_hazard_means_no_announcement(venue):
    assert plan_doors(venue, make_request([])).announcement == ""


def test_fire_in_lobby_restates_the_plan(venue):
    text = plan_doors(venue, make_request([("FIRE", 20, 4)])).announcement
    assert text.startswith("Attention. Fire in the lobby.")
    assert "Do not use the south exit." in text
    assert "dock exit" in text and "Door D9 between the east corridor and the loading dock is open." in text
    for word in ("surviv", "safe now", "saved"):
        assert word not in text.lower()


def test_gas_adds_the_no_switching_rule_and_opens_nothing_nearby(venue):
    text = plan_doors(venue, make_request([("GAS", 20, 14)])).announcement
    assert "A gas leak in the hall." in text
    assert text.endswith("Do not operate switches near the hall.")
    assert "D4" not in text


def test_ineffective_duplicates_are_not_repeated():
    text = build_announcement({"HALL": "Hall"}, {"E1": "South exit"},
                              [{"type": "FIRE", "zone_id": "HALL", "effective": True},
                               {"type": "FIRE", "zone_id": "HALL", "effective": True},
                               {"type": "WATER", "zone_id": "HALL", "effective": False}],
                              [{"id": "E1", "safe": True, "modeled_crossings": 3}], [])
    assert text == "Attention. Fire in the hall. Use the south exit."
