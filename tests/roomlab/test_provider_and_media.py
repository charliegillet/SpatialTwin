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
from backend.app.roomlab.contracts import EvidenceFrame, MediaRecord, RoomSceneV1
from backend.app.roomlab.media import process_media
from backend.app.roomlab.provider_schema import (
    ProviderRoomPayload,
    normalize_provider_payload,
    provider_response_json_schema,
)
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
        f"testsrc=duration={duration_s}:size=320x240:rate=10",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-y",
        str(out_file),
    ]
    subprocess.run(cmd, check=True, timeout=20)
    return out_file.read_bytes()


def test_process_media_valid_mp4_decodes_frames(tmp_path: pathlib.Path) -> None:
    mp4_bytes = _make_sample_mp4(tmp_path, duration_s=1.5)
    media_root = tmp_path / "media"
    record = process_media(mp4_bytes, "walkthrough_clip.mp4", "video/mp4", media_root)

    assert record.media_id.startswith("media-")
    assert record.mime_type == "video/mp4"
    assert 1.0 <= record.duration_s <= 2.5
    assert record.video_url == f"/media/{record.media_id}/source.mp4"
    assert 2 <= len(record.frames) <= 12

    for idx, frame in enumerate(record.frames, start=1):
        assert frame.frame_id == f"{record.media_id}-frame-{idx:03d}"
        assert frame.relative_path == f"{record.media_id}/frame-{idx:03d}.jpg"
        assert frame.url == f"/media/{record.media_id}/frame-{idx:03d}.jpg"
        frame_file = media_root / frame.relative_path
        assert frame_file.is_file()
        assert frame_file.stat().st_size > 100


def test_process_media_rejects_bad_container_and_long_video(tmp_path: pathlib.Path) -> None:
    media_root = tmp_path / "media"
    with pytest.raises(ValueError, match="Unsupported media format"):
        process_media(b"not a real video file at all 1234567890", "fake.mp4", "video/mp4", media_root)

    long_mp4 = _make_sample_mp4(tmp_path, duration_s=16.2)
    with pytest.raises(ValueError, match="exceeds the 15s maximum limit"):
        process_media(long_mp4, "too_long.mp4", "video/mp4", media_root)


def test_provider_schema_and_normalization_filters_unknown_frames() -> None:
    schema = provider_response_json_schema()
    assert schema["type"] == "object"
    assert "floor_vertices" in schema["properties"]

    raw_payload = {
        "name": "Test Studio Room",
        "wall_height_m": 2.8,
        "wall_thickness_m": 0.14,
        "floor_vertices": [
            {"x_m": -2.5, "z_m": -2.0},
            {"x_m": 2.5, "z_m": -2.0},
            {"x_m": 2.5, "z_m": 2.0},
            {"x_m": -2.5, "z_m": 2.0},
        ],
        "openings": [
            {
                "id": "door-main",
                "wall_id": "wall-1",
                "kind": "door",
                "offset_m": 1.2,
                "width_m": 0.9,
                "height_m": 2.1,
                "sill_m": 0.5,  # should be clamped to 0.0 for door
                "visibility": "observed",
                "evidence_frame_ids": ["media-1-frame-001", "invented-frame-999"],
                "note": "North entrance",
            }
        ],
        "objects": [
            {
                "id": "table-center",
                "label": "Work Table",
                "category": "table",
                "x_m": 0.0,
                "z_m": 0.2,
                "width_m": 1.6,
                "depth_m": 0.8,
                "height_m": 0.75,
                "yaw_deg": 15.0,
                "movable": True,
                "uncertainty_radius_m": 0.12,
                "visibility": "partial",
                "evidence_frame_ids": ["invented-frame-888"],
                "note": "Far edge partially occluded",
            }
        ],
        "notes": ["Scale uncalibrated."],
    }

    parsed = ProviderRoomPayload.model_validate(raw_payload)
    valid_ids = {"media-1-frame-001", "media-1-frame-002"}
    draft, warnings = normalize_provider_payload(
        parsed,
        valid_ids,
        ["media-1-frame-001", "media-1-frame-002"],
    )
    assert len(draft.floor) == 4
    assert len(draft.walls) == 4
    assert draft.walls[0].provenance.evidence_frame_ids == []
    assert draft.openings[0].sill_m == 0.0
    assert draft.openings[0].provenance.evidence_frame_ids == ["media-1-frame-001"]
    assert draft.openings[0].provenance.visibility == "partial"  # downgraded because sill_m was clamped
    assert draft.objects[0].provenance.evidence_frame_ids == []
    assert "No element-specific frame evidence cited." in draft.objects[0].provenance.note
    assert any("Dropped unknown evidence frame IDs" in w for w in warnings)
    assert any("Clamped door 'door-main' sill_m" in w for w in warnings)


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
