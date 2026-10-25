import json
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from backend.app.incident.gates import ControllerConfig
from backend.app.incident.manager import IncidentManager
from backend.app.incident.routes import build_incident_router, set_default_manager

FAST = ControllerConfig(transit_s=0.01, ack_timeout_s=0.02, stall_timeout_s=0.02, heartbeat_timeout_s=0.03)
HOME = json.loads((Path(__file__).parents[1] / "venues" / "fixtures" / "home_flat.json").read_text())

LOBBY_FIRE = {"id": "h0", "type": "FIRE", "position": {"x": 20, "y": 4}, "source": "simulated"}
HALL_FIRE = {"id": "h0", "type": "FIRE", "position": {"x": 20, "y": 14}, "source": "simulated"}


@pytest.fixture
def manager():
    m = IncidentManager(FAST)
    set_default_manager(m)
    yield m
    set_default_manager(None)


@pytest.fixture
async def client(manager):
    app = FastAPI()
    app.include_router(build_incident_router())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def plan_with(client, hazard, venue_id="building-v2"):
    state = (await client.get("/api/incident")).json()
    response = await client.post("/api/incident/hazards", json={
        "venue_id": venue_id, "expected_plan_revision": state["plan_revision"], "hazards": [hazard]})
    assert response.status_code == 200, response.text
    return response.json()


def approve_body(state):
    plan = state["plan"]
    return {"plan_revision": plan["plan_revision"], "candidate_hash": plan["candidate_hash"], "door_states": plan["door_states"]}
