"""Fixtures for phone signs: a fake clock, an isolated service and incident, and loopback / LAN / Vite-proxy clients.

``guarded_app`` wraps the app in ``SignAwareGuard``, a copy of main.NetworkGuard with exactly the hook the lead adds
(see docs/plans/contracts/signs.md), plus a StaticFiles mount standing in for frontend/dist, so the whole phone path
(QR -> cookie -> sign page -> assets -> public API) is exercised the way it runs on stage.
"""
import json
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.incident.gates import ControllerConfig
from backend.app.incident.manager import IncidentManager
from backend.app.incident.routes import build_incident_router, set_default_manager
from backend.app.signs import build_signs_router, scoped_access
from backend.app.signs.guard import is_loopback_host
from backend.app.signs.proposals import ProposalQueue
from backend.app.signs.service import SignsService, set_default_service
from backend.app.signs.tokens import TokenSigner

FAST = ControllerConfig(transit_s=0.01, ack_timeout_s=0.02, stall_timeout_s=0.02, heartbeat_timeout_s=0.03)
HOME = json.loads((Path(__file__).parents[1] / "venues" / "fixtures" / "home_flat.json").read_text())
LOBBY_FIRE = {"id": "h0", "type": "FIRE", "position": {"x": 20, "y": 4}, "source": "simulated"}
LOBBY_GAS = {"id": "g0", "type": "GAS", "position": {"x": 20, "y": 4}, "source": "simulated"}
PHONE = ("192.168.8.31", 51000)
LOOPBACK = ("127.0.0.1", 50000)
LAN_IP = "192.168.8.20"
VITE_ORIGIN = {"Origin": "http://192.168.8.20:5173", "Referer": "http://192.168.8.20:5173/"}


class Clock:
    """Wall clock (token expiry) and monotonic clock (rate limits) the tests move by hand."""

    def __init__(self, start: float = 1_800_000_000.0):
        self.wall = start
        self.mono = 1000.0

    def time(self) -> float:
        return self.wall

    def monotonic(self) -> float:
        return self.mono

    def advance(self, seconds: float) -> None:
        self.wall += seconds
        self.mono += seconds


class SignAwareGuard:
    """main.NetworkGuard with the signs hook (the X-API-Token branch is irrelevant here and omitted)."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            client = scope.get("client")
            if not (client and is_loopback_host(client[0])) and scoped_access(scope) is None:
                if scope["type"] == "websocket":
                    await send({"type": "websocket.close", "code": 1008})
                else:
                    await JSONResponse(status_code=403, content={"detail": "remote_access_denied"})(scope, receive, send)
                return
        await self.inner(scope, receive, send)


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def probe_result():
    """What the LAN listening probe answers; a test may set ``probe_result["value"]``."""
    return {"value": True, "calls": []}


@pytest.fixture
def service(clock, probe_result):
    def probe(host, port):
        probe_result["calls"].append((host, port))
        return probe_result["value"]

    s = SignsService(signer=TokenSigner(secret=b"s" * 32, now=clock.time), proposals=ProposalQueue(clock=clock.monotonic),
                     lan_ip=lambda: LAN_IP, probe=probe)
    set_default_service(s)
    yield s
    set_default_service(None)


@pytest.fixture
def manager():
    m = IncidentManager(FAST)
    set_default_manager(m)
    yield m
    set_default_manager(None)


@pytest.fixture
def dist(tmp_path):
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "sign.html").write_text("<!doctype html><title>sign</title>")
    (root / "index.html").write_text("<!doctype html><title>operator app</title>")
    (root / "assets" / "sign-AbC_12-x.js").write_text("console.log('sign')")
    (root / "assets" / "sign-AbC_12-x.css").write_text("body{}")
    (root / "secret.txt").write_text("not for phones")
    return root


@pytest.fixture
def app(service, manager, dist):
    application = FastAPI()
    application.include_router(build_incident_router())
    application.include_router(build_signs_router())
    application.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")
    return application


def make_client(app, peer, guarded=True):
    asgi = SignAwareGuard(app) if guarded else app
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=asgi, client=peer), base_url="http://127.0.0.1:8000")


@pytest.fixture
async def local(app):
    async with make_client(app, LOOPBACK) as c:
        yield c


@pytest.fixture
async def phone(app):
    async with make_client(app, PHONE) as c:
        yield c


async def mint(local, **body):
    response = await local.post("/api/signs/tokens", json={"scope": "sign:read", **body})
    assert response.status_code == 200, response.text
    return response.json()


def token_of(minted):
    return minted["url"].rsplit("/s/", 1)[1]


async def redeem(phone, minted):
    """Scan the QR: returns the redirect response; the phone client keeps the cookie."""
    response = await phone.get(f"/s/{token_of(minted)}")
    assert response.status_code == 303, response.text
    return response


async def plan_with(local, *hazards, venue_id="building-v2"):
    state = (await local.get("/api/incident")).json()
    response = await local.post("/api/incident/hazards", json={
        "venue_id": venue_id, "expected_plan_revision": state["plan_revision"], "hazards": list(hazards)})
    assert response.status_code == 200, response.text
    return response.json()
