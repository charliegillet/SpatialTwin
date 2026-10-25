"""End-to-end connection check against a running SpatialTwin server (simulator, no provider calls).

Drives every route in the order an operator session uses them and confirms each hop works:
frontend assets -> API -> state/planner/checker -> event stream -> hardware bridge (simulator) -> observation.
Grounding uses the fixture path and the investigation uses the local solver, so no Gemini tokens are spent.

    .venv/bin/python -m uvicorn backend.app.main:app --port 8765   # demo mode, SERIAL_PORT empty
    .venv/bin/python tools/smoke_connections.py --base http://127.0.0.1:8765
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from datetime import datetime, timezone
from uuid import uuid4

import httpx

SCENARIO = "facility-demo"


class Check:
    def __init__(self) -> None:
        self.rows: list[tuple[str, bool, str]] = []

    def record(self, name: str, ok: bool, detail: str = "") -> bool:
        self.rows.append((name, ok, detail))
        print(f"{'PASS' if ok else 'FAIL'}  {name}{('  · ' + detail) if detail else ''}", flush=True)
        return ok


class EventListener(threading.Thread):
    """Counts server-sent events so the check can confirm state changes reach live clients."""

    def __init__(self, base: str) -> None:
        super().__init__(daemon=True)
        self.base = base
        self.events: list[str] = []
        self.connected = threading.Event()

    def run(self) -> None:
        try:
            with httpx.stream("GET", f"{self.base}/api/scenarios/{SCENARIO}/events", timeout=None) as response:
                self.connected.set()
                for line in response.iter_lines():
                    if line.startswith("event: "):
                        self.events.append(line[7:])
        except httpx.HTTPError:
            self.connected.set()


def wait_for(predicate, timeout: float, interval: float = 0.2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8765")
    args = parser.parse_args(argv)
    base = args.base.rstrip("/")
    check = Check()
    http = httpx.Client(base_url=base, timeout=30)

    def snapshot() -> dict:
        return http.get(f"/api/scenarios/{SCENARIO}").json()

    def context() -> dict:
        return snapshot()["context"]

    # 1. Server, configuration and frontend assets
    health = http.get("/health")
    check.record("GET /health", health.status_code == 200 and "hardware_mode" in health.json(),
                 f"hardware_mode={health.json().get('hardware_mode') if health.status_code == 200 else health.status_code}")
    caps = http.get("/api/ai/capabilities")
    check.record("GET /api/ai/capabilities", caps.status_code == 200 and {"video_static", "video_agentic"} <= set(caps.json()),
                 json.dumps(caps.json()) if caps.status_code == 200 else str(caps.status_code))
    index = http.get("/")
    check.record("GET / (frontend shell)", index.status_code == 200 and "<div id=\"root\"" in index.text)
    assets = re.findall(r'(?:src|href)="(/assets/[^"]+)"', index.text)
    check.record("frontend assets load", bool(assets) and all(http.get(a).status_code == 200 for a in assets),
                 f"{len(assets)} assets")

    # 2. Live event stream
    listener = EventListener(base)
    listener.start()
    listener.connected.wait(5)
    check.record("GET events (SSE connects, initial snapshot)",
                 bool(wait_for(lambda: "snapshot" in listener.events, 5)), f"events={listener.events[:3]}")

    # 3. Reset to a known baseline
    ctx = context()
    reset = http.post(f"/api/scenarios/{SCENARIO}/commands", json={
        "type": "RESET_SCENARIO", "expected_context": ctx,
        "expected_scenario_revision": ctx["scenario_revision"], "idempotency_key": f"smoke-reset-{uuid4().hex}"})
    check.record("POST commands RESET_SCENARIO", reset.status_code == 200, str(reset.status_code))

    # 4. Grounding (fixture path) -> reviewed proposal -> applied blockage -> checked plan
    ctx = context()
    capture_id = f"smoke-{uuid4().hex[:12]}"
    grounding = http.post(f"/api/scenarios/{SCENARIO}/grounding", json={
        "capture_id": capture_id, "timestamp_iso": datetime.now(timezone.utc).isoformat(),
        "source_context": ctx, "dimensions": [1920, 1080], "source_kind": "fixture",
        "mode": "fixture", "fixture_target": "P2"})
    proposal = grounding.json() if grounding.status_code == 200 else {}
    check.record("POST grounding (fixture → proposal)",
                 grounding.status_code == 200 and proposal.get("proposal_id") and proposal.get("provenance") == "fixture",
                 f"status={proposal.get('status')} target={((proposal.get('proposal') or {}).get('selected_entity_id'))}")
    before_events = len(listener.events)
    apply = http.post(f"/api/scenarios/{SCENARIO}/commands", json={
        "type": "APPLY_BLOCKAGE", "expected_context": ctx, "expected_scenario_revision": ctx["scenario_revision"],
        "idempotency_key": f"smoke-apply-{uuid4().hex}", "target_type": "portal", "target_id": "P2",
        "source": "grounding_proposal", "proposal_id": proposal.get("proposal_id"), "reviewed": True})
    applied = apply.json() if apply.status_code == 200 else {}
    plan = applied.get("plan") or {}
    check.record("POST commands APPLY_BLOCKAGE (reviewed proposal)",
                 apply.status_code == 200 and "P2" in applied.get("snapshot", {}).get("blocked_portals", []),
                 f"{apply.status_code} completed={plan.get('completed_crossings')}")
    check.record("planner result checked", bool(plan.get("validator_report", {}).get("is_valid")),
                 f"status={plan.get('status')}")
    check.record("event stream receives the change",
                 bool(wait_for(lambda: len(listener.events) > before_events, 5)),
                 f"new events={listener.events[before_events:before_events + 3]}")
    duplicate = http.post(f"/api/scenarios/{SCENARIO}/commands", json={
        "type": "APPLY_BLOCKAGE", "expected_context": ctx, "expected_scenario_revision": ctx["scenario_revision"],
        "idempotency_key": f"smoke-stale-{uuid4().hex}", "target_type": "portal", "target_id": "P2"})
    check.record("stale context is refused", duplicate.status_code in (400, 409), str(duplicate.status_code))

    # 5. Read paths over the checked state
    run_id = plan.get("run_id")
    run = http.get(f"/api/runs/{run_id}") if run_id else None
    check.record("GET /api/runs/{run_id}", bool(run is not None and run.status_code == 200), str(run.status_code if run else "no run"))
    matrix = http.get(f"/api/scenarios/{SCENARIO}/matrix")
    check.record("GET matrix", matrix.status_code == 200 and matrix.json().get("hypothetical") is True, str(matrix.status_code))
    ctx = context()
    lab = http.post(f"/api/scenarios/{SCENARIO}/lab", json={"expected_context": ctx, "reserve_basis": "reported"})
    check.record("POST lab", lab.status_code == 200 and bool(lab.json().get("cases")), str(lab.status_code))
    hazard = http.post("/api/hazard/simulate", json={"alternative_id": "KEEP_CURRENT",
                                                     "events": [{"element_id": "P1", "close_at_s": 12}]})
    hz = hazard.json() if hazard.status_code == 200 else {}
    check.record("POST hazard/simulate", hazard.status_code == 200 and hz.get("is_valid") is True
                 and hz.get("modeled_exposure_people_seconds") is not None,
                 f"crossings={hz.get('completed_crossings')} exposure={hz.get('modeled_exposure_people_seconds')}")
    check.record("hazard baseline matches the live checked plan",
                 hz.get("baseline_completed_crossings") == plan.get("completed_crossings"),
                 f"baseline={hz.get('baseline_completed_crossings')} plan={plan.get('completed_crossings')}")
    check.record("hazard closure never adds crossings over the live state",
                 hz.get("completed_crossings") is not None and plan.get("completed_crossings") is not None
                 and hz["completed_crossings"] <= plan["completed_crossings"],
                 f"forecast={hz.get('completed_crossings')} live={plan.get('completed_crossings')}")
    bad_hazard = http.post("/api/hazard/simulate", json={"alternative_id": "KEEP_CURRENT",
                                                         "events": [{"element_id": "ZZ", "close_at_s": 12}]})
    check.record("hazard rejects unknown element", bad_hazard.status_code == 422, str(bad_hazard.status_code))

    # 6. Investigation (local solver) -> progress -> cancel semantics -> review
    investigation_id = uuid4().hex
    inv = http.post(f"/api/scenarios/{SCENARIO}/investigate", json={
        "expected_context": ctx, "investigation_id": investigation_id, "mode": "local"}, timeout=90)
    result = (inv.json() or {}).get("investigation", {}) if inv.status_code == 200 else {}
    check.record("POST investigate (local)", inv.status_code == 200 and result.get("status") == "completed",
                 f"recommended={result.get('recommended_alternative')}")
    progress = http.get(f"/api/scenarios/{SCENARIO}/investigations/{investigation_id}/progress")
    check.record("GET investigation progress", progress.status_code == 200, str(progress.status_code))
    cancel = http.post(f"/api/scenarios/{SCENARIO}/investigations/{investigation_id}/cancel", json={"expected_context": ctx})
    check.record("POST cancel (finished run → handled, not 500)", cancel.status_code < 500, str(cancel.status_code))
    review = http.post(f"/api/scenarios/{SCENARIO}/review", json={"expected_context": ctx, "investigation_id": investigation_id})
    check.record("POST review", review.status_code == 200 and review.json().get("provenance") == "local_review",
                 str(review.status_code))

    # 7. Physical path through the simulator: approval -> ACK -> observed arrival -> stop
    hardware_mode = health.json().get("hardware_mode") if health.status_code == 200 else None
    candidate = next((c for c in result.get("candidate_envelopes", []) if c.get("alternative_id") == "OPEN_P3"), None)
    if hardware_mode != "simulator":
        check.record("approval path (simulator only)", True, "skipped: server is on physical hardware")
    elif result.get("recommended_alternative") != "OPEN_P3" or not candidate:
        check.record("approval path", False, "investigation did not recommend OPEN_P3")
    else:
        approval = http.post("/api/hardware/operator-approve", json={
            "expected_context": ctx, "candidate_alternative": "OPEN_P3", "investigation_id": investigation_id,
            "candidate_run_id": candidate["run_id"], "idempotency_key": f"smoke-approve-{uuid4().hex}"})
        body = approval.json() if approval.status_code == 200 else {}
        check.record("POST operator-approve (device ACK)", approval.status_code == 200 and body.get("acknowledged") is True,
                     f"{approval.status_code} {body.get('command_id', approval.text[:80])}")
        opened = wait_for(lambda: snapshot().get("physical_gate_state") == "OPEN", 15)
        check.record("gate arrival observed by endpoint report", bool(opened),
                     f"physical_gate_state={snapshot().get('physical_gate_state')}")
        repeat = http.post("/api/hardware/operator-approve", json={
            "expected_context": ctx, "candidate_alternative": "OPEN_P3", "investigation_id": investigation_id,
            "candidate_run_id": candidate["run_id"], "idempotency_key": f"smoke-approve-{uuid4().hex}"})
        check.record("approval on stale context is refused", repeat.status_code in (409, 422), str(repeat.status_code))
    stop = http.post("/api/hardware/stop")
    check.record("POST hardware/stop (device ACK)", stop.status_code == 200 and stop.json().get("status") == "STOP_ACKNOWLEDGED",
                 str(stop.status_code))

    # 8. Back to baseline
    ctx = context()
    final_reset = http.post(f"/api/scenarios/{SCENARIO}/commands", json={
        "type": "RESET_SCENARIO", "expected_context": ctx,
        "expected_scenario_revision": ctx["scenario_revision"], "idempotency_key": f"smoke-reset-{uuid4().hex}"})
    check.record("POST commands RESET_SCENARIO (cleanup)", final_reset.status_code == 200, str(final_reset.status_code))

    failed = [name for name, ok, _ in check.rows if not ok]
    print(f"\n{len(check.rows) - len(failed)}/{len(check.rows)} connection checks passed")
    if failed:
        print("Failed: " + "; ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
