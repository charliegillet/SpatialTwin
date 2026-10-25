"""The last-live-receipt record keeps only kind, model and time, and never fails a live call."""
import json
from datetime import datetime, timedelta, timezone

from backend.app.ai import receipts
from backend.app.ai.grounding.adapter import GroundingAdapter
from backend.app.contracts import Capture, RunContext


def test_records_metadata_only(tmp_path):
    receipts.record_live_receipt("camera_card_read", "gemini-4-argon")
    stored = json.loads((receipts.receipts_dir() / "last_live.json").read_text())
    assert set(stored) == {"kind", "model", "at"}
    found = receipts.last_live_receipt(tmp_path / "no-probes")
    assert found["kind"] == "camera_card_read" and found["model"] == "gemini-4-argon"


def test_newest_source_wins(tmp_path):
    probes = tmp_path / "probes"
    probes.mkdir()
    now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
    (probes / "P1.json").write_text(json.dumps({"pass": True, "probe_id": "P1",
                                                "timestamp_utc": (now - timedelta(hours=1)).isoformat()}))
    receipts.record_live_receipt("direct_grounding", "gemini-4-argon", now=now - timedelta(hours=3))
    found = receipts.last_live_receipt(probes, now=now)
    assert found["kind"] == "probe:P1" and round(found["age_seconds"]) == 3600


def test_ignores_failed_naive_and_garbage_receipts(tmp_path):
    probes = tmp_path / "probes"
    probes.mkdir()
    (probes / "P5.json").write_text(json.dumps({"pass": False, "timestamp_utc": "2026-10-25T00:00:00+00:00"}))
    (probes / "P6.json").write_text(json.dumps({"pass": "true", "timestamp_utc": "2026-10-25T00:00:00+00:00"}))
    (probes / "P7.json").write_text(json.dumps({"pass": True, "timestamp_utc": "2026-10-25T00:00:00"}))
    (probes / "P8.json").write_text("not json")
    assert receipts.last_live_receipt(probes) is None


def test_future_dated_receipts_do_not_read_as_fresh(tmp_path):
    now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
    receipts.record_live_receipt("direct_grounding", None, now=now + timedelta(days=1))
    assert receipts.last_live_receipt(tmp_path / "no-probes", now=now) is None


async def test_fixture_and_unconfigured_calls_write_no_receipt():
    """Only a verified live completion records; a fixture proposal and an unconfigured live attempt do not."""
    context = RunContext(geometry_revision="geom-shack15-v1", scenario_revision=1, physical_revision=1)
    capture = Capture(capture_id="cap-receipt-1", timestamp_iso="2026-10-24T00:00:00Z", source_kind="fixture",
                      source_geometry_revision=context.geometry_revision, expected_scenario_revision=1,
                      expected_physical_revision=1)
    adapter = GroundingAdapter(api_key="")
    fixture = await adapter.interpret_capture(capture, context, force_target="P2")
    assert fixture.provenance == "fixture" and fixture.status == "completed"
    live = await adapter.interpret_capture(capture.model_copy(update={"source_kind": "upload"}), context)
    assert live.status in ("unavailable", "failed")
    assert not (receipts.receipts_dir() / "last_live.json").exists()


def test_unwritable_runtime_is_silent(tmp_path, monkeypatch):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    monkeypatch.setenv(receipts.RECEIPTS_DIR_ENV, str(blocker / "nested"))
    receipts.record_live_receipt("direct_grounding", "gemini-4-argon")  # must not raise
