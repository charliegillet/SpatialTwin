"""Deterministic Pillow-based frame quality scoring, perceptual deduplication, and
coverage-aware keyframe selection for SpatialTwin video walkthroughs.

Scores each decoded frame on edge-gradient sharpness (Laplacian/Sobel luma energy),
brightness mean, contrast std, and a 64-bit horizontal difference hash (dHash).
Selects up to max_frames (clamped to 2..96) across uniform timeline coverage buckets
while always preserving the start and end frames, rejecting near-duplicate stationary
views unless needed to prevent timeline gaps, and reporting explicit rejection reasons
without claiming that frame selection alone guarantees metric geometric accuracy.
"""
from __future__ import annotations

import math
import pathlib
from typing import Literal

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from backend.app.roomlab.contracts import EvidenceFrame, MediaRecord

RejectionReason = Literal[
    "motion_blur",
    "underexposed",
    "overexposed",
    "near_duplicate",
    "budget_subsampled",
]


class FrameQualityMetric(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    frame_id: str
    timestamp_s: float
    sharpness_score: float = Field(
        ge=0.0,
        le=100.0,
        description="Deterministic Pillow gradient energy normalized to 0..100.",
    )
    brightness_mean: float = Field(ge=0.0, le=255.0)
    contrast_std: float = Field(ge=0.0, le=255.0)
    dhash_hex: str = Field(
        min_length=16,
        max_length=16,
        description="64-bit horizontal difference hash encoded as 16-char lowercase hex.",
    )
    viewpoint_delta: float = Field(
        ge=0.0,
        le=1.0,
        description="Normalized Hamming distance (0..1) relative to previous kept frame.",
    )
    selected: bool = True
    rejected_reason: RejectionReason | None = None


class FrameSelectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    selected_frames: list[EvidenceFrame]
    selected_frame_ids: list[str]
    rejected_frame_ids: dict[str, RejectionReason]
    metrics: list[FrameQualityMetric]
    coverage_ratio: float = Field(ge=0.0, le=1.0)
    low_sharpness_count: int = Field(ge=0)
    duplicate_skipped_count: int = Field(ge=0)
    exposure_flagged_count: int = Field(ge=0)
    notes: list[str] = Field(default_factory=list)


def _safe_media_frame_path(media_root: pathlib.Path, rel_path: str) -> pathlib.Path:
    root = pathlib.Path(media_root).resolve()
    clean_rel = (rel_path or "").lstrip("/\\")
    if not clean_rel or ".." in pathlib.PurePath(clean_rel).parts:
        raise ValueError(f"Unsafe relative media path: {rel_path!r}")
    candidate = (root / clean_rel).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Media path escapes media_root: {rel_path!r}") from exc
    if not candidate.is_file():
        raise ValueError(f"Media frame file does not exist: {clean_rel}")
    return candidate


def compute_dhash_hex(gray_img: Image.Image) -> str:
    """Compute a 64-bit horizontal difference hash (9x8 grayscale grid) as 16-char hex."""
    small = gray_img.resize((9, 8), Image.Resampling.BILINEAR)
    pixels = list(small.tobytes())
    bits = 0
    for row in range(8):
        row_offset = row * 9
        for col in range(8):
            left = pixels[row_offset + col]
            right = pixels[row_offset + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return f"{bits:016x}"


def dhash_hamming_distance(hash_a: str, hash_b: str) -> int:
    """Return bit-level Hamming distance (0..64) between two 16-char hex dHashes."""
    val_a = int(hash_a, 16)
    val_b = int(hash_b, 16)
    return (val_a ^ val_b).bit_count()


def score_image_file(
    image_path: pathlib.Path,
    frame_id: str,
    timestamp_s: float,
) -> FrameQualityMetric:
    """Compute deterministic Pillow-only sharpness, exposure, contrast, and 64-bit dHash."""
    with Image.open(image_path) as img:
        gray = img.convert("L")
        dhash = compute_dhash_hex(gray)
        eval_w, eval_h = 160, 120
        resized = gray.resize((eval_w, eval_h), Image.Resampling.BILINEAR)
        px = list(resized.tobytes())

    n = len(px)
    if n == 0:
        raise ValueError(f"Decoded image '{frame_id}' has zero pixels.")

    mean_luma = sum(px) / float(n)
    var_luma = sum((v - mean_luma) ** 2 for v in px) / float(n)
    std_luma = math.sqrt(max(0.0, var_luma))

    # Compute mean absolute 2D Laplacian + Sobel gradient energy across interior pixels
    grad_sum = 0.0
    grad_count = 0
    for y in range(1, eval_h - 1):
        row = y * eval_w
        row_up = (y - 1) * eval_w
        row_dn = (y + 1) * eval_w
        for x in range(1, eval_w - 1):
            c = px[row + x]
            gx = abs(px[row + x + 1] - px[row + x - 1]) * 0.5
            gy = abs(px[row_dn + x] - px[row_up + x]) * 0.5
            lap = abs(4 * c - px[row + x - 1] - px[row + x + 1] - px[row_up + x] - px[row_dn + x])
            grad_sum += 0.5 * (gx + gy) + 0.5 * lap
            grad_count += 1

    raw_grad = grad_sum / float(max(1, grad_count))
    # Normalize raw gradient energy into a bounded [0.0, 100.0] sharpness score
    sharpness_score = round(min(100.0, max(0.0, raw_grad * 1.45)), 3)

    return FrameQualityMetric(
        frame_id=frame_id,
        timestamp_s=round(float(timestamp_s), 3),
        sharpness_score=sharpness_score,
        brightness_mean=round(mean_luma, 3),
        contrast_std=round(std_luma, 3),
        dhash_hex=dhash,
        viewpoint_delta=1.0,
        selected=True,
        rejected_reason=None,
    )


def _quality_composite(metric: FrameQualityMetric, min_sharpness: float) -> float:
    """Rank frames within a timeline bucket by sharpness + exposure balance."""
    exposure_penalty = 0.0
    if metric.brightness_mean < 28.0:
        exposure_penalty = (28.0 - metric.brightness_mean) * 0.8
    elif metric.brightness_mean > 232.0:
        exposure_penalty = (metric.brightness_mean - 232.0) * 0.8
    blur_penalty = max(0.0, (min_sharpness - metric.sharpness_score) * 2.5)
    contrast_bonus = min(12.0, metric.contrast_std * 0.18)
    return metric.sharpness_score + contrast_bonus - exposure_penalty - blur_penalty


def _classify_intrinsic_issue(
    metric: FrameQualityMetric,
    min_sharpness_score: float,
) -> RejectionReason | None:
    if metric.brightness_mean < 24.0:
        return "underexposed"
    if metric.brightness_mean > 236.0:
        return "overexposed"
    if metric.sharpness_score < min_sharpness_score:
        return "motion_blur"
    return None


def select_quality_frames(
    media: MediaRecord,
    media_root: pathlib.Path,
    *,
    max_frames: int = 96,
    duplicate_hamming_threshold: int = 5,
    min_sharpness_score: float = 6.0,
) -> FrameSelectionResult:
    """Select up to max_frames (clamped to 2..96) coverage-aware keyframes from media.frames.

    Guarantees:
    1. Always retains the first and last frames in media.frames (mandatory start/end timeline anchor).
    2. Rejects near-duplicate stationary views (64-bit dHash Hamming distance <= duplicate_hamming_threshold)
       unless retaining a frame is necessary to avoid a timeline coverage gap.
    3. Partitions the interior timeline into uniform coverage buckets and selects the sharpest,
       best-exposed frame in each bucket.
    4. Reports per-frame metrics and explicit rejection reasons ('motion_blur', 'underexposed',
       'overexposed', 'near_duplicate', 'budget_subsampled') plus epistemic disclosures.
    """
    if not media.frames:
        raise ValueError("MediaRecord contains no frames to evaluate.")

    bounded_max = max(2, min(96, int(max_frames)))
    root = pathlib.Path(media_root).resolve()

    ordered_frames = sorted(media.frames, key=lambda f: (f.timestamp_s, f.frame_id))
    raw_metrics: list[FrameQualityMetric] = []
    for frame in ordered_frames:
        fpath = _safe_media_frame_path(root, frame.relative_path)
        raw_metrics.append(score_image_file(fpath, frame.frame_id, frame.timestamp_s))

    total = len(ordered_frames)
    low_sharpness_count = sum(1 for m in raw_metrics if m.sharpness_score < min_sharpness_score)
    exposure_flagged_count = sum(
        1 for m in raw_metrics if m.brightness_mean < 24.0 or m.brightness_mean > 236.0
    )

    if total <= 2:
        final_metrics: list[FrameQualityMetric] = []
        for idx, m in enumerate(raw_metrics):
            delta = (
                1.0
                if idx == 0
                else round(dhash_hamming_distance(raw_metrics[idx - 1].dhash_hex, m.dhash_hex) / 64.0, 4)
            )
            final_metrics.append(m.model_copy(update={"viewpoint_delta": delta, "selected": True, "rejected_reason": None}))
        notes = [
            "Adaptive frame selection retains sharpest viewpoints but does not turn uncalibrated monocular video into surveyed metric geometry."
        ]
        return FrameSelectionResult(
            selected_frames=list(ordered_frames),
            selected_frame_ids=[f.frame_id for f in ordered_frames],
            rejected_frame_ids={},
            metrics=final_metrics,
            coverage_ratio=1.0,
            low_sharpness_count=low_sharpness_count,
            duplicate_skipped_count=0,
            exposure_flagged_count=exposure_flagged_count,
            notes=notes,
        )

    # Step 1: Identify near-duplicate interior frames relative to the most recent unique candidate,
    # while never allowing a timeline gap larger than max_gap_s without a candidate.
    span_s = max(0.001, ordered_frames[-1].timestamp_s - ordered_frames[0].timestamp_s)
    max_gap_s = max(3.5, span_s / float(max(2, min(bounded_max, total) - 1)) * 2.2)

    rejected_reasons: dict[int, RejectionReason] = {}
    candidate_indices: list[int] = [0]
    last_kept_idx = 0

    for idx in range(1, total - 1):
        m = raw_metrics[idx]
        prev_m = raw_metrics[last_kept_idx]
        hamming = dhash_hamming_distance(prev_m.dhash_hex, m.dhash_hex)
        dt = m.timestamp_s - prev_m.timestamp_s

        if hamming <= duplicate_hamming_threshold and dt < max_gap_s:
            # If the new frame is noticeably sharper than the previous stationary frame (and last_kept is not 0),
            # upgrade the kept representative to the sharper frame and mark the older one as near_duplicate/motion_blur.
            if (
                last_kept_idx != 0
                and _quality_composite(m, min_sharpness_score)
                > _quality_composite(prev_m, min_sharpness_score) + 1.5
            ):
                issue = _classify_intrinsic_issue(prev_m, min_sharpness_score) or "near_duplicate"
                rejected_reasons[last_kept_idx] = issue
                candidate_indices[-1] = idx
                last_kept_idx = idx
            else:
                rejected_reasons[idx] = "near_duplicate"
            continue

        # Also reject severely blurred/badly exposed frames if neighbors cover the timeline window
        intrinsic = _classify_intrinsic_issue(m, min_sharpness_score)
        next_dt = ordered_frames[min(total - 1, idx + 1)].timestamp_s - prev_m.timestamp_s
        if intrinsic is not None and next_dt <= max_gap_s:
            rejected_reasons[idx] = intrinsic
            continue

        candidate_indices.append(idx)
        last_kept_idx = idx

    # Always include the final frame as mandatory end anchor
    if candidate_indices[-1] != total - 1:
        # If the last interior candidate is a near-duplicate of the mandatory end frame, drop the interior duplicate
        if len(candidate_indices) > 1:
            last_cand = candidate_indices[-1]
            if (
                dhash_hamming_distance(raw_metrics[last_cand].dhash_hex, raw_metrics[-1].dhash_hex)
                <= duplicate_hamming_threshold
            ):
                candidate_indices.pop()
                rejected_reasons[last_cand] = "near_duplicate"
        candidate_indices.append(total - 1)

    # Ensure we have at least min(bounded_max, 2) frames; if aggressive blur/duplicate filtering left too few
    # and we have room, rescue the highest-scoring non-duplicate frames if needed.
    if len(candidate_indices) > bounded_max:
        # Partition interior candidates into (bounded_max - 2) uniform timeline buckets
        # and pick the highest-quality frame in each bucket.
        interior = candidate_indices[1:-1]
        target_interior = bounded_max - 2
        selected_set: set[int] = {0, total - 1}

        if target_interior > 0 and interior:
            t_start = ordered_frames[0].timestamp_s
            t_end = ordered_frames[-1].timestamp_s
            bucket_width = max(1e-6, (t_end - t_start) / float(target_interior))
            buckets: list[list[int]] = [[] for _ in range(target_interior)]
            for c_idx in interior:
                t_rel = max(0.0, ordered_frames[c_idx].timestamp_s - t_start)
                b_i = min(target_interior - 1, int(t_rel / bucket_width))
                buckets[b_i].append(c_idx)

            for b_list in buckets:
                if not b_list:
                    continue
                best_idx = max(
                    b_list,
                    key=lambda i: (_quality_composite(raw_metrics[i], min_sharpness_score), -i),
                )
                selected_set.add(best_idx)
                for other_idx in b_list:
                    if other_idx != best_idx:
                        rejected_reasons[other_idx] = (
                            _classify_intrinsic_issue(raw_metrics[other_idx], min_sharpness_score)
                            or "budget_subsampled"
                        )

            # If some buckets were empty and we still have budget, fill from remaining top-scoring interior candidates
            if len(selected_set) < bounded_max:
                remaining = [i for i in interior if i not in selected_set]
                remaining.sort(
                    key=lambda i: _quality_composite(raw_metrics[i], min_sharpness_score),
                    reverse=True,
                )
                for extra_idx in remaining[: bounded_max - len(selected_set)]:
                    selected_set.add(extra_idx)
                    rejected_reasons.pop(extra_idx, None)
        else:
            for c_idx in interior:
                rejected_reasons[c_idx] = (
                    _classify_intrinsic_issue(raw_metrics[c_idx], min_sharpness_score)
                    or "budget_subsampled"
                )

        final_indices = sorted(selected_set)
    else:
        final_indices = sorted(set(candidate_indices))

    selected_index_set = set(final_indices)
    final_metrics = []
    prev_selected_hash: str | None = None
    for idx, m in enumerate(raw_metrics):
        is_sel = idx in selected_index_set
        if is_sel:
            delta = (
                1.0
                if prev_selected_hash is None
                else round(dhash_hamming_distance(prev_selected_hash, m.dhash_hex) / 64.0, 4)
            )
            prev_selected_hash = m.dhash_hex
            final_metrics.append(
                m.model_copy(
                    update={
                        "viewpoint_delta": delta,
                        "selected": True,
                        "rejected_reason": None,
                    }
                )
            )
        else:
            reason = (
                rejected_reasons.get(idx)
                or _classify_intrinsic_issue(m, min_sharpness_score)
                or "budget_subsampled"
            )
            ref_hash = prev_selected_hash or raw_metrics[0].dhash_hex
            delta = round(dhash_hamming_distance(ref_hash, m.dhash_hex) / 64.0, 4)
            final_metrics.append(
                m.model_copy(
                    update={
                        "viewpoint_delta": delta,
                        "selected": False,
                        "rejected_reason": reason,
                    }
                )
            )

    selected_frames = [ordered_frames[i] for i in final_indices]
    selected_ids = [f.frame_id for f in selected_frames]
    rejected_map: dict[str, RejectionReason] = {
        m.frame_id: m.rejected_reason
        for m in final_metrics
        if not m.selected and m.rejected_reason is not None
    }
    duplicate_skipped_count = sum(1 for r in rejected_map.values() if r == "near_duplicate")

    # Compute timeline coverage ratio across 10 equal time bins
    num_bins = min(10, total)
    covered_bins = 0
    for b in range(num_bins):
        b0 = ordered_frames[0].timestamp_s + (span_s * b) / float(num_bins)
        b1 = ordered_frames[0].timestamp_s + (span_s * (b + 1)) / float(num_bins)
        if any(b0 - 0.5 <= f.timestamp_s <= b1 + 0.5 for f in selected_frames):
            covered_bins += 1
    coverage_ratio = round(covered_bins / float(max(1, num_bins)), 3)

    notes: list[str] = [
        f"Selected {len(selected_frames)}/{total} keyframes (start={selected_frames[0].timestamp_s:.2f}s, end={selected_frames[-1].timestamp_s:.2f}s, coverage={coverage_ratio * 100:.0f}%).",
        "Adaptive frame selection prioritizes sharp, non-duplicate viewpoints but does not turn uncalibrated monocular video into surveyed metric geometry.",
    ]
    if duplicate_skipped_count > 0:
        notes.append(
            f"Skipped {duplicate_skipped_count} near-duplicate stationary frame(s) to preserve viewpoint diversity."
        )
    if low_sharpness_count > 0:
        notes.append(
            f"Detected {low_sharpness_count} motion-blurred/low-sharpness frame(s); walk slowly and pause briefly at corners for higher fidelity."
        )
    if exposure_flagged_count > 0:
        notes.append(
            f"Detected {exposure_flagged_count} under/over-exposed frame(s); even indoor lighting improves boundary recognition."
        )

    return FrameSelectionResult(
        selected_frames=selected_frames,
        selected_frame_ids=selected_ids,
        rejected_frame_ids=rejected_map,
        metrics=final_metrics,
        coverage_ratio=coverage_ratio,
        low_sharpness_count=low_sharpness_count,
        duplicate_skipped_count=duplicate_skipped_count,
        exposure_flagged_count=exposure_flagged_count,
        notes=notes,
    )
