import asyncio
import uuid
import pytest
from backend.app.contracts import (
    AlternativeId,
    ApplyBlockageCommand,
    EntityType,
    GateObservedState,
    GateTarget,
    TargetId,
)
from backend.app.hardware.protocol import make_arm_command, make_gate_target_command
from backend.app.hardware.simulator import HardwareSimulator
from backend.app.planner.flow_solver import FlowPlanner
from backend.app.state.manager import StateManager


@pytest.fixture
def state_manager():
    return StateManager()


def test_adversarial_stale_scenario_revision_rejected(state_manager):
    """
    Devil's Advocate Attack: A late proposal or malicious client attempts to apply
    a blockage on an obsolete scenario revision.
    """
    current_rev = state_manager.get_current_context().scenario_revision

    cmd = ApplyBlockageCommand(
        scenario_id="facility-demo",
        expected_scenario_revision=current_rev - 1,  # Stale!
        idempotency_key=f"stale-{uuid.uuid4()}",
        target_type=EntityType.PORTAL,
        target_id=TargetId.P2,
    )
    success, err, env = state_manager.apply_blockage(cmd)
    assert not success
    assert "Stale scenario revision" in err


def test_adversarial_duplicate_idempotency_rejected(state_manager):
    """
    Devil's Advocate Attack: Network retry or duplicate user click must not apply twice.
    """
    current_rev = state_manager.get_current_context().scenario_revision
    key = f"key-{uuid.uuid4()}"

    cmd = ApplyBlockageCommand(
        scenario_id="facility-demo",
        expected_scenario_revision=current_rev,
        idempotency_key=key,
        target_type=EntityType.PORTAL,
        target_id=TargetId.P2,
    )
    # First attempt: succeeds
    success1, _, _ = state_manager.apply_blockage(cmd)
    assert success1

    # Second attempt with same key: rejected!
    success2, err, _ = state_manager.apply_blockage(cmd)
    assert not success2
    assert "Duplicate idempotency key" in err or "Stale scenario revision" in err


@pytest.mark.asyncio
async def test_adversarial_command_ack_does_not_commit_open_state():
    """
    Devil's Advocate Attack: Verify that receiving an ACK from the firmware does NOT
    falsely set gate state to OPEN. Only endpoint switch sensing establishes OPEN.
    """
    sim = HardwareSimulator()
    sim.handle_line(make_arm_command("sess-1", "cmd-arm", sim.boot_id))

    # Send move command
    sim.handle_line(
        make_gate_target_command("sess-1", "cmd-move-1", GateTarget.OPEN, sim.boot_id, 1, 1)
    )

    # Immediately after command, state MUST be TRANSIT, not OPEN!
    assert sim.gate_state == GateObservedState.TRANSIT
    assert sim.open_switch is False


def test_adversarial_no_benefit_b2_blocked():
    """
    Devil's Advocate Attack: Verify that the planner does NOT fabricate improvement
    when downstream boundary B2 is closed.
    """
    planner = FlowPlanner()
    ctx = StateManager().get_current_context()

    env_keep = planner.solve(
        base_context=ctx,
        alternative_id=AlternativeId.KEEP_CURRENT,
        blocked_portals=set(),
        blocked_boundaries={"B2"},
    )
    env_open = planner.solve(
        base_context=ctx,
        alternative_id=AlternativeId.OPEN_P3,
        blocked_portals=set(),
        blocked_boundaries={"B2"},
    )

    # Net gain MUST be exactly 0
    gain = env_open.completed_crossings - env_keep.completed_crossings
    assert gain == 0
    assert env_open.completed_crossings == 60
    assert env_open.remaining_population == 60
