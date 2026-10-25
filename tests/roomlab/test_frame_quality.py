"""Unit tests for deterministic Pillow-based frame_quality scoring, near-duplicate
rejection, mandatory start/end preservation, and timeline coverage selection.
"""
from __future__ import annotations

import pathlib

import pytest
from PIL import Image, ImageDraw, ImageFilter

from backend.app.roomlab.contracts import EvidenceFrame, MediaRecord
from backend.app.roomlab.frame_quality import (
    dhash_hamming_distance,
    score_image_file,
    select_quality_frames,
)


def _save_checker_image(
    path: pathlib.Path,
    *,
    shift_x: int = 0,
    blur_radius: float = 0.0,
    brightness: int = 160,
) -> None:
    img = Image.new("RGB", (320, 240), (max(0, brightness - 50), max(0, brightness - 50), max(0, brightness - 50)))
    draw = ImageDraw.Draw(img)
    for y in range(0, 240, 24):
        for x in range(0, 320, 24):
            if ((x + shift_x) // 24 + y // 24) % 2 == 0:
                c = min(255, brightness + 45)
                draw.rectangle([x, y, x + 20, y + 20], fill=(c, c, c))
    # Draw distinct asymmetric landmark bars so dHash changes with shift_x
    bar_x = (40 + shift_x * 17) % 240
    draw.rectangle([bar_x, 20, bar_x + 35, 220], fill=(min(255, brightness + 70), 40, 40))
    if blur_radius > 0:
        img = img.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    img.save(path, format="JPEG", quality=90)


def test_score_image_file_distinguishes_sharp_blurred_and_dark_frames(tmp_path: pathlib.Path) -> None:
    sharp_path = tmp_path / "sharp.jpg"
    blur_path = tmp_path / "blur.jpg"
    dark_path = tmp_path / "dark.jpg"

    _save_checker_image(sharp_path, shift_x=1, blur_radius=0.0, brightness=150)
    _save_checker_image(blur_path, shift_x=1, blur_radius=6.0, brightness=150)
    _save_checker_image(dark_path, shift_x=1, blur_radius=0.0, brightness=8)

    m_sharp = score_image_file(sharp_path, "f-sharp", 1.0)
    m_blur = score_image_file(blur_path, "f-blur", 2.0)
    m_dark = score_image_file(dark_path, "f-dark", 3.0)

    assert m_sharp.sharpness_score > m_blur.sharpness_score * 2.5
    assert m_sharp.sharpness_score > 15.0
    assert m_blur.sharpness_score < 8.0
    assert m_dark.brightness_mean < 25.0
    assert len(m_sharp.dhash_hex) == 16


def test_select_quality_frames_rejects_near_duplicates_and_keeps_start_end_and_coverage(
    tmp_path: pathlib.Path,
) -> None:
    media_id = "media-qual-test"
    media_dir = tmp_path / media_id
    media_dir.mkdir(parents=True)

    frames: list[EvidenceFrame] = []
    # Create 12 frames across 11 seconds:
    # - Frame 1 (0.0s): sharp start
    # - Frame 2 (1.0s): exact duplicate of Frame 1 -> should be rejected as near_duplicate
    # - Frame 3 (2.0s): motion-blurred view -> should be rejected as motion_blur
    # - Frame 4..11 (3.0s..10.0s): distinct sharp viewpoints
    # - Frame 12 (11.0s): sharp end
    for idx in range(1, 13):
        fname = f"frame-{idx:03d}.jpg"
        fpath = media_dir / fname
        ts = float(idx - 1)
        if idx in (1, 2):
            _save_checker_image(fpath, shift_x=0, blur_radius=0.0, brightness=150)
        elif idx == 3:
            _save_checker_image(fpath, shift_x=2, blur_radius=8.0, brightness=150)
        else:
            _save_checker_image(fpath, shift_x=idx * 3, blur_radius=0.0, brightness=150)
        frames.append(
            EvidenceFrame(
                frame_id=f"{media_id}-frame-{idx:03d}",
                media_id=media_id,
                timestamp_s=ts,
                url=f"/media/{media_id}/{fname}",
                relative_path=f"{media_id}/{fname}",
            )
        )

    record = MediaRecord(
        media_id=media_id,
        filename="walkthrough.mp4",
        mime_type="video/mp4",
        duration_s=11.0,
        video_url=f"/media/{media_id}/source.mp4",
        frames=frames,
    )

    res = select_quality_frames(
        record,
        tmp_path,
        max_frames=6,
        duplicate_hamming_threshold=4,
        min_sharpness_score=8.0,
    )

    assert len(res.selected_frames) == 6
    assert res.selected_frame_ids[0] == f"{media_id}-frame-001"
    assert res.selected_frame_ids[-1] == f"{media_id}-frame-012"
    assert f"{media_id}-frame-002" in res.rejected_frame_ids
    assert res.rejected_frame_ids[f"{media_id}-frame-002"] == "near_duplicate"
    assert f"{media_id}-frame-003" in res.rejected_frame_ids
    assert res.rejected_frame_ids[f"{media_id}-frame-003"] == "motion_blur"
    assert res.duplicate_skipped_count >= 1
    assert res.low_sharpness_count >= 1
    assert res.coverage_ratio >= 0.7
    assert any("does not turn uncalibrated monocular video" in n for n in res.notes)


def test_select_quality_frames_rejects_unsafe_relative_path(tmp_path: pathlib.Path) -> None:
    bad_frame = EvidenceFrame(
        frame_id="bad-1",
        media_id="media-bad",
        timestamp_s=0.0,
        url="/media/../secret.jpg",
        relative_path="../secret.jpg",
    )
    record = MediaRecord(
        media_id="media-bad",
        filename="bad.mp4",
        mime_type="video/mp4",
        duration_s=1.0,
        video_url="/media/media-bad/source.mp4",
        frames=[bad_frame],
    )
    with pytest.raises(ValueError, match="Unsafe relative media path"):
        select_quality_frames(record, tmp_path)
