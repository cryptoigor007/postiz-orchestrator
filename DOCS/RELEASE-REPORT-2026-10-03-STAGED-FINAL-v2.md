# Platform Orchestrator 8.6.0 — Final staged release report v2

Date: 2026-10-03

## Verification

- Full pytest: **987 passed / 5 skipped / 0 failed**.
- `scripts/final_audit.py`: **ALL AUTOMATED CHECKS PASSED (RC=0)** on the canonical source tree.
- Capability audit: **42/42**.
- Platform gate: **126 passed**.
- Python parse/compile: **169 source modules**.
- Runtime bare `except: pass`: **0**.
- Active secret/query-key scan: **0**.
- Owner-specific active IP scan: **0**.
- Provider-list unlogged exception paths: **0**.
- Exact test dependency pins: `pytest 8.3.5`, `pytest-asyncio 0.25.3`.

## Packaging correction

The first staged master kept the `.app` only under `MAC/`. The release-contract tests require it directly inside the complete program tree. v2 keeps the same verified app in both locations.

## Stage packaging

R0, R1, R2 and R3 are separate self-contained archives and are also nested in the master distribution.

## Launch

- macOS: double-click `MAC/Platform Orchestrator.app`.
- macOS/Linux source: run `install.sh`, then `start.sh`.
- Windows: run `install.bat`, then `start.bat`.

## API approval boundary

The stage archives and API guide are designed to minimize avoidable review failures. They cannot guarantee an external provider approval decision. Credentials, provider approvals and live account state are intentionally absent.
