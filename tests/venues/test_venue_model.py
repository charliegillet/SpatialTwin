import copy
import json

import pytest
from pydantic import ValidationError

from backend.app.venues.model import VENUE_FILE, VenueV2, load_building_v2


def raw():
    return copy.deepcopy(json.loads(VENUE_FILE.read_text()))


def test_building_v2_loads_and_matches_declared_shape(venue):
    assert [z.id for z in venue.zones][:2] == ["HALL", "LOBBY"]
    assert len(venue.zones) == 8 and len(venue.doors) == 10 and len(venue.exits) == 4
    assert sum(z.initial_occupants for z in venue.zones) == 125
    assert venue.default_horizon_seconds == 40 and venue.time_step_seconds == 2


def test_to_json_round_trips_the_file(venue):
    assert venue.to_json() == json.loads(VENUE_FILE.read_text())


@pytest.mark.parametrize("mutate", [
    lambda d: d["zones"].append(dict(d["zones"][0])),                                     # duplicate zone id
    lambda d: d["zones"][0].update(id="hall"),                                             # bad id pattern
    lambda d: d["doors"][0].update(zones=["HALL", "HALL"]),                                # door joins zone to itself
    lambda d: d["doors"][0].update(zones=["LOBBY", "NOWHERE"]),                            # unknown zone
    lambda d: d["doors"].append({**d["doors"][0], "id": "D11", "zones": ["HALL", "LOBBY"]}),  # second door on a pair
    lambda d: d["doors"].append({**d["doors"][0], "id": "D11", "zones": ["WEST_CORR", "HALL"]}),  # reversed duplicate pair
    lambda d: d["exits"][0].update(zone="NOWHERE"),                                        # unknown exit zone
    lambda d: d["led_map"].update(E9=[0, 1]),                                              # unknown led element
    lambda d: d["exits"][0].update(id="D1"),                                               # id collision
])
def test_validator_rejects(mutate):
    data = raw()
    mutate(data)
    with pytest.raises(ValidationError):
        VenueV2.model_validate(data)


def test_locate_zone_wall_resolves_to_first_zone_and_outside_is_none(venue):
    assert venue.locate_zone(20, 14) == "HALL"
    assert venue.locate_zone(20, 8) == "HALL"  # shared wall HALL/LOBBY: first in venue order
    assert venue.locate_zone(12, 4) == "LOBBY"  # LOBBY precedes WEST_CORR in venue order
    assert venue.locate_zone(100, 100) is None
    assert venue.locate_zone(0, 0) is None  # south-west corner is outside every zone


def test_load_is_cached():
    assert load_building_v2() is load_building_v2()
