"""Typed request/response models for the sign routes. Field names are the contract in docs/plans/contracts/signs.md.

Public (phone) models carry only what a sign or a proposer needs: no plan internals, door states, reasons,
candidate hashes or hazard coordinates.
"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.app.signs.tokens import DEFAULT_TTL_SECONDS, EXIT_ID_PATTERN, MAX_TTL_SECONDS, MIN_TTL_SECONDS, Scope
from backend.app.venues.model import VENUE_ID_PATTERN

HazardType = Literal["FIRE", "SMOKE", "GAS", "CHEMICAL", "WATER"]
HAZARD_TYPES: List[str] = ["FIRE", "SMOKE", "GAS", "CHEMICAL", "WATER"]
ExitLamp = Literal["green_flash", "green", "red_x", "red_static"]
SignStatus = Literal["normal", "incident", "unchecked", "inactive"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# -- operator (loopback) -------------------------------------------------------------------------------------------

class MintRequest(_Strict):
    scope: Scope
    venue_id: Optional[str] = Field(default=None, pattern=VENUE_ID_PATTERN)  # default: the incident's venue
    exit_id: Optional[str] = Field(default=None, pattern=EXIT_ID_PATTERN)  # sign:read only; None = every exit
    ttl_seconds: int = Field(default=DEFAULT_TTL_SECONDS, ge=MIN_TTL_SECONDS, le=MAX_TTL_SECONDS)
    base_url: Optional[str] = Field(default=None, max_length=300)  # e.g. "http://192.168.8.20:8000"


class LanInfo(_Strict):
    base_url: str
    source: Literal["request", "env", "detected", "fallback"]
    listening_on_lan: Optional[bool]
    warning: Optional[str] = None


class MintResponse(_Strict):
    token_id: str
    scope: Scope
    venue_id: str
    exit_id: Optional[str]
    exit_name: Optional[str]
    url: str
    qr_svg: str
    expires_at: str
    ttl_seconds: int
    lan: LanInfo


# -- phones --------------------------------------------------------------------------------------------------------

class SignExit(_Strict):
    exit_id: str
    name: str
    lamp: Optional[ExitLamp]  # None when there is no checked plan to follow
    routed: Optional[int]  # modeled crossings through this exit in the checked plan


class SignHazard(_Strict):
    type: HazardType
    room: str


class SignState(_Strict):
    simulated: Literal[True] = True
    venue_id: str
    venue_name: str
    status: SignStatus
    plan_revision: Optional[int]
    plan_label: Optional[Literal["primary", "fallback"]] = None
    exits: List[SignExit]
    hazards: List[SignHazard]
    count_label: Literal["modeled crossings"] = "modeled crossings"
    expires_at: Optional[str] = None  # this phone's link expiry (None for the loopback view)
    server_time: str


class ProposalRequest(_Strict):
    type: HazardType
    zone_id: str = Field(pattern=r"^[A-Z0-9_]{1,64}$")


class Room(_Strict):
    id: str
    name: str


class ProposalLimits(_Strict):
    min_interval_seconds: float
    max_pending_per_phone: int


class ProposalPublic(_Strict):
    proposal_id: str
    type: HazardType
    room: str
    status: Literal["pending", "confirmed", "rejected", "expired"]
    created_at: str
    decided_at: Optional[str]


class ProposerState(_Strict):
    simulated: Literal[True] = True
    venue_id: str
    venue_name: str
    active: bool
    rooms: List[Room]
    hazard_types: List[HazardType]
    mine: List[ProposalPublic]
    limits: ProposalLimits
    expires_at: str
    server_time: str
