# SpatialTwin: Devil's Advocate & Adversarial Review Report

**Date:** 24 October 2026  
**Auditor:** Claude Opus Adversarial Reviewer  
**Scope:** Architecture boundaries, AI contracts, numerical conservation, and physical safety  

---

## 1. Executive Summary & Stage Readiness

The SpatialTwin codebase was subjected to rigorous adversarial boundary testing to ensure the live demonstration remains honest and mathematically sound even under unfamiliar or unhelpful judge actions.

**Overall Stage Readiness Verdict:** **READY FOR STAGE REHEARSAL**  
All critical boundary invariants are enforced. The system distinguishes simulated outputs from verified physical state, prevents fake progress claims, and truthfully reports zero improvement when an intervention cannot help.

---

## 2. Adversarial Attack Findings and Retest Evidence

| Threat / Attack Boundary | Severity | Result | Reproduction / Defense Verification |
|---|---|---|---|
| **Attack 1: Stale Scenario Revision Injection**<br>A delayed proposal or client applies a change to an older revision. | **P0 (Critical)** | **MITIGATED** | `apply_blockage` validates `cmd.expected_scenario_revision == state.context.scenario_revision`. Stale revisions return HTTP 400. Verified in `test_adversarial_stale_scenario_revision_rejected`. |
| **Attack 2: Duplicate Command Replay / Rapid Clicking**<br>Multiple identical requests trigger duplicate mutations. | **P1 (High)** | **MITIGATED** | SQLite unique constraint on `idempotency_key` ensures exactly-once execution. Repeated keys return error. Verified in `test_adversarial_duplicate_idempotency_rejected`. |
| **Attack 3: Firmware ACK Treated as Physical Arrival**<br>System repaints green route lights upon serial ACK before servo completes travel. | **P0 (Critical)** | **MITIGATED** | Receiving ACK sets state to `TRANSIT` (LEDs amber). Reserve route remains unavailable until independent microswitch D2 reads LOW (pressed). Verified in `test_adversarial_command_ack_does_not_commit_open_state`. |
| **Attack 4: Unhelpful Intervention Masked as Success**<br>When B2 is blocked, OPEN_P3 connects to blocked B2. System must not claim benefits. | **P1 (High)** | **MITIGATED** | Numerical flow solver enforces boundary capacity quotas. Net gain is exactly 0. Managed agent reports no improvement honestly. Verified in `test_adversarial_no_benefit_b2_blocked`. |
| **Attack 5: Sensor Contradiction (Both Switches Pressed)**<br>Switch jam or short circuit activates both switches simultaneously. | **P1 (High)** | **MITIGATED** | Firmware and simulator treat `open_switch && closed_switch` as `STATE_FAULT`, disarm PCA9685 OE, and report sensor contradiction. |
| **Attack 6: Occupant Leakage / Vanishing Crowd**<br>Occupants trapped in blocked areas disappear from the metric display. | **P0 (Critical)** | **MITIGATED** | Two-phase all-population flow routes unassigned occupants to physical holding states. Independent checker verifies $N_{initial} == N_{completed} + N_{remaining}$. Verified in `test_checker_catches_conservation_discrepancy`. |

---

## 3. Verified Invariants Checklist

- [x] **No Cloud Motor Actuation**: Cloud AI tools have zero serial/servo parameters. Movement requires local operator approval.
- [x] **No Structured Response Hallucinations in Prose**: Application numbers derive strictly from the checked tool ledger.
- [x] **Dual Independent Microswitches**: Debounced D2 (OPEN) and D3 (CLOSED) determine mechanical position.
- [x] **Provable Population Conservation**: Every synthetic occupant is tracked throughout the horizon.
- [x] **Honest Offline & Fixture Identification**: When API keys are absent, UI cards display `Argon Fixture` and `Simulator`.
