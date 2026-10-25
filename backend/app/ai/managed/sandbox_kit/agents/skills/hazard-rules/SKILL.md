---
name: hazard-rules
description: The declared hazard model the solver kit implements (whole-zone effects, precedence, door rules).
---
# Hazard rules (declared model, not physics)

- A hazard applies to the whole zone that contains its point.
- Same-zone precedence: FIRE = CHEMICAL > GAS > SMOKE > WATER. Safety locks (gas) are unions across all hazards.
- Closing a door means closed to ENTRY; occupants inside a hazard zone may still leave until it is untenable.
- FIRE, CHEMICAL: no entry from t=0; untenable at T; hold-open doors bounding the zone release; zone exits unsafe.
- SMOKE: no entry; throughput x0.5 on bounding doors and zone exits; untenable at T; zone exits closed from t=0.
- GAS: no entry; untenable at T; nothing is switched near gas; motorized and servo doors bounding the zone stay
  locked in their default state (they leave the controllable set).
- WATER: passable; throughput x0.5 and travel x2 on bounding doors and zone exits.
- Faults in the scenario grammar only remove or slow capacity: a stuck door is closed for the whole horizon, a
  blocked exit is closed from t=0, a jam multiplies throughput (a half-jammed door in smoke passes x0.25).

The source of truth is `/workspace/kit/spatialtwin_kit/effects_v2.py`, a copy of the laptop's module (see
`/workspace/kit/manifest.json` for hashes). Counts are modeled crossings, never survival.
