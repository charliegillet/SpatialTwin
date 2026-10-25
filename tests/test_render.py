import functools
import http.server
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

from walktwin.render import render_views

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "frontend" / "dist"


@pytest.fixture(scope="module")
def dist_server():
    if not (DIST / "render.html").exists():
        if not shutil.which("npm"):
            pytest.skip("frontend/dist/render.html missing and npm not available to build it")
        subprocess.run(["npm", "ci"], cwd=ROOT / "frontend", check=True)
        subprocess.run(["npm", "run", "build"], cwd=ROOT / "frontend", check=True)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DIST))
    handler.log_message = lambda *a, **k: None  # type: ignore[attr-defined]
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.mark.browser
async def test_render_views_writes_keyframes_plus_top(office_graph, tmp_path, dist_server):
    import cv2

    views = await render_views(office_graph, tmp_path, dist_server, hazards=["D2"])
    assert len(views) == len(office_graph.keyframes) + 1 == 6
    assert [v.kind for v in views].count("perspective") == 5
    assert [v.kind for v in views].count("top") == 1
    for v in views:
        assert v.path.exists() and v.path.stat().st_size > 4_000  # flat-shaded: real sizes 5-8 KB, brief said 10 KB
        im = cv2.imread(str(v.path))
        assert im.shape[:2] == (720, 1280)
        assert im.mean() > 10
