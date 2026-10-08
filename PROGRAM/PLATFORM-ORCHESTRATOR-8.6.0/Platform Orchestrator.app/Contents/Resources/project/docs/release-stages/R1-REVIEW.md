# Platform Orchestrator 8.6.0 — R1 Review build

Build date: 2026-10-03
Stage: R1
Target destination: Reviewer/test destination only
Automation state: OFF

## Purpose

Provider-specific review build containing only the exact capability and minimum permissions for the requested access tier.

## Submission rules

- Bind exactly one provider and one use case.
- Disable unrelated providers/capabilities in the review configuration.
- Request only scopes actually demonstrated by the submitted build.
- Record exact redirect URIs, app/client ID, privacy/support URLs, test destination and build fingerprint.
- Use a real OAuth flow; never substitute passwords, cookies or browser-session tokens.
- Demonstrate one real API operation and show the resulting provider resource/status.
- Provide a deterministic reviewer script and a complete screencast.

## Reviewer evidence

Use `docs/API-AND-LAUNCH-GUIDE-2026-10-03.md` and the provider entry in `docs/provider-catalog.yaml`.

## Next stage

- Approval → move to R3 after the provider grants the requested access.
- Rejection → move to R2 and change only the stated blocker.
