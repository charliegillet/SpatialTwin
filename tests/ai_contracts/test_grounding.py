import pytest
from backend.app.ai.grounding.adapter import GroundingAdapter
from backend.app.contracts import (
    Capture,
    EntityType,
    GroundingProposalV1,
    GroundingStatus,
    RunContext,
)


@pytest.fixture
def context():
    return RunContext(
        geometry_revision="geom-shack15-v1",
        scenario_revision=1,
        physical_revision=1,
    )


@pytest.fixture
def capture(context):
    return Capture(
        capture_id="cap-test-1",
        timestamp_iso="2026-10-24T00:00:00Z",
        source_kind="fixture",
        source_geometry_revision=context.geometry_revision,
        expected_scenario_revision=1,
        expected_physical_revision=1,
    )


def test_semantic_validation_rejects_unallowlisted_target(context):
    # Inventing a target like "portal:P99" or "door:D1"
    prop = GroundingProposalV1(
        capture_id="cap-1",
        source_context=context,
        status=GroundingStatus.MATCHED,
        candidate_ids=["portal:P1", "portal:P2", "boundary:B2"],
        selected_entity_type=EntityType.PORTAL,
        selected_entity_id="P99",  # Not in allowlist!
        evidence="Token placed on P99",
    )
    valid, errors = prop.validate_semantic_soundness()
    assert not valid
    assert any("not in allowlisted stage targets" in e for e in errors)


def test_semantic_validation_rejects_applied_entity_in_ambiguous(context):
    prop = GroundingProposalV1(
        capture_id="cap-1",
        source_context=context,
        status=GroundingStatus.AMBIGUOUS,
        candidate_ids=["portal:P1", "portal:P2", "boundary:B2"],
        selected_entity_type=EntityType.PORTAL,
        selected_entity_id="P1",  # Must be None when ambiguous!
        evidence="Token placed in between",
    )
    valid, errors = prop.validate_semantic_soundness()
    assert not valid
    assert any("Ambiguous status must not contain an applied" in e for e in errors)


@pytest.mark.asyncio
async def test_fixture_proposals_for_all_supported_targets(context, capture):
    grounding = GroundingAdapter(api_key="")

    # Test P1
    p1_result = await grounding.interpret_capture(capture, context, force_target="P1")
    assert p1_result.provenance == "fixture"
    assert p1_result.status == "completed"
    p1_prop = p1_result.proposal
    assert p1_prop.status == GroundingStatus.MATCHED
    assert p1_prop.selected_entity_id == "P1"
    assert p1_prop.validate_semantic_soundness()[0]

    # Test P2
    p2_prop = (await grounding.interpret_capture(capture, context, force_target="P2")).proposal
    assert p2_prop.status == GroundingStatus.MATCHED
    assert p2_prop.selected_entity_id == "P2"
    assert p2_prop.validate_semantic_soundness()[0]

    # Test B2
    b2_prop = (await grounding.interpret_capture(capture, context, force_target="B2")).proposal
    assert b2_prop.status == GroundingStatus.MATCHED
    assert b2_prop.selected_entity_id == "B2"
    assert b2_prop.validate_semantic_soundness()[0]

    # Test Ambiguous
    amb_prop = (await grounding.interpret_capture(capture, context, force_target="ambiguous")).proposal
    assert amb_prop.status == GroundingStatus.AMBIGUOUS
    assert amb_prop.selected_entity_id is None
    assert amb_prop.validate_semantic_soundness()[0]

    no_match = await grounding.interpret_capture(capture, context, force_target="no_match")
    assert no_match.provenance == "fixture"
    assert no_match.proposal.status == GroundingStatus.NO_MATCH
    assert no_match.proposal.candidate_ids == []
    assert no_match.proposal.selected_entity_type is None
    assert no_match.proposal.selected_entity_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["P3", "B1", "portal:P1", "", "typo"])
async def test_invalid_fixture_targets_never_default_to_p2(context, capture, target):
    result = await GroundingAdapter(api_key="").interpret_capture(capture, context, force_target=target)
    assert result.status == "failed"
    assert result.proposal is None
    assert result.errors == ["invalid_fixture_target"]


@pytest.mark.asyncio
async def test_fixture_source_requires_explicit_selection(context, capture):
    result = await GroundingAdapter(api_key="").interpret_capture(capture, context)
    assert result.status == "unavailable"
    assert result.proposal is None
    assert result.errors == ["explicit_fixture_target_required"]
