"""Phone exit signs and phone hazard proposals (no hardware): token minting, the QR entry, public sign state + SSE,
and the operator's proposal queue.

Operator routes (loopback only, re-checked here even though NetworkGuard already blocks phones; a loopback peer whose
Origin/Referer names a LAN host is refused too, which catches a phone browsing through ``vite --host``):

  POST /api/signs/tokens                         -> MintResponse (url + SVG QR + LAN reachability)
  POST /api/signs/revoke                         -> every phone token issued so far stops working
  GET  /api/signs/status                         -> connected sign streams, pending proposals (preflight)
  GET  /api/signs/proposals                      -> {version, pending, recent}
  GET  /api/signs/proposals/events               -> SSE "proposals" (same body) on every change
  POST /api/signs/proposals/{id}/confirm         -> {proposal, hazard}: a simulated HazardInput for the twin
  POST /api/signs/proposals/{id}/reject          -> {proposal}

Phone routes (a valid scoped cookie; see guard.py for the exact allowlist):

  GET  /s/{token}                                -> 303 to /sign.html, sets the HttpOnly SameSite=Strict cookie
  GET  /api/public/signs/{venue_id}[?exit=E1]    -> SignState
  GET  /api/public/signs/{venue_id}/events       -> SSE "sign" (on change), "heartbeat" (~10 s), "expired"
  GET  /api/public/hazard-proposals              -> ProposerState (rooms, my proposals)
  POST /api/public/hazard-proposals              -> 201 ProposalPublic; 429 rate_limited, 409 venue_not_active

Mount (backend/app/main.py, lead), before the frontend StaticFiles mount: ``app.include_router(build_signs_router())``.
Errors are ``{"detail": {"code": "..."}}``; nothing echoes a token.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from html import escape
from typing import Any, AsyncIterator, Callable, Dict, Optional
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Path, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse

from backend.app.incident.events import now_iso
from backend.app.incident.manager import IncidentManager
from backend.app.signs.guard import cookie_values, forwarded_from_remote, is_loopback_host
from backend.app.signs.models import (
    HAZARD_TYPES, LanInfo, MintRequest, MintResponse, ProposalLimits, Plan, ProposalPublic, ProposalRequest, ProposerState,
    Room, SignState,
)
from backend.app.signs.network import DEFAULT_PORT, env_base_url, parse_base_url
from backend.app.signs.proposals import MAX_PENDING_PER_DEVICE, MIN_INTERVAL_SECONDS, ProposalError
from backend.app.signs.qr import qr_svg
from backend.app.signs.service import SignsService, default_service
from backend.app.signs.tokens import COOKIE_NAMES, EXIT_ID_PATTERN, SignClaims, TokenError
from backend.app.signs.views import interior_point, plan_geometry, sign_state, venue_name, zone_at
from backend.app.venues.model import VENUE_ID_PATTERN, VenueV2, get_venue
from backend.app.venues.schemas import HazardInput

SSE_HEADERS = {"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
NO_STORE = {"Cache-Control": "no-store"}
PROPOSAL_ID_PATTERN = r"^pp-[0-9a-f]{10}$"
OPERATOR_POLL_SECONDS = 0.5
OPERATOR_PING_SECONDS = 10.0
NOT_LISTENING = ("The server is not listening on {host}:{port}, so phones cannot reach it. Restart uvicorn with "
                 "--host 0.0.0.0 serving the built frontend/dist (never point phones at vite --host).")
NO_LAN = ("No LAN address was found, so this link only works on this laptop. Join the demo Wi-Fi or set "
          "SPATIALTWIN_SIGN_BASE_URL=http://<laptop-ip>:<port>.")


def _error(http_status: int, code: str, headers: Optional[Dict[str, str]] = None, **extra: Any) -> HTTPException:
    return HTTPException(http_status, detail={"code": code, **extra}, headers=headers)


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="seconds")


def is_local_operator(request: Request) -> bool:
    """A loopback peer whose own headers do not say a LAN browser or proxy sent the request."""
    client = request.client
    return bool(client and is_loopback_host(client.host)) and not forwarded_from_remote(request.scope)


def _require_local(request: Request) -> None:
    if not is_local_operator(request):
        raise _error(403, "loopback_only")


def _cookie_token(request: Request, scope: str, service: SignsService) -> tuple[Optional[str], Optional[SignClaims]]:
    """The first cookie value of ``scope`` that verifies, with its claims; (None, None) when there is none."""
    for value in cookie_values(request.scope.get("headers", []), COOKIE_NAMES[scope]):
        try:
            return value, service.signer.verify(value, scope)
        except TokenError:
            continue
    return None, None


def _frame(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


def _empty_snapshot() -> Dict[str, Any]:
    return {}


def _link_page(code: str) -> str:
    expired = code in ("token_expired", "token_revoked")
    title = "This sign link has expired" if expired else "This sign link is not valid"
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" "
            "content=\"width=device-width,initial-scale=1\"><title>SpatialTwin sign</title><style>body{margin:0;"
            "min-height:100vh;display:grid;place-items:center;background:#0c0f10;color:#f1f3ef;font:16px/1.4 "
            "system-ui,sans-serif;text-align:center;padding:24px}h1{font-size:24px;margin:0 0 8px}p{color:#a1ada7;"
            "margin:0}</style></head><body><main><h1>" + escape(title) + "</h1><p>Ask the presenter for a new QR "
            "code and scan it again.</p></main></body></html>")


async def sign_event_stream(service: SignsService, manager: IncidentManager, venue: VenueV2, exit_id: Optional[str],
                            token: Optional[str], expires_at: Optional[str]) -> AsyncIterator[str]:
    """``sign`` on every visible change, ``heartbeat`` when idle, ``expired`` (then end) once the cookie stops verifying.

    The incident hub is the wake-up source: any incident event (plan, gate, reset, its 10 s ping) re-derives the
    public view, and only a changed view is sent, so a phone sees a confirmed hazard within one event. The token is
    re-verified on every wake-up, so expiry and revoke-all also end streams that were opened earlier.
    """
    key = f"{venue.venue_id}/{exit_id or '*'}"
    service.stream_opened(key)
    upstream = None
    try:
        yield "retry: 3000\n\n"
        last: Optional[Dict[str, Any]] = None
        upstream = manager.hub.stream(None, _empty_snapshot)
        async for frame in upstream:
            if token is not None:
                try:
                    service.signer.verify(token, "sign:read")
                except TokenError as error:
                    yield _frame("expired", {"code": error.code})
                    return
            try:
                state = sign_state(manager, venue, exit_id, expires_at).model_dump(mode="json")
            except KeyError:
                yield _frame("sign_error", {"code": "unknown_exit"})
                return
            visible = {k: v for k, v in state.items() if k != "server_time"}
            if visible != last:
                last = visible
                yield _frame("sign", state)
            elif frame.startswith(":"):
                yield _frame("heartbeat", {"server_time": now_iso()})
    finally:
        service.stream_closed(key)
        if upstream is not None:
            await upstream.aclose()


async def proposal_event_stream(service: SignsService, poll_seconds: float = OPERATOR_POLL_SECONDS,
                                ping_seconds: float = OPERATOR_PING_SECONDS) -> AsyncIterator[str]:
    """The operator's queue: the full view first, then again on every change; ``: ping`` while idle."""
    yield "retry: 3000\n\n"
    queue = service.proposals
    seen = None
    idle = 0.0
    while True:
        view = queue.view()  # also expires stale pending proposals, which bumps the version
        if view["version"] != seen:
            seen = view["version"]
            idle = 0.0
            yield _frame("proposals", view)
        elif idle >= ping_seconds:
            idle = 0.0
            yield ": ping\n\n"
        await asyncio.sleep(poll_seconds)
        idle += poll_seconds


def build_signs_router(incident: Optional[Callable[[], IncidentManager]] = None,
                       service: Optional[SignsService] = None) -> APIRouter:
    """Both dependencies are resolved per request when not given, so tests can swap the defaults."""
    router = APIRouter()

    def svc() -> SignsService:
        return service or default_service()

    def mgr() -> IncidentManager:
        if incident is not None:
            return incident()
        from backend.app.incident.routes import default_manager
        return default_manager()

    def active_venue_id() -> Optional[str]:
        try:
            return mgr().state().venue_id
        except Exception:  # noqa: BLE001 - an unreadable incident means "no venue is active", never a crash
            return None

    def venue_or_404(venue_id: str) -> VenueV2:
        venue = get_venue(venue_id)
        if venue is None:
            raise _error(404, "unknown_venue")
        return venue

    async def lan_info(request: Request, requested: Optional[str], s: SignsService) -> LanInfo:
        server = request.scope.get("server") or (None, None)
        port = server[1] if len(server) > 1 and isinstance(server[1], int) else DEFAULT_PORT
        configured = requested or env_base_url()
        source = "request" if requested else "env"
        if configured:
            parsed = parse_base_url(configured)
            if parsed is None:
                raise _error(422, "invalid_base_url")
            scheme, host, explicit = parsed
            # No port means this server's port over http (the usual typo), 443 behind an https proxy.
            port = explicit if explicit is not None else (443 if scheme == "https" else port)
            base = f"{scheme}://{host}" + ("" if port == (443 if scheme == "https" else 80) else f":{port}")
        else:
            host = await asyncio.to_thread(s.lan_ip)
            if host is None:
                return LanInfo(base_url=f"http://127.0.0.1:{port}", source="fallback", listening_on_lan=None,
                               warning=NO_LAN)
            source, base = "detected", f"http://{host}:{port}"
        listening = await asyncio.to_thread(s.probe, host, port)
        warning = NOT_LISTENING.format(host=host, port=port) if listening is False else None
        return LanInfo(base_url=base, source=source, listening_on_lan=listening, warning=warning)

    # -- operator ----------------------------------------------------------------------------------------------

    @router.post("/api/signs/tokens", response_model=MintResponse)
    async def mint(request: Request, body: MintRequest) -> MintResponse:
        _require_local(request)
        s = svc()
        venue = venue_or_404(body.venue_id or active_venue_id() or "building-v2")
        if body.scope == "hazard:propose" and body.exit_id is not None:
            raise _error(422, "exit_not_allowed_for_scope")
        exit_name = None
        if body.exit_id is not None:
            found = next((x for x in venue.exits if x.id == body.exit_id), None)
            if found is None:
                raise _error(422, "unknown_exit")
            exit_name = found.name
        lan = await lan_info(request, body.base_url, s)
        try:
            token, claims = s.signer.mint(body.scope, venue.venue_id, body.exit_id, body.ttl_seconds)
        except TokenError as error:
            raise _error(503, error.code) from None
        s.minted += 1
        url = f"{lan.base_url}/s/{token}"
        label = f"Exit sign {body.exit_id}" if body.exit_id else (
            "Exit signs" if body.scope == "sign:read" else "Hazard proposal")
        return MintResponse(token_id=claims.jti, scope=claims.scope, venue_id=venue.venue_id, exit_id=body.exit_id,
                            exit_name=exit_name, url=url, qr_svg=qr_svg(url, "M", label=label),
                            expires_at=_iso(claims.exp), ttl_seconds=claims.exp - claims.iat, lan=lan)

    @router.post("/api/signs/revoke")
    async def revoke(request: Request) -> Dict[str, Any]:
        _require_local(request)
        return {"revoked_before": _iso(svc().signer.revoke_all())}

    @router.get("/api/signs/status")
    async def status(request: Request) -> Dict[str, Any]:
        _require_local(request)
        s = svc()
        return {"sign_streams": s.stream_count, "by_sign": dict(sorted(s.streams.items())),
                "tokens_minted": s.minted, "pending_proposals": len(s.proposals.pending()),
                "secret_source": s.signer.secret_source, "disabled_reason": s.signer.disabled_reason,
                "simulated": True}

    @router.get("/api/signs/proposals")
    async def list_proposals(request: Request) -> Dict[str, Any]:
        _require_local(request)
        return svc().proposals.view()

    @router.get("/api/signs/proposals/events")
    async def proposal_events(request: Request):
        _require_local(request)
        return StreamingResponse(proposal_event_stream(svc()), media_type="text/event-stream", headers=SSE_HEADERS)

    def operator_proposal(proposal_id: str):
        proposal = svc().proposals.get(proposal_id)
        if proposal is None:
            raise _error(404, "unknown_proposal")
        if proposal.status != "pending":
            raise _error(409, "proposal_not_pending", status=proposal.status)
        return proposal

    @router.post("/api/signs/proposals/{proposal_id}/confirm")
    async def confirm(request: Request, proposal_id: str = Path(pattern=PROPOSAL_ID_PATTERN)) -> Dict[str, Any]:
        _require_local(request)
        proposal = operator_proposal(proposal_id)
        venue = get_venue(proposal.venue_id)
        if venue is None or active_venue_id() != proposal.venue_id:
            raise _error(409, "venue_not_active")
        point = interior_point(venue, proposal.zone_id)
        if point is None and proposal.position is None:
            raise _error(422, "room_has_no_interior_point")
        if proposal.position is not None:  # the judge's exact tap wins over the room's interior point
            point = proposal.position
        hazard = HazardInput(id=f"phone-{proposal.proposal_id[3:]}", type=proposal.type,
                             position={"x": point[0], "y": point[1]}, zone_id=proposal.zone_id, source="simulated",
                             untenable_s=None, proposal_id=proposal.proposal_id)
        svc().proposals.decide(proposal.proposal_id, "confirmed", hazard.id)
        return {"proposal": proposal.operator(), "hazard": hazard.model_dump(mode="json"),
                "note": "Operator-confirmed phone proposal: add this simulated hazard to the twin; it is planned "
                        "like any other hazard."}

    @router.post("/api/signs/proposals/{proposal_id}/reject")
    async def reject(request: Request, proposal_id: str = Path(pattern=PROPOSAL_ID_PATTERN)) -> Dict[str, Any]:
        _require_local(request)
        proposal = operator_proposal(proposal_id)
        svc().proposals.decide(proposal.proposal_id, "rejected")
        return {"proposal": proposal.operator()}

    # -- phones ------------------------------------------------------------------------------------------------

    @router.get("/s/{token}")
    async def redeem(request: Request, token: str):
        s = svc()
        try:
            invite = s.signer.verify(token)
            device_token, device = s.signer.derive_device(invite)
        except TokenError as error:
            status_code = 410 if error.code in ("token_expired", "token_revoked") else 403
            return HTMLResponse(_link_page(error.code), status_code=status_code,
                                headers={**NO_STORE, "Referrer-Policy": "no-referrer"})
        query = {"venue": device.venue_id}
        if device.scope == "sign:read":
            if device.exit_id:
                query["exit"] = device.exit_id
        else:
            query["mode"] = "propose"
        response = RedirectResponse(f"/sign.html?{urlencode(query)}", status_code=303,
                                    headers={**NO_STORE, "Referrer-Policy": "no-referrer"})
        response.set_cookie(COOKIE_NAMES[device.scope], device_token, max_age=s.signer.remaining_seconds(device),
                            path="/", httponly=True, samesite="strict", secure=request.url.scheme == "https")
        return response

    def sign_access(request: Request, venue_id: str, exit_query: Optional[str]):
        s = svc()
        token, claims = _cookie_token(request, "sign:read", s)
        if claims is None and not is_local_operator(request):
            raise _error(403, "sign_link_required")
        if claims is not None and claims.venue_id != venue_id:
            raise _error(403, "sign_link_wrong_venue")
        venue = venue_or_404(venue_id)
        exit_id = claims.exit_id if claims is not None and claims.exit_id else exit_query
        expires_at = _iso(claims.exp) if claims is not None else None
        return s, token, venue, exit_id, expires_at

    @router.get("/api/public/signs/{venue_id}", response_model=SignState)
    async def public_sign(request: Request, venue_id: str = Path(pattern=VENUE_ID_PATTERN),
                          exit: Optional[str] = Query(default=None, pattern=EXIT_ID_PATTERN)):
        _, _, venue, exit_id, expires_at = sign_access(request, venue_id, exit)
        try:
            state = sign_state(mgr(), venue, exit_id, expires_at)
        except KeyError:
            raise _error(404, "unknown_exit") from None
        return JSONResponse(state.model_dump(mode="json"), headers=NO_STORE)

    @router.get("/api/public/signs/{venue_id}/events")
    async def public_sign_events(request: Request, venue_id: str = Path(pattern=VENUE_ID_PATTERN),
                                 exit: Optional[str] = Query(default=None, pattern=EXIT_ID_PATTERN)):
        s, token, venue, exit_id, expires_at = sign_access(request, venue_id, exit)
        if exit_id is not None and all(x.id != exit_id for x in venue.exits):
            raise _error(404, "unknown_exit")
        if s.stream_count >= s.max_streams:
            raise _error(503, "too_many_signs")
        return StreamingResponse(sign_event_stream(s, mgr(), venue, exit_id, token, expires_at),
                                 media_type="text/event-stream", headers=SSE_HEADERS)

    def proposer(request: Request) -> SignClaims:
        _, claims = _cookie_token(request, "hazard:propose", svc())
        if claims is None:
            raise _error(403, "propose_link_required")
        return claims

    @router.get("/api/public/hazard-proposals", response_model=ProposerState)
    async def proposer_state(request: Request):
        claims = proposer(request)
        venue = venue_or_404(claims.venue_id)
        queue = svc().proposals
        state = ProposerState(
            venue_id=venue.venue_id, venue_name=venue_name(venue), active=active_venue_id() == venue.venue_id,
            rooms=[Room(id=z.id, name=z.name) for z in venue.zones], plan=Plan(**plan_geometry(venue)),
            hazard_types=HAZARD_TYPES,
            mine=[ProposalPublic(**p.public()) for p in queue.mine(claims.device_id)],
            limits=ProposalLimits(min_interval_seconds=MIN_INTERVAL_SECONDS,
                                  max_pending_per_phone=MAX_PENDING_PER_DEVICE),
            expires_at=_iso(claims.exp), server_time=now_iso())
        return JSONResponse(state.model_dump(mode="json"), headers=NO_STORE)

    @router.post("/api/public/hazard-proposals", status_code=201, response_model=ProposalPublic)
    async def propose(request: Request, body: ProposalRequest):
        claims = proposer(request)
        venue = venue_or_404(claims.venue_id)
        if active_venue_id() != venue.venue_id:
            raise _error(409, "venue_not_active")
        position = None
        if body.position is not None:
            position = (round(body.position.x, 2), round(body.position.y, 2))
            found = zone_at(venue, *position)
            if found is None:
                raise _error(422, "outside_building")
            if body.zone_id is not None and body.zone_id != found:
                raise _error(422, "zone_mismatch")
            zone = next(z for z in venue.zones if z.id == found)
        else:
            zone = next((z for z in venue.zones if z.id == body.zone_id), None)
            if zone is None:
                raise _error(422, "unknown_room")
        try:
            proposal = svc().proposals.submit(venue_id=venue.venue_id, hazard_type=body.type, zone_id=zone.id,
                                              room_name=zone.name, device_id=claims.device_id,
                                              invite_id=claims.invite_id, position=position)
        except ProposalError as error:
            headers = {"Retry-After": str(error.retry_after)} if error.retry_after else None
            raise _error(error.status, error.code, headers=headers, retry_after_seconds=error.retry_after) from None
        return JSONResponse(ProposalPublic(**proposal.public()).model_dump(mode="json"), status_code=201,
                            headers=NO_STORE)

    return router
