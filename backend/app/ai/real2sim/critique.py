"""Real2Sim critique: at most a bounded number of rounds in which Argon fixes its own reading.

A round runs only when the local graph checks report errors (or nothing could be compiled). It chains onto the
previous interaction (``previous_interaction_id``; the source image is already in that stored conversation), sends
the overlay of what the compiler built from the reading plus the typed issues, and asks for a full corrected
VenueDraftV1. The local rule decides, never the model: the correction is kept only if it compiles and the graph-check
errors strictly decrease (or stay equal while warnings decrease). Every round is recorded as
``{round, issues_before, issues_after, accepted, note}`` so the operator sees "round 1: 3 errors -> 0".

The overlay labels are ours; the source image's text stays untrusted scene content. Argon is told never to add a
door or exit just to clear an issue.
"""
from __future__ import annotations

import base64
import hashlib
import inspect
import json
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field

from backend.app.ai.grounding.adapter import GroundingAdapter
from backend.app.ai.real2sim.extract import (
    DEFAULT_THINKING_LEVEL,
    MEDIA_RESOLUTION,
    REAL2SIM_SYSTEM_INSTRUCTION,
    ExtractionResult,
    ThoughtSink,
    run_draft_interaction,
)
from backend.app.ai.real2sim.schema import CompileResult, VenueDraftV1
from backend.app.venues.graph_checks import GraphIssue

RECEIPT_KIND_CRITIQUE = "real2sim_critique"
DEFAULT_CRITIQUE_ROUNDS = 1
MAX_CRITIQUE_ROUNDS = 2
DEFAULT_CRITIQUE_DEADLINE_SECONDS = 90.0
MAX_ISSUES_SENT = 24

CRITIQUE_SYSTEM_INSTRUCTION = REAL2SIM_SYSTEM_INSTRUCTION + """

Critique round: earlier in this conversation you read the floor plan. A local compiler turned your reading into the
attached overlay (drawn by us: room outlines and names, door ticks, exit markers, the evidence points you gave, and
anything it could not place in red) and local graph checks found the listed issues. Look again at the original
image and return one full corrected VenueDraftV1 with the same schema. Fix only what the original image supports:
move a box onto the walls you see, put a door on the wall two rooms really share, join rooms through the opening
that is drawn. Never add a door or an exit only to clear an issue; if the image shows no opening, leave it out and
say so in unreadable. Keep keys stable for elements you do not change."""

IssueRecord = Dict[str, Any]


@dataclass
class Assessment:
    """A compiled reading and its graph-check issues; ``compile_error`` means no venue could be built."""
    result: CompileResult
    issues: List[GraphIssue] = field(default_factory=list)

    @property
    def compile_error(self) -> Optional[str]:
        return self.result.error if self.result.venue is None else None

    def counts(self) -> Dict[str, Any]:
        errors = sum(1 for issue in self.issues if issue.severity == "error")
        warnings = sum(1 for issue in self.issues if issue.severity == "warning")
        if self.compile_error is not None:
            errors += 1
        return {"errors": errors, "warnings": warnings, "compile_failed": self.compile_error is not None}

    def has_errors(self) -> bool:
        return self.counts()["errors"] > 0


Recompile = Callable[[VenueDraftV1], Union[Assessment, Awaitable[Assessment]]]

COMPILE_ERROR_HINTS = {
    "no_exit_survived": ("No exit was read. Return an exit only where the image marks one (EXIT text, a running-man "
                         "sign, an arrow leading outside, a door in an outside wall); otherwise keep exits empty."),
    "no_room_survived": "No room could be built from the boxes; check that every box follows walls you can see.",
}


class CritiqueRound(BaseModel):
    round: int
    issues_before: Dict[str, Any]
    issues_after: Optional[Dict[str, Any]] = None
    accepted: bool
    note: str
    errors: List[str] = Field(default_factory=list)
    interaction_id_hash: Optional[str] = None
    provider_model: Optional[str] = None
    token_usage: Dict[str, int] = Field(default_factory=dict)
    latency_ms: float = 0.0
    overlay_sent: bool = False
    # salvage_draft lists for the correction (shown with the round; they replace the reading's lists if kept)
    dropped: List[str] = Field(default_factory=list)
    repaired: List[str] = Field(default_factory=list)


@dataclass
class CritiqueOutcome:
    record: CritiqueRound
    call: ExtractionResult
    draft: Optional[VenueDraftV1] = None          # set only when the correction was accepted
    assessment: Optional[Assessment] = None       # the accepted correction's assessment


def hash_identifier(identifier: Optional[str]) -> Optional[str]:
    """Same digest as tools/probe_capabilities.py: the raw provider id is never persisted."""
    return hashlib.sha256(str(identifier).encode()).hexdigest()[:16] if identifier else None


def improved(before: Dict[str, Any], after: Dict[str, Any]) -> bool:
    """Strictly fewer errors, or as many errors and fewer warnings. A reading that compiles beats one that does not;
    a correction that no longer compiles never wins."""
    def key(counts: Dict[str, Any]) -> Tuple[bool, int, int]:
        return bool(counts["compile_failed"]), int(counts["errors"]), int(counts["warnings"])
    return key(after) < key(before)


def _draft_keys(report_ids: Dict[str, str]) -> Dict[str, str]:
    return {venue_id: key for key, venue_id in report_ids.items()}


def issues_for_prompt(assessment: Assessment) -> List[IssueRecord]:
    """Typed issues with venue ids translated back to the draft keys Argon used."""
    reverse = _draft_keys(assessment.result.report.element_ids)
    records: List[IssueRecord] = []
    if assessment.compile_error is not None:
        code = assessment.compile_error.split(":")[0]
        records.append({"code": "compile_failed", "severity": "error", "detail": code,
                        "message": COMPILE_ERROR_HINTS.get(code, "The compiler could not build a venue from it."),
                        "draft_keys": []})
    for issue in assessment.issues[:MAX_ISSUES_SENT]:
        records.append({"code": issue.code, "severity": issue.severity, "message": issue.message,
                        "draft_keys": [reverse.get(element, element) for element in issue.element_ids]})
    return records


def critique_prompt(round_number: int, assessment: Assessment) -> Dict[str, Any]:
    report = assessment.result.report
    return {"type": "text", "text": json.dumps({
        "task": "critique_round",
        "round": round_number,
        "issues": issues_for_prompt(assessment),
        "compiler": {"dropped": report.dropped[:24], "edits": report.edits[:24], "defaults": report.defaults[:24],
                     "element_ids": report.element_ids},
        "return": "one full corrected VenueDraftV1 (schema_version draft-1)",
    }, separators=(",", ":"))}


async def run_critique_round(
    adapter: GroundingAdapter,
    *,
    round_number: int,
    previous_interaction_id: str,
    assessment: Assessment,
    recompile: Recompile,
    overlay_png: Optional[bytes] = None,
    thinking_level: str = DEFAULT_THINKING_LEVEL,
    stream: bool = True,
    deadline_seconds: float = DEFAULT_CRITIQUE_DEADLINE_SECONDS,
    on_thought: Optional[ThoughtSink] = None,
) -> CritiqueOutcome:
    """One chained round. The caller decides whether a round is due and how many may run."""
    before = assessment.counts()
    parts: List[Dict[str, Any]] = [critique_prompt(round_number, assessment)]
    if overlay_png:
        parts.append({"type": "image", "data": base64.b64encode(overlay_png).decode("ascii"),
                      "mime_type": "image/png", "resolution": MEDIA_RESOLUTION})
    call = await run_draft_interaction(
        adapter,
        receipt_kind=RECEIPT_KIND_CRITIQUE,
        system_instruction=CRITIQUE_SYSTEM_INSTRUCTION,
        input_parts=parts,
        previous_interaction_id=previous_interaction_id,
        thinking_level=thinking_level,
        stream=stream,
        deadline_seconds=deadline_seconds,
        on_thought=on_thought,
    )
    record = CritiqueRound(
        round=round_number, issues_before=before, accepted=False, note="", errors=list(call.errors),
        interaction_id_hash=hash_identifier(call.provider_interaction_id), provider_model=call.provider_model,
        token_usage=call.token_usage, latency_ms=round(call.latency_ms, 1), overlay_sent=bool(overlay_png),
        dropped=list(call.dropped), repaired=list(call.repaired),
    )
    if call.status != "completed" or call.draft is None:
        record.note = f"critique call {call.status}: {call.errors[0] if call.errors else 'no draft'}; reading kept"
        return CritiqueOutcome(record=record, call=call)
    try:
        corrected = recompile(call.draft)
        if inspect.isawaitable(corrected):
            corrected = await corrected
    except Exception:
        record.errors.append("local_processing_failure")
        record.note = "the correction could not be compiled locally; reading kept"
        return CritiqueOutcome(record=record, call=call)
    after = corrected.counts()
    record.issues_after = after
    if improved(before, after):
        record.accepted = True
        record.note = (f"round {round_number}: {before['errors']} errors, {before['warnings']} warnings -> "
                       f"{after['errors']} errors, {after['warnings']} warnings; correction kept")
        return CritiqueOutcome(record=record, call=call, draft=call.draft, assessment=corrected)
    record.note = (f"round {round_number}: {before['errors']} errors, {before['warnings']} warnings -> "
                   f"{after['errors']} errors, {after['warnings']} warnings; not better, reading kept")
    return CritiqueOutcome(record=record, call=call)


def clamp_rounds(value: Any) -> int:
    try:
        rounds = int(value)
    except (TypeError, ValueError):
        return DEFAULT_CRITIQUE_ROUNDS
    return max(0, min(MAX_CRITIQUE_ROUNDS, rounds))
