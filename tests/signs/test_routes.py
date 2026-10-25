"""Mint (loopback only), the QR entry, the public sign view derived from the incident plan, and its SSE."""
import json

import pytest
from starlette.requests import Request

from backend.app.signs.routes import build_signs_router, sign_event_stream
from backend.app.venues.model import VenueV2, get_venue, load_building_v2
from backend.app.venues.registry import venue_registry
from tests.signs.conftest import (
    HOME, LAN_IP, LOBBY_FIRE, LOBBY_GAS, LOOPBACK, PHONE, VITE_ORIGIN, make_client, mint, plan_with, redeem, token_of,
)


# -- mint ------------------------------------------------------------------------------------------------------

async def test_mint_returns_a_lan_url_and_an_svg_qr(local, probe_result):
    minted = await mint(local, exit_id="E1")
    assert minted["url"].startswith(f"http://{LAN_IP}:8000/s/v1.sign.building-v2.E1.")
    assert minted["qr_svg"].startswith("<svg") and 'aria-label="Exit sign E1"' in minted["qr_svg"]
    assert (minted["exit_id"], minted["exit_name"], minted["venue_id"]) == ("E1", "South exit", "building-v2")
    assert minted["lan"] == {"base_url": f"http://{LAN_IP}:8000", "source": "detected", "listening_on_lan": True,
                             "warning": None}
    assert probe_result["calls"] == [(LAN_IP, 8000)] and minted["ttl_seconds"] == 4 * 3600


async def test_mint_warns_when_the_server_only_listens_on_loopback(local, probe_result):
    probe_result["value"] = False
    lan = (await mint(local))["lan"]
    assert lan["listening_on_lan"] is False and "--host 0.0.0.0" in lan["warning"] and "vite --host" in lan["warning"]


async def test_mint_falls_back_to_loopback_with_a_warning_when_no_lan_address(local, service):
    service.lan_ip = lambda: None
    minted = await mint(local)
    assert minted["url"].startswith("http://127.0.0.1:8000/s/") and minted["lan"]["source"] == "fallback"
    assert "SPATIALTWIN_SIGN_BASE_URL" in minted["lan"]["warning"]


async def test_mint_base_url_from_request_or_env(local, monkeypatch):
    assert (await mint(local, base_url="http://10.0.0.7:9000"))["url"].startswith("http://10.0.0.7:9000/s/")
    monkeypatch.setenv("SPATIALTWIN_SIGN_BASE_URL", "http://demo-laptop.local")
    lan = (await mint(local))["lan"]
    assert lan["base_url"] == "http://demo-laptop.local:8000" and lan["source"] == "env"
    for bad in ("ftp://x", "http://x/path", "http://user@x", "javascript:alert(1)", "http://x:99999"):
        response = await local.post("/api/signs/tokens", json={"scope": "sign:read", "base_url": bad})
        assert response.status_code == 422 and response.json()["detail"]["code"] == "invalid_base_url", bad


async def test_mint_validates_venue_exit_and_scope(local):
    async def code(**body):
        response = await local.post("/api/signs/tokens", json=body)
        return response.status_code, response.json()["detail"]["code"]

    assert await code(scope="sign:read", venue_id="no-such-venue") == (404, "unknown_venue")
    assert await code(scope="sign:read", exit_id="E9") == (422, "unknown_exit")
    assert await code(scope="hazard:propose", exit_id="E1") == (422, "exit_not_allowed_for_scope")
    response = await local.post("/api/signs/tokens", json={"scope": "admin"})
    assert response.status_code == 422
    response = await local.post("/api/signs/tokens", json={"scope": "sign:read", "ttl_seconds": 10 * 3600})
    assert response.status_code == 422


async def test_mint_refuses_non_loopback_and_the_vite_proxy(app):
    async with make_client(app, PHONE, guarded=False) as remote:
        response = await remote.post("/api/signs/tokens", json={"scope": "sign:read"})
        assert response.status_code == 403 and response.json()["detail"]["code"] == "loopback_only"
    async with make_client(app, LOOPBACK) as proxied:
        response = await proxied.post("/api/signs/tokens", json={"scope": "sign:read"}, headers=VITE_ORIGIN)
        assert response.status_code == 403 and response.json()["detail"]["code"] == "loopback_only"
        ok = await proxied.post("/api/signs/tokens", json={"scope": "sign:read"},
                                headers={"Origin": "http://localhost:5173", "Referer": "http://localhost:5173/"})
        assert ok.status_code == 200


async def test_mint_defaults_to_the_incident_venue(local):
    venue_registry().save_venue(VenueV2.model_validate(HOME), {"name": "Test flat"})
    await plan_with(local, venue_id="home-flat")
    minted = await mint(local, exit_id="E3")
    assert minted["venue_id"] == "home-flat" and minted["exit_name"] == "Escape window"


# -- /s/<token> ------------------------------------------------------------------------------------------------

async def test_redeem_sets_a_strict_httponly_device_cookie_and_redirects(local, phone, service):
    minted = await mint(local, exit_id="E2", ttl_seconds=3600)
    response = await redeem(phone, minted)
    assert response.headers["location"] == "/sign.html?venue=building-v2&exit=E2"
    assert response.headers["cache-control"] == "no-store" and response.headers["referrer-policy"] == "no-referrer"
    cookie = response.headers["set-cookie"]
    attributes = {part.strip().split("=")[0].lower(): part.strip() for part in cookie.split(";")}
    assert "httponly" in attributes and attributes["samesite"].lower() == "samesite=strict"
    assert attributes["path"] == "Path=/" and attributes["max-age"] == "Max-Age=3600" and "secure" not in attributes
    value = cookie.split(";")[0].split("=", 1)[1]
    assert value != token_of(minted)
    device = service.signer.verify(value, "sign:read")
    assert device.parent == minted["token_id"] and device.exit_id == "E2"


async def test_redeem_propose_token_goes_to_the_propose_mode(local, phone):
    minted = await mint(local, scope="hazard:propose")
    response = await redeem(phone, minted)
    assert response.headers["location"] == "/sign.html?venue=building-v2&mode=propose"
    assert response.headers["set-cookie"].startswith("st_propose=")


async def test_redeem_rejects_forged_and_expired_links_with_a_page_not_a_cookie(local, phone, clock):
    minted = await mint(local, ttl_seconds=600)
    forged = await phone.get("/s/" + token_of(minted)[:-3] + "AAA")
    assert forged.status_code == 403 and "not valid" in forged.text and "set-cookie" not in forged.headers
    clock.advance(601)
    expired = await phone.get(f"/s/{token_of(minted)}")
    assert expired.status_code == 410 and "expired" in expired.text and "set-cookie" not in expired.headers
    assert token_of(minted) not in expired.text


# -- public sign state from the incident ------------------------------------------------------------------------

def plan_exit(state, exit_id):
    return next(x for x in state["plan"]["exits"] if x["id"] == exit_id)


async def test_before_any_plan_the_signs_are_normal_and_unlit(local):
    body = (await local.get("/api/public/signs/building-v2")).json()
    assert body["status"] == "normal" and body["simulated"] is True and body["hazards"] == []
    assert [x["exit_id"] for x in body["exits"]] == ["E1", "E2", "E3", "E4"]
    assert all(x["lamp"] is None and x["routed"] is None for x in body["exits"])


async def test_sign_state_follows_the_checked_plan_and_exposes_nothing_else(local, phone):
    incident = await plan_with(local, LOBBY_FIRE)
    await redeem(phone, await mint(local, exit_id="E1"))
    body = (await phone.get("/api/public/signs/building-v2")).json()
    assert set(body) == {"simulated", "venue_id", "venue_name", "status", "plan_revision", "plan_label", "exits",
                         "hazards", "count_label", "expires_at", "server_time"}
    assert body["status"] == "incident" and body["plan_revision"] == incident["plan"]["plan_revision"]
    assert body["hazards"] == [{"type": "FIRE", "room": "Lobby"}] and body["count_label"] == "modeled crossings"
    [e1] = body["exits"]
    assert set(e1) == {"exit_id", "name", "lamp", "routed"}
    assert e1 == {"exit_id": "E1", "name": "South exit", "lamp": plan_exit(incident, "E1")["lamp"],
                  "routed": plan_exit(incident, "E1")["modeled_crossings"]}
    assert e1["lamp"] == "red_x"
    text = json.dumps(body)
    for leaked in ("door_states", "candidate_hash", "reason", "position", "D4", "zone"):
        assert leaked not in text
    everything = (await local.get("/api/public/signs/building-v2")).json()["exits"]
    assert {x["exit_id"]: x["lamp"] for x in everything} == {x["id"]: x["lamp"] for x in incident["plan"]["exits"]}
    assert any(x["lamp"] in ("green", "green_flash") for x in everything)


async def test_gas_lock_shows_static_red(local):
    incident = await plan_with(local, LOBBY_GAS)
    body = (await local.get("/api/public/signs/building-v2?exit=E1")).json()
    assert body["exits"][0]["lamp"] == "red_static" == plan_exit(incident, "E1")["lamp"]
    assert body["hazards"] == [{"type": "GAS", "room": "Lobby"}]


async def test_a_withdrawn_or_invalid_plan_is_unchecked_and_unlit(local, manager):
    await plan_with(local, LOBBY_FIRE)
    manager.plan = manager.plan.model_copy(update={"valid": False})
    body = (await local.get("/api/public/signs/building-v2")).json()
    assert body["status"] == "unchecked" and all(x["lamp"] is None for x in body["exits"])
    manager.plan, manager.plan_error = None, "outside_building"
    assert (await local.get("/api/public/signs/building-v2")).json()["status"] == "unchecked"


async def test_a_sign_for_a_venue_that_is_not_on_screen_is_inactive(local):
    venue_registry().save_venue(VenueV2.model_validate(HOME), {"name": "Test flat"})
    await plan_with(local, {"id": "k", "type": "FIRE", "position": {"x": 7.5, "y": 2.5}, "source": "simulated"},
                    venue_id="home-flat")
    old = (await local.get("/api/public/signs/building-v2")).json()
    assert old["status"] == "inactive" and old["plan_revision"] is None and all(x["lamp"] is None for x in old["exits"])
    home = (await local.get("/api/public/signs/home-flat")).json()
    assert home["status"] == "incident" and home["venue_name"] == "Test flat" and home["hazards"][0]["type"] == "FIRE"


async def test_exit_filter_token_wins_over_query(local, phone):
    await redeem(phone, await mint(local, exit_id="E1"))
    assert [x["exit_id"] for x in (await phone.get("/api/public/signs/building-v2?exit=E3")).json()["exits"]] == ["E1"]
    assert [x["exit_id"] for x in (await local.get("/api/public/signs/building-v2?exit=E3")).json()["exits"]] == ["E3"]
    missing = await local.get("/api/public/signs/building-v2?exit=E9")
    assert missing.status_code == 404 and missing.json()["detail"]["code"] == "unknown_exit"
    assert (await local.get("/api/public/signs/building-v2?exit=e1")).status_code == 422
    assert (await local.get("/api/public/signs/no-such-venue")).json()["detail"]["code"] == "unknown_venue"


async def test_an_all_exits_sign_link_shows_every_exit(local, phone):
    await redeem(phone, await mint(local))
    assert len((await phone.get("/api/public/signs/building-v2")).json()["exits"]) == 4


async def test_revoke_all_cuts_off_phones(local, phone):
    await redeem(phone, await mint(local, exit_id="E1"))
    assert (await phone.get("/api/public/signs/building-v2")).status_code == 200
    assert (await local.post("/api/signs/revoke")).status_code == 200
    assert (await phone.get("/api/public/signs/building-v2")).status_code == 403
    assert (await phone.get("/sign.html")).status_code == 403


# -- SSE ---------------------------------------------------------------------------------------------------------

def parse(frame):
    out = {}
    for line in frame.strip().splitlines():
        key, _, value = line.partition(": ")
        out[key] = value
    return out


async def next_frame(stream, timeout=2.0):
    import asyncio
    return parse(await asyncio.wait_for(stream.__anext__(), timeout))


async def test_sign_stream_pushes_a_confirmed_hazard_heartbeats_and_ends_on_expiry(local, service, manager, clock):
    token, claims = service.signer.mint("sign:read", "building-v2", "E1", ttl_seconds=600)
    stream = sign_event_stream(service, manager, load_building_v2(), "E1", token, "later")
    assert (await stream.__anext__()) == "retry: 3000\n\n"
    first = await next_frame(stream)
    assert first["event"] == "sign" and json.loads(first["data"])["status"] == "normal"
    assert service.stream_count == 1 and service.streams == {"building-v2/E1": 1}
    await plan_with(local, LOBBY_FIRE)
    update = await next_frame(stream)
    assert update["event"] == "sign"
    data = json.loads(update["data"])
    assert data["status"] == "incident" and data["exits"][0]["lamp"] == "red_x" and data["expires_at"] == "later"
    manager.hub.ping_seconds = 0.01
    assert (await next_frame(stream))["event"] == "heartbeat"
    clock.advance(601)
    expired = await next_frame(stream)
    assert expired["event"] == "expired" and json.loads(expired["data"]) == {"code": "token_expired"}
    with pytest.raises(StopAsyncIteration):
        await stream.__anext__()
    assert service.stream_count == 0 and manager.hub._subscribers == []


async def test_sign_stream_only_sends_visible_changes_and_closes_cleanly(local, service, manager):
    stream = sign_event_stream(service, manager, load_building_v2(), "E1", None, None)
    await stream.__anext__()
    await next_frame(stream)
    manager.hub.publish("gate", {"line": "noise"})  # wakes the stream; nothing the sign shows changed
    await plan_with(local, LOBBY_FIRE)
    frame = await next_frame(stream)
    assert frame["event"] == "sign" and json.loads(frame["data"])["exits"][0]["lamp"] == "red_x"
    await stream.aclose()
    assert service.stream_count == 0 and manager.hub._subscribers == []


async def test_events_route_checks_access_and_caps_streams(app, local, phone, service):
    assert (await local.get("/api/public/signs/building-v2/events?exit=E9")).status_code == 404
    service.max_streams = 0
    response = await local.get("/api/public/signs/building-v2/events")
    assert response.status_code == 503 and response.json()["detail"]["code"] == "too_many_signs"
    service.max_streams = 64
    async with make_client(app, PHONE, guarded=False) as stranger:
        assert (await stranger.get("/api/public/signs/building-v2/events")).status_code == 403
    route = next(r for r in build_signs_router(service=service).routes if r.path == "/api/public/signs/{venue_id}/events")
    request = Request({"type": "http", "method": "GET", "path": "/api/public/signs/building-v2/events", "headers": [],
                       "client": LOOPBACK, "query_string": b"", "server": ("127.0.0.1", 8000)})
    response = await route.endpoint(request, "building-v2", "E1")
    assert response.media_type == "text/event-stream" and response.headers["cache-control"] == "no-cache"
    await response.body_iterator.aclose()


async def test_status_counts_streams_and_is_loopback_only(app, local, service, manager):
    stream = sign_event_stream(service, manager, get_venue("building-v2"), None, None, None)
    await stream.__anext__()
    status = (await local.get("/api/signs/status")).json()
    assert status["sign_streams"] == 1 and status["by_sign"] == {"building-v2/*": 1}
    assert status["secret_source"] == "explicit" and status["simulated"] is True
    await stream.aclose()
    async with make_client(app, PHONE, guarded=False) as remote:
        assert (await remote.get("/api/signs/status")).status_code == 403
