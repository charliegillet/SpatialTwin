# SpatialTwin integration status

Updated 24 October 2026. Prior milestone labels and an unsubstantiated live-verification claim have been superseded by the dated audit and explicit evidence gates.

| Area | Current evidence |
|---|---|
| Argon grounding and managed orchestration | Hardened async implementation with strict schema/context checks, explicit modes, durable tool claims and bounded execution. See production-readiness.md. |
| Backend tests | Offline regression suite blocks network/device use and isolates SQLite. 167 backend tests passed; latest evidence in integration-assurance-2026-10-24.md. |
| Frontend | 13 policy/client tests and production build; isolated mocked browser checks distinguish live, fixture, local, failed and stale evidence. |
| Live provider | Actual direct and managed public-API trial passed; inspect runtime/argon-http-live-check.json and integration-assurance-2026-10-24.md. Configuration alone is not verification. |
| Real capture accuracy | Pending board assembly; user confirmed the board is not ready. Build plan requires twenty varied actual captures; synthetic/mock evidence does not satisfy this gate. |
| Planner and hardware | AI changes do not certify the numerical model or physical assembly. Simulator tests are not actual bench observations. |
| Venue | Four-zone illustrative tabletop model, not a surveyed or approved SHACK15 plan. |

Exact Python environment: requirements.lock (google-genai2.33.0). Frontend environment: package-lock.json. Operational instructions and remaining release gates: [production-readiness.md](production-readiness.md).
