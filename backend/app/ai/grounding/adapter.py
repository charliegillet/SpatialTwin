"""
Direct Gemini 4 Argon Grounding Adapter
Integrates overhead image perception to propose canonical scenario blockages.
Strictly separates proposal from state acceptance and enforces local semantic validation.
"""

from __future__ import annotations
import base64
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple
from google import genai
from google.genai import types

from backend.app.contracts import (
    Capture,
    EntityType,
    GroundingProposalV1,
    GroundingStatus,
    RunContext,
    SUPPORTED_TARGET_PAIRS,
    SUPPORTED_TARGET_IDS,
)

logger = logging.getLogger("spatialtwin.grounding")

GROUNDING_SYSTEM_INSTRUCTION = """
You are a spatial perception model for the SpatialTwin tabletop evacuation demonstrator at SHACK15.
An overhead still shows a reviewed physical floor plan with token pads:
- T_P1: portal:P1 (Main West)
- T_P2: portal:P2 (Main East)
- T_B2: boundary:B2 (East floor exit)

A judge may place a red or black circular BLOCKED token on one of these pads.
Your task:
1. Detect if a BLOCKED token is present.
2. Determine if it unambiguously occupies one supported target.
3. Return JSON adhering to this schema:
{
  "status": "matched" | "ambiguous" | "no_match",
  "candidate_ids": ["portal:P1", "portal:P2", "boundary:B2"],
  "selected_entity_type": "portal" | "boundary" | null,
  "selected_entity_id": "P1" | "P2" | "B2" | null,
  "operation": "SET_UNAVAILABLE",
  "evidence": "concise description of visible token and pad placement",
  "box_2d": [ymin, xmin, ymax, xmax]  // normalized 0-1000 coordinates
}

If no token is placed, return status "no_match".
If multiple tokens or an occluded/in-between token is observed, return status "ambiguous" with null selected entity.
Never invent exits or doors not in the catalog.
"""


class GroundingAdapter:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "").strip()
        self.client: Optional[genai.Client] = None
        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
                logger.info("Direct Argon client initialized with API key.")
            except Exception as e:
                logger.warning(f"Failed to initialize google-genai client: {e}")
                self.client = None

    def is_live_configured(self) -> bool:
        return self.client is not None

    async def interpret_capture(
        self,
        capture: Capture,
        context: RunContext,
        force_target: Optional[str] = None,
        thinking_level: Literal["low", "medium", "high"] = "low",
    ) -> Tuple[GroundingProposalV1, str]:
        """
        Interprets a capture into a GroundingProposalV1.
        Returns (proposal, provenance: 'live' | 'fixture').
        """
        if force_target:
            return self._generate_fixture_proposal(capture, context, target_id=force_target, thinking_level=thinking_level), "fixture"

        if not self.is_live_configured() or not capture.image_base64:
            # Honest fallback to labeled fixture mode
            target_id = capture.notes if capture.notes in ("P1", "P2", "B2") else "P2"
            logger.info(f"Running grounding in labeled fixture mode for target {target_id}")
            return self._generate_fixture_proposal(capture, context, target_id=target_id, thinking_level=thinking_level), "fixture"

        try:
            prompt_text = (
                f"{GROUNDING_SYSTEM_INSTRUCTION}\n"
                f"Source context: geometry={context.geometry_revision}, "
                f"scenario_rev={context.scenario_revision}, physical_rev={context.physical_revision}."
            )

            # Call gemini-4-argon using interactions API with configured thinking level
            interaction = self.client.interactions.create(
                model="gemini-4-argon",
                input=[
                    {"type": "text", "text": prompt_text},
                    {"type": "image", "data": capture.image_base64, "mime_type": "image/jpeg"},
                ],
                generation_config={"thinking_level": thinking_level},
                response_format={"type": "text", "mime_type": "application/json"},
            )

            output_text = getattr(interaction, "output_text", None) or ""
            parsed_json = json.loads(output_text)

            proposal = GroundingProposalV1(
                capture_id=capture.capture_id,
                source_context=context,
                status=GroundingStatus(parsed_json.get("status", "no_match")),
                candidate_ids=parsed_json.get("candidate_ids", list(SUPPORTED_TARGET_IDS)),
                selected_entity_type=EntityType(parsed_json["selected_entity_type"]) if parsed_json.get("selected_entity_type") else None,
                selected_entity_id=parsed_json.get("selected_entity_id"),
                operation="SET_UNAVAILABLE",
                evidence=parsed_json.get("evidence", "Visual token detected via Gemini 4 Argon"),
                thinking_level=thinking_level,
                box_2d=parsed_json.get("box_2d"),
            )

            is_valid, errors = proposal.validate_semantic_soundness()
            if not is_valid:
                logger.warning(f"Argon proposal semantic validation failed: {errors}. Converting to ambiguous.")
                proposal.status = GroundingStatus.AMBIGUOUS
                proposal.selected_entity_type = None
                proposal.selected_entity_id = None
                proposal.evidence = f"Semantic validation failed: {'; '.join(errors)}"

            return proposal, "live"

        except Exception as e:
            logger.error(f"Live Argon grounding call failed: {e}. Falling back to labeled fixture.")
            target_id = capture.notes if capture.notes in ("P1", "P2", "B2") else "P2"
            return self._generate_fixture_proposal(capture, context, target_id=target_id), "fixture"

    def _generate_fixture_proposal(
        self,
        capture: Capture,
        context: RunContext,
        target_id: str = "P2",
        thinking_level: Literal["low", "medium", "high"] = "low",
    ) -> GroundingProposalV1:
        """
        Produces an honest, reproducible fixture proposal clearly tagged for testing.
        """
        boxes = {
            "P1": [200, 150, 320, 270],
            "P2": [200, 600, 320, 720],
            "B2": [700, 650, 820, 770],
        }

        if target_id == "P1":
            return GroundingProposalV1(
                capture_id=capture.capture_id,
                source_context=context,
                status=GroundingStatus.MATCHED,
                candidate_ids=list(SUPPORTED_TARGET_IDS),
                selected_entity_type=EntityType.PORTAL,
                selected_entity_id="P1",
                operation="SET_UNAVAILABLE",
                evidence="[FIXTURE] Circular BLOCKED token clearly visible on pad T_P1 (Portal P1 West)",
                thinking_level=thinking_level,
                box_2d=boxes["P1"],
            )
        elif target_id == "B2":
            return GroundingProposalV1(
                capture_id=capture.capture_id,
                source_context=context,
                status=GroundingStatus.MATCHED,
                candidate_ids=list(SUPPORTED_TARGET_IDS),
                selected_entity_type=EntityType.BOUNDARY,
                selected_entity_id="B2",
                operation="SET_UNAVAILABLE",
                evidence="[FIXTURE] Circular BLOCKED token clearly visible on pad T_B2 (Boundary B2 East Exit)",
                thinking_level=thinking_level,
                box_2d=boxes["B2"],
            )
        elif target_id == "ambiguous":
            return GroundingProposalV1(
                capture_id=capture.capture_id,
                source_context=context,
                status=GroundingStatus.AMBIGUOUS,
                candidate_ids=list(SUPPORTED_TARGET_IDS),
                selected_entity_type=None,
                selected_entity_id=None,
                operation="SET_UNAVAILABLE",
                evidence="[FIXTURE] Token placed between pads T_P1 and T_P2. Operator disambiguation required.",
                thinking_level=thinking_level,
                box_2d=[200, 380, 320, 500],
            )
        elif target_id == "no_match":
            return GroundingProposalV1(
                capture_id=capture.capture_id,
                source_context=context,
                status=GroundingStatus.NO_MATCH,
                candidate_ids=list(SUPPORTED_TARGET_IDS),
                selected_entity_type=None,
                selected_entity_id=None,
                operation="SET_UNAVAILABLE",
                evidence="[FIXTURE] No blockage tokens identified on any supported pad.",
                thinking_level=thinking_level,
                box_2d=None,
            )
        else:  # Default P2
            return GroundingProposalV1(
                capture_id=capture.capture_id,
                source_context=context,
                status=GroundingStatus.MATCHED,
                candidate_ids=list(SUPPORTED_TARGET_IDS),
                selected_entity_type=EntityType.PORTAL,
                selected_entity_id="P2",
                operation="SET_UNAVAILABLE",
                evidence="[FIXTURE] Circular BLOCKED token clearly visible on pad T_P2 (Portal P2 East)",
                thinking_level=thinking_level,
                box_2d=boxes["P2"],
            )
