"""Evidence overlay and top-down render for a compiled Real2Sim draft (Pillow only, deterministic).

``render_overlay`` draws the *compiled* geometry back onto the source image, through the inverse of the compiler's
transform (``venues/compiler.py``): translucent room outlines with names, door gaps as thick ticks labelled with
venue ids, exits as green markers, the evidence points Argon pointed at as small circles joined to the element
they became, and everything the compiler dropped in red. The operator checks this picture before pressing Accept:
if a tick sits in the wrong wall, the compile (not the model) is what they are looking at.

``render_topdown`` draws the VenueV2 alone (what the 3D scene and the planner will see), with ids and capacities.

No network, no random numbers, no system fonts: Pillow's bundled font at fixed sizes, so the same input gives the
same bytes. Output is capped at MAX_SIDE_PX per side.
"""
from __future__ import annotations

import io
from typing import List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

from backend.app.ai.real2sim.schema import CompileResult, SourceImage, VenueDraftV1
from backend.app.venues.compiler import _Frame, _segments
from backend.app.venues.model import VenueV2

MAX_SIDE_PX = 2400
MIN_TOPDOWN_PX, DEFAULT_TOPDOWN_PX = 300, 1200
ROOM = (46, 110, 200)
DOOR = (30, 90, 220)
FREE_DOOR = (235, 130, 20)
FIRE_DOOR = (190, 60, 150)
EXIT_C = (0, 150, 80)
EVIDENCE = (240, 190, 0)
DROPPED = (215, 30, 30)
INK = (30, 34, 40)
PAPER = (250, 249, 244)


def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.load_default(size=max(8, int(size)))


def _flatten(image: Image.Image) -> Image.Image:
    """RGBA / LA / P (with transparency) -> RGB on white, so every input mode renders the same way."""
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        base = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        base.alpha_composite(rgba)
        return base.convert("RGB")
    return image.convert("RGB")


def _png(image: Image.Image) -> bytes:
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def _axis_at(polygons: Sequence[Sequence[Tuple[float, float]]], position: Tuple[float, float]) -> str:
    """'h' when the wall under ``position`` runs east-west, 'v' when north-south (default 'h')."""
    px, py = position
    for polygon in polygons:
        for axis, at, lo, hi in _segments(polygon):
            along, across = (px, py) if axis == "h" else (py, px)
            if abs(across - at) < 1e-6 and lo - 1e-6 <= along <= hi + 1e-6:
                return axis
    return "h"


def _tick(position: Tuple[float, float], width: float, axis: str) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    x, y = position
    return ((x - width / 2, y), (x + width / 2, y)) if axis == "h" else ((x, y - width / 2), (x, y + width / 2))


def _beside(mid: Tuple[float, float], axis: str, gap: float) -> Tuple[float, float]:
    """Where to put a tick's label so it does not sit on the wall: above a horizontal wall, right of a vertical one."""
    return (mid[0], mid[1] - gap) if axis == "h" else (mid[0] + gap, mid[1])


def _label(draw: ImageDraw.ImageDraw, xy: Tuple[float, float], text: str, font, fill, halo=(255, 255, 255)) -> None:
    x, y = xy
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        draw.text((x + dx, y + dy), text, font=font, fill=halo, anchor="mm")
    draw.text((x, y), text, font=font, fill=fill, anchor="mm")


def _dropped_target(draft: VenueDraftV1, line: str) -> Optional[Tuple[str, Tuple[int, int], Optional[List[int]]]]:
    """Parse a 'door KEY: reason' / 'room KEY: reason' / 'exit KEY: reason' dropped entry into (key, [y, x], box)."""
    head = line.split(":", 1)[0].split()
    if len(head) != 2:
        return None
    kind, key = head
    if kind == "door":
        item = next((d for d in draft.doors if d.key == key), None)
        return (key, (item.point[0], item.point[1]), None) if item else None
    if kind == "exit":
        item = next((e for e in draft.exits if e.key == key), None)
        return (key, (item.point[0], item.point[1]), None) if item else None
    if kind == "room":
        item = next((r for r in draft.rooms if r.key == key), None)
        return (key, (item.label_point[0], item.label_point[1]), item.box) if item else None
    return None


def render_overlay(image_bytes: bytes, draft: VenueDraftV1, result: CompileResult) -> bytes:
    """The source image with the compiled geometry projected back onto it, a legend strip underneath. PNG bytes."""
    with Image.open(io.BytesIO(image_bytes)) as opened:
        base = _flatten(opened)
    src_w, src_h = base.size
    shrink = min(1.0, MAX_SIDE_PX / max(src_w, src_h))
    if shrink < 1.0:
        base = base.resize((max(1, round(src_w * shrink)), max(1, round(src_h * shrink))), Image.LANCZOS)
    width, height = base.size
    unit = max(1.0, min(width, height) / 700)             # line weights and fonts scale with the picture
    font, small = _font(14 * unit), _font(11 * unit)

    # The compiler's frame works in the original pixels; scale into the possibly shrunk image.
    frame = _Frame(SourceImage(src_w, src_h, ""), draft)
    mpp = result.report.metres_per_px or 1.0

    def to_px(x_m: float, y_m: float) -> Tuple[float, float]:
        return (frame.minx_px + x_m / mpp) * shrink, (frame.maxy_px - y_m / mpp) * shrink

    def draft_px(point: Sequence[float]) -> Tuple[float, float]:
        return point[1] / 1000 * width, point[0] / 1000 * height

    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    venue = result.venue
    notes = []
    if venue is not None:
        polygons = {z.id: z.polygon for z in venue.zones}
        for zone in venue.zones:
            pts = [to_px(x, y) for x, y in zone.polygon]
            draw.polygon(pts, fill=ROOM + (46,), outline=ROOM + (230,), width=max(2, round(2 * unit)))
        for zone in venue.zones:
            at = result.report.evidence_points.get(zone.id)
            if at:
                x, y = draft_px(at)
                _label(draw, (x, y + 17 * unit), zone.name, small, ROOM + (255,))
        for door in venue.doors:
            axis = _axis_at([polygons[z] for z in door.zones], door.position)
            a, b = (to_px(*p) for p in _tick(door.position, door.width, axis))
            free = door.planner_can_open and door.default_state == "closed"
            colour = FREE_DOOR if free else FIRE_DOOR if door.kind == "fire_door" else DOOR
            draw.line([a, b], fill=colour + (255,), width=max(5, round(7 * unit)))
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            ev = result.report.evidence_points.get(door.id)
            if ev:
                draw.line([draft_px(ev), mid], fill=EVIDENCE + (200,), width=max(1, round(unit)))
            _label(draw, _beside(mid, axis, 14 * unit), door.id, small, colour + (255,))
        for exit_ in venue.exits:
            zone_poly = polygons[exit_.zone]
            axis = _axis_at([zone_poly], exit_.position)
            a, b = (to_px(*p) for p in _tick(exit_.position, exit_.width, axis))
            draw.line([a, b], fill=EXIT_C + (255,), width=max(6, round(9 * unit)))
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            r = 7 * unit
            draw.rectangle([mid[0] - r, mid[1] - r, mid[0] + r, mid[1] + r], fill=EXIT_C + (255,))
            ev = result.report.evidence_points.get(exit_.id)
            if ev:
                draw.line([draft_px(ev), mid], fill=EVIDENCE + (200,), width=max(1, round(unit)))
            _label(draw, _beside(mid, axis, 18 * unit), exit_.id, small, EXIT_C + (255,))
        for element_id, at in sorted(result.report.evidence_points.items()):
            x, y = draft_px(at)
            r = 4 * unit
            draw.ellipse([x - r, y - r, x + r, y + r], outline=EVIDENCE + (255,), width=max(2, round(2 * unit)))
    else:
        notes.append(f"no venue: {result.error}")
    for line in result.report.dropped:
        target = _dropped_target(draft, line)
        if not target:
            continue
        key, at, box = target
        if box:
            x0, y0, x1, y1 = box[1] / 1000 * width, box[0] / 1000 * height, box[3] / 1000 * width, box[2] / 1000 * height
            draw.rectangle([x0, y0, x1, y1], outline=DROPPED + (255,), width=max(2, round(3 * unit)))
        x, y = draft_px(at)
        r = 9 * unit
        draw.line([x - r, y - r, x + r, y + r], fill=DROPPED + (255,), width=max(3, round(4 * unit)))
        draw.line([x - r, y + r, x + r, y - r], fill=DROPPED + (255,), width=max(3, round(4 * unit)))
        _label(draw, (x, y + 16 * unit), key, small, DROPPED + (255,))
    composed = base.convert("RGBA")
    composed.alpha_composite(layer)

    # legend strip
    strip_h = round(46 * unit)
    out = Image.new("RGB", (width, height + strip_h), PAPER)
    out.paste(composed.convert("RGB"), (0, 0))
    d = ImageDraw.Draw(out)
    items = [("room", ROOM, "rect"), ("door", DOOR, "line"), ("controllable door", FREE_DOOR, "line"),
             ("fire door", FIRE_DOOR, "line"), ("exit", EXIT_C, "rect"), ("evidence point", EVIDENCE, "ring"),
             ("dropped", DROPPED, "x")]
    x, y = 12 * unit, height + strip_h / 2
    for text, colour, shape in items:
        s = 7 * unit
        if shape == "rect":
            d.rectangle([x, y - s, x + 2 * s, y + s], fill=colour)
        elif shape == "line":
            d.line([x, y, x + 2 * s, y], fill=colour, width=max(4, round(6 * unit)))
        elif shape == "ring":
            d.ellipse([x + s / 2, y - s, x + s / 2 + 2 * s, y + s], outline=colour, width=max(2, round(2 * unit)))
        else:
            d.line([x, y - s, x + 2 * s, y + s], fill=colour, width=3)
            d.line([x, y + s, x + 2 * s, y - s], fill=colour, width=3)
        d.text((x + 2 * s + 6 * unit, y), text, font=small, fill=INK, anchor="lm")
        x += 2 * s + 6 * unit + d.textlength(text, font=small) + 18 * unit
    tail = f"{len(result.report.dropped)} dropped" + (f"; {notes[0]}" if notes else "")
    d.text((width - 10 * unit, y), tail, font=small, fill=DROPPED if result.report.dropped or notes else INK, anchor="rm")
    return _png(out)


def render_topdown(venue: VenueV2, width_px: int = DEFAULT_TOPDOWN_PX) -> bytes:
    """The venue plan alone, north up, with ids, names, capacities and a metre scale bar. PNG bytes."""
    width_px = max(MIN_TOPDOWN_PX, min(int(width_px), MAX_SIDE_PX))
    margin = max(24, width_px // 30)
    ex, ey = max(venue.extent[0], 1e-6), max(venue.extent[1], 1e-6)
    scale = (width_px - 2 * margin) / ex
    if ey * scale + 2 * margin + 40 > MAX_SIDE_PX:
        scale = (MAX_SIDE_PX - 2 * margin - 40) / ey
    height_px = round(ey * scale + 2 * margin + 40)
    width_px = round(ex * scale + 2 * margin)
    unit = max(1.0, width_px / 900)
    font, small = _font(14 * unit), _font(11 * unit)
    img = Image.new("RGB", (width_px, height_px), PAPER)
    d = ImageDraw.Draw(img)

    def to_px(x: float, y: float) -> Tuple[float, float]:
        return margin + x * scale, margin + (ey - y) * scale

    polygons = {z.id: z.polygon for z in venue.zones}
    for zone in venue.zones:
        pts = [to_px(x, y) for x, y in zone.polygon]
        load = zone.initial_occupants / zone.max_capacity if zone.max_capacity else 0
        fill = (int(238 - 40 * min(load, 1)), int(243 - 25 * min(load, 1)), 252)
        d.polygon(pts, fill=fill)
        d.line(pts + [pts[0]], fill=INK, width=max(3, round(4 * unit)), joint="curve")
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        _label(d, (cx, cy - 8 * unit), zone.name, font, INK)
        _label(d, (cx, cy + 10 * unit), f"{zone.id}  {zone.initial_occupants}/{zone.max_capacity}", small, (90, 96, 104))
    for door in venue.doors:
        axis = _axis_at([polygons[z] for z in door.zones], door.position)
        a, b = (to_px(*p) for p in _tick(door.position, door.width, axis))
        free = door.planner_can_open and door.default_state == "closed"
        colour = FREE_DOOR if free else FIRE_DOOR if door.kind == "fire_door" else DOOR
        d.line([a, b], fill=colour, width=max(6, round(8 * unit)))
        _label(d, _beside(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), axis, 13 * unit), door.id, small, colour)
    for exit_ in venue.exits:
        axis = _axis_at([polygons[exit_.zone]], exit_.position)
        a, b = (to_px(*p) for p in _tick(exit_.position, exit_.width, axis))
        d.line([a, b], fill=EXIT_C, width=max(7, round(10 * unit)))
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        _label(d, _beside(mid, axis, 16 * unit), exit_.id, small, EXIT_C)
    # metre scale bar
    bar_m = 5 if ex >= 15 else 2 if ex >= 6 else 1
    y = height_px - 22
    d.line([margin, y, margin + bar_m * scale, y], fill=INK, width=3)
    d.line([margin, y - 6, margin, y + 6], fill=INK, width=2)
    d.line([margin + bar_m * scale, y - 6, margin + bar_m * scale, y + 6], fill=INK, width=2)
    d.text((margin + bar_m * scale + 10, y), f"{bar_m} m", font=small, fill=INK, anchor="lm")
    d.text((width_px - margin, y), f"{venue.venue_id}  {ex:g} x {ey:g} m  {venue.geometry_revision}", font=small,
           fill=(90, 96, 104), anchor="rm")
    return _png(img)
