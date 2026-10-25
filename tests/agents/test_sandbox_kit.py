"""Sandbox kit: manifest and sizes, standalone run (exact copy and pure-Python estimate) against the local checker,
hook guardrails, and the inline network-disabled environment."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from backend.app.ai.managed import sandbox
from backend.app.ai.managed.door_agent import DoorToolbox
from backend.app.ai.managed.robustness import ScenarioEvaluator
from backend.app.hazard.door_planner import plan_doors
from backend.app.venues.model import VenueV2, load_building_v2
from tests.venues.conftest import make_request
from tools import build_sandbox_kit as kit_tool

KIT = sandbox.KIT_DIR
SCRIPTS = KIT / "agents" / "hooks-scripts"


def test_committed_kit_is_current_and_within_inline_limits():
    stale = kit_tool.stale_paths()
    assert stale == [], f"sandbox kit is stale ({stale}); run: .venv/bin/python -m tools.build_sandbox_kit"
    manifest = json.loads((KIT / "manifest.json").read_text())
    assert manifest["total_bytes"] < sandbox.INLINE_TOTAL_LIMIT
    assert all(entry["bytes"] < sandbox.INLINE_FILE_LIMIT for entry in manifest["files"])
    targets = {entry["target"] for entry in manifest["files"]}
    assert {".agents/AGENTS.md", ".agents/hooks.json", ".agents/hooks-scripts/guard.py",
            ".agents/hooks-scripts/audit.py", ".agents/skills/robustness-sweep/SKILL.md",
            ".agents/skills/hazard-rules/SKILL.md", ".agents/skills/responder-brief/SKILL.md",
            "workspace/kit/spatialtwin_kit/flow_solver_v2.py", "workspace/kit/spatialtwin_kit/checker_v2.py",
            "workspace/kit/spatialtwin_kit/effects_v2.py", "workspace/kit/spatialtwin_kit/scenarios.py",
            "workspace/kit/spatialtwin_kit/sweep.py", "workspace/kit/spatialtwin_kit/estimate.py"} <= targets
    copies = {e["path"]: e for e in manifest["files"] if "source" in e}
    assert set(copies) == set(kit_tool.COPIES)
    for entry in copies.values():
        source = (kit_tool.REPO_ROOT / entry["source"]).read_bytes()
        assert entry["source_sha256"] == hashlib.sha256(source).hexdigest()
    for path in (KIT / "kit" / "spatialtwin_kit").glob("*.py"):
        assert not re.search(r"^\s*(from|import) backend\b", path.read_text(), re.M), path.name


def test_skills_have_front_matter_and_hooks_are_well_formed():
    for skill in ("robustness-sweep", "hazard-rules", "responder-brief"):
        text = (KIT / "agents" / "skills" / skill / "SKILL.md").read_text()
        assert text.startswith(f"---\nname: {skill}\ndescription: ")
    hooks = json.loads((KIT / "agents" / "hooks.json").read_text())
    pre = hooks["inputs-readonly-guardrail"]["pre_tool_execution"][0]
    assert pre["matcher"] == "code_execution|write_to_file|replace_file_content|delete_file"
    assert pre["hooks"][0]["command"] == "python3 /.agents/hooks-scripts/guard.py"
    assert hooks["audit-log"]["post_tool_execution"][0]["matcher"] == ".*"
    rules = (KIT / "agents" / "AGENTS.md").read_text()
    assert "never survival" in rules and "The local checker decides" in rules and "read-only" in rules.lower()
    assert "guardrail, not authority" in (SCRIPTS / "guard.py").read_text()


def run_hook(script, payload, env=None):
    out = subprocess.run([sys.executable, "-I", str(SCRIPTS / script)], input=json.dumps(payload), text=True,
                         capture_output=True, env={**os.environ, **(env or {})}, timeout=30)
    return json.loads(out.stdout)


@pytest.mark.parametrize("payload, decision", [
    ({"tool_call": {"name": "write_to_file", "args": {"path": "/workspace/inputs/venue.json"}}}, "deny"),
    ({"tool_call": {"name": "replace_file_content", "args": {"TargetFile": "/.agents/hooks.json"}}}, "deny"),
    ({"tool_call": {"name": "delete_file", "args": {"path": "/.agents/AGENTS.md"}}}, "deny"),
    ({"tool_call": {"name": "code_execution", "args": {
        "code": "python3 -c \"open('/workspace/inputs/venue.json','w').write('{}')\""}}}, "deny"),
    ({"tool_call": {"name": "code_execution", "args": {"code": "rm -rf /.agents/hooks-scripts"}}}, "deny"),
    ({"tool_call": {"name": "code_execution", "args": {"code": "cat /workspace/inputs/venue.json"}}}, "allow"),
    ({"tool_call": {"name": "code_execution", "args": {
        "code": "cd /workspace/kit && python3 -m spatialtwin_kit.sweep > /workspace/out/log.txt"}}}, "allow"),
    ({"tool_call": {"name": "write_to_file", "args": {"path": "/workspace/out/brief.md"}}}, "allow"),
    ({"tool_call": {"name": "view_file", "args": {"path": "/workspace/inputs/venue.json"}}}, "allow"),
    ({}, "allow"),
])
def test_guard_hook_denies_writes_to_inputs_and_agents(payload, decision):
    assert run_hook("guard.py", payload)["decision"] == decision


def test_guard_hook_fails_open_on_garbage():
    out = subprocess.run([sys.executable, "-I", str(SCRIPTS / "guard.py")], input="not json", text=True,
                         capture_output=True, timeout=30)
    assert json.loads(out.stdout) == {"decision": "allow"}


def test_audit_hook_appends_without_code(tmp_path):
    log = tmp_path / "out" / "audit.jsonl"
    secret_code = "print('the sandbox code itself')"
    for payload in ({"tool_call": {"name": "code_execution", "args": {"code": secret_code}}},
                    {"tool_call": {"name": "write_to_file", "args": {"path": "/workspace/out/x"}}, "error": "boom"}):
        assert run_hook("audit.py", payload, {"SPATIALTWIN_AUDIT": str(log)}) == {}
    lines = [json.loads(line) for line in log.read_text().splitlines()]
    assert lines[0]["tool"] == "code_execution" and lines[0]["code_chars"] == len(secret_code)
    assert lines[1] == {**lines[1], "tool": "write_to_file", "path": "/workspace/out/x", "error": True}
    assert "sandbox code itself" not in log.read_text()


def mount(tmp_path, venue, request):
    """Lay the kit and the inputs out exactly as the inline sources would in the sandbox."""
    plan = plan_doors(venue, request)
    evaluator = ScenarioEvaluator(venue, request)
    documents = sandbox.input_documents(venue, evaluator.base.horizon, evaluator.base.hazards,
                                        DoorToolbox(plan, evaluator).checked_plan())
    environment = sandbox.sandbox_environment(documents)
    for source in environment["sources"]:
        path = tmp_path / source["target"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source["content"])
    return evaluator, environment


@pytest.mark.parametrize("which", ["building", "home"])
def test_standalone_sweep_matches_the_local_checker(tmp_path, which):
    if which == "building":
        venue, request = load_building_v2(), make_request([("FIRE", 20, 4)])
    else:
        venue = VenueV2.model_validate(json.loads((Path(__file__).parents[1] / "venues" / "fixtures" /
                                                   "home_flat.json").read_text()))
        request = make_request([("FIRE", 1, 1)])
    evaluator, environment = mount(tmp_path, venue, request)
    assert environment["network"] == "disabled" and environment["type"] == "remote"
    env = {**os.environ, "SPATIALTWIN_INPUTS": str(tmp_path / "workspace/inputs"),
           "SPATIALTWIN_OUT": str(tmp_path / "workspace/out"), "PYTHONDONTWRITEBYTECODE": "1"}
    # Run as the agent would (cd /workspace/kit; python3 -m ...); the venv's networkx makes it the exact copy.
    done = subprocess.run([sys.executable, "-m", "spatialtwin_kit.sweep", "--only-single"],
                          cwd=tmp_path / "workspace/kit", env=env, capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr[-2000:]
    report = json.loads((tmp_path / "workspace/out/sweep.json").read_text())
    assert report["engine"] == "exact" and report["engine_label"] == "exact copy of the local solver"
    assert len(report["suggested_claims"]) <= 12 and not report["errors"]
    for row in report["results"]:
        local = evaluator.evaluate(report["candidate"], row["scenario"])
        assert (row["completed_crossings"], row["candidate_hash"], row["holds"]) == (
            local["completed_crossings"], local["candidate_hash"], local["holds"]), row["scenario"]
    # Without networkx: the pure-Python estimator, labelled, with the same crossings and hashes.
    sys.path.insert(0, str(tmp_path / "workspace/kit"))
    try:
        for name in [m for m in sys.modules if m.startswith("spatialtwin_kit")]:
            del sys.modules[name]
        from spatialtwin_kit import sweep as kit_sweep
        estimate = kit_sweep.run(kit_sweep.load_inputs(str(tmp_path / "workspace/inputs")), engine="estimate")
    finally:
        sys.path.remove(str(tmp_path / "workspace/kit"))
        for name in [m for m in sys.modules if m.startswith("spatialtwin_kit")]:
            del sys.modules[name]
    assert estimate["engine_label"] == "sandbox estimate"
    for row in estimate["results"]:
        local = evaluator.evaluate(estimate["candidate"], row["scenario"])
        assert (row["completed_crossings"], row["candidate_hash"]) == (local["completed_crossings"],
                                                                       local["candidate_hash"]), row["scenario"]
        assert row["is_valid"] is None


def test_environment_size_checks_and_tampered_kit(tmp_path):
    documents = {"venue": "{}", "hazards": "{}", "checked_plan": "x" * (sandbox.INLINE_FILE_LIMIT + 1)}
    with pytest.raises(sandbox.SandboxKitError) as error:
        sandbox.sandbox_environment(documents)
    assert str(error.value) == "sandbox_source_too_large"
    copy = tmp_path / "kit"
    shutil.copytree(KIT, copy)
    (copy / "agents" / "AGENTS.md").write_text("edited")
    with pytest.raises(sandbox.SandboxKitError):
        sandbox.load_kit(str(copy))
    assert sandbox.kit_summary(str(copy)) == {"available": False, "error": "sandbox_kit_invalid"}
    summary = sandbox.kit_summary()
    assert summary["available"] and summary["files"] >= 15
