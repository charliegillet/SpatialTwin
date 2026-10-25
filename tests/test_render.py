import http.server
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

from walktwin import render as render_mod
from walktwin.contracts import VenueGraph
from walktwin.render import render_views

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "frontend" / "dist"


def _serve(directory: Path):
    requests: list[str] = []

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(directory), **k)

        def log_message(self, fmt, *args):
            requests.append(self.path)

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, requests


@pytest.fixture(scope="module")
def dist_server():
    if not (DIST / "render.html").exists():
        if not shutil.which("npm"):
            pytest.skip("frontend/dist/render.html missing and npm not available to build it")
        try:
            subprocess.run(["npm", "ci"], cwd=ROOT / "frontend", check=True)
            subprocess.run(["npm", "run", "build"], cwd=ROOT / "frontend", check=True)
        except subprocess.CalledProcessError as e:
            pytest.skip(f"frontend build failed: {e}")
    srv, requests = _serve(DIST)
    yield f"http://127.0.0.1:{srv.server_address[1]}", requests
    srv.shutdown()
    srv.server_close()


async def _render(graph, out, base, **kw):
    try:
        return await render_views(graph, out, base, **kw)
    except Exception as e:  # Chromium missing / cannot launch
        if "Executable doesn't exist" in str(e) or "BrowserType.launch" in str(e):
            pytest.skip(f"Playwright Chromium unavailable: {e}")
        raise


@pytest.mark.browser
async def test_render_views_writes_keyframes_plus_top(office_graph, tmp_path, dist_server):
    import cv2

    base, requests = dist_server
    views = await _render(office_graph, tmp_path / "haz", base, hazards=["D2"])
    assert len(views) == len(office_graph.keyframes) + 1 == 6
    assert [v.kind for v in views].count("perspective") == 5
    assert [v.kind for v in views].count("top") == 1
    for v in views:
        assert v.path.exists() and v.path.stat().st_size > 4_000  # flat-shaded: real 5-8 KB
        im = cv2.imread(str(v.path))
        assert im.shape[:2] == (720, 1280)
        assert im.mean() > 10
    assert any("hazards=D2" in r for r in requests)

    plain = await _render(office_graph, tmp_path / "plain", base)
    top_h = cv2.imread(str(views[-1].path))
    top_p = cv2.imread(str(plain[-1].path))
    assert (top_h != top_p).any(), "hazard D2 did not change the top-down render"


async def test_hazards_bare_str_rejected(office_graph, tmp_path):
    with pytest.raises(TypeError):
        await render_views(office_graph, tmp_path, "http://x", hazards="D2")


@pytest.mark.browser
async def test_render_error_path(office_graph, tmp_path, dist_server, monkeypatch):
    base, _ = dist_server
    monkeypatch.setattr(VenueGraph, "model_dump_json", lambda self, *a, **k: "{not json")
    with pytest.raises(RuntimeError, match=r"t=2\.0"):
        await _render(office_graph, tmp_path, base)


@pytest.mark.browser
async def test_render_timeout_path(office_graph, tmp_path, monkeypatch):
    blank = tmp_path / "site"
    blank.mkdir()
    (blank / "render.html").write_text("<html><body>never ready</body></html>")
    srv, _ = _serve(blank)
    monkeypatch.setattr(render_mod, "READY_TIMEOUT_MS", 500)
    try:
        with pytest.raises(RuntimeError, match=r"never became ready for t=2\.0"):
            await _render(office_graph, tmp_path / "out", f"http://127.0.0.1:{srv.server_address[1]}")
    finally:
        srv.shutdown()
        srv.server_close()
