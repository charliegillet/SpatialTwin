#!/usr/bin/env python3
"""Serve the built UI in an isolated, local review workspace. Never loads .env."""

from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hashlib
from html import escape as html_escape
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import socket
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
REPORT_LIMIT = 5_000_000
BODY_LIMIT = 8_000_000


def arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Local responsive and accessibility review of SpatialTwin's real built UI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Run from the repository root:
  cd frontend && npm ci && npm run build
  cd .. && .venv/bin/python tools/ui_review.py
  # Open http://127.0.0.1:8031/__review in Codex's browser.

Options and scope:
  Use --port 8032 when another review is already listening on 8031.
  Use --delay-seconds 3 to inspect fixture/local loading, cancel and reset states.
  Choose Fixture in Observe and Local solver in Compare. Computation is real;
  visual input is an explicit fixture and gate state uses an in-memory simulator.
  Cloud inference, camera/microphone access and physical serial are disabled.
  Every run gets a new ignored runtime/ui-toolkit session database. Existing
  localhost:8000, runtime/spatialtwin.sqlite3 and .env files are untouched.
  Axe comes from frontend/node_modules/axe-core/axe.min.js and is injected only
  into this review iframe. It is not included in the production UI.
  Reports are saved under runtime/ui-toolkit/reports and can be exported as JSON.
  Automated checks and viewport measurements assist manual review; an empty
  findings list is not accessibility certification. Keyboard, zoom, screen-reader,
  real-device and live-provider checks remain separate.
  Rebuild the frontend and reload the iframe after editing source. Ctrl+C stops
  this server; review databases/reports remain as ignored local evidence.
""",
    )
    parser.add_argument("--port", type=int, default=8031, help="Loopback port (default: 8031; 8000/5173 reserved)")
    parser.add_argument("--delay-seconds", type=float, default=0, help="Fixture/local delay, 0–10 seconds (default: 0)")
    parsed = parser.parse_args(argv)
    if not 1024 <= parsed.port <= 65535 or parsed.port in (8000, 5173):
        parser.error("choose an unused port from 1024–65535 other than app ports 8000/5173")
    if not math.isfinite(parsed.delay_seconds) or not 0 <= parsed.delay_seconds <= 10:
        parser.error("--delay-seconds must be a finite value from 0 to 10")
    return parsed


def build_review_app(*, port: int, delay_seconds: float = 0):
    """Import the backend only after process-local isolation has been established."""
    if "backend.app.main" in sys.modules:
        raise RuntimeError("Backend app is already imported; start ui_review.py in a fresh process")
    dist = ROOT / "frontend" / "dist"
    index_path = dist / "index.html"
    axe_path = ROOT / "frontend" / "node_modules" / "axe-core" / "axe.min.js"
    html_path = ROOT / "tools" / "ui_review_assets.html"
    for path, instruction in (
        (index_path, "Build the frontend first: cd frontend && npm run build"),
        (axe_path, "Install locked frontend dependencies first: cd frontend && npm ci"),
        (html_path, "Restore tools/ui_review_assets.html from the repository"),
    ):
        if not path.is_file():
            raise RuntimeError(instruction)

    # These assignments affect this review process only. Never read or modify .env.
    for key in (
        "GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS",
        "GOOGLE_GENAI_USE_VERTEXAI", "GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION",
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "FIRECRAWL_API_KEY", "SERIAL_PORT",
    ):
        os.environ[key] = ""
    os.environ["SPATIALTWIN_MODE"] = "demo"
    os.environ["SPATIALTWIN_ORIGINS"] = f"http://127.0.0.1:{port},http://localhost:{port}"
    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    toolkit_dir = ROOT / "runtime" / "ui-toolkit"
    toolkit_dir.mkdir(parents=True, exist_ok=True)
    session_id = uuid4().hex
    session_dir = toolkit_dir / f"session-{session_id}"
    session_dir.mkdir(exist_ok=False)
    db_path = session_dir / "review.sqlite3"
    if db_path.exists() or db_path.resolve() == (ROOT / "runtime" / "spatialtwin.sqlite3").resolve():
        raise RuntimeError("Review database collision; no existing database will be used")
    report_dir = toolkit_dir / "reports"
    report_dir.mkdir(exist_ok=True)

    from backend.app.state.store import SQLiteStore

    original_init = SQLiteStore.__init__

    def isolated_init(store, db_path_arg=None):
        if db_path_arg is not None and Path(db_path_arg).resolve() != db_path.resolve():
            raise RuntimeError("This process may only use its isolated review database")
        original_init(store, str(db_path))

    SQLiteStore.__init__ = isolated_init
    from backend.app import main as backend
    from starlette.applications import Starlette
    from starlette.responses import FileResponse, HTMLResponse, JSONResponse
    from starlette.routing import Mount, Route

    if backend.grounding_adapter.is_live_configured() or backend.managed_agent_adapter.is_live_configured() or backend.hardware_bridge.port:
        raise RuntimeError("Review isolation failed: cloud or physical serial configuration is present")
    if Path(backend.state_manager.store.db_path).resolve() != db_path.resolve():
        raise RuntimeError("Backend did not select the isolated review database")

    if delay_seconds:
        original_grounding = backend.grounding_adapter.interpret_capture
        original_investigation = backend.managed_agent_adapter.investigate_scenario

        async def delayed_grounding(**kwargs):
            await asyncio.sleep(delay_seconds)
            return await original_grounding(**kwargs)

        async def delayed_investigation(*args, **kwargs):
            await asyncio.sleep(delay_seconds)
            return await original_investigation(*args, **kwargs)

        backend.grounding_adapter.interpret_capture = delayed_grounding
        backend.managed_agent_adapter.investigate_scenario = delayed_investigation

    metadata = {
        "tool": "SpatialTwin local UI review", "session_id": session_id,
        "source": "UI review fixture + actual local numerical solver",
        "cloud_inference": "blocked", "physical_devices": "disabled; in-memory simulator only",
        "camera_microphone": "disabled", "database": str(db_path.relative_to(ROOT)),
        "startup_build_modified_iso": datetime.fromtimestamp(index_path.stat().st_mtime, timezone.utc).isoformat(),
        "startup_build_index_sha256": hashlib.sha256(index_path.read_bytes()).hexdigest(),
        "delay_seconds": delay_seconds,
        "audit_limits": "Automated findings assist manual review; zero findings is not certification.",
    }

    async def review_page(request):
        return HTMLResponse(html_path.read_text(encoding="utf-8"))

    async def app_page(request):
        with index_path.open("rb") as handle:
            raw_index = handle.read()
            build_timestamp = datetime.fromtimestamp(os.fstat(handle.fileno()).st_mtime, timezone.utc).isoformat()
        build_hash = hashlib.sha256(raw_index).hexdigest()
        html = raw_index.decode("utf-8")
        # Offline review must not fetch CDN fonts, tracking, or other external assets.
        html = re.sub(r'<link\b[^>]*(?:href=["\']https?://)[^>]*>', "", html, flags=re.I)
        if request.query_params.get("__ui_review") == "1":
            identity = (f'<meta name="spatialtwin-review-build" content="{html_escape(build_hash, quote=True)}">'
                f'<meta name="spatialtwin-review-build-time" content="{html_escape(build_timestamp, quote=True)}">')
            html = html.replace("</head>", identity + '<script src="/__review/axe.min.js" defer></script></head>')
        return HTMLResponse(html)

    async def review_metadata(request):
        return JSONResponse(metadata)

    async def health(request):
        value = backend.health()
        value["review"] = metadata
        value["status"] = "ui_review_fixture"
        return JSONResponse(value)

    async def axe_asset(request):
        return FileResponse(axe_path, media_type="application/javascript")

    async def save_report(request):
        if request.headers.get("content-type", "").split(";", 1)[0] != "application/json":
            return JSONResponse({"detail": "Use an application/json review report"}, status_code=415)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > REPORT_LIMIT:
                return JSONResponse({"detail": "Review report is too large"}, status_code=413)
        try:
            report = json.loads(body)
            if not isinstance(report, dict):
                raise ValueError()
        except (ValueError, UnicodeDecodeError):
            return JSONResponse({"detail": "A JSON object is required"}, status_code=422)
        created = datetime.now(timezone.utc)
        filename = f"review-{created.strftime('%Y%m%dT%H%M%S%fZ')}-{uuid4().hex[:8]}.json"
        output = report_dir / filename
        payload = {"review": metadata, "saved_at_iso": created.isoformat(), "report": report}
        with output.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
        return JSONResponse({"saved": True, "path": str(output.relative_to(ROOT)), "download_url": f"/__review/reports/{filename}"})

    async def download_report(request):
        filename = request.path_params["filename"]
        if not re.fullmatch(r"review-[0-9TZ]+-[a-f0-9]{8}\.json", filename):
            return JSONResponse({"detail": "Unknown review report"}, status_code=404)
        output = report_dir / filename
        if not output.is_file():
            return JSONResponse({"detail": "Review report not found"}, status_code=404)
        return FileResponse(output, media_type="application/json", filename=filename)

    @asynccontextmanager
    async def lifespan(app):
        async with backend.lifespan(backend.app):
            if not backend.hardware_bridge.is_simulator or backend.hardware_bridge.serial_conn is not None:
                raise RuntimeError("UI review may only start the in-memory simulator")
            yield

    review = Starlette(routes=[
        Route("/__review", review_page), Route("/__review/meta", review_metadata),
        Route("/__review/axe.min.js", axe_asset), Route("/__review/report", save_report, methods=["POST"]),
        Route("/__review/reports/{filename}", download_report), Route("/health", health),
        Route("/", app_page), Mount("/", app=backend.app),
    ], lifespan=lifespan)

    class LocalReviewGuard:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] != "http":
                return await self.app(scope, receive, send)
            headers = {key.decode("latin1").lower(): value.decode("latin1") for key, value in scope.get("headers", [])}
            allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
            allowed_origins = {f"http://{host}" for host in allowed_hosts}
            try:
                local = ipaddress.ip_address(scope.get("client", ("",))[0]).is_loopback
            except ValueError:
                local = False
            if not local or headers.get("host") not in allowed_hosts or (headers.get("origin") and headers["origin"] not in allowed_origins):
                return await JSONResponse({"detail": "UI review accepts same-origin loopback requests only"}, status_code=403)(scope, receive, send)

            path = scope.get("path", "")
            if scope.get("method") == "POST" and path.endswith(("/grounding", "/investigate")):
                raw = bytearray()
                while True:
                    message = await receive()
                    if message["type"] != "http.request":
                        return
                    raw.extend(message.get("body", b""))
                    if len(raw) > BODY_LIMIT:
                        return await JSONResponse({"detail": "Review request is too large"}, status_code=413)(scope, receive, send)
                    if not message.get("more_body", False):
                        break
                try:
                    payload = json.loads(raw)
                    mode = payload.get("mode") if isinstance(payload, dict) else None
                except (ValueError, UnicodeDecodeError):
                    mode = None
                allowed_mode = "fixture" if path.endswith("/grounding") else "local"
                if mode != allowed_mode:
                    return await JSONResponse({"detail": f"Cloud calls are blocked in UI review. Select {allowed_mode} mode."}, status_code=403)(scope, receive, send)
                delivered = False
                original_receive = receive

                async def replay_receive():
                    nonlocal delivered
                    if not delivered:
                        delivered = True
                        return {"type": "http.request", "body": bytes(raw), "more_body": False}
                    return await original_receive()

                receive = replay_receive

            async def guarded_send(message):
                if message["type"] == "http.response.start":
                    message["headers"] = [*message.get("headers", []),
                        (b"cache-control", b"no-store"),
                        (b"content-security-policy", b"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'"),
                        (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                        (b"x-content-type-options", b"nosniff"),
                    ]
                await send(message)

            await self.app(scope, receive, guarded_send)

    return LocalReviewGuard(review), metadata


def main(argv: list[str] | None = None) -> int:
    options = arguments(argv)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        listener.bind(("127.0.0.1", options.port))
        listener.listen(128)
    except OSError:
        listener.close()
        print(f"Port {options.port} is unavailable. No backend or database was opened; choose --port 8032.", file=sys.stderr)
        return 2
    try:
        app, metadata = build_review_app(port=options.port, delay_seconds=options.delay_seconds)
        import uvicorn
        print(f"UI REVIEW FIXTURE · real local solver · no cloud/physical devices\nOpen http://127.0.0.1:{options.port}/__review\nIsolated database: {metadata['database']}\nCtrl+C stops this review server.", flush=True)
        config = uvicorn.Config(app, host="127.0.0.1", port=options.port, log_level="warning", proxy_headers=False)
        uvicorn.Server(config).run(sockets=[listener])
        return 0
    except KeyboardInterrupt:
        print("UI review stopped. Local reports were retained.")
        return 0
    except (RuntimeError, ImportError) as error:
        print(f"UI review could not start: {error}", file=sys.stderr)
        return 2
    finally:
        listener.close()


if __name__ == "__main__":
    raise SystemExit(main())
