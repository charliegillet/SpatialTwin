"""Generate printable assets for the Camera twin from venue/building_v2.json.

Writes to venue/print/:
  building_v2_sheet.svg  A3 landscape floor sheet with four corner markers (TL, TR, BR, BL)
  sheet_v2.json          scale and marker floor coordinates used by camera calibration
  hazard_cards.svg       A4 page of red hazard cards (FIRE, SMOKE, GAS, CHEMICAL, WATER), two of each

Run: .venv/bin/python -m tools.print_assets
"""

from __future__ import annotations

import json
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
VENUE = ROOT / "venue" / "building_v2.json"
OUT = ROOT / "venue" / "print"

SHEET_W_MM, SHEET_H_MM = 420.0, 297.0  # A3 landscape
SCALE = 8.0  # mm per metre
MARKER_OFFSET_M = 2.5  # marker centres sit this far outside the building corners
MARKER_MM = 18.0
CARD_W_MM, CARD_H_MM = 40.0, 28.0  # small enough to sit inside a 4 m corridor turned sideways
CARD_RED = "#d0161b"

# Simple icon paths on a 24x24 grid (drawn white on the red card).
ICONS = {
    "FIRE": "M12 2c1 4 5 6 5 11a5 5 0 0 1-10 0c0-3 2-4 2-7 2 1 3 3 3 5 1-2 0-6 0-9z",
    "SMOKE": "M6 17a4 4 0 0 1 0-8 5 5 0 0 1 9.5-1.5A4 4 0 0 1 18 17zM5 20h14v1.6H5z",
    "GAS": "M9 2h6v3h-1v2a6 6 0 0 1 4 5.6V21a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1v-8.4A6 6 0 0 1 10 7V5H9z",
    "CHEMICAL": "M9 2h6v1.6h-1v6l5.6 9.2A1.6 1.6 0 0 1 18.2 21H5.8a1.6 1.6 0 0 1-1.4-2.2L10 9.6v-6H9z",
    "WATER": "M12 2c3 5 7 9 7 13a7 7 0 0 1-14 0c0-4 4-8 7-13z",
}


def _floor_to_sheet(x_m: float, y_m: float, extent: list[float]) -> tuple[float, float]:
    """Floor metres (x east, y north) to sheet millimetres (y down), building centred."""
    width_mm = extent[0] * SCALE
    height_mm = extent[1] * SCALE
    ox = (SHEET_W_MM - width_mm) / 2
    oy = (SHEET_H_MM - height_mm) / 2
    return ox + x_m * SCALE, oy + (extent[1] - y_m) * SCALE


def _marker(cx: float, cy: float, label: str) -> str:
    half = MARKER_MM / 2
    inner = MARKER_MM * 0.42
    # Each corner gets a distinct inner notch so orientation is unambiguous.
    notch = {
        "TL": (cx - half + 2.5, cy - half + 2.5),
        "TR": (cx + half - 2.5 - inner / 2, cy - half + 2.5),
        "BR": (cx + half - 2.5 - inner / 2, cy + half - 2.5 - inner / 2),
        "BL": (cx - half + 2.5, cy + half - 2.5 - inner / 2),
    }[label]
    return (
        f'<rect x="{cx - half:.2f}" y="{cy - half:.2f}" width="{MARKER_MM}" height="{MARKER_MM}" fill="#000"/>'
        f'<rect x="{cx - inner / 2:.2f}" y="{cy - inner / 2:.2f}" width="{inner:.2f}" height="{inner:.2f}" fill="#fff"/>'
        f'<rect x="{notch[0]:.2f}" y="{notch[1]:.2f}" width="{inner / 2:.2f}" height="{inner / 2:.2f}" fill="#fff"/>'
        f'<text x="{cx:.2f}" y="{cy + half + 6:.2f}" font-size="5" text-anchor="middle" '
        f'font-family="Helvetica, Arial, sans-serif" font-weight="700">{label}</text>'
    )


def build_sheet(venue: dict) -> tuple[str, dict]:
    extent = venue["extent"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SHEET_W_MM}mm" height="{SHEET_H_MM}mm" '
        f'viewBox="0 0 {SHEET_W_MM} {SHEET_H_MM}">',
        f'<rect width="{SHEET_W_MM}" height="{SHEET_H_MM}" fill="#fff"/>',
    ]
    for zone in venue["zones"]:
        pts = " ".join("{:.2f},{:.2f}".format(*_floor_to_sheet(x, y, extent)) for x, y in zone["polygon"])
        parts.append(f'<polygon points="{pts}" fill="#f2f2f2" stroke="#222" stroke-width="1.4"/>')
        xs = [p[0] for p in zone["polygon"]]
        ys = [p[1] for p in zone["polygon"]]
        lx, ly = _floor_to_sheet(sum(xs) / len(xs), sum(ys) / len(ys), extent)
        # Narrow corridors get a vertical label so it stays inside the room.
        narrow = (max(xs) - min(xs)) < 6 and (max(ys) - min(ys)) > 2 * (max(xs) - min(xs))
        rotate = f' transform="rotate(-90 {lx:.2f} {ly:.2f})"' if narrow else ""
        parts.append(
            f'<text x="{lx:.2f}" y="{ly:.2f}" font-size="5.5" text-anchor="middle" fill="#555" '
            f'font-family="Helvetica, Arial, sans-serif"{rotate}>{escape(zone["name"])}</text>'
        )
    zones = {zone["id"]: zone for zone in venue["zones"]}
    for door in venue["doors"]:
        x, y = door["position"]
        first = zones[door["zones"][0]]["polygon"]
        vertical = any(abs(x - px) < 1e-9 for px, _ in first) and not any(abs(y - py) < 1e-9 for _, py in first)
        half = door["width"] / 2
        a = _floor_to_sheet(x, y - half, extent) if vertical else _floor_to_sheet(x - half, y, extent)
        b = _floor_to_sheet(x, y + half, extent) if vertical else _floor_to_sheet(x + half, y, extent)
        parts.append(
            f'<line x1="{a[0]:.2f}" y1="{a[1]:.2f}" x2="{b[0]:.2f}" y2="{b[1]:.2f}" stroke="#fff" stroke-width="2.4"/>'
        )
        dx, dy = _floor_to_sheet(x, y, extent)
        lx, ly = (dx + 3.2, dy + 1.4) if vertical else (dx, dy - 2.4)
        anchor = "start" if vertical else "middle"
        parts.append(
            f'<text x="{lx:.2f}" y="{ly:.2f}" font-size="3.6" text-anchor="{anchor}" fill="#888" '
            f'font-family="Helvetica, Arial, sans-serif">{door["id"]}</text>'
        )
    for exit_ in venue["exits"]:
        x, y = exit_["position"]
        half = exit_["width"] / 2
        vertical = x in (0, extent[0])
        a = _floor_to_sheet(x, y - half, extent) if vertical else _floor_to_sheet(x - half, y, extent)
        b = _floor_to_sheet(x, y + half, extent) if vertical else _floor_to_sheet(x + half, y, extent)
        parts.append(
            f'<line x1="{a[0]:.2f}" y1="{a[1]:.2f}" x2="{b[0]:.2f}" y2="{b[1]:.2f}" stroke="#1d7a45" stroke-width="2.4"/>'
        )
        ex, ey = _floor_to_sheet(x, y, extent)
        if vertical:
            lx, ly = (ex - 4, ey + 1.3) if x == 0 else (ex + 4, ey + 1.3)
            anchor = "end" if x == 0 else "start"
        else:
            lx, ly, anchor = ex, (ey + 5.5 if y == 0 else ey - 2.6), "middle"
        parts.append(
            f'<text x="{lx:.2f}" y="{ly:.2f}" font-size="4" text-anchor="{anchor}" fill="#1d7a45" '
            f'font-family="Helvetica, Arial, sans-serif" font-weight="700">{exit_["id"]}</text>'
        )
    off = MARKER_OFFSET_M
    fiducials = {
        "TL": [-off, extent[1] + off],
        "TR": [extent[0] + off, extent[1] + off],
        "BR": [extent[0] + off, -off],
        "BL": [-off, -off],
    }
    for label, (fx, fy) in fiducials.items():
        parts.append(_marker(*_floor_to_sheet(fx, fy, extent), label))
    parts.append(
        f'<text x="{SHEET_W_MM / 2:.1f}" y="{SHEET_H_MM - 6:.1f}" font-size="4.5" text-anchor="middle" fill="#777" '
        f'font-family="Helvetica, Arial, sans-serif">SpatialTwin building-v2 · illustrative plan, not a surveyed '
        f'building · print at 100% on matte A3 · north is up</text>'
    )
    parts.append("</svg>")
    meta = {
        "venue_id": venue["venue_id"],
        "geometry_revision": venue["geometry_revision"],
        "paper": "A3 landscape",
        "sheet_mm": [SHEET_W_MM, SHEET_H_MM],
        "scale_mm_per_m": SCALE,
        "fiducial_floor_m": fiducials,
        "fiducial_size_mm": MARKER_MM,
    }
    return "\n".join(parts), meta


def build_cards() -> str:
    page_w, page_h = 210.0, 297.0  # A4 portrait
    cols, gap = 3, 8.0
    kinds = list(ICONS)
    cards = kinds + kinds
    grid_w = cols * CARD_W_MM + (cols - 1) * gap
    ox = (page_w - grid_w) / 2
    oy = 20.0
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{page_w}mm" height="{page_h}mm" viewBox="0 0 {page_w} {page_h}">',
        f'<rect width="{page_w}" height="{page_h}" fill="#fff"/>',
    ]
    for index, kind in enumerate(cards):
        col, row = index % cols, index // cols
        x = ox + col * (CARD_W_MM + gap)
        y = oy + row * (CARD_H_MM + gap)
        icon_size = 13.0
        parts.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{CARD_W_MM}" height="{CARD_H_MM}" rx="3" fill="{CARD_RED}"/>')
        parts.append(
            f'<g transform="translate({x + (CARD_W_MM - icon_size) / 2:.2f} {y + 4:.2f}) scale({icon_size / 24:.4f})">'
            f'<path d="{ICONS[kind]}" fill="#fff"/></g>'
        )
        parts.append(
            f'<text x="{x + CARD_W_MM / 2:.2f}" y="{y + CARD_H_MM - 4.5:.2f}" font-size="{6.2 if len(kind) <= 6 else 5.2}" text-anchor="middle" '
            f'fill="#fff" font-family="Helvetica, Arial, sans-serif" font-weight="800" letter-spacing="0.6">{kind}</text>'
        )
    parts.append(
        f'<text x="{page_w / 2:.1f}" y="{page_h - 12:.1f}" font-size="4" text-anchor="middle" fill="#777" '
        f'font-family="Helvetica, Arial, sans-serif">Cut along the card edges · matte paper · one card marks one hazard in a room</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    venue = json.loads(VENUE.read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    sheet, meta = build_sheet(venue)
    (OUT / "building_v2_sheet.svg").write_text(sheet + "\n")
    (OUT / "sheet_v2.json").write_text(json.dumps(meta, indent=2) + "\n")
    (OUT / "hazard_cards.svg").write_text(build_cards() + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}/building_v2_sheet.svg, sheet_v2.json, hazard_cards.svg")


if __name__ == "__main__":
    main()
