"""End-to-end connection check against a running SpatialTwin server (simulator, no provider calls).

Drives every route in the order an operator session uses them and confirms each hop works:
frontend assets -> API -> state/planner/checker -> event stream -> hardware bridge (simulator) -> observation.
Grounding uses the fixture path and the investigation uses the local solver, so no Gemini tokens are spent.
Then the demo v2 path on building-v2: incident mirror, virtual doors (ACK, endpoint, jam -> fallback), the unattended
fail-safe (about 6 s of waiting) and a phone sign link. It resets the shared incident, so do not run it mid-demo.

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


LOBBY_FIRE = {"id": "smoke-lobby", "type": "FIRE", "position": {"x": 20, "y": 4}, "source": "simulated"}
HALL_FIRE = {"id": "smoke-hall", "type": "FIRE", "position": {"x": 20, "y": 14}, "source": "simulated"}


def incident_checks(http: httpx.Client, base: str, check: Check) -> None:
    """Demo v2 (no hardware): incident mirror, virtual doors, jam -> fallback, the unattended fail-safe, phone signs."""

    def state() -> dict:
        return http.get("/api/incident").json()

    def gate(current: dict, gate_id: str) -> dict:
        return next((g for g in current["controller"]["gates"] if g["gate_id"] == gate_id), {})

    def post_hazards(hazards: list) -> httpx.Response:
        return http.post("/api/incident/hazards", json={"venue_id": "building-v2", "hazards": hazards,
                                                        "expected_plan_revision": state()["plan_revision"]})

    def approve(current: dict) -> httpx.Response:
        plan = current["plan"]
        return http.post("/api/incident/approve", json={"plan_revision": plan["plan_revision"], "candidate_hash": plan["candidate_hash"],
                                                        "door_states": plan["door_states"]})

    def fresh(hazard: dict) -> dict:
        http.post("/api/incident/reset")
        response = post_hazards([hazard])
        return response.json() if response.status_code == 200 else {}

    try:
        reset = http.post("/api/incident/reset")
        check.record("POST /api/incident/reset", reset.status_code == 200 and reset.json()["failsafe"]["armed"] is False
                     and reset.json()["simulated"] is True, str(reset.status_code))

        # Approve: an ACK is not arrival; only the endpoint switch makes D9 read open.
        planned = post_hazards([LOBBY_FIRE])
        plan = planned.json().get("plan") or {} if planned.status_code == 200 else {}
        check.record("POST incident hazards FIRE in LOBBY (checked plan opens D9)",
                     planned.status_code == 200 and plan.get("valid") is True and plan.get("door_states", {}).get("D9") == "open",
                     f"r{plan.get('plan_revision')} {plan.get('completed_crossings')}/{plan.get('initial_population')} {plan.get('count_label')}")
        record = approve(planned.json()) if plan else None
        check.record("POST incident approve -> actuating (ACK, not arrival)",
                     record is not None and record.status_code == 200 and record.json()["status"] == "actuating"
                     and record.json()["commands"] == {"D9": "OPEN"}, record.text[:80] if record is not None else "no plan")
        arrived = wait_for(lambda: (now := state())["approvals"] and now["approvals"][-1]["status"] == "applied"
                           and gate(now, "D9").get("observed") == "open" and now, 10)
        check.record("D9 endpoint observed open (virtual door controller)", bool(arrived),
                     f"epoch={gate(arrived, 'D9').get('epoch')}" if arrived else "")

        # Jam: the door is never observed open, it is marked stuck and the server publishes a fallback.
        hall = fresh(HALL_FIRE)
        jam = http.post("/api/incident/faults", json={"gate_id": "D4", "fault": "stall"})
        jammed = approve(hall) if hall.get("plan") and jam.status_code == 200 else None
        fallback = wait_for(lambda: ((now := state())["plan"] or {}).get("label") == "fallback" and "D4" in now["stuck_doors"] and now, 15)
        check.record("Jam D4 then approve -> fallback with D4 stuck closed",
                     jammed is not None and jammed.status_code == 200 and bool(fallback),
                     (fallback["plan"]["reason"][:90] if fallback else (jammed.text[:80] if jammed is not None else "no plan")))
        door_plan = http.get("/api/incident/door-plan").json()
        check.record("GET /api/incident/door-plan follows the fallback",
                     bool(fallback) and door_plan.get("plan_revision") == fallback["plan"]["plan_revision"] and door_plan.get("door_plan") is not None,
                     f"r{door_plan.get('plan_revision')}")

        # The unattended fail-safe: nobody approves, so it approves, holding D4 (into the burning hall) closed.
        hall = fresh(HALL_FIRE)
        armed = http.post("/api/incident/failsafe", json={"armed": True, "window_seconds": 5})
        view = armed.json() if armed.status_code == 200 else {}
        check.record("POST /api/incident/failsafe arm (5 s window)", armed.status_code == 200 and view.get("status") == "counting_down"
                     and view.get("would_hold") == ["D4"], f"would_hold={view.get('would_hold')}")
        acted = wait_for(lambda: (now := state())["failsafe"]["status"] == "acted" and now, 12)
        last = (acted or {}).get("approvals", [{}])[-1] if acted else {}
        check.record("Nobody approved: fail-safe approved with D4 held closed",
                     bool(acted) and acted["plan"]["held_doors"] == ["D4"] and acted["plan"]["door_states"]["D4"] == "closed"
                     and last.get("actor") == "fail_safe", (acted["failsafe"]["last_action"]["summary"][:110] if acted else ""))
        off = http.post("/api/incident/failsafe", json={"armed": False})
        after = state()
        check.record("I'm here: disarm hands D4 back to the planner",
                     off.status_code == 200 and off.json()["status"] == "off" and after["plan"] is not None
                     and after["plan"]["held_doors"] == [] and after["plan"]["door_states"]["D4"] == "open",
                     f"r{after['plan_revision']} {after['plan']['completed_crossings'] if after['plan'] else '-'} modeled crossings")

        # A phone exit sign: mint (loopback only) -> redeem -> HttpOnly cookie -> the sign's own state.
        minted = http.post("/api/signs/tokens", json={"scope": "sign:read", "venue_id": "building-v2"})
        if minted.status_code == 503:
            check.record("POST /api/signs/tokens (signs disabled)", True, minted.json().get("detail", {}).get("code", ""))
            return
        url = minted.json().get("url", "") if minted.status_code == 200 else ""
        check.record("POST /api/signs/tokens (sign:read)", minted.status_code == 200 and "/s/" in url, str(minted.status_code))
        with httpx.Client(base_url=base, timeout=10, follow_redirects=False) as phone:
            redeemed = phone.get("/s/" + url.rsplit("/s/", 1)[-1])
            cookie = redeemed.headers.get("set-cookie", "")
            check.record("GET /s/<token> -> 303 to sign.html with an HttpOnly SameSite=Strict cookie",
                         redeemed.status_code == 303 and "sign.html" in redeemed.headers.get("location", "")
                         and "httponly" in cookie.lower() and "samesite=strict" in cookie.lower(), str(redeemed.status_code))
            sign = phone.get("/api/public/signs/building-v2")
            exits = sign.json().get("exits", []) if sign.status_code == 200 else []
            check.record("GET /api/public/signs/building-v2 (exit states)", sign.status_code == 200 and len(exits) == 4,
                         ", ".join(f"{x.get('exit_id')}:{x.get('state', x.get('lamp', '?'))}" for x in exits))
    finally:
        http.post("/api/incident/failsafe", json={"armed": False})
        cleaned = http.post("/api/incident/reset")
        check.record("POST /api/incident/reset (cleanup)", cleaned.status_code == 200, str(cleaned.status_code))


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
    check.record("GET /health", health.status_code == 200 and "hardware_mode" in health.json()
                 and isinstance(health.json().get("investigation_running"), bool),
                 f"hardware_mode={health.json().get('hardware_mode') if health.status_code == 200 else health.status_code}")
    caps = http.get("/api/ai/capabilities")
    check.record("GET /api/ai/capabilities", caps.status_code == 200 and {"video_static", "video_agentic"} <= set(caps.json()),
                 json.dumps(caps.json()) if caps.status_code == 200 else str(caps.status_code))
    index = http.get("/")
    check.record("GET / (frontend shell)", index.status_code == 200 and "<div id=\"root\"" in index.text)
    assets = re.findall(r'(?:src|href)="(/assets/[^"]+)"', index.text)
    check.record("frontend assets load", bool(assets) and all(http.get(a).status_code == 200 for a in assets),
                 f"{len(assets)} assets")

    # 1b. building-v2 venue and local door planner (stateless; no provider, no hardware)
    venue = http.get("/api/venues/building-v2")
    venue_json = venue.json() if venue.status_code == 200 else {}
    check.record("GET /api/venues/building-v2", venue.status_code == 200 and len(venue_json.get("zones", [])) == 8
                 and len(venue_json.get("doors", [])) == 10 and len(venue_json.get("exits", [])) == 4,
                 f"zones={len(venue_json.get('zones', []))} doors={len(venue_json.get('doors', []))}")
    unknown = http.get("/api/venues/unknown-venue")
    check.record("GET unknown venue -> 404 unknown_venue",
                 unknown.status_code == 404 and unknown.json().get("detail", {}).get("code") == "unknown_venue",
                 str(unknown.status_code))
    fire = http.post("/api/venues/building-v2/door-plan", json={"hazards": [
        {"id": "smoke-fire", "type": "FIRE", "position": {"x": 20, "y": 4}, "source": "simulated"}]})
    door_plan = fire.json() if fire.status_code == 200 else {}
    chosen = door_plan.get("chosen", {})
    check.record("POST door-plan FIRE in LOBBY (checked, local)",
                 fire.status_code == 200 and chosen.get("validator_report", {}).get("is_valid") is True
                 and door_plan.get("provenance") == "local_door_planner_v1" and door_plan.get("hypothetical") is True,
                 f"completed={chosen.get('completed_crossings')} baseline={door_plan.get('baseline', {}).get('completed_crossings')} "
                 f"of {chosen.get('initial_population')} in {door_plan.get('timings_ms')} ms")
    gas = http.post("/api/venues/building-v2/door-plan", json={"hazards": [
        {"id": "smoke-gas", "type": "GAS", "position": {"x": 20, "y": 14}, "source": "simulated"}]})
    gas_doors = {d["id"]: d for d in (gas.json().get("doors", []) if gas.status_code == 200 else [])}
    check.record("POST door-plan GAS in HALL (servo locked, nothing switched)",
                 gas.status_code == 200 and gas_doors.get("D4", {}).get("locked") is True
                 and not any(d["decided_by"] == "door_planner" for d in gas_doors.values()),
                 f"D4 decided_by={gas_doors.get('D4', {}).get('decided_by')}")
    bad = http.post("/api/venues/building-v2/door-plan", json={"hazards": [
        {"id": "x", "type": "FIRE", "position": {"x": 99, "y": 99}, "source": "simulated"}]})
    check.record("POST door-plan outside building -> 422 outside_building",
                 bad.status_code == 422 and bad.json().get("detail", {}).get("code") == "outside_building", str(bad.status_code))

    # 1c. Camera twin with a synthetic top-down still (fixture cards; no provider call)
    image = (1000, 600)
    # Fiducials at (-2.5..42.5, -2.5..26.5) m mapped linearly onto the still, north up.
    def to_px(x: float, y: float) -> tuple[float, float]:
        return (50 + (x + 2.5) / 45 * 900, 550 - (y + 2.5) / 29 * 500)
    corners = {"TL": to_px(-2.5, 26.5), "TR": to_px(42.5, 26.5), "BR": to_px(42.5, -2.5), "BL": to_px(-2.5, -2.5)}
    cal = http.post("/api/venues/building-v2/camera/calibration",
                    json={"corners_px": {k: list(v) for k, v in corners.items()}, "image_size": list(image)})
    cal_json = cal.json() if cal.status_code == 200 else {}
    check.record("POST camera calibration (4 clicked corners)", cal.status_code == 200
                 and cal_json.get("reprojection_error_m", 1) < 0.01, f"error={cal_json.get('reprojection_error_m')}")
    lobby_px = to_px(20, 4)
    point = [round(lobby_px[1] / image[1] * 1000), round(lobby_px[0] / image[0] * 1000)]
    read = http.post("/api/venues/building-v2/camera/hazard-read", json={
        "capture_id": f"smoke-{int(time.time())}", "timestamp_iso": datetime.now(timezone.utc).isoformat(),
        "dimensions": list(image), "calibration_id": cal_json.get("calibration_id"), "mode": "fixture",
        "fixture_cards": [{"type": "FIRE", "point": point, "box_2d": [point[0] - 15, point[1] - 15, point[0] + 15, point[1] + 15]}],
    })
    read_json = read.json() if read.status_code == 200 else {}
    cards = read_json.get("candidates", [])
    check.record("POST camera hazard-read (fixture card -> Lobby)", read.status_code == 200 and read_json.get("provenance") == "fixture"
                 and len(cards) == 1 and cards[0].get("zone_id") == "LOBBY", f"status={read.status_code} cards={len(cards)}")
    forged = [{"id": f"cam-{cards[0]['candidate_id']}" if cards else "cam-x", "type": "FIRE", "position": {"x": 20, "y": 4},
               "source": "camera", "proposal_id": read_json.get("read_id")}]
    refused = http.post("/api/venues/building-v2/door-plan", json={"hazards": forged})
    check.record("POST door-plan with unconfirmed camera card -> 422",
                 refused.status_code == 422 and refused.json().get("detail", {}).get("code") == "unconfirmed_camera_hazard",
                 str(refused.status_code))
    confirm = http.post(f"/api/venues/building-v2/camera/reads/{read_json.get('read_id')}/confirm",
                        json={"candidate_ids": [c["candidate_id"] for c in cards]})
    confirmed = confirm.json().get("hazards", []) if confirm.status_code == 200 else []
    planned = http.post("/api/venues/building-v2/door-plan", json={"hazards": confirmed})
    check.record("POST confirm + door-plan with confirmed camera card", confirm.status_code == 200 and planned.status_code == 200
                 and any(e["id"] == "E1" and not e["safe"] for e in planned.json().get("exits", [])),
                 f"confirm={confirm.status_code} plan={planned.status_code}")

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
    breakdown = hz.get("boundary_breakdown") or {}
    check.record("hazard boundary_breakdown (B1/B2 sum to crossings)",
                 set(breakdown) == {"B1", "B2"} and sum(breakdown.values()) == hz.get("completed_crossings"),
                 json.dumps(breakdown))
    odd = http.post("/api/hazard/simulate", json={"alternative_id": "KEEP_CURRENT",
                                                  "events": [{"element_id": "P1", "close_at_s": 7}]})
    check.record("hazard odd close time → invalid_close_time",
                 odd.status_code == 422 and odd.json().get("detail", {}).get("code") == "invalid_close_time",
                 str(odd.status_code))
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

    # 7b. Reset for next judge: close P3 again, arrival confirmed by the endpoint report
    if hardware_mode == "simulator":
        reset_gate = http.post("/api/hardware/reset-gate")
        status = reset_gate.json().get("status") if reset_gate.status_code == 200 else reset_gate.text[:80]
        check.record("POST hardware/reset-gate", reset_gate.status_code == 200
                     and status in ("CLOSE_ACKNOWLEDGED", "ALREADY_CLOSED"), f"{reset_gate.status_code} {status}")
        closed = wait_for(lambda: snapshot().get("physical_gate_state") == "CLOSED", 15)
        check.record("reset-gate arrival observed (CLOSED)", bool(closed),
                     f"physical_gate_state={snapshot().get('physical_gate_state')}")

    # 8. Back to baseline
    ctx = context()
    final_reset = http.post(f"/api/scenarios/{SCENARIO}/commands", json={
        "type": "RESET_SCENARIO", "expected_context": ctx,
        "expected_scenario_revision": ctx["scenario_revision"], "idempotency_key": f"smoke-reset-{uuid4().hex}"})
    check.record("POST commands RESET_SCENARIO (cleanup)", final_reset.status_code == 200, str(final_reset.status_code))

    # 9. Demo v2: incident, virtual doors, fail-safe, phone signs
    incident_checks(http, base, check)

    failed = [name for name, ok, _ in check.rows if not ok]
    print(f"\n{len(check.rows) - len(failed)}/{len(check.rows)} connection checks passed")
    if failed:
        print("Failed: " + "; ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
