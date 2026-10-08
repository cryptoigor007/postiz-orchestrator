# Platform Orchestrator 8.6.0 — Release Stage Archives

Date: 2026-10-03

This release is packaged as four sequential stage archives. Each stage archive is a self-contained copy of the full program plus the stage-specific passport and reviewer/operations instructions. The archives are not four different products: they are four controlled states of the same codebase.

## Stage map

| Stage | Archive role | External action | Live automation |
|---|---|---|---|
| R0 | Integration | Prove one real provider operation against an owner-controlled test destination | OFF |
| R1 | Review | Submit a provider-specific minimum-scope review build | OFF |
| R2 | Correction | Only after a rejection; correct the stated blocker and resubmit under provider rules | OFF |
| R3 | Production | After approval, add approved live accounts and run one live canary | ON only by explicit operator action |

## Important

The R1/R2/R3 archive is intentionally generic across providers. Before submission, the operator must bind one provider, one use case, one exact scope set, one test destination, one redirect-URI set (if applicable), and one exact build fingerprint. Never submit the entire multi-provider capability surface when a provider review asks for one narrow capability.

## What every stage contains

- complete source tree;
- tests and audit scripts;
- Linux/macOS/Windows launchers;
- the macOS double-click application bundle;
- provider catalog and functional reference;
- API/review master guide;
- stage passport and acceptance checklist.

## How to use the archives

1. Start with R0 for the provider you actually intend to activate.
2. Once the operation works on an owner-controlled test destination, create/bind the provider-specific R1 review configuration.
3. Submit exactly the R1 build fingerprint and evidence pack.
4. If rejected, do not jump to R3. Use R2, change only the rejected dimension, record the new fingerprint, and follow the platform's stated resubmission rule.
5. Use R3 only after written/console confirmation of the required access and after the live canary gate has been reviewed.

The archive does not and cannot guarantee a provider's approval decision.
