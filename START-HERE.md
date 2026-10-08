# Platform Orchestrator 8.6.0 — Final Staged Distribution

Start here.

## 1. Normal use

- macOS: open `MAC/Platform Orchestrator.app` or the standalone macOS app archive.
- macOS/Linux from source: run `install.sh`, then `start.sh`.
- Windows: run `install.bat`, then `start.bat`.

## 2. API approval sequence

Use the four stage archives in order:

R0 → R1 → (R2 if rejected) → R3 after approval.

Never submit R3 as a substitute for R1, and never request production permissions that the demonstrated use case does not require.

## 3. Files in this distribution

- `PROGRAM/` — complete source program.
- `STAGES/` — four self-contained stage archives.
- `MAC/` — double-click macOS app archive.
- `CHECKPOINT/` — rollback checkpoint.
- `DOCS/` — API/review guide and release report.
- `SHA256/` — checksums for the distributable files.

The package intentionally contains no user tokens, credentials, production database, or live account state.
