# Platform Orchestrator 8.6.0 — R3 Production build

Build date: 2026-10-03
Stage: R3
Target destination: Approved live account(s)
Automation state: ON only after explicit operator enablement

## Purpose

Production stage used only after the provider has granted the requested API/product access and all approval prerequisites are satisfied.

## Preconditions

- Written/console confirmation of the required provider access is saved.
- Exact approved scopes are recorded.
- Approved app/client identity and redirect URIs match the production configuration.
- Owner-controlled live account(s) are authorized for the application.
- Privacy/support/data handling requirements are published and working.
- One live canary is completed successfully.
- Rollback procedure is tested.

## Canary order

1. Add one approved live account.
2. Execute exactly one live operation.
3. Verify the provider result and status reconciliation.
4. Verify logs, quota handling and rollback behavior.
5. Only then enable scheduled automation.

## Safety boundary

R3 must never be used to bypass an unresolved provider review. Live automation remains an explicit operator action, not an implied consequence of unpacking the archive.
