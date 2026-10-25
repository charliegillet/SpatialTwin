"""Draw the synthetic Real2Sim fixtures (an evacuation-map style office and a hand-drawn style home).

    .venv/bin/python tools/gen_real2sim_fixtures.py

Writes venue/real2sim/<fixture_id>/{source.png, draft.json, meta.json} (Contract 2 in docs/plans/demo-v2-contracts.md).
Each draft.json is written *by construction* from the drawing coordinates, so it lines up with the picture exactly:
it is what a perfect reading would return. The images are labelled provenance "synthetic": drawn by this tool, not
a photograph and not a recorded Gemini run. Fixed seed, Pillow's bundled font, no network: byte-reproducible.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.ai.real2sim.schema import VenueDraftV1  # noqa: E402

OUT = ROOT / "venue" / "real2sim"
SEED = 20261024
PAPER, INK, GREEN, RED, BLUE = (250, 249, 244), (34, 38, 44), (0, 128, 72), (200, 38, 38), (40, 90, 170)


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.load_default(size=size)


class Canvas:
    """A Pillow canvas plus the pixel -> 0-1000 [y, x] conversion the draft needs."""

    def __init__(self, width: int, height: int):
        self.w, self.h = width, height
        self.img = Image.new("RGB", (width, height), PAPER)
        self.d = ImageDraw.Draw(self.img)

    def pt(self, x: float, y: float) -> List[int]:
        return [round(y / self.h * 1000), round(x / self.w * 1000)]

    def box(self, x0: float, y0: float, x1: float, y1: float) -> List[int]:
        return [round(y0 / self.h * 1000), round(x0 / self.w * 1000), round(y1 / self.h * 1000), round(x1 / self.w * 1000)]


# ---------------------------------------------------------------------------------------------------------------
# (a) evac-office: posted evacuation map
# ---------------------------------------------------------------------------------------------------------------
def running_man(d: ImageDraw.ImageDraw, cx: int, cy: int, s: int = 22) -> None:
    d.rectangle([cx - s, cy - s, cx + s, cy + s], fill=GREEN)
    white = (255, 255, 255)
    d.ellipse([cx - 3, cy - 14, cx + 5, cy - 6], fill=white)
    d.line([cx, cy - 5, cx - 4, cy + 4], fill=white, width=4)
    d.line([cx - 4, cy + 4, cx - 12, cy + 12], fill=white, width=4)
    d.line([cx - 4, cy + 4, cx + 6, cy + 12], fill=white, width=4)
    d.line([cx, cy - 4, cx + 10, cy - 8], fill=white, width=3)
    d.line([cx, cy - 4, cx - 8, cy - 8], fill=white, width=3)


def build_office() -> Tuple[Image.Image, dict, dict]:
    c = Canvas(1450, 1000)
    d = c.d
    # building 900 x 620 px; the scale bar below says 300 px = 10 m, so the building is 30 m x 20.7 m
    X0, X1, Y0, CY0, CY1, Y1 = 100, 1000, 140, 400, 470, 760
    rooms = {
        "OFFICE_A": ("Office A", "office", (100, Y0, 330, CY0)),
        "OFFICE_B": ("Office B", "office", (330, Y0, 560, CY0)),
        "MEETING": ("Meeting room", "room", (560, Y0, 790, CY0)),
        "WC": ("Toilets", "bathroom", (790, Y0, 900, CY0)),
        "STORE": ("Storage", "storage", (900, Y0, 1000, CY0)),
        "CORRIDOR": ("Corridor", "corridor", (100, CY0, 1000, CY1)),
        "LOBBY": ("Lobby", "lobby", (100, CY1, 420, Y1)),
        "OPEN": ("Open office", "office", (420, CY1, 780, Y1)),
        "KITCHEN": ("Kitchen", "kitchen", (780, CY1, 1000, Y1)),
    }
    fills = {"corridor": (236, 240, 236), "lobby": (240, 238, 226)}
    for key, (name, kind, (x0, y0, x1, y1)) in rooms.items():
        d.rectangle([x0, y0, x1, y1], fill=fills.get(kind, (255, 255, 252)))
    # doors: (key, between, x, y, orientation, width px, symbol)
    doors = [
        ("D_OA", ("OFFICE_A", "CORRIDOR"), 215, CY0, "h", 30, "swing"),
        ("D_OB", ("OFFICE_B", "CORRIDOR"), 445, CY0, "h", 30, "swing"),
        ("D_MT", ("MEETING", "CORRIDOR"), 675, CY0, "h", 36, "double"),
        ("D_WC", ("WC", "CORRIDOR"), 845, CY0, "h", 27, "swing"),
        ("D_ST", ("STORE", "CORRIDOR"), 950, CY0, "h", 27, "swing"),
        ("D_LC", ("LOBBY", "CORRIDOR"), 260, CY1, "h", 45, "fire_door"),
        ("D_OPC", ("OPEN", "CORRIDOR"), 600, CY1, "h", 45, "fire_door"),
        ("D_KC", ("KITCHEN", "CORRIDOR"), 890, CY1, "h", 30, "swing"),
        ("D_LO", ("LOBBY", "OPEN"), 420, 615, "v", 36, "opening"),
        ("D_OK", ("OPEN", "KITCHEN"), 780, 640, "v", 30, "swing"),
    ]
    exits = [
        ("X_MAIN", "LOBBY", 260, Y1, "h", 54, "door", "Main exit"),
        ("X_WEST", "CORRIDOR", X0, 435, "v", 36, "door", "West exit"),
        ("X_EAST", "CORRIDOR", X1, 435, "v", 36, "door", "East exit"),
        ("X_REAR", "OPEN", 600, Y1, "h", 45, "door", "Rear exit"),
    ]
    # walls: outline of every room, then paper-coloured gaps for doors/exits
    for key, (name, kind, (x0, y0, x1, y1)) in rooms.items():
        d.rectangle([x0, y0, x1, y1], outline=INK, width=6)
    for key, between, x, y, o, w, sym in doors:
        gap = [x - w // 2, y - 5, x + w // 2, y + 5] if o == "h" else [x - 5, y - w // 2, x + 5, y + w // 2]
        d.rectangle(gap, fill=PAPER)
        if sym in ("swing", "double"):
            r = w if sym == "swing" else w // 2
            if o == "h":
                d.arc([x - w // 2 - r, y - r, x - w // 2 + r, y + r], 270, 360, fill=INK, width=2)
            else:
                d.arc([x - r, y - w // 2 - r, x + r, y - w // 2 + r], 0, 90, fill=INK, width=2)
        if sym == "fire_door":
            d.rectangle(gap, outline=RED, width=2)
    for key, room, x, y, o, w, kind, label in exits:
        gap = [x - w // 2, y - 5, x + w // 2, y + 5] if o == "h" else [x - 5, y - w // 2, x + 5, y + w // 2]
        d.rectangle(gap, fill=PAPER)
        if o == "h":
            running_man(d, x, y + 40)
            d.text((x + 34, y + 40), "EXIT", font=font(22), fill=GREEN, anchor="lm")
            d.polygon([(x - 34, y + 40), (x - 24, y + 33), (x - 24, y + 47)], fill=GREEN)
        else:
            sx = -1 if x == X0 else 1
            running_man(d, x + sx * 52, y)
            d.text((x + sx * 52, y + 34), "EXIT", font=font(20), fill=GREEN, anchor="mm")
    for key, (name, kind, (x0, y0, x1, y1)) in rooms.items():
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        size = 15 if x1 - x0 < 130 else 22
        d.text((cx, cy - (24 if key == "OPEN" else 0)), name, font=font(size), fill=INK, anchor="mm")
    # you are here (in the lobby)
    yah = (330, 690)
    d.ellipse([yah[0] - 11, yah[1] - 11, yah[0] + 11, yah[1] + 11], fill=RED)
    d.ellipse([yah[0] - 20, yah[1] - 20, yah[0] + 20, yah[1] + 20], outline=RED, width=3)
    d.text((yah[0], yah[1] + 38), "YOU ARE HERE", font=font(18), fill=RED, anchor="mm")
    # title, scale bar, legend
    d.text((100, 60), "FIRE EVACUATION PLAN", font=font(46), fill=INK, anchor="lm")
    d.text((100, 104), "Level 1 - Meridian Offices (training drawing)", font=font(22), fill=(90, 96, 104), anchor="lm")
    bar_y, bar0, bar1 = 880, 760, 1060
    d.line([bar0, bar_y, bar1, bar_y], fill=INK, width=4)
    for i in range(3):
        x = bar0 + i * 150
        d.line([x, bar_y - 10, x, bar_y + 10], fill=INK, width=3)
    for i, label in enumerate(["0", "5", "10 m"]):
        d.text((bar0 + i * 150, bar_y + 28), label, font=font(20), fill=INK, anchor="mm")
    d.text((bar0, bar_y - 30), "Scale: 300 px = 10 m", font=font(18), fill=(90, 96, 104), anchor="lm")
    d.rectangle([1110, 140, 1390, 470], outline=INK, width=3, fill=(255, 255, 255))
    d.text((1130, 164), "LEGEND", font=font(24), fill=INK, anchor="lm")
    running_man(d, 1150, 214)
    d.text((1186, 214), "Emergency exit", font=font(20), fill=INK, anchor="lm")
    d.ellipse([1139, 263, 1161, 285], fill=RED)
    d.text((1186, 274), "You are here", font=font(20), fill=INK, anchor="lm")
    d.rectangle([1136, 322, 1164, 334], outline=RED, width=3)
    d.text((1186, 328), "Fire door", font=font(20), fill=INK, anchor="lm")
    d.line([1136, 382, 1164, 382], fill=INK, width=6)
    d.text((1186, 382), "Wall", font=font(20), fill=INK, anchor="lm")
    d.text((1130, 430), "In an emergency use the\nnearest exit; do not use lifts.", font=font(16), fill=(90, 96, 104),
           anchor="lm")

    draft = {
        "schema_version": "draft-1", "title": "Level 1 - Meridian Offices", "image_kind": "evacuation_map",
        "scale": {"basis": "scale_bar", "a": c.pt(bar0, bar_y), "b": c.pt(bar1, bar_y), "metres": 10.0,
                  "evidence": "Scale bar labelled 0, 5, 10 m under the plan."},
        "rooms": [{"key": key, "name": name, "kind": kind, "box": c.box(*box),
                   "label_point": c.pt((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)}
                  for key, (name, kind, box) in rooms.items()],
        "doors": [{"key": key, "between": list(between), "point": c.pt(x, y), "width_m": round(w / 30, 2),
                   "symbol": sym, "confidence": 0.95, "evidence": "door gap in the wall"}
                  for key, between, x, y, o, w, sym in doors],
        "exits": [{"key": key, "room": room, "point": c.pt(x, y), "width_m": round(w / 30, 2), "kind": kind,
                   "label": label, "confidence": 0.97, "evidence": "green EXIT sign"}
                  for key, room, x, y, o, w, kind, label in exits],
        "you_are_here": c.pt(*yah), "unreadable": [], "notes": "Synthetic evacuation map drawn by our tool.",
    }
    # source_kind "photo": a PNG standing in for a photo of a posted map (it is not a PDF).
    meta = {"fixture_id": "evac-office", "title": "Evacuation map: nine-room office floor", "source_kind": "photo",
            "provenance": "synthetic", "recorded_at": None, "interaction_id_hash": None,
            "note": "Synthetic PNG drawn by tools/gen_real2sim_fixtures.py, standing in for a photo of a posted map; "
                    "draft.json is what a perfect reading would return. Not a real photograph and not a recorded "
                    "Gemini run."}
    return c.img, draft, meta


# ---------------------------------------------------------------------------------------------------------------
# (b) sketch-home: hand-drawn style
# ---------------------------------------------------------------------------------------------------------------
def build_home() -> Tuple[Image.Image, dict, dict]:
    rng = random.Random(SEED)
    c = Canvas(1000, 800)
    d = c.d
    pen = (28, 38, 90)

    def wobble(x0, y0, x1, y1, width=4):
        steps = max(2, int(max(abs(x1 - x0), abs(y1 - y0)) // 40))
        pts = []
        for i in range(steps + 1):
            t = i / steps
            pts.append((x0 + (x1 - x0) * t + rng.uniform(-1.6, 1.6), y0 + (y1 - y0) * t + rng.uniform(-1.6, 1.6)))
        d.line(pts, fill=pen, width=width, joint="curve")
        # a second, lighter pass makes the pen overshoot like a real sketch
        d.line([(x0 + rng.uniform(-2, 2), y0 + rng.uniform(-2, 2)), (x1 + rng.uniform(-2, 2), y1 + rng.uniform(-2, 2))],
               fill=(70, 80, 130), width=1)

    def label(x, y, text, size=24, fill=pen, side=0):
        total = d.textlength(text, font=font(size))
        cx = x - total / 2 if side == 0 else (x - total if side < 0 else x)   # side -1: ends at x, +1: starts at x
        for ch in text:                        # per-character jitter reads as handwriting
            d.text((cx, y + rng.uniform(-2.5, 2.5)), ch, font=font(size), fill=fill, anchor="lm")
            cx += d.textlength(ch, font=font(size))

    X0, X1, Y0, HY0, HY1, Y1 = 120, 880, 140, 440, 520, 700
    rooms = {
        "LIVING": ("Living room", "room", (X0, Y0, 520, HY0)),
        "KITCHEN": ("Kitchen", "kitchen", (520, Y0, X1, HY0)),
        "HALL": ("Hall", "corridor", (X0, HY0, X1, HY1)),
        "BED_1": ("Bedroom 1", "bedroom", (X0, HY1, 420, Y1)),
        "BATH": ("Bathroom", "bathroom", (420, HY1, 600, Y1)),
        "BED_2": ("Bedroom 2", "bedroom", (600, HY1, X1, Y1)),
    }
    doors = [
        ("D_LH", ("LIVING", "HALL"), 300, HY0, "h", 55, "swing"),
        ("D_KH", ("KITCHEN", "HALL"), 700, HY0, "h", 55, "swing"),
        ("D_B1", ("BED_1", "HALL"), 270, HY1, "h", 52, "swing"),
        ("D_BA", ("BATH", "HALL"), 510, HY1, "h", 48, "swing"),
        ("D_B2", ("BED_2", "HALL"), 740, HY1, "h", 52, "swing"),
        ("D_LK", ("LIVING", "KITCHEN"), 520, 290, "v", 70, "opening"),
    ]
    exits = [
        ("X_FRONT", "LIVING", X0, 290, "v", 58, "door", "Front door"),
        ("X_BACK", "KITCHEN", X1, 290, "v", 58, "door", "Back door"),
        # Short label: the left margin is ~100 px, so "escape window" would be cut off at the image edge.
        ("X_WIN", "BED_1", X0, 610, "v", 40, "window", "Window"),
    ]
    def wall(x0, y0, x1, y1):
        """Draw a wall as pen strokes with gaps wherever a door or exit lies on it."""
        vertical = abs(x0 - x1) < 1
        lo, hi = (min(y0, y1), max(y0, y1)) if vertical else (min(x0, x1), max(x0, x1))
        cuts = []
        for x, y, o, w in [(t[2], t[3], t[4], t[5]) for t in [*doors, *exits]]:
            if vertical and o == "v" and abs(x - x0) < 1 and lo <= y <= hi:
                cuts.append((y - w / 2, y + w / 2))
            if not vertical and o == "h" and abs(y - y0) < 1 and lo <= x <= hi:
                cuts.append((x - w / 2, x + w / 2))
        cursor = lo
        for a, b in sorted(cuts):
            if a > cursor:
                wobble(*( (x0, cursor, x0, a) if vertical else (cursor, y0, a, y0) ))
            cursor = b
        if cursor < hi:
            wobble(*((x0, cursor, x0, hi) if vertical else (cursor, y0, hi, y0)))

    seen = set()
    for key, (name, kind, (x0, y0, x1, y1)) in rooms.items():
        for edge in ((x0, y0, x1, y0), (x1, y0, x1, y1), (x0, y1, x1, y1), (x0, y0, x0, y1)):
            if edge not in seen:
                seen.add(edge)
                wall(*edge)
    for key, between, x, y, o, w, sym in doors:
        if sym == "swing":                      # door leaf arc
            r = w
            if o == "h":
                d.arc([x - w // 2, y - r, x - w // 2 + 2 * r, y + r], 270, 360, fill=pen, width=2)
        elif sym == "opening":
            d.line([x, y - w // 2 - 4, x, y - w // 2 + 4], fill=pen, width=3)
            d.line([x, y + w // 2 - 4, x, y + w // 2 + 4], fill=pen, width=3)
    for key, room, x, y, o, w, kind, name in exits:
        if kind == "window":
            d.line([x - 7, y - w // 2, x - 7, y + w // 2], fill=pen, width=2)
            d.line([x + 7, y - w // 2, x + 7, y + w // 2], fill=pen, width=2)
        label(x - 22 if x == X0 else x + 22, y, name.lower(), 20, RED if kind == "door" else BLUE,
              side=-1 if x == X0 else 1)
    for key, (name, kind, (x0, y0, x1, y1)) in rooms.items():
        label((x0 + x1) / 2, (y0 + y1) / 2, name, 28)
    # dimension label under the house
    dy = 760
    wobble(X0, dy, X1, dy, 3)
    wobble(X0, dy - 12, X0, dy + 12, 3)
    wobble(X1, dy - 12, X1, dy + 12, 3)
    label((X0 + X1) / 2, dy + 28, "12 m", 28)
    label(500, 80, "our flat - rough sketch", 30)

    draft = {
        "schema_version": "draft-1", "title": "Home sketch", "image_kind": "sketch",
        "scale": {"basis": "dimension_label", "a": c.pt(X0, dy), "b": c.pt(X1, dy), "metres": 12.0,
                  "evidence": "Dimension line under the house labelled 12 m."},
        "rooms": [{"key": key, "name": name, "kind": kind, "box": c.box(*box),
                   "label_point": c.pt((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)}
                  for key, (name, kind, box) in rooms.items()],
        "doors": [{"key": key, "between": list(between), "point": c.pt(x, y), "width_m": None, "symbol": sym,
                   "confidence": 0.85, "evidence": "gap in the pen line"} for key, between, x, y, o, w, sym in doors],
        "exits": [{"key": key, "room": room, "point": c.pt(x, y), "width_m": None, "kind": kind, "label": name,
                   "confidence": 0.9, "evidence": "labelled in the margin"}
                  for key, room, x, y, o, w, kind, name in exits],
        "you_are_here": None, "unreadable": [], "notes": "Synthetic hand-drawn style sketch drawn by our tool.",
    }
    meta = {"fixture_id": "sketch-home", "title": "Hand-drawn home sketch: six rooms, window exit",
            "source_kind": "sketch", "provenance": "synthetic", "recorded_at": None, "interaction_id_hash": None,
            "note": "Synthetic image drawn by tools/gen_real2sim_fixtures.py with jittered pen lines; draft.json is "
                    "what a perfect reading would return. Not a photograph and not a recorded Gemini run."}
    return c.img, draft, meta


def write(fixture_id: str, built: Tuple[Image.Image, dict, dict], out: Path = OUT) -> None:
    image, draft, meta = built
    VenueDraftV1.model_validate(draft)          # the draft must satisfy the frozen contract
    folder = out / fixture_id
    folder.mkdir(parents=True, exist_ok=True)
    image.save(folder / "source.png", optimize=False)
    (folder / "draft.json").write_text(json.dumps(draft, indent=2) + "\n")
    (folder / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"wrote {folder}  ({image.width}x{image.height})")


def main(out: Path = OUT) -> None:
    write("evac-office", build_office(), out)
    write("sketch-home", build_home(), out)


if __name__ == "__main__":
    main()
