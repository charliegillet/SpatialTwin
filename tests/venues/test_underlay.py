"""Map underlay: the accepted venue's own source image, placed in venue metres, drawn only when it lines up.

Every image here is synthetic and generated in tmp_path; no runtime photo is ever read or copied by these tests.
"""
import hashlib
import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.ai.real2sim.schema import SourceImage
from backend.app.signs.guard import scoped_access
from backend.app.venues.compiler import compile_draft, image_frame
from backend.app.venues.registry import VenueRegistry
from backend.app.venues.underlay import ALIGN_TOL_M, build_underlay_router, misalignment_m, provenance_label
from tests.real2sim.test_compiler import build, home_raw, make, room, exit_

DRAFT_ID = "r2s-" + "ab" * 12
VENUE_ID = "home-underlay"


def synthetic_image(fmt="PNG", size=(1000, 1000), exif_orientation=None):
    image = Image.new("RGB", size, (236, 236, 228))
    for x in range(100, 900, 40):          # a few grey lines so the bytes are not a flat fill
        for y in range(size[1]):
            image.putpixel((x, y), (120, 120, 120))
    out = io.BytesIO()
    kwargs = {}
    if exif_orientation is not None:
        exif = Image.Exif()
        exif[0x0112] = exif_orientation
        kwargs["exif"] = exif
    image.save(out, format=fmt, **kwargs)
    return out.getvalue()


@pytest.fixture
def setup(tmp_path):
    """A registry with the home draft accepted as a venue and its synthetic source stored like real2sim stores it."""
    registry = VenueRegistry(str(tmp_path / "venues.sqlite3"))
    root = tmp_path / "real2sim"

    def accept(*, data=None, name="source.png", width_m=12.0, compile_width_m=None, draft=None, record_extra=None,
               size=(1000, 1000), venue_id=VENUE_ID):
        data = synthetic_image(size=size) if data is None else data
        draft = draft or build(home_raw())
        image = SourceImage(size[0], size[1], hashlib.sha256(data).hexdigest())
        result = compile_draft(draft, image, venue_id=venue_id,
                               building_width_m=width_m if compile_width_m is None else compile_width_m)
        assert result.venue is not None
        (root / DRAFT_ID).mkdir(parents=True, exist_ok=True)
        (root / DRAFT_ID / name).write_bytes(data)
        record = {"name": "Home", "source_kind": "photo", "draft_id": DRAFT_ID, "source_sha256": image.sha256,
                  "provenance": "live", "draft": draft.model_dump(mode="json"), "building_width_m": width_m,
                  **(record_extra or {})}
        registry.save_venue(result.venue, record)
        return result.venue, data

    app = FastAPI()
    app.include_router(build_underlay_router(lambda: registry, runtime_dir=root))
    return TestClient(app), accept, root


def test_corners_place_the_image_by_the_compilers_own_map(setup):
    client, accept, _ = setup
    venue, _ = accept()
    body = client.get(f"/api/venues/{VENUE_ID}/underlay").json()
    assert body["available"] is True and body["reason"] is None
    assert body["geometry_revision"] == venue.geometry_revision
    assert (body["width_px"], body["height_px"], body["mime_type"]) == (1000, 1000, "image/png")
    # Rooms span x 100-900 and y 100-900 px; 12 m over 800 px. The building's south-west corner (x 100, y 900 px) is
    # the venue origin, so the image's own corners sit 1.5 m outside it on every side.
    assert body["corners_m"] == [[-1.5, 13.5], [13.5, 13.5], [13.5, -1.5], [-1.5, -1.5]]
    assert body["image_url"].startswith(f"/api/venues/{VENUE_ID}/underlay.jpg?v=")
    assert body["provenance_label"] == "Source photo · read by Gemini 4 Argon"


def test_every_room_corner_lands_on_its_pixel(setup):
    """Bilinear through the four corners (what the scene does) maps each drawn box onto the stored polygon."""
    client, accept, _ = setup
    venue, _ = accept()
    tl, tr, br, bl = client.get(f"/api/venues/{VENUE_ID}/underlay").json()["corners_m"]

    def at(x_px, y_px):
        u, v = x_px / 1000, y_px / 1000
        return (tl[0] + (tr[0] - tl[0]) * u, tl[1] + (bl[1] - tl[1]) * v)

    zones = {zone.id: zone.polygon for zone in venue.zones}
    for spec in home_raw()["rooms"]:
        ymin, xmin, ymax, xmax = spec["box"]
        x0, y1 = at(xmin, ymin)
        x1, y0 = at(xmax, ymax)
        xs = [p[0] for p in zones[spec["key"]]]
        ys = [p[1] for p in zones[spec["key"]]]
        assert (min(xs), min(ys), max(xs), max(ys)) == pytest.approx((x0, y0, x1, y1), abs=1e-6)


def test_image_route_serves_the_stored_bytes_unaltered(setup):
    client, accept, _ = setup
    _, data = accept()
    url = client.get(f"/api/venues/{VENUE_ID}/underlay").json()["image_url"]
    response = client.get(url)
    assert response.status_code == 200
    assert response.content == data
    assert response.headers["content-type"] == "image/png"
    assert response.headers["etag"] == f'"{hashlib.sha256(data).hexdigest()}"'
    assert response.headers["x-content-type-options"] == "nosniff"


def test_a_jpeg_source_is_sent_as_a_jpeg(setup):
    client, accept, _ = setup
    _, data = accept(data=synthetic_image("JPEG"), name="source.jpg")
    assert client.get(f"/api/venues/{VENUE_ID}/underlay").json()["mime_type"] == "image/jpeg"
    response = client.get(f"/api/venues/{VENUE_ID}/underlay.jpg")
    assert response.headers["content-type"] == "image/jpeg" and response.content == data


def test_a_wide_image_keeps_metres_square(setup):
    client, accept, _ = setup
    accept(size=(2000, 1000))
    tl, tr, br, bl = client.get(f"/api/venues/{VENUE_ID}/underlay").json()["corners_m"]
    # 2000 x 1000 px at one scale: the image is twice as wide as it is tall in metres too.
    assert (tr[0] - tl[0]) == pytest.approx(2 * (tl[1] - bl[1]))
    assert tl[1] == tr[1] and bl[1] == br[1] and tl[0] == bl[0] and tr[0] == br[0]


def test_builtin_venue_has_no_photo(setup):
    client, _, _ = setup
    body = client.get("/api/venues/building-v2/underlay").json()
    assert body["available"] is False and body["reason"] == "no_source_image"
    assert body["geometry_revision"] == "geom-building-v2"
    assert body["image_url"] is None and body["corners_m"] is None and body["provenance_label"] is None
    response = client.get("/api/venues/building-v2/underlay.jpg")
    assert response.status_code == 404 and response.json()["detail"] == {"code": "underlay_unavailable"}


def test_unknown_venue_is_404(setup):
    client, _, _ = setup
    assert client.get("/api/venues/no-such-venue/underlay").json()["detail"] == {"code": "unknown_venue"}
    assert client.get("/api/venues/no-such-venue/underlay").status_code == 404
    assert client.get("/api/venues/BAD_ID!/underlay").status_code == 404
    response = client.get("/api/venues/no-such-venue/underlay.jpg")
    assert response.status_code == 404 and response.json()["detail"] == {"code": "underlay_unavailable"}


def test_a_changed_source_is_never_served(setup):
    client, accept, root = setup
    accept()
    (root / DRAFT_ID / "source.png").write_bytes(synthetic_image(size=(1000, 1000), fmt="PNG")[:-8] + b"tampered")
    body = client.get(f"/api/venues/{VENUE_ID}/underlay").json()
    assert body["available"] is False and body["reason"] == "source_changed"
    assert client.get(f"/api/venues/{VENUE_ID}/underlay.jpg").status_code == 404


def test_a_missing_source_is_unavailable(setup):
    client, accept, root = setup
    accept()
    (root / DRAFT_ID / "source.png").unlink()
    assert client.get(f"/api/venues/{VENUE_ID}/underlay").json()["reason"] == "source_missing"
    assert client.get(f"/api/venues/{VENUE_ID}/underlay.jpg").status_code == 404


def test_a_pdf_source_has_nothing_to_draw(setup):
    client, accept, _ = setup
    accept(record_extra={"source_kind": "pdf"})
    assert client.get(f"/api/venues/{VENUE_ID}/underlay").json()["reason"] == "pdf_source"


@pytest.mark.parametrize("draft_id", ["../../etc", "r2s-short", None, ""])
def test_a_record_cannot_point_outside_the_runtime_folder(setup, draft_id):
    client, accept, _ = setup
    accept(record_extra={"draft_id": draft_id})
    body = client.get(f"/api/venues/{VENUE_ID}/underlay").json()
    assert body["available"] is False and body["reason"] in ("invalid_record", "no_source_image")


def test_a_venue_built_at_another_scale_is_not_drawn(setup):
    """The record says 12 m but the stored venue was compiled at 18 m: the photo would not line up, so none."""
    client, accept, _ = setup
    accept(width_m=12.0, compile_width_m=18.0)
    body = client.get(f"/api/venues/{VENUE_ID}/underlay").json()
    assert body["available"] is False and body["reason"] == "underlay_misaligned"
    assert client.get(f"/api/venues/{VENUE_ID}/underlay.jpg").status_code == 404


def test_a_rotated_source_is_not_drawn(setup):
    client, accept, _ = setup
    accept(data=synthetic_image("JPEG", exif_orientation=6), name="source.jpg")
    assert client.get(f"/api/venues/{VENUE_ID}/underlay").json()["reason"] == "source_rotated"


def test_a_dropped_outer_box_does_not_hide_an_aligned_photo(setup):
    """An extra box that does not touch its room is dropped by the compiler; the photo still lines up room by room."""
    client, accept, _ = setup
    raw = home_raw()
    raw["rooms"][1] = room("KITCHEN", [100, 500, 500, 900], extra_boxes=[[100, 940, 200, 990]])
    draft = build(raw)
    accept(draft=draft)
    assert client.get(f"/api/venues/{VENUE_ID}/underlay").json()["available"] is True


def test_voids_frame_the_image_like_the_compiler(setup):
    """A void along the west edge frames the drawing; the rooms keep their offset and the corners account for it."""
    client, accept, _ = setup
    raw = home_raw()
    raw["rooms"].append(room("ATRIUM", [100, 20, 900, 100], "void"))
    venue, _ = accept(draft=build(raw))
    body = client.get(f"/api/venues/{VENUE_ID}/underlay").json()
    assert body["available"] is True
    tl = body["corners_m"][0]
    # Frame origin is now x = 20 px (the void's west edge); 12 m over 880 px.
    assert tl[0] == pytest.approx(-20 * 12 / 880, abs=1e-3)
    assert min(p[0] for zone in venue.zones for p in zone.polygon) > 0


def test_image_frame_uses_the_scale_compile_chose():
    draft = build(home_raw())
    image = SourceImage(1000, 1000, "0" * 64)
    for width in (None, 12.0, 40.0):
        frame = image_frame(draft, image, building_width_m=width)
        assert frame.metres_per_px == compile_draft(draft, image, venue_id="x-frame",
                                                    building_width_m=width).report.metres_per_px
    # With a drawn scale reference (300 px = 6 m) and no operator width.
    scaled = make(home_raw()["rooms"], [], [exit_("FRONT", "LIVING", [300, 100])],
                  scale={"basis": "scale_bar", "a": [950, 100], "b": [950, 400], "metres": 6.0})
    assert image_frame(scaled, image).metres_per_px == pytest.approx(6.0 / 300)


def test_image_frame_does_not_change_the_compile():
    draft = build(home_raw())
    image = SourceImage(1000, 1000, "0" * 64)
    before = compile_draft(draft, image, venue_id="home-test", building_width_m=12).venue.to_json()
    image_frame(draft, image, building_width_m=12)
    assert compile_draft(draft, image, venue_id="home-test", building_width_m=12).venue.to_json() == before


def test_misalignment_is_zero_for_the_reading_that_built_the_venue():
    draft = build(home_raw())
    image = SourceImage(1000, 1000, "0" * 64)
    venue = compile_draft(draft, image, venue_id="home-test", building_width_m=12).venue
    assert misalignment_m(venue, draft, image, 12.0) == 0
    assert misalignment_m(venue, draft, image, 12.6) > ALIGN_TOL_M


def test_provenance_labels_never_overclaim():
    assert provenance_label("live", "photo") == "Source photo · read by Gemini 4 Argon"
    assert provenance_label("live", "sketch") == "Source sketch · read by Gemini 4 Argon"
    assert "not live" in provenance_label("saved_run", "photo")
    synthetic = provenance_label("synthetic", "photo")
    assert "Synthetic" in synthetic and "not a photograph" in synthetic and "Gemini" not in synthetic
    assert provenance_label(None, None) == "Source image · provenance not recorded"


def test_phones_cannot_reach_the_underlay(monkeypatch):
    """Not in the phone allowlist: a sign cookie never opens these paths, and a remote peer is refused outright."""
    monkeypatch.delenv("SPATIALTWIN_API_TOKEN", raising=False)
    for path in (f"/api/venues/{VENUE_ID}/underlay", f"/api/venues/{VENUE_ID}/underlay.jpg"):
        assert scoped_access({"type": "http", "path": path, "method": "GET", "headers": []}) is None
    from backend.app import main
    remote = TestClient(main.app, client=("203.0.113.9", 4000))
    assert remote.get(f"/api/venues/{VENUE_ID}/underlay.jpg").status_code == 403
