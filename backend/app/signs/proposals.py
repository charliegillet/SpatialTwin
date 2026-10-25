"""Phone hazard proposals: a bounded, rate-limited queue that only the operator (loopback) can decide.

Same shape as the camera twin (backend/app/venues/camera.py): a phone *proposes* a hazard (type + room); nothing
changes until the operator confirms it on the laptop, and the confirmation hands back a normal simulated
HazardInput that the presenter adds to the twin like any other hazard. A phone can never confirm, reject, list
other phones' proposals or name another venue (the venue comes from its token).

Limits (all in memory, for one demo laptop): per phone at most ``MAX_PENDING_PER_DEVICE`` pending and one proposal
every ``MIN_INTERVAL_SECONDS``; per QR (all phones that scanned it) at most ``MAX_PER_INVITE_PER_WINDOW`` per
``WINDOW_SECONDS``; at most ``MAX_PENDING`` pending overall (new ones are refused, never silently dropped).
Pending proposals expire after ``PENDING_TTL_SECONDS`` so a forgotten one cannot be confirmed much later.
Everything runs on the event-loop thread (async routes only), so there is no locking.
"""
from __future__ import annotations

import math
import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from typing import Callable, Deque, Dict, List, Literal, Optional, Tuple
from uuid import uuid4

from backend.app.incident.events import now_iso

ProposalStatus = Literal["pending", "confirmed", "rejected", "expired"]

MAX_PENDING = 12
MAX_PENDING_PER_DEVICE = 2
MIN_INTERVAL_SECONDS = 10.0
WINDOW_SECONDS = 600.0
MAX_PER_INVITE_PER_WINDOW = 20
PENDING_TTL_SECONDS = 600.0
MAX_DECIDED_KEPT = 40
MAX_TRACKED_CLIENTS = 256


class ProposalError(Exception):
    def __init__(self, code: str, status: int, retry_after: Optional[int] = None):
        super().__init__(code)
        self.code = code
        self.status = status
        self.retry_after = retry_after


@dataclass
class Proposal:
    proposal_id: str
    venue_id: str
    type: str
    zone_id: str
    room_name: str
    device_id: str
    invite_id: str
    created_at: str
    created_mono: float
    position: Optional[Tuple[float, float]] = None  # exact tap in metres; None = "somewhere in the room"
    status: ProposalStatus = "pending"
    decided_at: Optional[str] = None
    hazard_id: Optional[str] = None

    def public(self) -> Dict[str, object]:
        """What the proposing phone may see: no device ids, no other phones."""
        return {"proposal_id": self.proposal_id, "type": self.type, "room": self.room_name,
                "position": {"x": self.position[0], "y": self.position[1]} if self.position else None,
                "status": self.status, "created_at": self.created_at, "decided_at": self.decided_at}

    def operator(self) -> Dict[str, object]:
        return {**self.public(), "venue_id": self.venue_id, "zone_id": self.zone_id,
                "phone": self.device_id[:6], "hazard_id": self.hazard_id, "source": "phone_proposal"}


class ProposalQueue:
    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self.clock = clock
        self._items: "OrderedDict[str, Proposal]" = OrderedDict()
        self._last_by_device: "OrderedDict[str, float]" = OrderedDict()
        self._by_invite: "OrderedDict[str, Deque[float]]" = OrderedDict()
        self.version = 0  # bumps on every change; the operator SSE compares it

    # -- bookkeeping -------------------------------------------------------------------------------------------

    def _changed(self) -> None:
        self.version += 1

    def _expire(self) -> None:
        cutoff = self.clock() - PENDING_TTL_SECONDS
        changed = False
        for item in self._items.values():
            if item.status == "pending" and item.created_mono < cutoff:
                item.status, item.decided_at = "expired", now_iso()
                changed = True
        decided = [pid for pid, item in self._items.items() if item.status != "pending"]
        for pid in decided[:max(0, len(decided) - MAX_DECIDED_KEPT)]:
            del self._items[pid]
        if changed:
            self._changed()

    @staticmethod
    def _remember(table: "OrderedDict", key: str, value) -> None:
        table[key] = value
        table.move_to_end(key)
        while len(table) > MAX_TRACKED_CLIENTS:
            table.popitem(last=False)

    def pending(self) -> List[Proposal]:
        self._expire()
        return [item for item in self._items.values() if item.status == "pending"]

    # -- phone side --------------------------------------------------------------------------------------------

    def submit(self, *, venue_id: str, hazard_type: str, zone_id: str, room_name: str, device_id: str,
               invite_id: str, position: Optional[Tuple[float, float]] = None) -> Proposal:
        self._expire()
        now = self.clock()
        last = self._last_by_device.get(device_id)
        if last is not None and now - last < MIN_INTERVAL_SECONDS:
            raise ProposalError("rate_limited", 429, math.ceil(MIN_INTERVAL_SECONDS - (now - last)))
        window = self._by_invite.get(invite_id) or deque()
        while window and now - window[0] >= WINDOW_SECONDS:
            window.popleft()
        if len(window) >= MAX_PER_INVITE_PER_WINDOW:
            raise ProposalError("rate_limited", 429, math.ceil(WINDOW_SECONDS - (now - window[0])))
        pending = self.pending()
        if sum(1 for item in pending if item.device_id == device_id) >= MAX_PENDING_PER_DEVICE:
            raise ProposalError("too_many_pending", 429)
        if len(pending) >= MAX_PENDING:
            raise ProposalError("proposal_queue_full", 503)
        proposal = Proposal(proposal_id=f"pp-{uuid4().hex[:10]}", venue_id=venue_id, type=hazard_type,
                            zone_id=zone_id, room_name=room_name, device_id=device_id, invite_id=invite_id,
                            created_at=now_iso(), created_mono=now, position=position)
        self._items[proposal.proposal_id] = proposal
        self._remember(self._last_by_device, device_id, now)
        window.append(now)
        self._remember(self._by_invite, invite_id, window)
        self._changed()
        return proposal

    def mine(self, device_id: str) -> List[Proposal]:
        self._expire()
        return [item for item in self._items.values() if item.device_id == device_id]

    # -- operator side -----------------------------------------------------------------------------------------

    def get(self, proposal_id: str) -> Optional[Proposal]:
        self._expire()
        return self._items.get(proposal_id)

    def decide(self, proposal_id: str, status: Literal["confirmed", "rejected"],
               hazard_id: Optional[str] = None) -> Proposal:
        item = self.get(proposal_id)
        if item is None:
            raise ProposalError("unknown_proposal", 404)
        if item.status != "pending":
            raise ProposalError("proposal_not_pending", 409)
        item.status, item.decided_at, item.hazard_id = status, now_iso(), hazard_id
        self._changed()
        return item

    def view(self) -> Dict[str, object]:
        self._expire()
        items = list(self._items.values())
        return {"version": self.version,
                "pending": [item.operator() for item in items if item.status == "pending"],
                "recent": [item.operator() for item in reversed(items) if item.status != "pending"]}

    def clear(self) -> None:
        self._items.clear()
        self._last_by_device.clear()
        self._by_invite.clear()
        self._changed()
