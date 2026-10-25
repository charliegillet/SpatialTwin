"""Answer-key benchmark: scores an extracted VenueGraph against human-measured doors.

``score`` is pure. The CLI (``python -m walktwin.benchmark run``) needs a Gemini key and the
extract/loop/sfm lanes; those are imported lazily inside ``run_cli``.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from walktwin.contracts import Door, VenueGraph

_GROUP = {"door": "door", "opening": "door", "exit": "exit", "stair": "exit"}
ALL_MODES = ("static", "static_hifps", "agentic", "agentic_loop")


class KeyDoor(BaseModel):
    t_s: float = Field(ge=0)
    kind: Literal["door", "opening", "exit", "stair"]
    measured_width_m: float | None = Field(default=None, gt=0)


class AnswerKey(BaseModel):
    venue: str
    video_sha256: str
    source: Literal["tape", "roomplan"]
    doors: list[KeyDoor]


class BenchmarkScore(BaseModel):
    mode: str
    door_precision: float
    door_recall: float
    door_f1: float
    exit_recall: float
    width_mae_m: float | None = None
    final_illegal_crossings: int | None = None
    agentic_observed: bool | None = None
    matched: list[tuple[str, int]] = Field(default_factory=list)


def _div(n: float, d: float) -> float:
    return n / d if d else 0.0


def _distance(door: Door, t_s: float, tol: float) -> float | None:
    """Smallest |midpoint - t| over evidence intervals (widened by tol) containing t."""
    best: float | None = None
    for ev in door.evidence:
        if ev.start_s - tol <= t_s <= ev.end_s + tol:
            d = abs((ev.start_s + ev.end_s) / 2 - t_s)
            if best is None or d < best:
                best = d
    return best


def score(graph: VenueGraph, key: AnswerKey, tolerance_s: float = 2.0,
          mode: str = "unlabelled") -> BenchmarkScore:
    cands: list[tuple[float, str, int]] = []
    for door in graph.doors:
        for i, kd in enumerate(key.doors):
            if _GROUP[door.kind] != _GROUP[kd.kind]:
                continue
            d = _distance(door, kd.t_s, tolerance_s)
            if d is not None:
                cands.append((d, door.id, i))
    cands.sort()  # nearest midpoint, then door id, then key index
    used_doors: set[str] = set()
    used_keys: set[int] = set()
    matched: list[tuple[str, int]] = []
    for _, did, i in cands:
        if did in used_doors or i in used_keys:
            continue
        used_doors.add(did)
        used_keys.add(i)
        matched.append((did, i))

    n_match = len(matched)
    precision = _div(n_match, len(graph.doors))
    recall = _div(n_match, len(key.doors))
    f1 = _div(2 * precision * recall, precision + recall)
    key_exits = [i for i, k in enumerate(key.doors) if k.kind == "exit"]
    exit_recall = _div(sum(1 for i in key_exits if i in used_keys), len(key_exits))

    by_id = {d.id: d for d in graph.doors}
    errs = [
        abs((by_id[did].clear_width.low_m + by_id[did].clear_width.high_m) / 2
            - key.doors[i].measured_width_m)
        for did, i in matched
        if key.doors[i].measured_width_m is not None
    ]
    return BenchmarkScore(
        mode=mode, door_precision=precision, door_recall=recall, door_f1=f1, exit_recall=exit_recall,
        width_mae_m=sum(errs) / len(errs) if errs else None, matched=matched,
    )


# ---------------------------------------------------------------- CLI (live: pending key)

def mode_label(mode: str, agentic_observed: bool | None) -> str:
    if mode == "agentic" and agentic_observed is False:
        return "agentic (not observed)"
    return mode


def _validate_modes(raw: str) -> list[str]:
    modes = [m.strip() for m in raw.split(",") if m.strip()]
    if not modes:
        raise SystemExit("--modes is empty")
    bad = [m for m in modes if m not in ALL_MODES]
    if bad:
        raise SystemExit(f"unknown mode(s) {bad!r}; choose from {', '.join(ALL_MODES)}")
    return modes


def _geometry_summary(iterations: list[Any]) -> dict[str, Any]:
    last = iterations[-1] if iterations else None
    geo = getattr(last, "geometry", None) if last is not None else None
    if geo is None:
        return {"available": False, "reason": "no measured geometry on the final iteration",
                "final_illegal_crossings": None}
    return {"available": True, "reason": None,
            "final_illegal_crossings": len(geo.illegal_crossings)}


async def run_cli_async(args: argparse.Namespace) -> int:
    # Lazy imports: these modules are owned by other lanes.
    from walktwin import extract as extract_mod
    from walktwin import loop as loop_mod
    from walktwin import sfm as sfm_mod
    from walktwin.genai_client import make_client
    from walktwin.media import prepare_video

    modes = _validate_modes(args.modes)
    bench_dir = Path(args.venue)
    venue = bench_dir.name
    key = AnswerKey.model_validate_json((bench_dir / "answer_key.json").read_text())
    raw = Path(args.video) if args.video else bench_dir / "walkthrough.mp4"
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    work = out_root / "work" / venue
    video = prepare_video(raw, work)
    if video.sha256 != key.video_sha256:
        print(f"warning: prepared video sha256 {video.sha256} != key {key.video_sha256}",
              file=sys.stderr)

    client = make_client()
    receipts_dir = out_root / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    extractions: dict[str, Any] = {}
    out = out_root / f"{venue}.json"

    def save_receipt(name: str, receipt: Any) -> str | None:
        if receipt is None:
            return None
        path = receipts_dir / f"{venue}_{name}.json"
        data = receipt.model_dump(mode="json") if hasattr(receipt, "model_dump") else receipt
        path.write_text(json.dumps(data, indent=2))
        return str(path)

    def flush() -> None:
        out.write_text(json.dumps({"venue": venue, "source": key.source, "rows": rows}, indent=2))

    async def extraction_for(mode: str) -> Any:
        if mode not in extractions:
            extractions[mode] = await extract_mod.extract_venue(
                client, video, mode=mode, deadline_s=args.deadline_s)
        return extractions[mode]

    for mode in modes:
        base_mode = "agentic" if mode == "agentic_loop" else mode
        res = await extraction_for(base_mode)
        if res.graph is None:
            rows.append({"mode": mode, "score": None, "geometry": None, "receipt": None,
                         "error": f"extraction {res.status}: {res.error}"})
            print(f"{mode}: extraction {res.status} ({res.error}); not scored")
            flush()
            continue

        geometry: dict[str, Any] | None = None
        receipt_note: str | None = None
        if mode == "agentic_loop":
            sfm = sfm_mod.run_sfm(video, work / "sfm")
            alignment = None
            reason = None
            if sfm.status != "completed":
                reason = f"sfm {sfm.status}: {sfm.error}"
            else:
                try:
                    alignment = sfm_mod.fit_alignment(sfm, res.graph)
                except Exception as exc:  # noqa: BLE001 - recorded, not hidden
                    reason = f"alignment failed: {exc}"
            use_geo = alignment is not None
            graph, iterations = await loop_mod.refine_graph(
                client, res.graph, video, res, sfm=sfm if use_geo else None,
                alignment=alignment, base_url=args.base_url, deadline_s=args.deadline_s)
            geometry = _geometry_summary(iterations)
            if reason is not None:
                geometry = {"available": False, "reason": reason, "final_illegal_crossings": None}
            s = score(graph, key, args.tolerance_s, mode=mode)
            s = s.model_copy(update={
                "final_illegal_crossings": geometry["final_illegal_crossings"],
                "agentic_observed": res.agentic_observed})
            receipt_path = save_receipt("agentic_loop_base_extraction", res.receipt)
            receipt_note = "receipt of the agentic extraction the loop started from"
        else:
            s = score(res.graph, key, args.tolerance_s, mode=mode)
            s = s.model_copy(update={
                "agentic_observed": res.agentic_observed if mode == "agentic" else None})
            receipt_path = save_receipt(mode, res.receipt)
        label = mode_label(mode, s.agentic_observed)
        rows.append({"mode": mode, "score": s.model_copy(update={"mode": label}).model_dump(mode="json"),
                     "geometry": geometry, "receipt": receipt_path,
                     "receipt_note": receipt_note, "error": None})
        print(f"{label}: F1={s.door_f1:.2f} P={s.door_precision:.2f} R={s.door_recall:.2f}")
        flush()

    flush()
    print(f"wrote {out}")
    return 0


def run_cli(args: argparse.Namespace) -> int:
    return asyncio.run(run_cli_async(args))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="walktwin.benchmark")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run extraction modes and score against the answer key")
    r.add_argument("--venue", required=True, help="bench/<venue> directory")
    r.add_argument("--modes", default=",".join(ALL_MODES))
    r.add_argument("--video", help="raw video (default bench/<venue>/walkthrough.mp4)")
    r.add_argument("--out", default="runtime/bench")
    r.add_argument("--tolerance-s", type=float, default=2.0, dest="tolerance_s")
    r.add_argument("--deadline-s", type=float, default=900.0, dest="deadline_s")
    r.add_argument("--base-url", default="http://127.0.0.1:8000", dest="base_url")
    return run_cli(p.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
