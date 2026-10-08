# Platform Orchestrator 8.6.0 — R2 Correction build

Build date: 2026-10-03
Stage: R2
Target destination: Reviewer/test destination only
Automation state: OFF

## Purpose

Correction release used only after a review rejection, failed audit, or explicit reviewer request.

## Rules

1. Save the exact rejection/request text and the exact R1 build fingerprint.
2. Classify the blocker: identity, eligibility, policy, scope, demo, test access, technical behavior, or product capability.
3. Fix only the stated blocker first.
4. Record the new fingerprint and the exact changed files/configuration.
5. Preserve the same evidence trail and test destination unless the provider explicitly requires a different one.
6. Follow the provider-specific resubmission mechanism; do not send repeated identical support requests.

## Important

Do not use R2 to add unrelated permissions or future features. R2 is a corrective build, not a broader product release.

## Exit

- Reviewer accepts → use R3 only after approval is actually confirmed.
- Reviewer requests another correction → produce another R2 correction release with a new fingerprint.
