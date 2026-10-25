"""Camera-to-floor calibration for the Camera twin (pure math, no provider calls).

Four printed corner markers (TL, TR, BR, BL on venue/print/building_v2_sheet.svg) have known floor
coordinates in metres (venue/print/sheet_v2.json). Their image positions, clicked by the presenter
or pointed at by Gemini, fix a planar homography from image pixels to floor metres. Card positions
are then mapped onto the reviewed floor plan; nothing is reconstructed in 3D.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[4]
SHEET_META = ROOT / "venue" / "print" / "sheet_v2.json"
CORNER_ORDER = ("TL", "TR", "BR", "BL")
MAX_REPROJECTION_ERROR_M = 0.05
# Four points always fit their own homography exactly, so the residual is not a quality measure;
# a quad this small in the image is the useful sanity check.
MIN_CORNER_SIDE_PX = 40.0

Point = Tuple[float, float]
Matrix = List[List[float]]


class CalibrationError(ValueError):
    """Raised with a stable code: missing_corner, corner_outside_image, corners_out_of_order, corners_too_close,
    degenerate_calibration."""

    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code


def load_sheet(path: Path = SHEET_META) -> dict:
    return json.loads(path.read_text())


def _solve_linear(a: List[List[float]], b: List[float]) -> List[float]:
    """Gaussian elimination with partial pivoting; raises on a singular system."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-12:
            raise CalibrationError("degenerate_calibration", "corner points do not define a plane mapping")
        m[col], m[pivot] = m[pivot], m[col]
        for r in range(col + 1, n):
            factor = m[r][col] / m[col][col]
            for c in range(col, n + 1):
                m[r][c] -= factor * m[col][c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (m[r][n] - sum(m[r][c] * x[c] for c in range(r + 1, n))) / m[r][r]
    return x


def solve_homography(src: Sequence[Point], dst: Sequence[Point]) -> Matrix:
    """Direct linear transform for exactly four correspondences (h33 = 1)."""
    if len(src) != 4 or len(dst) != 4:
        raise CalibrationError("missing_corner", "exactly four correspondences are required")
    a: List[List[float]] = []
    b: List[float] = []
    for (x, y), (u, v) in zip(src, dst):
        a.append([x, y, 1.0, 0.0, 0.0, 0.0, -u * x, -u * y])
        b.append(u)
        a.append([0.0, 0.0, 0.0, x, y, 1.0, -v * x, -v * y])
        b.append(v)
    h = _solve_linear(a, b)
    return [[h[0], h[1], h[2]], [h[3], h[4], h[5]], [h[6], h[7], 1.0]]


def apply_homography(h: Matrix, point: Point) -> Point:
    x, y = point
    w = h[2][0] * x + h[2][1] * y + h[2][2]
    if abs(w) < 1e-12:
        raise CalibrationError("degenerate_calibration", "point maps to infinity")
    return ((h[0][0] * x + h[0][1] * y + h[0][2]) / w, (h[1][0] * x + h[1][1] * y + h[1][2]) / w)


def _signed_area(points: Sequence[Point]) -> float:
    return 0.5 * sum(
        points[i][0] * points[(i + 1) % len(points)][1] - points[(i + 1) % len(points)][0] * points[i][1]
        for i in range(len(points))
    )


def _is_convex(points: Sequence[Point]) -> bool:
    signs = set()
    n = len(points)
    for i in range(n):
        ax, ay = points[i]
        bx, by = points[(i + 1) % n]
        cx, cy = points[(i + 2) % n]
        cross = (bx - ax) * (cy - by) - (by - ay) * (cx - bx)
        if abs(cross) > 1e-9:
            signs.add(cross > 0)
    return len(signs) == 1


@dataclass(frozen=True)
class Calibration:
    corners_px: Dict[str, Point]
    image_size: Tuple[int, int]
    homography: Matrix
    reprojection_error_m: float

    def to_floor(self, point_px: Point) -> Point:
        return apply_homography(self.homography, point_px)


def calibrate(corners_px: Dict[str, Sequence[float]], image_size: Sequence[int], sheet: dict | None = None) -> Calibration:
    """Corners in image pixels (x right, y down) for TL, TR, BR, BL -> pixel-to-floor homography."""
    sheet = sheet or load_sheet()
    width, height = int(image_size[0]), int(image_size[1])
    if width <= 0 or height <= 0:
        raise CalibrationError("corner_outside_image", "image size must be positive")
    src: List[Point] = []
    for label in CORNER_ORDER:
        if label not in corners_px:
            raise CalibrationError("missing_corner", f"corner {label} is missing")
        x, y = float(corners_px[label][0]), float(corners_px[label][1])
        if not (math.isfinite(x) and math.isfinite(y)) or not (0 <= x <= width and 0 <= y <= height):
            raise CalibrationError("corner_outside_image", f"corner {label} lies outside the image")
        src.append((x, y))
    # In image coordinates (y down) TL->TR->BR->BL runs clockwise on screen, i.e. positive signed area.
    if not _is_convex(src) or _signed_area(src) <= 0:
        raise CalibrationError("corners_out_of_order", "corners must be TL, TR, BR, BL around the sheet")
    if min(math.dist(src[i], src[(i + 1) % 4]) for i in range(4)) < MIN_CORNER_SIDE_PX:
        raise CalibrationError("corners_too_close", "the four corners must be at least 40 px apart")
    dst = [tuple(map(float, sheet["fiducial_floor_m"][label])) for label in CORNER_ORDER]
    homography = solve_homography(src, dst)
    error = max(math.dist(apply_homography(homography, s), d) for s, d in zip(src, dst))
    if error > MAX_REPROJECTION_ERROR_M:
        raise CalibrationError("degenerate_calibration", f"reprojection error {error:.3f} m")
    return Calibration(
        corners_px={label: src[i] for i, label in enumerate(CORNER_ORDER)},
        image_size=(width, height),
        homography=homography,
        reprojection_error_m=error,
    )


def normalized_to_px(point_yx_1000: Sequence[float], image_size: Sequence[int]) -> Point:
    """Gemini spatial output is [y, x] normalised to 0-1000; convert to pixel (x, y)."""
    y, x = float(point_yx_1000[0]), float(point_yx_1000[1])
    return (x / 1000.0 * image_size[0], y / 1000.0 * image_size[1])


def box_corners_px(box_2d_1000: Sequence[float], image_size: Sequence[int]) -> List[Point]:
    """[ymin, xmin, ymax, xmax] normalised to 0-1000 -> four pixel corners."""
    ymin, xmin, ymax, xmax = (float(v) for v in box_2d_1000)
    return [
        normalized_to_px((ymin, xmin), image_size),
        normalized_to_px((ymin, xmax), image_size),
        normalized_to_px((ymax, xmax), image_size),
        normalized_to_px((ymax, xmin), image_size),
    ]


@dataclass(frozen=True)
class CardPlacement:
    floor_xy: Point
    inside_building: bool
    crosses_building_edge: bool


def map_card(
    calibration: Calibration,
    point_yx_1000: Sequence[float],
    box_2d_1000: Sequence[float] | None,
    extent_m: Sequence[float],
) -> CardPlacement:
    """Map a card's centre to the floor and check whether its box stays on the building footprint."""
    floor = calibration.to_floor(normalized_to_px(point_yx_1000, calibration.image_size))
    width_m, height_m = float(extent_m[0]), float(extent_m[1])

    def inside(p: Point) -> bool:
        return 0.0 <= p[0] <= width_m and 0.0 <= p[1] <= height_m

    crosses = False
    if box_2d_1000 is not None:
        corners = [calibration.to_floor(c) for c in box_corners_px(box_2d_1000, calibration.image_size)]
        flags = [inside(c) for c in corners]
        crosses = any(flags) and not all(flags)
    return CardPlacement(floor_xy=floor, inside_building=inside(floor), crosses_building_edge=crosses)
