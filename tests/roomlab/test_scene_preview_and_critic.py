"""Offline unit tests for deterministic BEV scene_preview rendering and multimodal agent_critic."""
from __future__ import annotations

import io
import json
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image

from backend.app.roomlab.agent_critic import critique_scene
from backend.app.roomlab.contracts import (
    CritiqueContext,
    CritiqueFrame,
    CritiqueResult,
    EvidenceFrame,
    FloorVoid,
    Opening,
    RoomObject,
    RoomSceneV1,
    SolveResult,
    Wall,
    geometry_hash,
)
from backend.app.roomlab.scene_preview import render_scene_preview
from backend.app.roomlab.validation import validate_scene
from backend.app.roomlab.video_extractor import MODEL_ID


def _build_test_scene() -> RoomSceneV1:
    floor = [[-4.0, -3.0], [4.0, -3.0], [4.0, 3.0], [-4.0, 3.0]]
    walls = [
        Wall(role="shell", id="wall-1", start=[-4.0, -3.0], end=[4.0, -3.0], height_m=3.0, thickness_m=0.15),
        Wall(role="shell", id="wall-2", start=[4.0, -3.0], end=[4.0, 3.0], height_m=3.0, thickness_m=0.15),
        Wall(role="shell", id="wall-3", start=[4.0, 3.0], end=[-4.0, 3.0], height_m=3.0, thickness_m=0.15),
        Wall(role="shell", id="wall-4", start=[-4.0, 3.0], end=[-4.0, -3.0], height_m=3.0, thickness_m=0.15),
        Wall(role="partition", id="wall-part-1", start=[0.5, -3.0], end=[0.5, 3.0], height_m=3.0, thickness_m=0.12),
        Wall(role="railing", id="wall-rail-1", start=[-2.0, -1.5], end=[-2.0, 1.5], height_m=1.05, thickness_m=0.08),
    ]
    voids = [
        FloorVoid(id="void-1", polygon=[[-3.5, -1.5], [-2.1, -1.5], [-2.1, 1.5], [-3.5, 1.5]]),
    ]
    openings = [
        Opening(id="door-part-1", wall_id="wall-part-1", kind="door", offset_m=2.0, width_m=1.2, height_m=2.2, sill_m=0.0),
    ]
    objects = [
        RoomObject(
            id="obj-counter-1",
            label="Reception Counter",
            category="counter",
            center=[2.2, 0.0],
            width_m=0.9,
            depth_m=2.4,
            height_m=1.1,
            yaw_deg=15.0,
            movable=False,
        ),
        RoomObject(
            id="obj-stool-1",
            label="Wooden Stool",
            category="stool",
            center=[1.1, -1.2],
            width_m=0.4,
            depth_m=0.4,
            height_m=0.48,
            yaw_deg=0.0,
            movable=True,
        ),
    ]
    frames = [
        EvidenceFrame(
            frame_id="media-test-frame-001",
            media_id="media-test",
            timestamp_s=0.5,
            url="/media/media-test/frame-001.jpg",
            relative_path="media-test/frame-001.jpg",
        ),
        EvidenceFrame(
            frame_id="media-test-frame-002",
            media_id="media-test",
            timestamp_s=2.0,
            url="/media/media-test/frame-002.jpg",
            relative_path="media-test/frame-002.jpg",
        ),
    ]
    return RoomSceneV1(
        scene_id="scene-preview-test",
        scene_revision=2,
        name="Preview & Critic Test Room",
        floor=floor,
        floor_voids=voids,
        walls=walls,
        openings=openings,
        objects=objects,
        evidence_frames=frames,
    )


def _build_test_context() -> CritiqueContext:
    scene = _build_test_scene()
    report = validate_scene(scene)
    bev_bytes = render_scene_preview(scene)
    ghash = geometry_hash(scene)
    ehash = "e" * 64
    buf = io.BytesIO()
    Image.new("RGB", (32, 24), (120, 140, 160)).save(buf, format="JPEG")
    jpeg_bytes = buf.getvalue()
    return CritiqueContext(
        scene=scene,
        validation=report,
        solve=None,
        geometry_hash=ghash,
        evidence_hash=ehash,
        bev_png=bev_bytes,
        frames=[
            CritiqueFrame(record=scene.evidence_frames[0], jpeg_bytes=jpeg_bytes),
            CritiqueFrame(record=scene.evidence_frames[1], jpeg_bytes=jpeg_bytes),
        ],
    )


def test_render_scene_preview_is_deterministic_and_checks_solve_hash() -> None:
    scene = _build_test_scene()
    png_a = render_scene_preview(scene)
    png_b = render_scene_preview(scene)
    assert png_a == png_b
    assert png_a.startswith(b"\x89PNG\r\n\x1a\n")

    with Image.open(io.BytesIO(png_a)) as img:
        assert img.size == (960, 760)

    ghash = geometry_hash(scene)
    matched_solve = SolveResult(
        status="ROBUST_PASS",
        scene_revision=scene.scene_revision,
        geometry_hash=ghash,
        path=[[-1.0, 0.0], [0.5, -0.4], [1.6, 0.0]],
        path_length_m=2.7,
        minimum_clearance_m=0.22,
        message="Pass",
        assumptions=[],
    )
    png_with_path = render_scene_preview(scene, matched_solve)
    assert png_with_path != png_a

    stale_solve = matched_solve.model_copy(update={"geometry_hash": "0" * 64})
    png_with_stale = render_scene_preview(scene, stale_solve)
    assert png_with_stale == png_a


@pytest.mark.asyncio
async def test_multimodal_critique_scene_valid_response_and_receipt_stamping() -> None:
    context = _build_test_context()
    captured_kwargs: dict[str, Any] = {}

    class FakeInteractions:
        async def create(self, **kwargs: Any) -> Any:
            captured_kwargs.update(kwargs)
            payload = {
                "summary": "Partition wall-part-1 and atrium void-1 align with keyframes; measure doorway door-part-1.",
                "findings": [
                    {
                        "kind": "needs_evidence",
                        "element_ids": ["wall-part-1", "door-part-1", "wall-part-1"],
                        "frame_ids": ["media-test-frame-001", "media-test-frame-001"],
                        "message": "Verify clear opening width of door-part-1 before moving wide carts.",
                        "measurement_request": "Measure clear width of door-part-1 in meters.",
                    },
                    {
                        "kind": "observation",
                        "element_ids": ["void-1", "obj-counter-1"],
                        "frame_ids": ["media-test-frame-002"],
                        "message": "Atrium cutout void-1 is separated from reception counter by partition.",
                    },
                ],
            }
            return SimpleNamespace(
                id="inter-critic-1",
                status="completed",
                model=MODEL_ID,
                errors=None,
                output_text=json.dumps(payload),
            )

    fake_client = SimpleNamespace(aio=SimpleNamespace(interactions=FakeInteractions()))
    res = await critique_scene(context, api_key="fake-key-123", client=fake_client)
    assert isinstance(res, CritiqueResult)
    assert res.scene_id == context.scene.scene_id
    assert res.scene_revision == context.scene.scene_revision
    assert res.geometry_hash == context.geometry_hash
    assert res.evidence_hash == context.evidence_hash
    assert res.reviewed_frame_ids == ["media-test-frame-001", "media-test-frame-002"]
    assert len(res.findings) == 2

    f0 = res.findings[0]
    assert f0.kind == "needs_evidence"
    assert f0.element_ids == ["wall-part-1", "door-part-1"]
    assert f0.frame_ids == ["media-test-frame-001"]
    assert f0.measurement_request == "Measure clear width of door-part-1 in meters."

    input_parts = captured_kwargs["input"]
    assert any(p.get("type") == "image" and p.get("mime_type") == "image/png" for p in input_parts)
    assert sum(1 for p in input_parts if p.get("type") == "image" and p.get("mime_type") == "image/jpeg") == 2


@pytest.mark.asyncio
async def test_multimodal_critique_rejects_unknown_element_or_frame_and_missing_frame() -> None:
    context = _build_test_context()

    def make_client_with_output(text: str) -> Any:
        class FakeInteractions:
            async def create(self, **kwargs: Any) -> Any:
                return SimpleNamespace(
                    id="inter-critic-err",
                    status="completed",
                    model=MODEL_ID,
                    errors=None,
                    output_text=text,
                )

        return SimpleNamespace(aio=SimpleNamespace(interactions=FakeInteractions()))

    # 1. Unknown element ID
    unknown_el_json = json.dumps(
        {
            "summary": "Summary",
            "findings": [
                {
                    "kind": "observation",
                    "element_ids": ["wall-part-1", "hallucinated-wall-99"],
                    "frame_ids": ["media-test-frame-001"],
                    "message": "Bad element reference.",
                }
            ],
        }
    )
    with pytest.raises(RuntimeError, match="unknown scene element citation"):
        await critique_scene(context, api_key="fake-key", client=make_client_with_output(unknown_el_json))

    # 2. Unknown frame ID
    unknown_fr_json = json.dumps(
        {
            "summary": "Summary",
            "findings": [
                {
                    "kind": "observation",
                    "element_ids": ["wall-part-1"],
                    "frame_ids": ["invented-frame-999"],
                    "message": "Bad frame reference.",
                }
            ],
        }
    )
    with pytest.raises(RuntimeError, match="unknown evidence frame citation"):
        await critique_scene(context, api_key="fake-key", client=make_client_with_output(unknown_fr_json))

    # 3. Missing frame citation (empty frame_ids)
    empty_fr_json = json.dumps(
        {
            "summary": "Summary",
            "findings": [
                {
                    "kind": "observation",
                    "element_ids": ["wall-part-1"],
                    "frame_ids": [],
                    "message": "No frame cited.",
                }
            ],
        }
    )
    with pytest.raises(RuntimeError, match="must cite at least one supplied source frame"):
        await critique_scene(context, api_key="fake-key", client=make_client_with_output(empty_fr_json))

    # 4. Malformed JSON output
    with pytest.raises(RuntimeError, match="malformed JSON"):
        await critique_scene(context, api_key="fake-key", client=make_client_with_output("{not-valid-json"))

    # 5. Bounded sanitized provider failure (never leaks secret key or raw payload)
    class FailingInteractions:
        async def create(self, **kwargs: Any) -> Any:
            raise RuntimeError("Upstream failure with secret-api-key-777 and raw request dump")

    failing_client = SimpleNamespace(aio=SimpleNamespace(interactions=FailingInteractions()))
    with pytest.raises(RuntimeError) as exc_info:
        await critique_scene(context, api_key="secret-api-key-777", client=failing_client)
    assert "secret-api-key-777" not in str(exc_info.value)
    assert "raw request dump" not in str(exc_info.value)
    assert "Gemini provider call failed (RuntimeError)." in str(exc_info.value)
