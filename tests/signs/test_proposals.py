"""Phone hazard proposals: a phone only proposes; the operator (loopback) confirms or rejects; limits hold."""
import asyncio
import json

import pytest

from backend.app.signs.proposals import (
    MAX_PENDING, MAX_PER_INVITE_PER_WINDOW, PENDING_TTL_SECONDS, ProposalError, ProposalQueue,
)
from backend.app.signs.routes import proposal_event_stream
from backend.app.signs.views import interior_point
from backend.app.venues.model import Point2, VenueV2, load_building_v2
from backend.app.venues.registry import venue_registry
from tests.signs.conftest import HOME, PHONE, VITE_ORIGIN, Clock, make_client, mint, plan_with, redeem

FIRE_LOBBY = {"type": "FIRE", "zone_id": "LOBBY"}


@pytest.fixture
async def proposer(app, local):
    """A phone that scanned the hazard-proposal QR."""
    async with make_client(app, PHONE) as client:
        await redeem(client, await mint(local, scope="hazard:propose"))
        yield client


async def test_the_proposer_sees_rooms_and_only_its_own_proposals(proposer, app, local):
    state = (await proposer.get("/api/public/hazard-proposals")).json()
    assert state["venue_id"] == "building-v2" and state["active"] is True and state["mine"] == []
    assert {"id": "LOBBY", "name": "Lobby"} in state["rooms"] and state["hazard_types"][0] == "FIRE"
    assert state["limits"] == {"min_interval_seconds": 10.0, "max_pending_per_phone": 2}
    created = await proposer.post("/api/public/hazard-proposals", json=FIRE_LOBBY)
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "pending" and body["room"] == "Lobby" and set(body) == {
        "proposal_id", "type", "room", "position", "status", "created_at", "decided_at"}
    assert [p["proposal_id"] for p in (await proposer.get("/api/public/hazard-proposals")).json()["mine"]] == [body["proposal_id"]]
    async with make_client(app, PHONE) as other:  # a second phone scanning the same QR has its own list
        await redeem(other, await mint(local, scope="hazard:propose"))
        assert (await other.get("/api/public/hazard-proposals")).json()["mine"] == []


async def test_rate_limits_per_phone(proposer, clock):
    assert (await proposer.post("/api/public/hazard-proposals", json=FIRE_LOBBY)).status_code == 201
    fast = await proposer.post("/api/public/hazard-proposals", json=FIRE_LOBBY)
    assert fast.status_code == 429 and fast.json()["detail"] == {"code": "rate_limited", "retry_after_seconds": 10}
    assert fast.headers["retry-after"] == "10"
    clock.advance(11)
    assert (await proposer.post("/api/public/hazard-proposals", json={"type": "SMOKE", "zone_id": "HALL"})).status_code == 201
    clock.advance(11)
    third = await proposer.post("/api/public/hazard-proposals", json=FIRE_LOBBY)
    assert third.status_code == 429 and third.json()["detail"]["code"] == "too_many_pending"


async def test_bad_requests_from_a_phone(proposer, local):
    assert (await proposer.post("/api/public/hazard-proposals", json={"type": "FIRE", "zone_id": "MARS"})).json()["detail"]["code"] == "unknown_room"
    assert (await proposer.post("/api/public/hazard-proposals", json={"type": "LAVA", "zone_id": "LOBBY"})).status_code == 422
    assert (await proposer.post("/api/public/hazard-proposals", json={**FIRE_LOBBY, "venue_id": "home-flat"})).status_code == 422
    venue_registry().save_venue(VenueV2.model_validate(HOME), {"name": "Test flat"})
    await plan_with(local, venue_id="home-flat")
    inactive = await proposer.post("/api/public/hazard-proposals", json=FIRE_LOBBY)
    assert inactive.status_code == 409 and inactive.json()["detail"]["code"] == "venue_not_active"
    assert (await proposer.get("/api/public/hazard-proposals")).json()["active"] is False


async def test_a_sign_phone_cannot_propose_and_a_proposer_cannot_decide(app, local, proposer):
    async with make_client(app, PHONE) as sign_phone:
        await redeem(sign_phone, await mint(local, exit_id="E1"))
        assert (await sign_phone.post("/api/public/hazard-proposals", json=FIRE_LOBBY)).status_code == 403
    proposal = (await proposer.post("/api/public/hazard-proposals", json=FIRE_LOBBY)).json()
    for path in (f"/api/signs/proposals/{proposal['proposal_id']}/confirm", f"/api/signs/proposals/{proposal['proposal_id']}/reject"):
        assert (await proposer.post(path)).status_code == 403
    assert (await proposer.get("/api/signs/proposals")).status_code == 403
    async with make_client(app, PHONE, guarded=False) as unguarded:  # even past the guard, the route refuses
        assert (await unguarded.post(f"/api/signs/proposals/{proposal['proposal_id']}/confirm")).json()["detail"]["code"] == "loopback_only"
    vite = await local.post(f"/api/signs/proposals/{proposal['proposal_id']}/confirm", headers=VITE_ORIGIN)
    assert vite.status_code == 403
    assert (await local.get("/api/signs/proposals")).json()["pending"][0]["status"] == "pending"


async def test_operator_confirm_yields_a_simulated_hazard_the_incident_plans(proposer, local):
    before = (await local.get("/api/public/signs/building-v2?exit=E1")).json()
    proposal = (await proposer.post("/api/public/hazard-proposals", json=FIRE_LOBBY)).json()
    listed = (await local.get("/api/signs/proposals")).json()
    [pending] = listed["pending"]
    assert pending["zone_id"] == "LOBBY" and pending["venue_id"] == "building-v2" and pending["source"] == "phone_proposal"
    assert len(pending["phone"]) == 6 and (await local.get("/api/signs/status")).json()["pending_proposals"] == 1
    assert before["exits"][0]["lamp"] is None  # nothing changed on a proposal alone
    confirmed = await local.post(f"/api/signs/proposals/{proposal['proposal_id']}/confirm")
    assert confirmed.status_code == 200
    hazard = confirmed.json()["hazard"]
    assert hazard["source"] == "simulated" and hazard["type"] == "FIRE" and hazard["zone_id"] == "LOBBY"
    assert hazard["proposal_id"] == proposal["proposal_id"] and hazard["id"].startswith("phone-")
    assert load_building_v2().locate_zone(hazard["position"]["x"], hazard["position"]["y"]) == "LOBBY"
    await plan_with(local, hazard)  # what the presenter does: add it to the twin's hazards
    after = (await local.get("/api/public/signs/building-v2?exit=E1")).json()
    assert after["status"] == "incident" and after["exits"][0]["lamp"] == "red_x"
    again = await local.post(f"/api/signs/proposals/{proposal['proposal_id']}/confirm")
    assert again.status_code == 409 and again.json()["detail"] == {"code": "proposal_not_pending", "status": "confirmed"}
    assert (await proposer.get("/api/public/hazard-proposals")).json()["mine"][0]["status"] == "confirmed"


async def test_operator_reject_and_unknown_ids(proposer, local):
    proposal = (await proposer.post("/api/public/hazard-proposals", json=FIRE_LOBBY)).json()
    rejected = await local.post(f"/api/signs/proposals/{proposal['proposal_id']}/reject")
    assert rejected.json()["proposal"]["status"] == "rejected"
    assert (await proposer.get("/api/public/hazard-proposals")).json()["mine"][0]["status"] == "rejected"
    assert (await local.post("/api/signs/proposals/pp-0000000000/confirm")).status_code == 404
    assert (await local.post("/api/signs/proposals/not-an-id/confirm")).status_code == 422
    assert (await local.post("/api/signs/proposals/pp-0000000000%2F..%2Fx/confirm")).status_code != 200


async def test_confirm_refuses_a_proposal_for_a_venue_that_is_no_longer_on_screen(proposer, local):
    proposal = (await proposer.post("/api/public/hazard-proposals", json=FIRE_LOBBY)).json()
    venue_registry().save_venue(VenueV2.model_validate(HOME), {"name": "Test flat"})
    await plan_with(local, venue_id="home-flat")
    response = await local.post(f"/api/signs/proposals/{proposal['proposal_id']}/confirm")
    assert response.status_code == 409 and response.json()["detail"]["code"] == "venue_not_active"


async def test_pending_proposals_expire(proposer, local, clock):
    proposal = (await proposer.post("/api/public/hazard-proposals", json=FIRE_LOBBY)).json()
    clock.advance(PENDING_TTL_SECONDS + 1)
    response = await local.post(f"/api/signs/proposals/{proposal['proposal_id']}/confirm")
    assert response.status_code == 409 and response.json()["detail"]["status"] == "expired"
    assert (await local.get("/api/signs/proposals")).json()["recent"][0]["status"] == "expired"


def test_queue_bounds_overall_and_per_qr():
    clock = Clock()
    queue = ProposalQueue(clock=clock.monotonic)
    for i in range(MAX_PENDING):
        queue.submit(venue_id="building-v2", hazard_type="FIRE", zone_id="LOBBY", room_name="Lobby",
                     device_id=f"d{i}", invite_id=f"i{i}")
    with pytest.raises(ProposalError) as full:
        queue.submit(venue_id="building-v2", hazard_type="FIRE", zone_id="LOBBY", room_name="Lobby",
                     device_id="new", invite_id="new")
    assert (full.value.code, full.value.status) == ("proposal_queue_full", 503)
    shared = ProposalQueue(clock=clock.monotonic)
    for i in range(MAX_PER_INVITE_PER_WINDOW):
        proposal = shared.submit(venue_id="v", hazard_type="FIRE", zone_id="Z", room_name="Z", device_id=f"d{i}",
                                 invite_id="one-qr")
        shared.decide(proposal.proposal_id, "rejected")
    with pytest.raises(ProposalError) as limited:
        shared.submit(venue_id="v", hazard_type="FIRE", zone_id="Z", room_name="Z", device_id="late", invite_id="one-qr")
    assert limited.value.code == "rate_limited" and limited.value.retry_after == 600
    clock.advance(601)
    shared.submit(venue_id="v", hazard_type="FIRE", zone_id="Z", room_name="Z", device_id="late", invite_id="one-qr")


async def test_operator_stream_announces_new_proposals(service):
    stream = proposal_event_stream(service, poll_seconds=0.005, ping_seconds=0.02)
    assert await stream.__anext__() == "retry: 3000\n\n"
    first = await asyncio.wait_for(stream.__anext__(), 1)
    assert first.startswith("event: proposals\n") and json.loads(first.split("data: ", 1)[1])["pending"] == []
    assert await asyncio.wait_for(stream.__anext__(), 1) == ": ping\n\n"
    service.proposals.submit(venue_id="building-v2", hazard_type="WATER", zone_id="HALL", room_name="Hall",
                             device_id="d", invite_id="i")
    update = json.loads((await asyncio.wait_for(stream.__anext__(), 1)).split("data: ", 1)[1])
    assert update["pending"][0]["type"] == "WATER"
    await stream.aclose()


def test_interior_point_lands_in_its_own_room_for_every_room():
    for venue in (load_building_v2(), VenueV2.model_validate(HOME)):
        for zone in venue.zones:
            point = interior_point(venue, zone.id)
            assert point is not None and venue.locate_zone(*point) == zone.id, (venue.venue_id, zone.id)


def test_interior_point_handles_an_l_shaped_room_whose_centroid_is_outside():
    l_shape: list[Point2] = [(0, 0), (10, 0), (10, 1), (1, 1), (1, 10), (0, 10)]
    venue = load_building_v2().model_copy(update={"zones": [
        load_building_v2().zones[0].model_copy(update={"id": "ELL", "polygon": l_shape})]})
    x, y = interior_point(venue, "ELL")
    assert venue.locate_zone(x, y) == "ELL" and (x <= 1 or y <= 1)
    assert interior_point(venue, "NOPE") is None


# -- tap anywhere on the floor plan -----------------------------------------------------------------------------------

async def test_the_proposer_state_carries_venue_geometry_and_nothing_else(proposer):
    state = (await proposer.get("/api/public/hazard-proposals")).json()
    plan, venue = state["plan"], load_building_v2()
    assert set(plan) == {"extent", "rooms", "doors", "exits"} and plan["extent"] == list(venue.extent)
    assert [set(r) for r in plan["rooms"]] == [{"id", "name", "polygon"}] * len(venue.zones)
    assert plan["rooms"][0]["polygon"] == [list(p) for p in venue.zones[0].polygon]
    assert {tuple(sorted(d)) for d in plan["doors"]} == {("id", "position", "width")} and len(plan["doors"]) == len(venue.doors)
    assert {tuple(sorted(x)) for x in plan["exits"]} == {("id", "kind", "name", "position")}
    assert {x["kind"] for x in plan["exits"]} <= {"door", "stair", "window"}
    text = json.dumps(plan)
    for leaked in ("default_state", "planner_can_open", "actuation", "occupants", "capacity", "throughput", "hash", "reason"):
        assert leaked not in text


async def test_a_tapped_point_resolves_to_its_room(proposer, local):
    venue = load_building_v2()
    x, y = interior_point(venue, "ROOM_A")
    created = await proposer.post("/api/public/hazard-proposals", json={"type": "SMOKE", "position": {"x": x + 0.37, "y": y - 0.21}})
    assert created.status_code == 201
    body = created.json()
    assert body["room"] == "Room A" or body["room"] == venue.zone("ROOM_A").name
    assert body["position"] == {"x": round(x + 0.37, 2), "y": round(y - 0.21, 2)}
    [pending] = (await local.get("/api/signs/proposals")).json()["pending"]
    assert pending["zone_id"] == "ROOM_A"
    mine = (await proposer.get("/api/public/hazard-proposals")).json()["mine"]
    assert mine[0]["position"] == body["position"]


async def test_a_point_outside_every_room_is_refused(proposer, local):
    for point in ({"x": -5, "y": 3}, {"x": 500, "y": 500}, {"x": 20, "y": 30}):
        response = await proposer.post("/api/public/hazard-proposals", json={"type": "FIRE", "position": point})
        assert response.status_code == 422 and response.json()["detail"]["code"] == "outside_building", point
    assert (await local.get("/api/signs/proposals")).json()["pending"] == []
    for bad in ({"x": "nan", "y": 1}, {"x": 1}, {"x": 1e9, "y": 1}, {"x": 1, "y": 1, "z": 2}):
        assert (await proposer.post("/api/public/hazard-proposals", json={"type": "FIRE", "position": bad})).status_code == 422
    assert (await proposer.post("/api/public/hazard-proposals", json={"type": "FIRE"})).status_code == 422


async def test_a_point_on_a_wall_is_refused_and_a_mismatched_room_is_too(proposer):
    wall = await proposer.post("/api/public/hazard-proposals", json={"type": "FIRE", "position": {"x": 12, "y": 14}})
    assert wall.status_code == 422 and wall.json()["detail"]["code"] == "outside_building"
    x, y = interior_point(load_building_v2(), "LOBBY")
    mismatch = await proposer.post("/api/public/hazard-proposals", json={"type": "FIRE", "zone_id": "HALL", "position": {"x": x, "y": y}})
    assert mismatch.status_code == 422 and mismatch.json()["detail"]["code"] == "zone_mismatch"
    both = await proposer.post("/api/public/hazard-proposals", json={"type": "FIRE", "zone_id": "LOBBY", "position": {"x": x, "y": y}})
    assert both.status_code == 201


async def test_the_confirmed_hazard_keeps_the_judges_exact_position(proposer, local, clock):
    venue = load_building_v2()
    x, y = interior_point(venue, "ROOM_A")
    tap = {"x": round(x + 0.37, 2), "y": round(y - 0.21, 2)}
    proposal = (await proposer.post("/api/public/hazard-proposals", json={"type": "GAS", "position": tap})).json()
    hazard = (await local.post(f"/api/signs/proposals/{proposal['proposal_id']}/confirm")).json()["hazard"]
    assert hazard["position"] == tap and hazard["zone_id"] == "ROOM_A" and hazard["proposal_id"] == proposal["proposal_id"]
    assert hazard["position"] != {"x": x, "y": y}
    clock.advance(11)
    room_only = (await proposer.post("/api/public/hazard-proposals", json={"type": "FIRE", "zone_id": "LOBBY"}))
    assert room_only.json()["position"] is None
