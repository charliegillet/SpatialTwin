"""Critique rounds: chained on the extraction, kept only when the local rule says the reading improved.

Also hosts the small fake Interactions client and the fake compiler that test_drafts / test_routes_real2sim reuse
(the real compiler is the compiler teammate's; these tests only need a deterministic stand-in).
"""
import asyncio
import copy
import json
from pathlib import Path
from types import SimpleNamespace as NS

from backend.app.ai.grounding.adapter import GroundingAdapter
from backend.app.ai.real2sim.critique import (
    Assessment,
    CRITIQUE_SYSTEM_INSTRUCTION,
    clamp_rounds,
    hash_identifier,
    improved,
    issues_for_prompt,
    run_critique_round,
)
from backend.app.ai.real2sim.schema import CompileReport, CompileResult, VenueDraftV1
from backend.app.venues.graph_checks import check_venue
from backend.app.venues.model import VenueV2

HOME = json.loads((Path(__file__).resolve().parents[1] / "venues" / "fixtures" / "home_flat.json").read_text())

FIVE_DOORS = [("KD1", "LIVING", "HALL"), ("KD2", "KITCHEN", "HALL"), ("KD3", "BED_1", "HALL"),
              ("KD4", "BED_2", "HALL"), ("KD5", "LIVING", "KITCHEN")]


def home_draft(doors=5, exits=1, title="Test flat"):
    """A draft whose rooms match tests/venues/fixtures/home_flat.json (boxes are illustrative)."""
    rooms = [("LIVING", "Living", "room", [100, 100, 450, 450]), ("KITCHEN", "Kitchen", "kitchen", [100, 450, 450, 900]),
             ("HALL", "Hall", "corridor", [450, 100, 550, 900]), ("BED_1", "Bedroom 1", "bedroom", [550, 100, 900, 450]),
             ("BED_2", "Bedroom 2", "bedroom", [550, 450, 900, 900])]
    return {
        "schema_version": "draft-1", "title": title, "image_kind": "sketch",
        "scale": {"basis": "unknown", "a": None, "b": None, "metres": None, "evidence": ""},
        "rooms": [{"key": k, "name": n, "kind": kind, "box": box, "extra_boxes": [],
                   "label_point": [(box[0] + box[2]) // 2, (box[1] + box[3]) // 2], "occupants_hint": None}
                  for k, n, kind, box in rooms],
        "doors": [{"key": key, "between": [a, b], "point": [450, 300], "width_m": None, "symbol": "swing",
                   "confidence": 0.9, "evidence": "gap"} for key, a, b in FIVE_DOORS[:doors]],
        "exits": [{"key": f"X{i + 1}", "room": "HALL", "point": [550, 500], "width_m": None, "kind": "door",
                   "label": "EXIT", "confidence": 0.9, "evidence": "EXIT sign"} for i in range(exits)],
        "sheet_corners": None, "you_are_here": None, "unreadable": [], "notes": "",
    }


def fake_compile(draft, image, *, venue_id, controllable_doors=(), headcount=None, building_width_m=None,
                 name=None, provenance=None):
    """Deterministic stand-in: home_flat with one over-capacity room per door missing from five, so the graph-check
    error count is 5 - len(doors); no exits -> no_exit_survived (as the real compiler reports it)."""
    report = CompileReport(element_ids={room.key: room.key for room in draft.rooms}, scale_basis="default_width")
    if not draft.exits:
        return CompileResult(None, report, "no_exit_survived")
    venue = copy.deepcopy(HOME)
    venue["venue_id"] = venue_id
    if provenance:
        venue["provenance"] = provenance
    for i, door in enumerate(draft.doors[:5]):
        report.element_ids[door.key] = venue["doors"][i]["id"]
    for i, exit_ in enumerate(draft.exits[:3]):
        report.element_ids[exit_.key] = venue["exits"][i]["id"]
    for zone in venue["zones"][:max(0, 5 - len(draft.doors))]:
        zone["initial_occupants"] = zone["max_capacity"] + 1
    for key in controllable_doors:
        door_id = report.element_ids.get(key)
        door = next((d for d in venue["doors"] if d["id"] == door_id), None)
        if door is None:
            report.dropped.append(f"controllable {key}: unknown door")
            continue
        door.update(default_state="closed", planner_can_open=True, actuation="motorized", kind="servo_door")
        venue["led_map"].setdefault(door_id, [20 + len(venue["led_map"]) * 3, 22 + len(venue["led_map"]) * 3])
    if headcount is not None:
        report.defaults.append(f"headcount {headcount} (operator)")
    return CompileResult(VenueV2.model_validate(venue), report, None)


def assess(draft):
    result = fake_compile(draft, None, venue_id="test-flat-abc123")
    return Assessment(result=result, issues=check_venue(result.venue) if result.venue else [])


class FakeStream:
    def __init__(self, events, gate=None):
        self.events, self.gate, self.closed = events, gate, False

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        for event in self.events:
            if self.gate is not None:
                while not self.gate.is_set():   # a threading.Event: set from the test thread
                    await asyncio.sleep(0.005)
            yield event

    async def close(self):
        self.closed = True


class FakeInteractions:
    """Records every create() call; each call consumes the next scripted response (event list or exception)."""

    def __init__(self, *responses, gate=None):
        self.responses = list(responses)
        self.calls = []
        self.gate = gate

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return FakeStream(response, self.gate)


def fake_adapter(interactions):
    adapter = GroundingAdapter(api_key="")
    adapter.client = NS(aio=NS(interactions=interactions))
    return adapter


def script(draft, *, thoughts=("Reading the walls.",), interaction_id="v1_fake", model="gemini-4-argon",
           status="completed"):
    text = draft if isinstance(draft, str) else json.dumps(draft)
    half = len(text) // 2
    events = [NS(event_type="interaction.created", interaction=NS(id=interaction_id, model=model,
                                                                  status="in_progress", usage=None)),
              NS(event_type="step.start", index=0, step=NS(type="thought"))]
    events += [NS(event_type="step.delta", index=0, delta=NS(type="thought_summary", content=NS(type="text", text=t)))
               for t in thoughts]
    events += [NS(event_type="step.stop", index=0), NS(event_type="step.start", index=1, step=NS(type="model_output")),
               NS(event_type="step.delta", index=1, delta=NS(type="text", text=text[:half])),
               NS(event_type="step.delta", index=1, delta=NS(type="text", text=text[half:])),
               NS(event_type="step.stop", index=1),
               NS(event_type="interaction.completed", interaction=NS(id=interaction_id, model=model, status=status,
                                                                     usage={"total_tokens": 42}))]
    return events


# --- tests -------------------------------------------------------------------------------------------------------

def test_improvement_rule():
    def counts(errors, warnings, failed=False):
        return {"errors": errors, "warnings": warnings, "compile_failed": failed}
    assert improved(counts(3, 0), counts(0, 2))
    assert improved(counts(2, 2), counts(2, 1))
    assert not improved(counts(2, 1), counts(2, 1))
    assert not improved(counts(2, 0), counts(3, 0))
    assert not improved(counts(1, 5), counts(2, 0))
    assert improved(counts(1, 0, failed=True), counts(4, 0))     # compiling beats not compiling
    assert not improved(counts(4, 0), counts(1, 0, failed=True))
    assert [clamp_rounds(v) for v in (-1, 0, 1, 2, 9, "x", None)] == [0, 0, 1, 2, 2, 1, 1]


def test_issues_are_translated_back_to_draft_keys():
    draft = VenueDraftV1.model_validate(home_draft(doors=3))
    records = issues_for_prompt(assess(draft))
    assert {r["code"] for r in records} == {"over_capacity"}
    assert {key for r in records for key in r["draft_keys"]} == {"LIVING", "KITCHEN"}
    no_exit = issues_for_prompt(assess(VenueDraftV1.model_validate(home_draft(exits=0))))
    assert no_exit[0]["code"] == "compile_failed" and no_exit[0]["detail"] == "no_exit_survived"
    assert "keep exits empty" in no_exit[0]["message"]


async def test_a_better_correction_is_kept_and_chained():
    draft = VenueDraftV1.model_validate(home_draft(doors=3))
    fake = FakeInteractions(script(home_draft(doors=5), interaction_id="v1_round1"))
    thoughts = []
    outcome = await run_critique_round(
        fake_adapter(fake), round_number=1, previous_interaction_id="v1_extract", assessment=assess(draft),
        recompile=assess, overlay_png=b"\x89PNG-overlay", on_thought=thoughts.append)
    record = outcome.record
    assert record.accepted and outcome.draft is not None and len(outcome.draft.doors) == 5
    assert record.issues_before == {"errors": 2, "warnings": 0, "compile_failed": False}
    assert record.issues_after["errors"] == 0
    assert record.interaction_id_hash == hash_identifier("v1_round1") and record.overlay_sent
    assert "2 errors" in record.note and "0 errors" in record.note
    assert thoughts == ["Reading the walls."]
    call = fake.calls[0]
    assert call["previous_interaction_id"] == "v1_extract" and call["store"] is True
    assert call["system_instruction"] == CRITIQUE_SYSTEM_INSTRUCTION
    assert call["generation_config"]["thinking_summaries"] == "auto"
    prompt, overlay = call["input"]
    assert json.loads(prompt["text"])["task"] == "critique_round"
    assert overlay["mime_type"] == "image/png" and overlay["resolution"] == "high"


async def test_a_correction_that_is_not_better_is_rejected():
    draft = VenueDraftV1.model_validate(home_draft(doors=3))
    fake = FakeInteractions(script(home_draft(doors=2)))
    outcome = await run_critique_round(fake_adapter(fake), round_number=1, previous_interaction_id="v1_extract",
                                       assessment=assess(draft), recompile=assess)
    assert not outcome.record.accepted and outcome.draft is None
    assert outcome.record.issues_after["errors"] == 3 and "not better" in outcome.record.note


async def test_async_recompile_and_provider_failure_are_recorded_not_raised():
    draft = VenueDraftV1.model_validate(home_draft(doors=4))

    async def recompile(corrected):
        return assess(corrected)

    ok = await run_critique_round(fake_adapter(FakeInteractions(script(home_draft(doors=5)))), round_number=2,
                                  previous_interaction_id="v1_x", assessment=assess(draft), recompile=recompile)
    assert ok.record.accepted and ok.record.round == 2
    failed = await run_critique_round(fake_adapter(FakeInteractions(script("not json"))), round_number=1,
                                      previous_interaction_id="v1_x", assessment=assess(draft), recompile=assess)
    assert not failed.record.accepted and failed.record.errors == ["invalid_provider_output"]
    assert failed.record.issues_after is None and "reading kept" in failed.record.note
