#!/usr/bin/env python
"""Live API probes (a)-(f). Needs GEMINI_API_KEY. live: pending key.

Usage:  python tools/probe.py all | text | video_static | video_agentic |
        video_chain | agent_tool | agent_env  [--clip runtime/probe_clip.mp4]

Each probe writes runtime/probes/<name>.json: its receipt(s), the SDK version and
a few observations. No secrets are written. Failures are recorded as failures
(``ok: false`` plus the error); a server refusal is recorded as ``refused: true``.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from walktwin.genai_client import (  # noqa: E402
    count_steps, joined_text, make_client, run_background, upload_video)

OUT = ROOT / "runtime" / "probes"
MODEL = "gemini-4-argon"
AGENT = "antigravity-preview-09-2026"
AGENT_CONFIG = {"type": "antigravity", "model": MODEL, "max_total_tokens": 300000}
DEADLINE = 600.0
DIRECT_GEN = {"max_output_tokens": 65536, "thinking_level": "high"}
SCHEMA = {"type": "object", "properties": {"doors_seen": {"type": "integer"}},
          "required": ["doors_seen"]}
RESPONSE_FORMAT = {"type": "text", "mime_type": "application/json", "schema": SCHEMA}
VIDEO_PROMPT = ("This is a walkthrough of an empty venue. Count the distinct doors you "
                "see and answer as JSON.")
ECHO_TOOL = {"type": "function", "name": "echo_number",
             "description": "Returns the integer it is given.",
             "parameters": {"type": "object", "properties": {"n": {"type": "integer"}},
                            "required": ["n"]}}


def sdk_version() -> str:
    from google.genai import version
    return version.__version__


def write(name: str, data: dict) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    data = {"probe": name, "sdk_version": sdk_version(),
            "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"), **data}
    p = OUT / f"{name}.json"
    p.write_text(json.dumps(data, indent=2, default=str))
    print(f"[{name}] ok={data.get('ok')} -> {p}")
    return p


def read(name: str) -> dict | None:
    p = OUT / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


REFUSAL_CODES = {400, 403, 404, 422}


def http_status(e: BaseException) -> int | None:
    """HTTP status from either SDK error family (GenAiError.status_code, errors.APIError.code)."""
    for attr in ("status_code", "code"):
        v = getattr(e, attr, None)
        if isinstance(v, int):
            return v
    return None


def is_api_refusal(e: BaseException) -> bool:
    """True only for a genuine API rejection (HTTP 400/403/404/422), never for
    timeouts, 429, 5xx, network errors or probe bugs."""
    return http_status(e) in REFUSAL_CODES


def err_info(e: BaseException) -> dict:
    return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:2000]}",
            "error_class": type(e).__name__, "http_status": http_status(e),
            "refused": is_api_refusal(e),
            "traceback": traceback.format_exc()[-2000:]}


def summarize(interaction, receipt) -> dict:
    return {"receipt": receipt.model_dump(), "text": joined_text(interaction)[:2000],
            "step_types": sorted({getattr(s, "type", "?") for s in interaction.steps or []})}


async def direct(client, **kw) -> tuple[Any, Any, dict]:
    """Direct Argon call; also records whether thinking_summaries:'auto' is accepted."""
    gen = {**DIRECT_GEN, "thinking_summaries": "auto", **kw.pop("generation_config", {})}
    obs: dict = {"thinking_summaries_auto_accepted": True}
    try:
        i, r = await run_background(client, deadline_s=DEADLINE, model=MODEL,
                                    generation_config=gen, **kw)
    except Exception as e:  # noqa: BLE001
        if "thinking_summar" not in str(e).lower():
            raise
        obs = {"thinking_summaries_auto_accepted": False, "thinking_summaries_error": str(e)[:500]}
        gen.pop("thinking_summaries")
        i, r = await run_background(client, deadline_s=DEADLINE, model=MODEL,
                                    generation_config=gen, **kw)
    return i, r, obs


def video_part(uri: str, processing: Any, **extra) -> dict:
    return {"type": "video", "uri": uri, "mime_type": "video/mp4",
            "processing": processing, **extra}


async def video_call(client, clip: Path, processing: Any, uploaded=None) -> tuple[Any, Any, dict]:
    """Try the Files-API URI first; fall back to inline base64 (<20 MB) if rejected."""
    obs: dict = {}
    try:
        up = uploaded or await upload_video(client, clip)
        obs["uri"] = up.uri
        i, r, o = await direct(client, input=[video_part(up.uri, processing),
                                              {"type": "text", "text": VIDEO_PROMPT}],
                               response_format=RESPONSE_FORMAT)
        return i, r, {**obs, **o, "input_mode": "uri"}
    except Exception as e:  # noqa: BLE001
        if clip.stat().st_size >= 20_000_000:
            raise
        obs["uri_error"] = str(e)[:800]
    data = base64.b64encode(clip.read_bytes()).decode()
    part = {"type": "video", "data": data, "mime_type": "video/mp4", "processing": processing}
    i, r, o = await direct(client, input=[part, {"type": "text", "text": VIDEO_PROMPT}],
                           response_format=RESPONSE_FORMAT)
    return i, r, {**obs, **o, "input_mode": "inline_base64"}


# ---------------------------------------------------------------- probes

async def probe_text(client, clip):
    i, r, obs = await direct(client, input="In one sentence, what is an egress route?")
    write("text", {"ok": r.status == "completed", **summarize(i, r), **obs})


async def probe_video_static(client, clip):
    i, r, obs = await video_call(client, clip, {"type": "static", "fps": 1})
    write("video_static", {"ok": r.status == "completed", **summarize(i, r), **obs})


async def probe_video_agentic(client, clip):
    i, r, obs = await video_call(client, clip, "agentic")
    ran = r.processing_calls > 0
    write("video_agentic", {"ok": r.status == "completed", "agentic_ran": ran,
                            "gate": None if ran else "processing_calls==0: use static_hifps as main mode",
                            **summarize(i, r), **obs})
    return i, r, obs


async def probe_video_chain(client, clip):
    prev = read("video_agentic")
    if not prev or not prev.get("receipt", {}).get("interaction_id"):
        await probe_video_agentic(client, clip)
        prev = read("video_agentic")
    if not prev or not prev.get("receipt", {}).get("interaction_id"):
        write("video_chain", {"ok": False, "repeated_uri_accepted": "inconclusive",
                              "error": "video_agentic did not produce an interaction"})
        return
    if prev.get("input_mode") != "uri" or not prev.get("uri"):
        write("video_chain", {"ok": False, "repeated_uri_accepted": "not testable",
                              "note": "turn 1 used inline base64, so there is no URI to repeat",
                              "input_mode": prev.get("input_mode")})
        return
    uri = prev["uri"]  # the SAME URI as turn 1: no re-upload
    first_usage = prev["receipt"]["usage"]
    frame = Path(tempfile.mkdtemp()) / "f.jpg"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1", "-i", str(clip),
                    "-frames:v", "1", str(frame)], check=True)
    image = {"type": "image", "mime_type": "image/jpeg",
             "data": base64.b64encode(frame.read_bytes()).decode()}
    zoom = video_part(uri, {"type": "static", "start_offset": "2s", "end_offset": "8s",
                            "fps": 5}, resolution="high")
    try:
        i, r, o = await direct(
            client, previous_interaction_id=prev["receipt"]["interaction_id"],
            input=[image, zoom, {"type": "text", "text":
                   "Using this extra image and the zoomed clip segment, recount the doors as JSON."}],
            response_format=RESPONSE_FORMAT)
    except Exception as e:  # noqa: BLE001
        info = err_info(e)
        if info["refused"]:
            write("video_chain", {**info, "repeated_uri_accepted": False,
                                  "note": "API refused: Task 11 should skip zoom parts"})
        else:
            write("video_chain", {**info, "repeated_uri_accepted": "inconclusive",
                                  "note": "not an API refusal (timeout/429/5xx/network/bug); rerun"})
        return
    u = r.usage
    delta = {k: u.get(k, 0) - first_usage.get(k, 0)
             for k in ("total_input_tokens", "total_tokens", "total_cached_tokens")
             if isinstance(u.get(k), int)}
    write("video_chain", {"ok": r.status == "completed", "repeated_uri_accepted": True,
                          "uri": uri, "usage_first_turn": first_usage, "usage_second_turn": u,
                          "usage_delta_vs_first": delta, **summarize(i, r), **o})


def _pending_calls(interaction, allow: set[str]) -> list:
    done = {s.call_id for s in interaction.steps or [] if s.type == "function_result"}
    return [s for s in interaction.steps or []
            if s.type == "function_call" and s.id not in done and s.name in allow]


async def agent_turn(client, **kw):
    return await run_background(client, deadline_s=DEADLINE, agent=AGENT,
                                agent_config=AGENT_CONFIG, **kw)


async def probe_agent_tool(client, clip):
    receipts: list[dict] = []
    i, r = await agent_turn(
        client, environment="remote", tools=[{"type": "code_execution"}, ECHO_TOOL],
        input="Call echo_number with n=7, then use code execution to compute that number "
              "times 6 and state the result.")
    receipts.append(r.model_dump())
    for _ in range(6):
        if r.status != "requires_action":
            break
        calls = _pending_calls(i, {"echo_number"})
        if not calls:
            break
        results = [{"type": "function_result", "name": c.name, "call_id": c.id,
                    "result": {"n": c.arguments.get("n")}} for c in calls]
        i, r = await agent_turn(client, previous_interaction_id=i.id,
                                environment=i.environment_id, input=results)
        receipts.append(r.model_dump())
    checks = {"final_status_completed": r.status == "completed",
              "provider_model_is_argon": r.provider_model == MODEL}
    write("agent_tool", {"ok": all(checks.values()), "checks": checks, "receipts": receipts,
                         "final_text": joined_text(i)[:1500],
                         "raw_model": str(getattr(i, "model", None)),
                         "raw_agent_config": str(getattr(i, "agent_config", None)),
                         "step_types": sorted({s.type for s in i.steps or []})})


async def probe_agent_env(client, clip):
    out: dict = {"ok": False}
    try:
        net_on = {"type": "remote", "network": {"allowlist": [{"domain": "*"}]}}
        i, r = await agent_turn(
            client, environment=net_on, tools=[{"type": "code_execution"}],
            input="Run `pip install networkx pydantic` in the sandbox and report whether it succeeded.")
        out["install"] = {"receipt": r.model_dump(), "text": joined_text(i)[:800]}
        env_id = i.environment_id
        out["environment_id_returned"] = bool(env_id)
        reuse: dict = {}
        for label, net in (("network_disabled", "disabled"),):
            try:
                i2, r2 = await agent_turn(
                    client, environment={"type": "remote", "environment_id": env_id, "network": net},
                    tools=[{"type": "code_execution"}],
                    input="Run python -c 'import networkx, pydantic; print(networkx.__version__, "
                          "pydantic.VERSION)' and report the output verbatim.")
                text = joined_text(i2)
                reuse = {"variant": label, "receipt": r2.model_dump(), "text": text[:800],
                         "imports_ok": r2.status == "completed" and "error" not in text.lower()}
                break
            except Exception as e:  # noqa: BLE001
                reuse = {"variant": label, **err_info(e)}
        out["reuse_offline"] = reuse
        out["ok"] = bool(reuse.get("imports_ok"))
        if not out["ok"]:
            out["gate"] = "env reuse with network off failed: Task 13 runs with an allowlist"
    except Exception as e:  # noqa: BLE001
        out.update(err_info(e))
    # Saved agent on Argon: docs conflict, so a refusal is recorded as a refusal.
    try:
        agent = await client.aio.agents.create(
            id="walktwin-probe", base_agent=AGENT, agent_config=AGENT_CONFIG,
            system_instruction="You are a terse probe agent.")
        i3, r3 = await run_background(client, deadline_s=DEADLINE, agent="walktwin-probe",
                                      environment="remote", input="Reply with the word ok.")
        out["saved_agent"] = {"accepted": True, "agent_id": getattr(agent, "id", None),
                              "receipt": r3.model_dump()}
    except Exception as e:  # noqa: BLE001
        out["saved_agent"] = {"accepted": False, **err_info(e)}
    finally:
        try:
            await client.aio.agents.delete(id="walktwin-probe")
        except Exception:  # noqa: BLE001
            pass
    write("agent_env", out)


PROBES = {"text": probe_text, "video_static": probe_video_static,
          "video_agentic": probe_video_agentic, "video_chain": probe_video_chain,
          "agent_tool": probe_agent_tool, "agent_env": probe_agent_env}


async def main(names: list[str], clip: Path) -> int:
    client = make_client()
    needs_clip = {"video_static", "video_agentic", "video_chain"}
    failed = 0
    for n in names:
        if n in needs_clip and not clip.exists():
            write(n, {"ok": False, "error": f"clip not found: {clip}"})
            failed += 1
            continue
        try:
            await PROBES[n](client, clip)
        except Exception as e:  # noqa: BLE001
            write(n, err_info(e))
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("probe", choices=["all", *PROBES])
    ap.add_argument("--clip", type=Path, default=ROOT / "runtime" / "probe_clip.mp4")
    a = ap.parse_args()
    names = list(PROBES) if a.probe == "all" else [a.probe]
    sys.exit(asyncio.run(main(names, a.clip)))
