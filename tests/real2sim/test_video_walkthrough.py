"""Video walkthrough drafts: looks (room colours, furniture) through salvage, compiler, planner, upload and edits."""
import json
import subprocess
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.ai.real2sim.drafts import Real2SimError, Real2SimService
from backend.app.ai.real2sim.extract import DraftExtractor, room_inputs
from backend.app.ai.real2sim.routes import build_real2sim_router
from backend.app.ai.real2sim.schema import SourceImage, salvage_draft
from backend.app.ai.real2sim.video_source import detect_container, ffmpeg_exe, prepare_video, select_timestamps
from backend.app.hazard.door_planner import plan_doors
from backend.app.venues.compiler import compile_draft, with_furniture
from backend.app.venues.graph_checks import check_venue, errors_in
from backend.app.venues.model import get_venue
from backend.app.venues.schemas import DoorPlanRequest
from tests.real2sim.test_critique import FakeInteractions, fake_adapter, script
from tests.real2sim.test_drafts import png_bytes
from tests.real2sim.test_room_compiler import lobby

PLAN = SourceImage(1000, 1000, "0" * 64, "video/mp4")


def room(key, name, box, **look):
    return {"key": key, "name": name, "kind": "room", "box": box, "extra_boxes": [],
            "label_point": [(box[0] + box[2]) // 2, (box[1] + box[3]) // 2], **look}


def one_room_draft(**extra):
    return {
        "schema_version": "draft-1", "title": "Studio", "image_kind": "video_walkthrough",
        "scale": {"basis": "video_estimate", "a": [200, 100], "b": [200, 900], "metres": 6.0,
                  "evidence": "front door about 0.9 m"},
        "rooms": [room("STUDIO", "Studio", [200, 100, 800, 900], wall_color="#E9E2D2", floor_color="a87a4f",
                       floor_material="wood")],
        "doors": [],
        "exits": [{"key": "FRONT", "room": "STUDIO", "point": [800, 500], "kind": "door", "label": "",
                   "confidence": 0.9, "evidence": "front door"}],
        "furniture": [
            {"room": "STUDIO", "label": "Sofa", "category": "sofa", "point": [300, 300], "width_m": 2.0,
             "depth_m": 0.9, "height_m": 0.8, "yaw_deg": 0, "color": "#4d5a7a"},
            {"room": "STUDIO", "label": "Table", "category": "table", "point": [500, 600], "width_m": 1.2,
             "depth_m": 0.8, "height_m": 0.75, "yaw_deg": 370, "color": "brown"},
        ],
        **extra,
    }


def flat_draft():
    draft = one_room_draft()
    draft["rooms"] = [room("LIVING", "Living", [200, 100, 600, 600], floor_material="carpet"),
                      room("KITCHEN", "Kitchen", [200, 600, 600, 900], floor_color="#c9c3b6", floor_material="tile"),
                      room("HALL", "Hall", [600, 100, 800, 900])]
    draft["doors"] = [{"key": "D_LH", "between": ["LIVING", "HALL"], "point": [600, 350], "symbol": "opening",
                       "confidence": 0.9, "evidence": "walked through"},
                      {"key": "D_KH", "between": ["KITCHEN", "HALL"], "point": [600, 750], "symbol": "swing",
                       "confidence": 0.8, "evidence": "seen"}]
    draft["exits"] = [{"key": "FRONT", "room": "HALL", "point": [800, 200], "kind": "door", "label": "",
                       "confidence": 0.9, "evidence": "front door"}]
    draft["furniture"] = [{"room": "LIVING", "label": "Sofa", "category": "sofa", "point": [300, 300],
                           "width_m": 2.0, "depth_m": 0.9, "height_m": 0.8, "color": "#4d5a7a"},
                          {"room": "GARAGE", "label": "Car", "point": [300, 300], "width_m": 4.0, "depth_m": 2.0,
                           "height_m": 1.5}]
    return draft


def test_salvage_keeps_looks_and_repairs_or_drops_bad_ones():
    salvaged = salvage_draft(flat_draft())
    draft = salvaged.draft
    assert draft is not None and draft.image_kind == "video_walkthrough" and draft.scale.basis == "video_estimate"
    assert [p.label for p in draft.furniture] == ["Sofa"]
    assert any("Car" in reason and "GARAGE" in reason for reason in salvaged.dropped)
    single = salvage_draft(one_room_draft()).draft
    assert single.rooms[0].wall_color == "#e9e2d2" and single.rooms[0].floor_color == "#a87a4f"
    assert single.furniture[1].color == "" and single.furniture[1].yaw_deg == 10.0
    odd = one_room_draft()
    odd["rooms"][0]["floor_material"] = "lino"
    odd["rooms"][0]["wall_color"] = "beige"
    kept = salvage_draft(odd).draft
    assert kept.rooms[0].floor_material == "unknown" and kept.rooms[0].wall_color == ""


def test_one_room_video_compiles_checks_and_plans_with_a_hazard():
    draft = salvage_draft(one_room_draft()).draft
    result = compile_draft(draft, PLAN, venue_id="studio-abc123")
    venue = result.venue
    assert venue is not None, result.error
    assert len(venue.zones) == 1 and venue.doors == [] and len(venue.exits) == 1
    assert errors_in(check_venue(venue)) == []
    assert venue.extent[0] == pytest.approx(6.0, abs=0.2)
    look = venue.appearance.zones["STUDIO"]
    assert (look.wall_color, look.floor_color, look.floor_material) == ("#e9e2d2", "#a87a4f", "wood")
    assert [f.id for f in venue.appearance.furniture] == ["F1", "F2"]
    for piece in venue.appearance.furniture:
        assert 0 <= piece.position[0] <= venue.extent[0] and 0 <= piece.position[1] <= venue.extent[1]
    # Looks never reach the planner's inputs.
    assert "appearance" not in venue.planning_json()
    sofa = venue.appearance.furniture[0].position
    plan = plan_doors(venue, DoorPlanRequest(hazards=[{"id": "h1", "type": "FIRE", "source": "simulated",
                                                       "position": {"x": sofa[0], "y": sofa[1]}}]))
    assert plan.venue_id == "studio-abc123"
    assert plan.no_hazard_completed > 0


def test_multi_room_video_keeps_per_room_looks():
    venue = compile_draft(salvage_draft(flat_draft()).draft, PLAN, venue_id="flat-abc123").venue
    assert venue is not None and len(venue.zones) == 3 and len(venue.doors) == 2
    assert errors_in(check_venue(venue)) == []
    assert set(venue.appearance.zones) == {"LIVING", "KITCHEN"}
    assert venue.appearance.furniture[0].zone == "LIVING"


def test_drafts_without_looks_compile_exactly_as_before():
    plain = one_room_draft(furniture=[])
    plain["rooms"][0] = room("STUDIO", "Studio", [200, 100, 800, 900])
    venue = compile_draft(salvage_draft(plain).draft, PLAN, venue_id="studio-abc123").venue
    assert venue.appearance is None and "appearance" not in venue.to_json()


def test_with_furniture_replaces_pieces_and_changes_the_revision():
    venue = compile_draft(salvage_draft(one_room_draft()).draft, PLAN, venue_id="studio-abc123").venue
    moved = [{"zone": "STUDIO", "label": "Bed", "category": "bed", "position": [99.0, -5.0], "width": 2.0,
              "depth": 1.6, "height": 0.5, "yaw_deg": 90, "color": ""}]
    edited = with_furniture(venue, moved)
    assert [f.label for f in edited.appearance.furniture] == ["Bed"]
    assert edited.appearance.furniture[0].position == (venue.extent[0], 0.0)
    assert edited.appearance.zones == venue.appearance.zones
    assert edited.geometry_revision != venue.geometry_revision
    assert [z.model_dump() for z in edited.zones] == [z.model_dump() for z in venue.zones]
    with pytest.raises(ValueError):
        with_furniture(venue, [{**moved[0], "zone": "NOPE"}])


def make_video(path, seconds, size="64x48", rate=4):
    subprocess.run([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    f"testsrc=duration={seconds}:size={size}:rate={rate}", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    str(path)], check=True)
    return path


def test_video_source_measures_takes_roomlab_keyframes_and_refuses(tmp_path):
    original = make_video(tmp_path / "walk.mp4", 3)
    source, notes = prepare_video(original)
    assert source.mime_type == "video/mp4" and source.source_kind == "video"
    assert source.data == original.read_bytes() and notes[0].startswith("MP4 walkthrough, 3 s")
    # A frame ffmpeg cannot seek to (the last one of a tiny clip) is skipped, never invented.
    assert len(select_timestamps(3.0)) - 1 <= len(source.frames) <= len(select_timestamps(3.0))
    assert source.frames[0][0] == "frame-001" and source.frames[0][1] == 0.0
    assert all(jpeg[:3] == b"\xff\xd8\xff" for _, _, jpeg in source.frames)
    parts = room_inputs(source)
    assert "frame-001" in parts[0]["text"] and parts[1]["type"] == "video"
    assert parts[1]["processing"] == {"type": "static", "fps": 1.0}
    assert [p["type"] for p in parts[2:4]] == ["text", "image"] and parts[2]["text"].startswith("Frame ID: frame-001")
    assert len(select_timestamps(120.0)) == 48
    with pytest.raises(Real2SimError) as too_long:
        prepare_video(make_video(tmp_path / "long.mp4", 122, size="16x16", rate=1))
    assert too_long.value.code == "video_too_long"
    (tmp_path / "note.txt").write_bytes(b"not a video at all, just text")
    with pytest.raises(Real2SimError) as wrong:
        prepare_video(tmp_path / "note.txt")
    assert wrong.value.code == "unsupported_mime_type"
    assert detect_container(b"\x00\x00\x00\x14ftypqt  ") == "video/quicktime"
    assert detect_container(b"\x1a\x45\xdf\xa3....") == "video/webm"


def wait_ready(client, draft_id, timeout=20.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        view = client.get(f"/api/real2sim/drafts/{draft_id}").json()
        if view["status"] in ("ready", "failed"):
            return view
        time.sleep(0.02)
    raise AssertionError("draft did not finish")


def test_video_route_reads_the_roomlab_way_edits_furniture_and_accepts(tmp_path):
    fake = FakeInteractions(script(lobby()))
    adapter = fake_adapter(fake)
    service = Real2SimService(adapter, runtime_dir=tmp_path / "runtime", extractor=DraftExtractor(adapter, stream=True),
                              critique_rounds=0, ping_seconds=0.05, topdown_fn=lambda venue: png_bytes(9, 9))
    app = FastAPI()
    app.include_router(build_real2sim_router(adapter, lambda: False, service=service))
    body = make_video(tmp_path / "walk.mp4", 2).read_bytes()
    with TestClient(app) as client:
        created = client.post("/api/real2sim/drafts/video", params={"name": "Studio"}, content=body,
                              headers={"content-type": "video/mp4"})
        assert created.status_code == 200, created.text
        view = wait_ready(client, created.json()["draft_id"])
        assert view["status"] == "ready" and view["source"]["kind"] == "video"
        assert view["source"]["mime_type"] == "video/mp4" and view["accept_blockers"] == []
        call = fake.calls[0]
        assert call["input"][1]["type"] == "video" and "spatial layout estimator" in call["system_instruction"]
        assert call["generation_config"]["thinking_level"] == "low" and call["generation_config"]["max_output_tokens"] == 8192
        assert "floor_vertices" in json.dumps(call["response_format"]["schema"])
        assert view["room"]["name"] == "Reception lobby" and view["counts"] == {"rooms": 2, "doors": 1, "exits": 1}
        assert [c["key"] for c in view["controllable_door_candidates"]] == ["D1"]
        preview = view["compile"]["venue"]
        assert {f["label"] for f in preview["appearance"]["furniture"]} == {"Reception counter", "Potted plant"}
        assert view["overlay_available"] and view["topdown_available"]

        lobby_zone = next(z["id"] for z in preview["zones"] if z["name"] == "Reception")
        pieces = [{**preview["appearance"]["furniture"][0], "position": [1.0, 1.0]},
                  {"zone": lobby_zone, "label": "Plant", "category": "plant", "position": [5.0, 3.0], "width": 0.5,
                   "depth": 0.5, "height": 1.2}]
        stale = client.put(f"/api/real2sim/drafts/{view['draft_id']}/furniture",
                           json={"expected_revision": view["revision"] - 1, "furniture": pieces})
        assert stale.status_code == 409
        saved = client.put(f"/api/real2sim/drafts/{view['draft_id']}/furniture",
                           json={"expected_revision": view["revision"], "furniture": pieces})
        assert saved.status_code == 200, saved.text
        assert [f["label"] for f in saved.json()["furniture"]][1] == "Plant"
        bad = client.put(f"/api/real2sim/drafts/{view['draft_id']}/furniture",
                         json={"expected_revision": saved.json()["revision"],
                               "furniture": [{**pieces[1], "zone": "ATTIC"}]})
        assert bad.status_code == 422 and bad.json()["detail"]["code"] == "invalid_furniture"

        accepted = client.post(f"/api/real2sim/drafts/{view['draft_id']}/accept",
                               json={"expected_revision": saved.json()["revision"], "controllable_doors": ["D1"]})
        assert accepted.status_code == 200, accepted.text
        stored = get_venue(accepted.json()["venue_id"])
        assert [f.label for f in stored.appearance.furniture][1] == "Plant"
        assert stored.doors[0].planner_can_open and len(stored.zones) == 2
        assert {f.kind for f in stored.appearance.features} == {"glass", "window"}


def test_video_route_refuses_non_video_and_missing_key(tmp_path):
    adapter = fake_adapter(FakeInteractions())
    service = Real2SimService(adapter, runtime_dir=tmp_path / "runtime", extractor=DraftExtractor(adapter))
    app = FastAPI()
    app.include_router(build_real2sim_router(adapter, lambda: False, service=service))
    with TestClient(app) as client:
        wrong = client.post("/api/real2sim/drafts/video", content=png_bytes(), headers={"content-type": "video/mp4"})
        assert wrong.status_code == 415
        empty = client.post("/api/real2sim/drafts/video", content=b"")
        assert empty.status_code == 422
    unconfigured = FastAPI()
    plain = Real2SimService(fake_adapter(FakeInteractions()), runtime_dir=tmp_path / "rt2")
    plain.extractor.adapter.client = None
    unconfigured.include_router(build_real2sim_router(plain.adapter, lambda: False, service=plain))
    with TestClient(unconfigured) as client:
        assert client.post("/api/real2sim/drafts/video", content=b"x").status_code == 503
