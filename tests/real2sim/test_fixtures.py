"""The synthetic Real2Sim fixtures: well-formed, honestly labelled, compile clean, plan, and regenerate identically."""
import json
from pathlib import Path

import pytest
from PIL import Image

from backend.app.ai.real2sim.overlay import render_overlay
from backend.app.ai.real2sim.schema import SourceImage, VenueDraftV1
from backend.app.hazard.door_planner import plan_doors
from backend.app.venues.compiler import compile_draft
from backend.app.venues.graph_checks import check_venue
from backend.app.venues.schemas import DoorPlanRequest
from tools import gen_real2sim_fixtures as gen

ROOT = Path(__file__).resolve().parents[2] / "venue" / "real2sim"
IDS = ["evac-office", "sketch-home"]
META_KEYS = {"fixture_id", "title", "source_kind", "provenance", "recorded_at", "interaction_id_hash", "note"}


def load(fixture_id):
    folder = ROOT / fixture_id
    image = Image.open(folder / "source.png")
    draft = VenueDraftV1.model_validate_json((folder / "draft.json").read_text())
    return folder, image, draft


@pytest.mark.parametrize("fixture_id", IDS)
def test_meta_is_labelled_synthetic(fixture_id):
    meta = json.loads((ROOT / fixture_id / "meta.json").read_text())
    assert set(meta) == META_KEYS and meta["fixture_id"] == fixture_id
    assert meta["provenance"] == "synthetic" and meta["source_kind"] in {"photo", "sketch", "pdf"}
    assert "drawn" in meta["note"] and meta["recorded_at"] is None and meta["interaction_id_hash"] is None


@pytest.mark.parametrize("fixture_id", IDS)
def test_fixture_compiles_clean_and_plans(fixture_id):
    folder, image, draft = load(fixture_id)
    result = compile_draft(draft, SourceImage(image.width, image.height, "0" * 64), venue_id=fixture_id)
    assert result.error is None and result.report.dropped == []
    assert check_venue(result.venue) == []
    zone = result.venue.zones[0]
    x = sum(p[0] for p in zone.polygon) / len(zone.polygon)
    y = sum(p[1] for p in zone.polygon) / len(zone.polygon)
    plan = plan_doors(result.venue, DoorPlanRequest(hazards=[
        {"id": "h1", "type": "FIRE", "position": {"x": x, "y": y}, "source": "simulated"}]))
    assert plan.chosen.validator_report.is_valid
    assert render_overlay((folder / "source.png").read_bytes(), draft, result).startswith(b"\x89PNG")


def test_evac_office_matches_the_brief():
    _, image, draft = load("evac-office")
    assert 8 <= len(draft.rooms) <= 10 and 3 <= len(draft.exits) <= 4 and draft.you_are_here is not None
    assert draft.image_kind == "evacuation_map" and draft.scale.basis == "scale_bar" and draft.scale.metres == 10.0
    assert any(r.kind in {"corridor", "lobby"} for r in draft.rooms)
    result = compile_draft(draft, SourceImage(image.width, image.height, ""), venue_id="evac-office")
    assert result.report.scale_basis == "scale_bar" and result.venue.extent[0] == pytest.approx(30.0, abs=0.3)


def test_sketch_home_matches_the_brief():
    _, image, draft = load("sketch-home")
    assert 5 <= len(draft.rooms) <= 6 and draft.image_kind == "sketch" and draft.scale.metres == 12.0
    assert {e.kind for e in draft.exits} >= {"door", "window"}
    result = compile_draft(draft, SourceImage(image.width, image.height, ""), venue_id="sketch-home")
    assert result.venue.extent[0] == pytest.approx(12.0, abs=0.1)


def test_generator_reproduces_the_committed_files(tmp_path):
    gen.main(tmp_path)
    for fixture_id in IDS:
        for name in ("draft.json", "meta.json"):
            assert (tmp_path / fixture_id / name).read_text() == (ROOT / fixture_id / name).read_text()
        fresh = Image.open(tmp_path / fixture_id / "source.png")
        committed = Image.open(ROOT / fixture_id / "source.png")
        assert fresh.size == committed.size and fresh.tobytes() == committed.tobytes()
