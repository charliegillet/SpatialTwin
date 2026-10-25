import math

import pytest

from backend.app.ai.grounding.calibration import (
    CORNER_ORDER,
    CalibrationError,
    apply_homography,
    box_corners_px,
    calibrate,
    load_sheet,
    map_card,
    normalized_to_px,
    solve_homography,
)

SHEET = load_sheet()
IMAGE = (1280, 720)
# A tilted overhead camera: floor metres -> image pixels, with real perspective (non-zero h31/h32).
CAMERA = [[22.0, 4.0, 160.0], [-1.5, -19.0, 640.0], [0.002, 0.004, 1.0]]


def _project(point):
    return apply_homography(CAMERA, point)


def _corners():
    return {label: _project(tuple(SHEET["fiducial_floor_m"][label])) for label in CORNER_ORDER}


def test_sheet_metadata_matches_the_printed_sheet():
    assert SHEET["venue_id"] == "building-v2"
    assert set(SHEET["fiducial_floor_m"]) == set(CORNER_ORDER)


def test_four_corners_round_trip_below_a_millimetre():
    cal = calibrate(_corners(), IMAGE)
    assert cal.reprojection_error_m < 1e-6
    for floor in [(0.5, 0.5), (20.0, 4.0), (39.0, 23.0), (10.0, 14.0), (36.0, 16.0)]:
        back = cal.to_floor(_project(floor))
        assert math.dist(back, floor) < 1e-6


def test_card_point_and_box_map_onto_the_floor():
    cal = calibrate(_corners(), IMAGE)
    # Build Gemini-style normalised output for a card centred in the lobby (20, 4).
    centre_px = _project((20.0, 4.0))
    point = (centre_px[1] / IMAGE[1] * 1000, centre_px[0] / IMAGE[0] * 1000)
    corners = [_project(p) for p in [(18.0, 3.0), (22.0, 3.0), (22.0, 5.0), (18.0, 5.0)]]
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    box = (min(ys) / IMAGE[1] * 1000, min(xs) / IMAGE[0] * 1000, max(ys) / IMAGE[1] * 1000, max(xs) / IMAGE[0] * 1000)
    placement = map_card(cal, point, box, SHEET_EXTENT)
    assert math.dist(placement.floor_xy, (20.0, 4.0)) < 1e-6
    assert placement.inside_building
    assert not placement.crosses_building_edge


SHEET_EXTENT = (40, 24)


def test_card_crossing_the_building_edge_is_flagged():
    cal = calibrate(_corners(), IMAGE)
    corners = [_project(p) for p in [(38.0, 10.0), (42.0, 10.0), (42.0, 12.0), (38.0, 12.0)]]
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    box = (min(ys) / IMAGE[1] * 1000, min(xs) / IMAGE[0] * 1000, max(ys) / IMAGE[1] * 1000, max(xs) / IMAGE[0] * 1000)
    centre = _project((40.0, 11.0))
    placement = map_card(cal, (centre[1] / IMAGE[1] * 1000, centre[0] / IMAGE[0] * 1000), box, SHEET_EXTENT)
    assert placement.crosses_building_edge


def test_card_off_the_building_is_outside():
    cal = calibrate(_corners(), IMAGE)
    centre = _project((-1.5, -1.5))
    placement = map_card(cal, (centre[1] / IMAGE[1] * 1000, centre[0] / IMAGE[0] * 1000), None, SHEET_EXTENT)
    assert not placement.inside_building


def test_missing_corner_is_rejected():
    corners = _corners()
    del corners["BR"]
    with pytest.raises(CalibrationError) as err:
        calibrate(corners, IMAGE)
    assert err.value.code == "missing_corner"


def test_corner_outside_the_image_is_rejected():
    corners = _corners()
    corners["TL"] = (-5.0, 10.0)
    with pytest.raises(CalibrationError) as err:
        calibrate(corners, IMAGE)
    assert err.value.code == "corner_outside_image"


def test_swapped_corners_are_rejected():
    corners = _corners()
    corners["TL"], corners["TR"] = corners["TR"], corners["TL"]
    with pytest.raises(CalibrationError) as err:
        calibrate(corners, IMAGE)
    assert err.value.code == "corners_out_of_order"


def test_collinear_points_are_degenerate():
    with pytest.raises(CalibrationError) as err:
        solve_homography([(0, 0), (1, 1), (2, 2), (3, 3)], [(0, 0), (1, 0), (1, 1), (0, 1)])
    assert err.value.code == "degenerate_calibration"


def test_normalised_coordinates_are_y_first():
    assert normalized_to_px((500, 250), (1000, 800)) == (250.0, 400.0)
    assert box_corners_px((0, 0, 1000, 1000), (100, 50)) == [(0.0, 0.0), (100.0, 0.0), (100.0, 50.0), (0.0, 50.0)]
