"""What a phone cookie unlocks through NetworkGuard: exactly the sign page, its assets and the public sign/proposal
API, and nothing for a missing, expired, forged or wrong-scope cookie, path tricks included."""
import pytest

from backend.app.signs.guard import cookie_values, forwarded_from_remote, scoped_access
from tests.signs.conftest import PHONE, VITE_ORIGIN, make_client, mint, redeem


def http(path, method="GET", cookie=None, headers=()):
    raw = [(b"cookie", cookie.encode())] if cookie else []
    raw += [(k.lower().encode(), v.encode()) for k, v in headers]
    return {"type": "http", "method": method, "path": path, "headers": raw, "client": PHONE}


@pytest.fixture
def cookies(service, clock):
    signer = service.signer
    sign = signer.derive_device(signer.mint("sign:read", "building-v2", "E1")[1])[0]
    propose = signer.derive_device(signer.mint("hazard:propose", "building-v2")[1])[0]
    return {"sign": f"st_sign={sign}", "propose": f"st_propose={propose}", "sign_token": sign, "propose_token": propose}


ALLOWED_FOR_SIGN = [("/sign.html", "GET"), ("/sign.html", "HEAD"), ("/assets/sign-AbC_12-x.js", "GET"),
                    ("/assets/react-vendor-BXFnCW6P.css", "GET"), ("/api/public/signs/building-v2", "GET"),
                    ("/api/public/signs/building-v2/events", "GET")]
NEVER = ["/", "/index.html", "/secret.txt", "/health", "/api/incident", "/api/incident/events", "/api/incident/approve",
         "/api/signs/tokens", "/api/signs/proposals", "/api/signs/status", "/api/venues", "/api/scenarios/facility-demo",
         "/api/public/signs/home-flat", "/api/public/signs/building-v2/", "/api/public/signs/building-v2/events/",
         "/api/public/signs/building-v2/../../incident", "/api/public/signs/building-v2/events/../../../incident",
         "/assets/../secret.txt", "/assets/../index.html", "/assets/sub/x.js", "/assets/x.js/..", "/assets/x.py",
         "/assets/x.map", "/assets/.js", "//sign.html", "/sign.html/", "/SIGN.HTML", "/sign.html/../index.html",
         "/sign.html?x", "/sign.html%00", "/sign.htm", "/sign", "/api/public/hazard-proposals/../signs/building-v2",
         "/api/public/hazard-proposals/", "/api/public"]


@pytest.mark.parametrize("path, method", ALLOWED_FOR_SIGN)
def test_a_sign_cookie_reaches_only_the_allowlist(cookies, path, method):
    assert scoped_access(http(path, method, cookies["sign"])) == "sign:read"


@pytest.mark.parametrize("path", NEVER)
def test_nothing_else_is_reachable_with_any_cookie(cookies, path):
    both = f"{cookies['sign']}; {cookies['propose']}"
    for method in ("GET", "POST", "HEAD", "PUT", "DELETE"):
        assert scoped_access(http(path, method, both)) is None, (path, method)


def test_methods_are_part_of_the_allowlist(cookies):
    assert scoped_access(http("/api/public/signs/building-v2", "POST", cookies["sign"])) is None
    assert scoped_access(http("/sign.html", "POST", cookies["sign"])) is None
    assert scoped_access(http("/api/public/hazard-proposals", "GET", cookies["propose"])) == "hazard:propose"
    assert scoped_access(http("/api/public/hazard-proposals", "POST", cookies["propose"])) == "hazard:propose"
    assert scoped_access(http("/api/public/hazard-proposals", "DELETE", cookies["propose"])) is None
    assert scoped_access({**http("/sign.html", "GET", cookies["sign"]), "type": "websocket"}) is None


def test_scopes_do_not_cross(cookies):
    assert scoped_access(http("/api/public/hazard-proposals", "POST", cookies["sign"])) is None
    assert scoped_access(http("/api/public/signs/building-v2", "GET", cookies["propose"])) is None
    assert scoped_access(http("/sign.html", "GET", cookies["propose"])) == "hazard:propose"
    # A valid token placed in the other scope's cookie does not count.
    assert scoped_access(http("/api/public/signs/building-v2", "GET", f"st_sign={cookies['propose_token']}")) is None
    assert scoped_access(http("/api/public/hazard-proposals", "POST", f"st_propose={cookies['sign_token']}")) is None


def test_missing_expired_revoked_and_forged_cookies_unlock_nothing(cookies, service, clock):
    for path in ("/sign.html", "/assets/sign-AbC_12-x.js", "/api/public/signs/building-v2"):
        assert scoped_access(http(path)) is None
        assert scoped_access(http(path, cookie="st_sign=")) is None
        assert scoped_access(http(path, cookie="st_sign=v1.sign.building-v2.E1.1.99999999999.0123456789ab.-.AAAA")) is None
        assert scoped_access(http(path, cookie=cookies["sign"][:-2])) is None
        assert scoped_access(http(path, cookie="other=" + cookies["sign_token"])) is None
    clock.advance(4 * 3600)
    assert scoped_access(http("/sign.html", cookie=cookies["sign"])) is None
    fresh = service.signer.mint("sign:read", "building-v2")[0]
    assert scoped_access(http("/sign.html", cookie=f"st_sign={fresh}")) == "sign:read"
    service.signer.revoke_all()
    assert scoped_access(http("/sign.html", cookie=f"st_sign={fresh}")) is None


def test_a_valid_duplicate_cookie_still_counts_and_garbage_is_bounded(cookies):
    header = f"st_sign=junk; {cookies['sign']}"
    assert scoped_access(http("/sign.html", cookie=header)) == "sign:read"
    flood = "; ".join(["st_sign=junk"] * 50 + [cookies["sign"]])
    assert len(cookie_values([(b"cookie", flood.encode())], "st_sign")) == 4
    assert scoped_access(http("/sign.html", cookie=flood)) is None


def test_the_qr_entry_path_needs_no_cookie_but_only_get_and_token_shaped():
    assert scoped_access(http("/s/v1.sign.x.y")) == "sign:entry"
    assert scoped_access(http("/s/v1.sign.x.y", "POST")) is None
    assert scoped_access(http("/s/")) is None
    assert scoped_access(http("/s/a/b")) is None
    assert scoped_access(http("/s/" + "a" * 300)) is None


@pytest.mark.parametrize("headers, remote", [
    ({}, False),
    ({"Origin": "http://localhost:5173"}, False),
    ({"Origin": "http://127.0.0.1:8000", "Referer": "http://127.0.0.1:8000/?mode=sim"}, False),
    ({"Referer": "http://[::1]:8000/"}, False),
    ({"Origin": "http://app.localhost:5173"}, False),
    (VITE_ORIGIN, True),
    ({"Referer": "http://192.168.8.20:5173/sign.html"}, True),
    ({"Origin": "null"}, True),
    ({"Origin": "http://evil.example"}, True),
    ({"X-Forwarded-For": "192.168.8.31"}, True),
    ({"X-Forwarded-For": "127.0.0.1"}, False),
    ({"Forwarded": "for=192.168.8.31"}, True),
])
def test_forwarded_from_remote_detects_the_vite_proxy_trap(headers, remote):
    assert forwarded_from_remote(http("/api/incident", headers=list(headers.items()))) is remote


# -- end to end through a NetworkGuard replica with the hook ------------------------------------------------------

async def test_phone_path_qr_to_cookie_to_page_to_api(app, local, phone):
    assert (await phone.get("/sign.html")).status_code == 403
    assert (await phone.get("/api/public/signs/building-v2")).json() == {"detail": "remote_access_denied"}
    minted = await mint(local, exit_id="E1")
    response = await redeem(phone, minted)
    assert response.headers["location"] == "/sign.html?venue=building-v2&exit=E1"
    assert (await phone.get("/sign.html?venue=building-v2&exit=E1")).text.startswith("<!doctype html><title>sign")
    assert (await phone.get("/assets/sign-AbC_12-x.js")).status_code == 200
    sign = await phone.get("/api/public/signs/building-v2")
    assert sign.status_code == 200 and [x["exit_id"] for x in sign.json()["exits"]] == ["E1"]
    for path in ("/", "/index.html", "/secret.txt", "/api/incident", "/api/public/signs/home-flat", "/assets/../secret.txt"):
        assert (await phone.get(path)).status_code == 403, path
    assert (await phone.post("/api/signs/tokens", json={"scope": "sign:read"})).status_code == 403
    assert (await phone.post("/api/incident/reset")).status_code == 403
    assert (await phone.post("/api/public/hazard-proposals", json={"type": "FIRE", "zone_id": "LOBBY"})).status_code == 403


async def test_a_phone_cookie_does_not_reach_operator_routes_even_if_the_guard_hook_were_missing(app, local):
    """Defense in depth: the routes check the peer and the cookie themselves."""
    minted = await mint(local, exit_id="E1")
    async with make_client(app, PHONE, guarded=False) as unguarded:
        await redeem(unguarded, minted)
        assert (await unguarded.post("/api/signs/tokens", json={"scope": "sign:read"})).json()["detail"]["code"] == "loopback_only"
        assert (await unguarded.get("/api/signs/proposals")).status_code == 403
        assert (await unguarded.get("/api/public/signs/home-flat")).json()["detail"]["code"] == "sign_link_wrong_venue"
        assert (await unguarded.get("/api/public/hazard-proposals")).json()["detail"]["code"] == "propose_link_required"
    async with make_client(app, PHONE, guarded=False) as stranger:
        assert (await stranger.get("/api/public/signs/building-v2")).json()["detail"]["code"] == "sign_link_required"
