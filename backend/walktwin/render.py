"""Headless capture of the three.js twin (frontend ``render.html``) via Playwright.

``base_url`` must be the origin that serves the built ``frontend/dist`` (so that
``<base_url>/render.html`` exists). The graph is delivered to the page from the same
origin: Playwright intercepts ``<base_url>/__walktwin_graph__.json`` and fulfils it with
``graph.model_dump_json()``; a copy is also written to ``out_dir/graph.json``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence

from playwright.async_api import async_playwright

from walktwin.contracts import VenueGraph

GRAPH_PATH = "/__walktwin_graph__.json"
CHROMIUM_ARGS = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
READY_TIMEOUT_MS = 15_000


@dataclass(frozen=True)
class RenderedView:
    t_s: float | None
    path: Path
    kind: Literal["perspective", "top"]


async def render_views(
    graph: VenueGraph,
    out_dir: Path,
    base_url: str,
    hazards: Sequence[str] = (),
) -> list[RenderedView]:
    """One perspective PNG per keyframe plus one top-down PNG (1280x720) in ``out_dir``."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = base_url.rstrip("/")
    graph_json = graph.model_dump_json()
    (out_dir / "graph.json").write_text(graph_json)
    haz = f"&hazards={','.join(hazards)}" if hazards else ""
    graph_q = f"graph={GRAPH_PATH}"

    targets: list[tuple[float | None, Literal["perspective", "top"], str, Path]] = []
    for i, k in enumerate(graph.keyframes):
        targets.append((k.t_s, "perspective", f"t={k.t_s}", out_dir / f"view_{i:02d}_t{k.t_s:g}.png"))
    targets.append((None, "top", "view=top", out_dir / "view_top.png"))

    views: list[RenderedView] = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=CHROMIUM_ARGS)
        try:
            page = await browser.new_page(viewport={"width": 1280, "height": 720})
            await page.route(
                f"{base}{GRAPH_PATH}",
                lambda route: route.fulfill(
                    status=200, content_type="application/json", body=graph_json
                ),
            )
            for t_s, kind, sel, path in targets:
                await page.goto(f"{base}/render.html?{graph_q}&{sel}{haz}")
                try:
                    await page.wait_for_function(
                        "window.__renderReady === true || !!window.__renderError",
                        timeout=READY_TIMEOUT_MS,
                    )
                except Exception as e:
                    raise RuntimeError(f"render.html never became ready for {sel}") from e
                err = await page.evaluate("window.__renderError || null")
                if err:
                    raise RuntimeError(f"render.html error for {sel}: {err}")
                await page.screenshot(path=str(path))
                views.append(RenderedView(t_s=t_s, path=path, kind=kind))
        finally:
            await browser.close()
    return views
