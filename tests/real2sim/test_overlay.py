"""Overlay and top-down renders: valid, bounded, deterministic PNGs for every input image mode."""
import io

import pytest
from PIL import Image

from backend.app.ai.real2sim.overlay import MAX_SIDE_PX, render_overlay, render_topdown
from backend.app.ai.real2sim.schema import SourceImage
from backend.app.venues.compiler import compile_draft
from backend.app.venues.model import load_building_v2
from tests.real2sim.test_compiler import build, compile_home, door, exit_, home_raw

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def image_bytes(mode="RGB", size=(1000, 1000), fmt="PNG"):
    colour = {"RGB": (240, 240, 230), "RGBA": (240, 240, 230, 128), "LA": (200, 128), "L": 200, "P": 3}[mode]
    out = io.BytesIO()
    Image.new(mode, size, colour).save(out, format=fmt)
    return out.getvalue()


def decode(png):
    assert png.startswith(PNG_MAGIC)
    return Image.open(io.BytesIO(png)).convert("RGB")


@pytest.mark.parametrize("mode", ["RGB", "RGBA", "LA", "P", "L"])
def test_overlay_handles_every_image_mode(mode):
    out = decode(render_overlay(image_bytes(mode), build(home_raw()), compile_home(building_width_m=12)))
    assert out.width == 1000 and out.height > 1000          # legend strip appended


def test_overlay_marks_rooms_doors_and_exits():
    result = compile_home(building_width_m=12)
    plain = Image.open(io.BytesIO(image_bytes())).convert("RGB")
    out = decode(render_overlay(image_bytes(), build(home_raw()), result)).crop((0, 0, 1000, 1000))
    assert out.tobytes() != plain.tobytes()
    # D1 (LIVING-HALL, at [y=500, x=300] on the 0-1000 grid) is drawn as a thick tick in the door blue
    near = [out.getpixel((300 + dx, 500)) for dx in range(-10, 11)]
    assert any(p[2] > 180 and p[0] < 80 for p in near)


def test_overlay_draws_dropped_elements_in_red():
    raw = home_raw()
    raw["doors"].append(door("DFAR", "LIVING", "BED_2", [400, 500]))
    draft = build(raw)
    result = compile_draft(draft, SourceImage(1000, 1000, ""), venue_id="home-test", building_width_m=12)
    assert result.report.dropped
    out = decode(render_overlay(image_bytes(), draft, result))
    assert any(p[0] > 190 and p[1] < 60 and p[2] < 60 for p in (out.getpixel((500 + d, 400)) for d in range(-9, 10)))


def test_overlay_without_a_venue_still_renders():
    draft = build({"rooms": home_raw()["rooms"], "doors": [], "exits": [exit_("X", "LIVING", [300, 100])]})
    result = compile_draft(draft, SourceImage(1000, 1000, ""), venue_id="home-test", building_width_m=12)
    result.venue, result.error = None, "no_exit_survived"
    assert decode(render_overlay(image_bytes(), draft, result)).width == 1000


def test_overlay_caps_huge_images_and_is_deterministic():
    result = compile_home(building_width_m=12)
    draft = build(home_raw())
    big = image_bytes(size=(5000, 3000))
    out = decode(render_overlay(big, draft, result))
    assert max(out.size) <= MAX_SIDE_PX + 200            # image capped, plus the legend strip
    assert render_overlay(big, draft, result) == render_overlay(big, draft, result)


def test_overlay_rejects_non_images():
    with pytest.raises(Exception):
        render_overlay(b"not an image", build(home_raw()), compile_home(building_width_m=12))


@pytest.mark.parametrize("width", [200, 800, 1200, 9000])
def test_topdown_is_bounded_and_deterministic(width):
    venue = compile_home(building_width_m=12).venue
    png = render_topdown(venue, width)
    img = decode(png)
    assert 300 <= img.width <= MAX_SIDE_PX and img.height <= MAX_SIDE_PX
    assert png == render_topdown(venue, width)


def test_topdown_renders_the_shipped_building():
    img = decode(render_topdown(load_building_v2()))
    assert img.width > 1000 and img.height > 600
