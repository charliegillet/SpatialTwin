# Signs contract: phone exit signs and phone hazard proposals (no hardware)

Owner: signs teammate. Code: `backend/app/signs/`, `frontend/sign.html`, `frontend/src/sign/`. Tests: `tests/signs/`,
`frontend/src/sign/signView.test.mjs`. Everything is **simulated**: payloads carry `"simulated": true` and every sign
says "Simulated sign · model output, not a certified exit sign".

A judge scans a QR on the presenter screen and the phone becomes exit sign `E1` (or the hazard proposer). Signs follow
the incident mirror's latest **checked** plan (`backend/app/incident`, incident.md recipe step 5). A phone never gets
operator authority: it can read one venue's sign view, or propose a hazard that the operator must confirm on the laptop.

## Mount (lead, `backend/app/main.py`)

```python
from backend.app.signs import build_signs_router, scoped_access

# NetworkGuard.__call__: one extra clause (a phone without X-API-Token gets only the sign allowlist)
            client = scope.get("client")
            if (not (client and is_loopback_client(client[0])) and not self._token_ok(scope)
                    and scoped_access(scope) is None):

# with the other routers, BEFORE the frontend StaticFiles mount at "/" (it would shadow /s/<token>)
app.include_router(build_signs_router())
```

Optional hardening (closes the Vite trap app-wide for browser requests): treat a loopback peer as remote when its own
headers name a LAN origin: `local = client and is_loopback_client(client[0]) and not forwarded_from_remote(scope)`
(`from backend.app.signs import forwarded_from_remote`). The sign routes already apply this to themselves.

## Running it for phones

```bash
cd frontend && npm run build                                   # dist/ now has sign.html
cd .. && .venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

- **Never point phones at `vite --host`.** Vite's proxy (`changeOrigin`, no `X-Forwarded-For`) makes every phone request
  arrive from 127.0.0.1, i.e. with full operator authority. The sign routes refuse loopback requests whose
  Origin/Referer names a LAN host (`loopback_only`), but other routes only do so with the optional hardening above.
- The QR uses `SPATIALTWIN_SIGN_BASE_URL` (e.g. `http://192.168.8.20:8000`; no port = this server's port) or the address
  of the interface with the default route. The mint response says whether the server is listening there.
- `SPATIALTWIN_SIGN_SECRET` (≥ 32 chars) keeps phone links valid across restarts; unset = random per process (every
  link dies on restart). Shorter = signs disabled (`503 sign_secret_too_short`), never a weak key.
- macOS firewall must allow incoming connections to Python; Wi-Fi client isolation blocks phones (travel router).
  Fallback: a loopback overview tab `http://127.0.0.1:8000/sign.html?venue=<id>` on a second screen (no cookie needed).

## Tokens and cookies

`v1.<sign|prop>.<venue_id>.<exit_id|->.<iat>.<exp>.<jti>.<parent|->.<tag>`, tag = base64url HMAC-SHA256 (derived
key, domain-separated). TTL 60 s–4 h (default 4 h). `/s/<token>` verifies the QR token and sets a **device** token
(new jti, same scope/venue/exit/expiry, parent = QR jti) in cookie `st_sign` or `st_propose`: `HttpOnly; SameSite=Strict;
Path=/; Max-Age=<remaining>` (`Secure` only over https). Device tokens make rate limits and "my proposals" per phone.

## What a phone cookie unlocks (`guard.scoped_access`, exact, decoded path, per method)

| path | methods | needs |
|---|---|---|
| `/s/<token-shaped>` | GET | nothing (the route verifies; invalid → 403 page, expired/revoked → 410 page, no cookie) |
| `/sign.html`, `/assets/<name>.js\|.css` (one segment) | GET, HEAD | any valid sign or proposal cookie |
| `/api/public/signs/<venue>`, `/api/public/signs/<venue>/events` | GET | `st_sign` for that venue |
| `/api/public/hazard-proposals` | GET, POST | `st_propose` |

Everything else (operator app, `/api/signs/*`, `/api/incident*`, websockets) stays `403 remote_access_denied`. Routes
re-check the cookie and peer themselves, so a missing guard hook cannot widen access. Expiry and revoke also end
open SSE streams (re-verified on every incident event or 10 s ping).

## Operator routes (loopback only; `403 loopback_only` otherwise)

| route | body → response |
|---|---|
| `POST /api/signs/tokens` | `{scope: "sign:read"\|"hazard:propose", venue_id?, exit_id?, ttl_seconds?, base_url?}` → `{token_id, scope, venue_id, exit_id, exit_name, url, qr_svg, expires_at, ttl_seconds, lan: {base_url, source: request\|env\|detected\|fallback, listening_on_lan: bool\|null, warning}}`. `venue_id` defaults to the incident's venue; `exit_id` omitted = an all-exits sign. 404 `unknown_venue`, 422 `unknown_exit` / `exit_not_allowed_for_scope` / `invalid_base_url`, 503 `sign_secret_too_short` |
| `POST /api/signs/revoke` | → `{revoked_before}`; every phone link issued so far stops (in memory; rotate the secret to revoke across restarts) |
| `GET /api/signs/status` | → `{sign_streams, by_sign: {"building-v2/E1": 2}, tokens_minted, pending_proposals, secret_source, disabled_reason, simulated}` (preflight: "N phones connected") |
| `GET /api/signs/proposals` | → `{version, pending: [P], recent: [P]}`, `P = {proposal_id, type, room, status, created_at, decided_at, venue_id, zone_id, phone, hazard_id, source: "phone_proposal"}` |
| `GET /api/signs/proposals/events` | SSE `proposals` (same body) on every change, `: ping` every 10 s |
| `POST /api/signs/proposals/{id}/confirm` | → `{proposal, hazard, note}`; `hazard` is a `HazardInput` (`source: "simulated"`, `id: "phone-…"`, `zone_id`, interior `position`, `proposal_id`). 404 `unknown_proposal`, 409 `proposal_not_pending` (+`status`), 409 `venue_not_active` |
| `POST /api/signs/proposals/{id}/reject` | → `{proposal}` |

Confirm does **not** touch the incident: the twin owns its hazards and syncs them (`useIncident`), so the presenter adds
`hazard` to the placement (as `PlacedHazard {id, type, x: position.x, y: position.y, zone_id, untenable_s: null,
source: "simulated", proposal_id}`, e.g. via `addCameraHazards`) and the normal debounce → `/api/incident/hazards` → plan →
sign SSE path follows. Label it "Phone proposal · operator-confirmed".

## Phone routes

`GET /api/public/signs/{venue_id}[?exit=E1]` → SignState (the cookie's exit wins over `?exit`):

```jsonc
{ "simulated": true, "venue_id": "building-v2", "venue_name": "Building v2",
  "status": "normal" | "incident" | "unchecked" | "inactive", "plan_revision": 4 | null, "plan_label": "primary" | "fallback" | null,
  "exits": [{ "exit_id": "E1", "name": "South exit", "lamp": "green_flash" | "green" | "red_x" | "red_static" | null, "routed": 40 | null }],
  "hazards": [{ "type": "FIRE", "room": "Lobby" }], "count_label": "modeled crossings",
  "expires_at": "ISO" | null, "server_time": "ISO" }
```

`inactive` = the incident is on another venue; `normal` = no hazards (lamps from the no-hazard plan, or none before any
plan); `unchecked` = hazards but the plan was withdrawn or is not checker-valid (no lamps). Nothing else from the plan
leaves the server. Errors: 403 `sign_link_required` / `sign_link_wrong_venue`, 404 `unknown_venue` / `unknown_exit`.

`GET /api/public/signs/{venue_id}/events` → SSE: `retry: 3000`, `sign` (SignState, only when it changes), `heartbeat`
(`{server_time}`, ~10 s when idle), `expired` (`{code}`, then the stream ends), `sign_error` (`unknown_exit`).
503 `too_many_signs` beyond 64 streams.

`GET /api/public/hazard-proposals` → `{venue_id, venue_name, active, rooms: [{id, name}], hazard_types, mine: [{proposal_id,
type, room, status, created_at, decided_at}], limits, expires_at, server_time}`. `POST` `{type, zone_id}` → 201; venue
comes from the token only. 422 `unknown_room`, 409 `venue_not_active`, 429 `rate_limited` (`retry_after_seconds`,
`Retry-After`) / `too_many_pending`, 503 `proposal_queue_full`. Limits: 1 per phone per 10 s, 2 pending per phone,
20 per QR per 10 min, 12 pending overall, pending expires after 10 min.

## Presenter UI recipe

1. For each exit of the active venue: `POST /api/signs/tokens {scope: "sign:read", exit_id}`; show
   `<img alt="QR for exit E1" src={"data:image/svg+xml;charset=utf-8," + encodeURIComponent(qr_svg)}>` (≥ 240 px, on
   white) plus `exit_name`, and `lan.warning` prominently when present. One more for `hazard:propose`.
2. Re-mint after a venue switch (old links show "sign idle", not wrong lamps) and before the 4 h expiry.
3. Pending proposals: subscribe to `/api/signs/proposals/events`; Confirm → add `hazard` to the twin; Reject.
4. Preflight: `GET /api/signs/status` for connected phones. Between judge groups: `POST /api/signs/revoke` and re-mint.

## Phone behaviour (`sign.html`)

Full-screen sign, system fonts, no three.js. `green_flash` during an incident: green running-man arrow pulsing at 0.8 Hz
with "N modeled crossings routed here" (steady under reduced motion); `green`/no plan: steady green EXIT; `red_x`: red
"DO NOT USE" X with the hazard type · room; `red_static`: static red no-entry "LOCKED · GAS"; `unchecked`: amber "NO
CHECKED PLAN · follow staff instructions"; `inactive`: grey "SIGN IDLE". No event for 25 s → grey "NOT UPDATING"
(never a stale arrow); 403/410 → "LINK EXPIRED · scan the new QR". SSE with auto-retry, polling fallback every 3 s,
backoff to 15 s, reconnect on visibility. Wake Lock is requested but needs a secure context, so on plain-http LAN it is a
no-op (set the phone's auto-lock to Never). "Full screen" button where the Fullscreen API exists (not iPhone Safari).
`?mode=propose` is the proposer: type + room buttons, send, and the status of this phone's own proposals.

## Known limits and caveats

- Plain HTTP on the LAN: anyone sniffing the Wi-Fi can copy a cookie; anyone who photographs a QR gets that link. Both
  are read-only sign access or rate-limited proposals for ≤ 4 h, and revocable.
- `/assets/*.js|css` is open to any cookie holder, so the operator app's bundle is downloadable (public code, no secrets).
  The sign entry also loads `react-vendor` only because `manualChunks` puts Vite's modulepreload polyfill there.
- SameSite=Strict cookies are sent after a QR scan (a browser-initiated navigation) in current Chrome and Safari; an
  in-app scanner browser that treats the scan as cross-site would show "LINK EXPIRED". Opening the link in the real
  browser fixes it.
- Revocation, rate limits, proposals and stream counts are in memory (one laptop, one process).
