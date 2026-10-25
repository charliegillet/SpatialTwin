"""Offline unit tests for RoomLab media validation/decoding, provider schema normalization,
direct Argon video_extractor serialization, and agent_critic handling.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
from types import SimpleNamespace
from typing import Any

import imageio_ffmpeg
import pytest

from backend.app.roomlab.agent_critic import critique_scene
from backend.app.roomlab.contracts import RoomSceneV1
from backend.app.roomlab.media import process_media
from backend.app.roomlab.provider_schema import (
    ProviderRoomPayload,
    normalize_provider_payload,
    provider_response_json_schema,
)
from backend.app.roomlab.validation import validate_scene
from backend.app.roomlab.video_extractor import MODEL_ID, propose_room


def _make_sample_mp4(tmp_path: pathlib.Path, duration_s: float = 1.6) -> bytes:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    out_file = tmp_path / "sample.mp4"
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"testsrc=duration={duration_s}:size=320x240:rate=5",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-y",
        str(out_file),
    ]
    subprocess.run(cmd, check=True, timeout=30)
    return out_file.read_bytes()


def test_process_media_valid_mp4_decodes_frames(tmp_path: pathlib.Path) -> None:
    mp4_bytes = _make_sample_mp4(tmp_path, duration_s=1.5)
    media_root = tmp_path / "media"
    record = process_media(mp4_bytes, "walkthrough_clip.mp4", "video/mp4", media_root)

    assert record.media_id.startswith("media-")
    assert record.mime_type == "video/mp4"
    assert 1.0 <= record.duration_s <= 2.5
    assert record.video_url == f"/media/{record.media_id}/source.mp4"
    assert 2 <= len(record.frames) <= 48

    for idx, frame in enumerate(record.frames, start=1):
        assert frame.frame_id == f"{record.media_id}-frame-{idx:03d}"
        assert frame.relative_path == f"{record.media_id}/frame-{idx:03d}.jpg"
        assert frame.url == f"/media/{record.media_id}/frame-{idx:03d}.jpg"
        frame_file = media_root / frame.relative_path
        assert frame_file.is_file()
        assert frame_file.stat().st_size > 100


def test_process_media_rejects_bad_container_and_long_video(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    media_root = tmp_path / "media"
    with pytest.raises(ValueError, match="Unsupported media format"):
        process_media(b"not a real video file at all 1234567890", "fake.mp4", "video/mp4", media_root)

    monkeypatch.setattr("backend.app.roomlab.media._probe_and_measure_duration", lambda *_a, **_kw: (_ for _ in ()).throw(ValueError("Video duration (125.00s) exceeds the 120s maximum limit.")))
    sample_mp4 = _make_sample_mp4(tmp_path, duration_s=1.0)
    with pytest.raises(ValueError, match="exceeds the 120s maximum limit"):
        process_media(sample_mp4, "too_long.mp4", "video/mp4", media_root)


def test_provider_schema_and_normalization_supports_voids_partitions_railings_and_stairs() -> None:
    schema = provider_response_json_schema()
    assert schema["type"] == "object"
    assert "floor_vertices" in schema["properties"]
    assert "floor_voids" in schema["properties"]
    assert "interior_walls" in schema["properties"]

    raw_payload = {
        "name": "Mezzanine & Partitioned Lounge",
        "wall_height_m": 3.4,
        "wall_thickness_m": 0.16,
        "floor_vertices": [
            {"x_m": -4.0, "z_m": -8.0},
            {"x_m": 5.0, "z_m": -8.0},
            {"x_m": 5.0, "z_m": 8.0},
            {"x_m": -4.0, "z_m": 8.0},
        ],
        "floor_voids": [
            {
                "id": "void-atrium",
                "vertices": [
                    {"x_m": -3.5, "z_m": -6.0},
                    {"x_m": -1.5, "z_m": -6.0},
                    {"x_m": -1.5, "z_m": 6.0},
                    {"x_m": -3.5, "z_m": 6.0},
                ],
                "visibility": "observed",
                "evidence_frame_ids": ["media-1-frame-001"],
                "note": "Central atrium drop-off",
            }
        ],
        "interior_walls": [
            {
                "id": "wall-glass-partition",
                "role": "partition",
                "start_x_m": 0.5,
                "start_z_m": -8.0,
                "end_x_m": 0.5,
                "end_z_m": 8.0,
                "height_m": 3.4,
                "thickness_m": 0.12,
                "visibility": "observed",
                "evidence_frame_ids": ["media-1-frame-002"],
                "note": "Glass storefront partition at x=0.5m",
            },
            {
                "id": "wall-atrium-railing",
                "role": "railing",
                "start_x_m": -1.4,
                "start_z_m": -6.0,
                "end_x_m": -1.4,
                "end_z_m": 6.0,
                "height_m": 1.05,
                "thickness_m": 0.08,
                "visibility": "observed",
                "evidence_frame_ids": ["media-1-frame-001"],
                "note": "Balustrade railing along atrium void",
            },
        ],
        "openings": [
            {
                "id": "door-glass-entry",
                "wall_id": "wall-glass-partition",
                "kind": "door",
                "offset_m": 6.5,
                "width_m": 2.0,
                "height_m": 2.4,
                "sill_m": 0.4,  # clamped to 0.0 for door
                "visibility": "observed",
                "evidence_frame_ids": ["media-1-frame-002", "invented-frame-999"],
                "note": "Double glass entry doors on interior partition",
            }
        ],
        "objects": [
            {
                "id": "table-center",
                "label": "Reception Counter",
                "category": "counter",
                "x_m": 2.4,
                "z_m": 0.0,
                "width_m": 1.0,
                "depth_m": 3.2,
                "height_m": 1.05,
                "yaw_deg": 0.0,
                "movable": True,
                "uncertainty_radius_m": 0.12,
                "visibility": "partial",
                "evidence_frame_ids": ["invented-frame-888"],
                "note": "Reception desk behind glass partition",
            },
            {
                "id": "stairs-east",
                "label": "Interior Staircase",
                "category": "stairs",
                "x_m": 3.5,
                "z_m": 4.5,
                "width_m": 2.0,
                "depth_m": 1.4,
                "height_m": 2.8,
                "yaw_deg": 0.0,
                "movable": True,  # forced to False by normalizer
                "uncertainty_radius_m": 0.2,
                "visibility": "observed",
                "evidence_frame_ids": ["media-1-frame-002"],
                "note": "Interior stairs",
            },
            {
                "id": "plant-near-stairs",
                "label": "Potted Plant (Near Stairs)",
                "category": "plant",
                "x_m": 2.2,
                "z_m": 4.2,
                "width_m": 0.7,
                "depth_m": 0.7,
                "height_m": 1.6,
                "yaw_deg": 0.0,
                "movable": True,
                "uncertainty_radius_m": 0.15,
                "visibility": "observed",
                "evidence_frame_ids": ["media-1-frame-002"],
                "note": "Plant near stairs",
            },
        ],
        "notes": ["Scale uncalibrated."],
    }

    parsed = ProviderRoomPayload.model_validate(raw_payload)
    valid_ids = {"media-1-frame-001", "media-1-frame-002"}
    draft, warnings = normalize_provider_payload(parsed, valid_ids)

    assert len(draft.floor) == 4
    assert draft.topology_review_required is False
    assert len(draft.floor_voids) == 1
    assert draft.floor_voids[0].id == "void-atrium"
    assert len(draft.walls) == 6  # 4 shell + 1 partition + 1 railing
    assert [w.role for w in draft.walls].count("shell") == 4
    assert [w.role for w in draft.walls].count("partition") == 1
    assert [w.role for w in draft.walls].count("railing") == 1
    assert draft.walls[0].provenance.evidence_frame_ids == []
    assert draft.openings[0].wall_id == "wall-glass-partition"
    assert draft.openings[0].sill_m == 0.0
    assert draft.openings[0].provenance.evidence_frame_ids == ["media-1-frame-002"]
    assert draft.openings[0].provenance.visibility == "partial"
    assert draft.objects[0].provenance.evidence_frame_ids == []
    assert "No element-specific frame evidence cited." in draft.objects[0].provenance.note
    stairs_obj = next(o for o in draft.objects if o.id == "stairs-east")
    assert stairs_obj.movable is False
    assert "Fixed single-level obstruction placeholder" in stairs_obj.provenance.note
    plant_obj = next(o for o in draft.objects if o.id == "plant-near-stairs")
    assert plant_obj.movable is True
    assert "Fixed single-level obstruction placeholder" not in plant_obj.provenance.note
    assert any("Dropped unknown evidence frame IDs" in w for w in warnings)
    assert any("Clamped door 'door-glass-entry' sill_m" in w for w in warnings)

    scene = RoomSceneV1(
        scene_id="scene-test-void-partition",
        **draft.model_dump(),
        evidence_frames=[],
    )
    # Verify canonical geometry validation passes with 0 errors once evidence frames are populated
    report = validate_scene(scene)
    error_codes = [i.code for i in report.issues if i.severity == "error" and i.code != "missing_evidence"]
    assert error_codes == []


def test_topology_review_required_and_geometry_fit_disclosure() -> None:
    raw_payload = {
        "name": "Clipped Void & Shifted Object Room",
        "wall_height_m": 3.0,
        "wall_thickness_m": 0.14,
        "floor_vertices": [
            {"x_m": -4.0, "z_m": -4.0},
            {"x_m": 4.0, "z_m": -4.0},
            {"x_m": 4.0, "z_m": 4.0},
            {"x_m": -4.0, "z_m": 4.0},
        ],
        "floor_voids": [
            {
                "id": "void-edge-touch",
                "vertices": [
                    {"x_m": -4.0, "z_m": -2.0},  # touches outer boundary -> clipped by 0.08m inset
                    {"x_m": -2.0, "z_m": -2.0},
                    {"x_m": -2.0, "z_m": 2.0},
                    {"x_m": -4.0, "z_m": 2.0},
                ],
                "visibility": "observed",
                "evidence_frame_ids": ["media-1-frame-001"],
            }
        ],
        "interior_walls": [
            {
                "id": "wall-part-1",
                "role": "partition",
                "start_x_m": 0.0,
                "start_z_m": -4.0,
                "end_x_m": 0.0,
                "end_z_m": 4.0,
                "height_m": 3.0,
                "thickness_m": 0.14,
                "visibility": "observed",
                "evidence_frame_ids": ["media-1-frame-001"],
            }
        ],
        "openings": [],
        "objects": [
            {
                "id": "stool-on-wall",
                "label": "Stool",
                "category": "chair",
                "x_m": 0.02,  # overlaps wall-part-1 at x=0.0 -> auto-translated
                "z_m": 0.0,
                "width_m": 0.4,
                "depth_m": 0.4,
                "height_m": 0.45,
                "yaw_deg": 0.0,
                "movable": True,
                "uncertainty_radius_m": 0.1,
                "visibility": "observed",
                "evidence_frame_ids": ["media-1-frame-001"],
            }
        ],
        "notes": [],
    }
    parsed = ProviderRoomPayload.model_validate(raw_payload)
    draft, warnings = normalize_provider_payload(parsed, {"media-1-frame-001"})
    assert draft.topology_review_required is True
    assert any("TOPOLOGY REVIEW REQUIRED" in n for n in draft.notes)
    assert draft.floor_voids[0].provenance.source == "geometry_fit"
    assert draft.floor_voids[0].provenance.visibility == "partial"
    assert draft.objects[0].provenance.source == "geometry_fit"
    assert draft.objects[0].provenance.visibility == "partial"
    assert "Auto-translated from" in draft.objects[0].provenance.note
    assert any("Auto-translated object 'stool-on-wall'" in w for w in warnings)


@pytest.mark.asyncio
async def test_propose_room_live_serialization_and_error_handling(tmp_path: pathlib.Path) -> None:
    mp4_bytes = _make_sample_mp4(tmp_path, duration_s=1.0)
    media_root = tmp_path / "media"
    media = process_media(mp4_bytes, "clip.mp4", "video/mp4", media_root)

    captured_kwargs: dict[str, Any] = {}

    class FakeInteractions:
        async def create(self, **kwargs: Any) -> Any:
            captured_kwargs.update(kwargs)
            response_json = {
                "name": "Extracted Conference Room",
                "wall_height_m": 2.7,
                "wall_thickness_m": 0.12,
                "floor_vertices": [
                    {"x_m": -3.0, "z_m": -2.0},
                    {"x_m": 3.0, "z_m": -2.0},
                    {"x_m": 3.0, "z_m": 2.0},
                    {"x_m": -3.0, "z_m": 2.0},
                ],
                "floor_voids": [],
                "interior_walls": [],
                "openings": [
                    {
                        "id": "door-1",
                        "wall_id": "wall-1",
                        "kind": "door",
                        "offset_m": 1.0,
                        "width_m": 0.9,
                        "height_m": 2.1,
                        "sill_m": 0.0,
                        "visibility": "observed",
                        "evidence_frame_ids": [media.frames[0].frame_id],
                    }
                ],
                "objects": [
                    {
                        "id": "desk-1",
                        "label": "Conference Table",
                        "category": "table",
                        "x_m": 0.0,
                        "z_m": 0.0,
                        "width_m": 1.8,
                        "depth_m": 0.9,
                        "height_m": 0.75,
                        "yaw_deg": 0.0,
                        "movable": True,
                        "uncertainty_radius_m": 0.1,
                        "visibility": "observed",
                        "evidence_frame_ids": [media.frames[0].frame_id],
                    }
                ],
                "notes": ["Estimated draft from short walkthrough."],
            }
            return SimpleNamespace(
                id="inter-test-123",
                status="completed",
                model=MODEL_ID,
                errors=None,
                output_text=json.dumps(response_json),
            )

    fake_client = SimpleNamespace(
        aio=SimpleNamespace(interactions=FakeInteractions()),
    )

    result = await propose_room(
        media,
        media_root,
        api_key="test-fake-key-do-not-print",
        client=fake_client,
    )
    assert result.model == MODEL_ID
    assert result.provenance == "live"
    assert result.latency_ms > 0
    assert result.draft.name == "Extracted Conference Room"
    assert len(result.draft.walls) == 4
    assert len(result.draft.objects) == 1
    assert captured_kwargs["model"] == MODEL_ID
    assert captured_kwargs["response_format"]["mime_type"] == "application/json"
    assert any(part.get("type") == "video" for part in captured_kwargs["input"])
    assert any(part.get("type") == "image" for part in captured_kwargs["input"])


@pytest.mark.asyncio
async def test_critique_scene_sanitizes_provider_errors() -> None:
    scene = RoomSceneV1(
        scene_id="scene-1",
        name="Room 1",
        floor=[[-2.0, -2.0], [2.0, -2.0], [2.0, 2.0], [-2.0, 2.0]],
    )

    class FailingInteractions:
        async def create(self, **kwargs: Any) -> Any:
            raise RuntimeError("Upstream error with secret-token-xyz and raw payload")

    fake_client = SimpleNamespace(
        aio=SimpleNamespace(interactions=FailingInteractions()),
    )
    with pytest.raises(RuntimeError) as exc_info:
        await critique_scene(scene, api_key="secret-token-xyz", client=fake_client)
    assert "secret-token-xyz" not in str(exc_info.value)
    assert "raw payload" not in str(exc_info.value)
    assert "Gemini provider call failed (RuntimeError)." in str(exc_info.value)
