# Platform Orchestrator 8.6.0 — R0 Integration build

Build date: 2026-10-03
Stage: R0
Target destination: Owner-controlled test destination
Automation state: OFF

## Purpose

Self-contained integration stage for proving one real provider operation against an account, Page, channel, profile, publication, or business destination owned or explicitly authorized by the operator.

## Required operator state

- Provider: record exactly one provider before the integration run.
- Use case: record exactly one capability being tested.
- Scopes: request only the minimum scopes needed for the test.
- Redirect URIs: copy them exactly from the running build where applicable.
- Destination: use an owner-controlled or explicitly authorized test destination.
- Build fingerprint: record the exact fingerprint before collecting evidence.

## Acceptance

1. Install and launch normally.
2. Run the automated test suite and final audit.
3. Complete real OAuth/API authorization where required.
4. Perform one real provider operation on the test destination.
5. Capture the returned resource/post/object ID and status.
6. Confirm error handling for auth/quota/transient failures.
7. Keep scheduled/live automation disabled.

## Next stage

After R0 succeeds, create a provider-specific R1 review configuration from the same source tree. Do not submit the generic multi-provider configuration.
