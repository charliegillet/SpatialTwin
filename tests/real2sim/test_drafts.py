"""Draft orchestration: saved-run loading, source validation, the replayable event log and the service pipeline."""
import asyncio
import base64
import io
import json
import os
import threading

import pytest
from PIL import Image

from backend.app.ai.real2sim import drafts as drafts_module
from backend.app.ai.real2sim.critique import hash_identifier
from backend.app.ai.real2sim.drafts import EventLog, Real2SimError, Real2SimService, decode_source, slug_venue_id
from backend.app.ai.real2sim.extract import DraftExtractor
from backend.app.ai.real2sim.fixtures import FixtureError, list_saved_runs, load_saved_run
from backend.app.venues.registry import venue_registry
from tests.real2sim.test_critique import FakeInteractions, fake_adapter, fake_compile, home_draft, script


def png_bytes(width=60, height=40, fmt="PNG", exif=None):
    buffer = io.BytesIO()
    image = Image.new("RGB", (width, height), (250, 250, 250))
    image.save(buffer, format=fmt, **({"exif": exif} if exif is not None else {}))
    return buffer.getvalue()


def write_saved_run(root, fixture_id="test-flat", provenance="synthetic", draft=None, thoughts=None, **meta):
    path = root / fixture_id
    path.mkdir(parents=True)
    (path / "source.png").write_bytes(png_bytes())
    (path / "draft.json").write_text(json.dumps(draft or home_draft()))
    (path / "meta.json").write_text(json.dumps({
        "fixture_id": fixture_id, "title": "Test flat (synthetic)", "source_kind": "sketch",
        "provenance": provenance, "recorded_at": None, "interaction_id_hash": None, "note": "drawn by a test",
        **({"thoughts": thoughts} if thoughts else {}), **meta}))
    return path


def fake_png(*args, **kwargs):
    return png_bytes(8, 8)


def make_service(tmp_path, adapter=None, **kwargs):
    adapter = adapter or fake_adapter(FakeInteractions())
    return Real2SimService(adapter, runtime_dir=tmp_path / "runtime", extractor=DraftExtractor(adapter, stream=True),
                           compile_fn=fake_compile, overlay_fn=lambda *a: png_bytes(8, 8), topdown_fn=fake_png,
                           **kwargs)


# --- saved runs --------------------------------------------------------------------------------------------------

def test_saved_runs_are_listed_validated_and_labelled(tmp_path):
    write_saved_run(tmp_path, "test-flat")
    write_saved_run(tmp_path, "recorded-run", provenance="saved_run", recorded_at="2026-10-25T18:00:00Z",
                    interaction_id_hash="0123456789abcdef")
    broken = write_saved_run(tmp_path, "broken-run")
    (broken / "draft.json").write_text("{}")
    listed = list_saved_runs(tmp_path)
    assert [s["fixture_id"] for s in listed["saved"]] == ["recorded-run", "test-flat"]
    assert listed["invalid"] == ["broken-run"]
    labels = {s["fixture_id"]: s["provenance_label"] for s in listed["saved"]}
    assert labels["test-flat"].startswith("Synthetic saved run") and "not a Gemini reading" in labels["test-flat"]
    assert "2026-10-25T18:00:00Z" in labels["recorded-run"] and "not a live call" in labels["recorded-run"]


@pytest.mark.parametrize("fixture_id", ["../etc", "..", "a/../../b", "/etc/passwd", "UPPER", "x", "a" * 49, "a\x00b",
                                        "evac-office/../../secrets", 7, None])
def test_fixture_ids_cannot_escape_the_directory(tmp_path, fixture_id):
    with pytest.raises(FixtureError) as error:
        load_saved_run(fixture_id, tmp_path)
    assert error.value.code == "invalid_fixture_id"


def test_symlinked_or_mismatched_saved_runs_are_refused(tmp_path):
    outside = tmp_path / "outside"
    write_saved_run(outside, "secret-run")
    root = tmp_path / "fixtures"
    root.mkdir()
    os.symlink(outside / "secret-run", root / "secret-run")
    with pytest.raises(FixtureError) as escaped:
        load_saved_run("secret-run", root)
    assert escaped.value.code == "invalid_fixture_id"
    write_saved_run(root, "renamed-run")
    meta = json.loads((root / "renamed-run" / "meta.json").read_text())
    (root / "renamed-run" / "meta.json").write_text(json.dumps({**meta, "fixture_id": "other-run"}))
    with pytest.raises(FixtureError) as mismatched:
        load_saved_run("renamed-run", root)
    assert mismatched.value.code == "invalid_fixture"
    with pytest.raises(FixtureError) as missing:
        load_saved_run("no-such-run", root)
    assert missing.value.code == "unknown_fixture"


def test_the_real_saved_runs_load_when_present():
    listed = list_saved_runs()
    for summary in listed["saved"]:
        assert summary["provenance"] in ("synthetic", "saved_run") and summary["provenance_label"]
    assert listed["invalid"] == []


# --- source validation -------------------------------------------------------------------------------------------

def b64(data):
    return base64.b64encode(data).decode("ascii")


def test_source_validation_codes(monkeypatch):
    png = png_bytes()
    document, notes = decode_source(b64(png), "image/png", "photo")
    assert (document.image.width_px, document.image.height_px) == (60, 40) and notes == []
    cases = [
        ((b64(png), "image/heic", "photo"), "unsupported_mime_type", 415),
        (("", "image/png", "photo"), "source_required", 422),
        (("not base64!", "image/png", "photo"), "invalid_source_encoding", 422),
        ((b64(png), "image/jpeg", "photo"), "source_mime_mismatch", 422),
        ((b64(b"%PDF-1.4\n"), "application/pdf", "photo"), "source_kind_mismatch", 422),
        ((b64(png), "image/png", "pdf"), "source_kind_mismatch", 422),
        ((b64(b"\x89PNG\r\n\x1a\nbroken"), "image/png", "photo"), "invalid_source_image", 422),
    ]
    for args, code, status in cases:
        with pytest.raises(Real2SimError) as error:
            decode_source(*args)
        assert (error.value.code, error.value.http_status) == (code, status)
    monkeypatch.setattr(drafts_module, "MAX_BASE64_CHARS", 16)
    with pytest.raises(Real2SimError) as large:
        decode_source(b64(png), "image/png", "photo")
    assert (large.value.code, large.value.http_status) == ("source_too_large", 413)


def test_pdf_page_size_and_exif_rotation():
    pdf, notes = decode_source(b64(b"%PDF-1.7\n1 0 obj << /Type /Page /MediaBox [0 0 1190.55 841.89] >>\n%%EOF"),
                               "application/pdf", "pdf")
    assert pdf.page_size_basis == "mediabox" and pdf.image.width_px == 1600 and pdf.image.height_px == 1131
    assert any("page 1 only" in note for note in notes)
    unknown, notes = decode_source(b64(b"%PDF-1.5\n(compressed object streams)"), "application/pdf", "pdf")
    assert unknown.page_size_basis == "assumed_a4_landscape" and any("assumed A4" in n for n in notes)
    exif = Image.Exif()
    exif[0x0112] = 6
    photo, notes = decode_source(b64(png_bytes(60, 40, "JPEG", exif.tobytes())), "image/jpeg", "photo")
    assert (photo.image.width_px, photo.image.height_px) == (40, 60)
    assert notes == ["rotated upright from EXIF orientation 6"]


def test_venue_ids_are_slugged_and_never_the_builtin():
    venue_id = slug_venue_id("Level 1 — Meridian Offices!", "seed")
    assert venue_id.startswith("level-1-meridian-offices-") and len(venue_id) <= 40
    assert slug_venue_id(None, "seed").startswith("venue-")
    assert slug_venue_id("building", "x") != "building-v2"


# --- event log ---------------------------------------------------------------------------------------------------

async def test_event_log_replays_after_last_event_id_pings_and_ends_after_terminal():
    log = EventLog(max_events=50)
    log.append("status", {"n": 1})
    log.append("thought", {"n": 2})
    received = []

    async def consume():
        async for chunk in log.stream(last_event_id=1, ping_seconds=0.01):
            received.append(chunk)

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.05)
    log.append("done", {"n": 3}, terminal=True)
    await asyncio.wait_for(task, 1)
    events = [c for c in received if not c.startswith(":")]
    assert events[0].startswith("id: 2\nevent: thought\n") and events[-1].startswith("id: 3\nevent: done\n")
    assert ": ping\n\n" in received
    assert log.append("late", {}) is None    # nothing after the terminal event
    assert [c async for c in log.stream(last_event_id=3)] == []


def test_event_log_is_bounded():
    log = EventLog(max_events=5)
    for i in range(12):
        log.append("thought", {"i": i})
    assert len(log.events) == 5 and log.events[0].id == 8 and log.last_id == 12


# --- service pipelines -------------------------------------------------------------------------------------------

async def test_fixture_pipeline_is_labelled_and_never_calls_the_provider(tmp_path):
    fake = FakeInteractions()
    service = make_service(tmp_path, adapter=fake_adapter(fake))
    saved = load_saved_run(write_saved_run(tmp_path / "fx", thoughts=["Recorded thought."]).name, tmp_path / "fx")
    created = await service.create_fixture(saved)
    await service.wait_idle()
    view = service.view(created["draft_id"])
    assert view["status"] == "ready" and view["mode"] == "fixture" and view["provenance"] == "synthetic"
    assert view["provenance_label"].startswith("Synthetic saved run")
    assert view["thoughts"] == [{"phase": "saved_run", "text": "Recorded thought.", "recorded": True}]
    assert view["receipts"] == [] and view["rounds"] == [] and "saved run" in view["critique_note"]
    assert view["compile"]["venue"]["provenance"].startswith("Compiled by the local compiler from a synthetic")
    assert view["overlay_available"] and view["topdown_available"] and fake.calls == []
    assert view["accept_blockers"] == []
    events = [e.event for e in service.event_log(created["draft_id"]).events]
    assert events[0] == "status" and events[-1] == "done" and "draft" in events and "checks" in events


async def test_live_pipeline_runs_one_critique_round_and_hashes_receipts(tmp_path):
    fake = FakeInteractions(script(home_draft(doors=3), interaction_id="v1_extract", thoughts=("Walls first.",)),
                            script(home_draft(doors=5), interaction_id="v1_critique", thoughts=("Fixing doors.",)))
    service = make_service(tmp_path, adapter=fake_adapter(fake), critique_rounds=1)
    source, notes = decode_source(b64(png_bytes()), "image/png", "photo")
    created = await service.create_live(source, name="My flat", notes=notes)
    assert created["status"] == "extracting" and service.live_busy()
    await service.wait_idle()
    assert not service.live_busy()
    view = service.view(created["draft_id"])
    assert view["status"] == "ready" and view["provenance"] == "live", view["errors"]
    assert len(view["draft"]["doors"]) == 5 and len(view["extracted_draft"]["doors"]) == 3
    assert view["checks"]["errors"] == 0
    [round_] = view["rounds"]
    assert round_["accepted"] and round_["issues_before"]["errors"] == 2 and round_["issues_after"]["errors"] == 0
    assert [r["interaction_id_hash"] for r in view["receipts"]] == [hash_identifier("v1_extract"),
                                                                     hash_identifier("v1_critique")]
    assert "v1_extract" not in json.dumps(view) and "v1_critique" not in json.dumps(view)
    assert [t["phase"] for t in view["thoughts"]] == ["extract", "critique-1"]
    assert fake.calls[1]["previous_interaction_id"] == "v1_extract"
    assert (tmp_path / "runtime" / created["draft_id"] / "source.png").read_bytes() == source.data
    assert service.image(created["draft_id"], "overlay.png").startswith(b"\x89PNG")


async def test_no_critique_without_errors_and_no_exit_is_reviewable(tmp_path):
    fake = FakeInteractions(script(home_draft(exits=0)))
    service = make_service(tmp_path, adapter=fake_adapter(fake), critique_rounds=0)
    source, _ = decode_source(b64(png_bytes()), "image/png", "sketch")
    created = await service.create_live(source)
    await service.wait_idle()
    view = service.view(created["draft_id"])
    assert view["status"] == "ready" and view["compile"]["error"] == "no_exit_survived"
    assert "compile:no_exit_survived" in view["accept_blockers"] and len(fake.calls) == 1
    assert view["overlay_available"] and not view["topdown_available"]
    with pytest.raises(Real2SimError) as error:
        await service.accept(created["draft_id"], expected_revision=view["revision"], controllable_doors=[])
    assert error.value.code == "compile_failed" and error.value.extra == {"error": "no_exit_survived"}


async def test_failed_extraction_releases_the_slot_and_ends_the_log(tmp_path):
    service = make_service(tmp_path, adapter=fake_adapter(FakeInteractions(script("[]"))))
    source, _ = decode_source(b64(png_bytes()), "image/png", "photo")
    created = await service.create_live(source)
    await service.wait_idle()
    view = service.view(created["draft_id"])
    assert view["status"] == "failed" and view["errors"] == ["draft_not_an_object"] and view["draft"] is None
    assert not service.live_busy()
    assert service.event_log(created["draft_id"]).events[-1].event == "error"


async def test_busy_live_slot_is_429_and_unconfigured_is_503(tmp_path):
    gate = threading.Event()
    service = make_service(tmp_path, adapter=fake_adapter(FakeInteractions(script(home_draft()), gate=gate)))
    source, _ = decode_source(b64(png_bytes()), "image/png", "photo")
    await service.create_live(source)
    with pytest.raises(Real2SimError) as busy:
        await service.create_live(source)
    assert (busy.value.code, busy.value.http_status) == ("real2sim_busy", 429)
    gate.set()
    await service.wait_idle()
    unconfigured = Real2SimService(fake_adapter(FakeInteractions()), runtime_dir=tmp_path)
    unconfigured.adapter.client = None
    with pytest.raises(Real2SimError) as missing:
        await unconfigured.create_live(source)
    assert (missing.value.code, missing.value.http_status) == ("configuration_missing", 503)


async def test_duplicate_draft_id_is_a_conflict_not_a_500(tmp_path, monkeypatch):
    monkeypatch.setattr(drafts_module.secrets, "token_hex", lambda n: "ab" * n)
    service = make_service(tmp_path)
    saved = load_saved_run(write_saved_run(tmp_path / "fx").name, tmp_path / "fx")
    await service.create_fixture(saved)
    with pytest.raises(Real2SimError) as error:
        await service.create_fixture(saved)
    assert (error.value.code, error.value.http_status) == ("draft_id_conflict", 409)
    await service.wait_idle()


async def test_orphaned_in_progress_draft_is_reported_failed(tmp_path):
    service = make_service(tmp_path)
    draft_id = "r2s-" + "c" * 24
    venue_registry().create_draft(draft_id, "extracting", {"schema": "real2sim-draft-1", "provenance": "live",
                                                           "errors": []})
    view = service.view(draft_id)
    assert view["status"] == "failed" and view["errors"] == ["pipeline_interrupted"]
    replay = service.event_log(draft_id)
    assert [e.event for e in replay.events] == ["status", "error"] and replay.closed
    with pytest.raises(Real2SimError) as unknown:
        service.view("r2s-" + "d" * 24)
    assert unknown.value.code == "unknown_draft"
