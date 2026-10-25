"""ADA egress checks (2010 ADA Standards) on measured/estimated widths.

Each check reports pass, fail or cannot_measure. A range that straddles a
threshold is never rounded into a pass or a fail.

Wording: a pass or fail on a tape-measured width (basis ``anchor_measured``)
says "within measured range"; every other basis is the model's estimate and
says "within the model's estimated range (model-reported)".
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from .contracts import Door, Measure, VenueGraph, Zone

Status = Literal["pass", "fail", "cannot_measure"]

DOOR_MIN_M = 0.813  # 32 in, doorway up to 24 in deep
DOOR_DEEP_MIN_M = 0.914  # 36 in, doorway deeper than 24 in
ROUTE_MIN_M = 0.914  # 36 in
TURN_MIN_M = 1.524  # 60 in turning circle

_CITE = "2010 ADA Standards §"
_MEASURED = "within measured range"
_MODEL = "within the model's estimated range (model-reported)"


def _within(m: Measure) -> str:
    return _MEASURED if m.basis == "anchor_measured" else _MODEL

ALWAYS_CANNOT_MEASURE: list[tuple[str, str]] = [
    ("ADA-404.2.5", "Door thresholds cannot be measured from video"),
    ("ADA-404.2.7", "Door hardware cannot be measured from video"),
    ("ADA-404.2.9", "Door opening force cannot be measured from video"),
    ("ADA-405.2", "Ramp slope cannot be measured from video"),
    ("ADA-SIGNAGE", "Signage cannot be assessed from video"),
    (
        "IBC/NFPA-OCCUPANT-LOAD",
        "IBC/NFPA occupant load: copyrighted model code; we cite section "
        "numbers and published factors, not code text",
    ),
]


class RuleResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule_id: str
    element_id: str
    statement: str
    threshold_m: float
    measured: Measure | None
    status: Status
    reason: str | None
    citation: str


def _range_status(m: Measure, threshold: float) -> Status:
    if m.low_m >= threshold:
        return "pass"
    if m.high_m < threshold:
        return "fail"
    return "cannot_measure"


def _door_result(d: Door) -> RuleResult:
    m = d.clear_width
    reason: str | None = None
    if m.basis == "assumed":
        status: Status = "cannot_measure"
        reason = "basis assumed"
    else:
        # Doorway depth is not visible in video, so the stricter 36 in
        # threshold must be cleared to pass; the 32 in floor is needed to fail.
        if m.low_m >= DOOR_DEEP_MIN_M:
            status = "pass"
        elif m.high_m < DOOR_MIN_M:
            status = "fail"
        else:
            status = "cannot_measure"
            reason = "doorway depth unknown"
    lo, hi = m.low_m, m.high_m
    if status == "pass":
        stmt = f"{d.id} clear width {lo:.2f}-{hi:.2f} m meets ADA §404.2.3 {_within(m)}"
    elif status == "fail" and m.basis == "anchor_measured":
        stmt = (f"{d.id} clear width {lo:.2f}-{hi:.2f} m (tape-measured) is below the "
                "0.813 m (32 in) minimum in ADA §404.2.3")
    elif status == "fail":
        stmt = (f"{d.id} clear width {lo:.2f}-{hi:.2f} m is below the 0.813 m (32 in) minimum "
                f"in ADA §404.2.3 {_MODEL}")
    elif reason == "basis assumed":
        stmt = f"{d.id} clear width is an assumed value; ADA §404.2.3 cannot measure"
    else:
        stmt = (
            f"{d.id} clear width {lo:.2f}-{hi:.2f} m spans 0.813 m (32 in) to 0.914 m (36 in); "
            "doorway depth is not visible, so ADA §404.2.3 cannot measure"
        )
    return RuleResult(
        rule_id="ADA-404.2.3", element_id=d.id, statement=stmt,
        threshold_m=DOOR_DEEP_MIN_M, measured=m, status=status, reason=reason,
        citation=_CITE + "404.2.3",
    )


def _route_result(d: Door) -> RuleResult:
    m = d.clear_width
    reason: str | None = None
    if m.basis == "assumed":
        status: Status = "cannot_measure"
        reason = "basis assumed"
    else:
        status = _range_status(m, ROUTE_MIN_M)
    lo, hi = m.low_m, m.high_m
    if status == "pass":
        stmt = f"{d.id} route width {lo:.2f}-{hi:.2f} m meets ADA §403.5.1 (0.914 m) {_within(m)}"
    elif status == "fail" and m.basis == "anchor_measured":
        stmt = (f"{d.id} route width {lo:.2f}-{hi:.2f} m (tape-measured) is below the "
                "0.914 m (36 in) minimum in ADA §403.5.1")
    elif status == "fail":
        stmt = (f"{d.id} route width {lo:.2f}-{hi:.2f} m is below the 0.914 m (36 in) minimum "
                f"in ADA §403.5.1 {_MODEL}")
    else:
        stmt = f"{d.id} route width {lo:.2f}-{hi:.2f} m: ADA §403.5.1 cannot measure against 0.914 m"
    return RuleResult(
        rule_id="ADA-403.5.1", element_id=d.id, statement=stmt,
        threshold_m=ROUTE_MIN_M, measured=m, status=status, reason=reason,
        citation=_CITE + "403.5.1",
    )


def _turning_result(z: Zone) -> RuleResult:
    side = min(z.rect[2], z.rect[3])
    # Zone rects are always estimates, so use the same +/-0.20 band as other
    # non-anchor widths: low = 0.8 * min side, high = 1.2 * min side.
    m = Measure(low_m=side * 0.8, high_m=side * 1.2, basis="estimated")
    reason: str | None = None
    if z.furniture_seen:
        status: Status = "cannot_measure"
        reason = "furniture seen"
    else:
        status = _range_status(m, TURN_MIN_M)
    base = f"{z.id} room footprint only: smallest dimension {m.low_m:.2f}-{m.high_m:.2f} m"
    if status == "cannot_measure" and reason:
        stmt = f"{base}; furniture was seen, so the ADA §304.3.1 turning circle cannot be measured"
    elif status == "pass":
        stmt = f"{base} meets the 1.524 m (60 in) turning circle of ADA §304.3.1 {_MODEL}"
    elif status == "fail":
        stmt = f"{base} is below the 1.524 m (60 in) turning circle of ADA §304.3.1 {_MODEL}"
    else:
        stmt = f"{base} spans the 1.524 m (60 in) turning circle of ADA §304.3.1; cannot measure"
    return RuleResult(
        rule_id="ADA-304.3.1", element_id=z.id, statement=stmt,
        threshold_m=TURN_MIN_M, measured=m, status=status, reason=reason,
        citation=_CITE + "304.3.1",
    )


def evaluate_rules(graph: VenueGraph) -> list[RuleResult]:
    out: list[RuleResult] = []
    for d in graph.doors:
        if d.kind in ("door", "exit"):
            out.append(_door_result(d))
        elif d.kind == "opening":
            out.append(_route_result(d))
    for z in graph.zones:
        out.append(_turning_result(z))
    return out
