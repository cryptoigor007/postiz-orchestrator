# Platform Orchestrator 8.6.0 — Final Deep Verification — 2026-10-02

## Release identity

- Release line: `8.6.0 HARD_CUT`
- Final verification date: `2026-10-02`
- Canonical residual: `docs/RESIDUAL-8.6.md`

## Completed code-level verification

| Check | Result |
|---|---:|
| Full pytest | **953 passed / 5 skipped / 0 failed** |
| Collected tests | **958** |
| Strict pytest | **946 passed / 5 skipped** |
| Platform gate | **126/126** |
| Social architecture gate | **PASS** |
| Capability audit | **42/42** |
| Dry/static provider canary | **42/42** |
| Catalog ↔ manifests | **42/42** |
| Python source modules | **169** |
| AST + compile | **169/169** |
| Runtime bare `except: pass` | **0** |
| Test `assert True` tautologies | **0** |
| YAML/JSON/TOML | **PASS** |
| JS syntax | **PASS** |
| Shell syntax | **PASS** |
| Schema version | **28** |
| Active secret/query-key scan | **0** |
| Active owner-IP scan | **0** |

## Coverage

Latest completed branch run:

- 63.93% statement coverage (full-suite coverage.py run)
- 51.59% branch coverage in the full-suite run (3,204 / 6,210)
- 6,202 measured branches

The project does not claim 100% branch execution.

## Final reviewer closure

The reviewer backlog items V-04, V-05, V-06, V-07, V-08, V-09, V-12, V-13, V-17, V-19, V-20 and V-21 are closed in code and regression-tested. Earlier BUG/R items are also closed or explicitly classified as product/external semantics.

`publish.completed` remains intentionally audit-only; it is not a hidden missing implementation.

## External boundary

The following cannot be honestly marked executed in this sandbox:

- real-account live publish/status/delete canaries;
- provider credentials and production access;
- Meta review / Advanced Access;
- WhatsApp Business onboarding;
- TikTok Direct Post production access/audit;
- real production systemd/HTTPS/webhook environment.

The code now includes an explicitly armed `ProviderContractCanary.live_write()` path requiring both:

- `ORCH_CANARY_LIVE_WRITE=1`
- `ORCH_CANARY_CONFIRM=PUBLISH_A_CANARY`

and a real media path via `ORCH_CANARY_MEDIA`. Cleanup is attempted automatically when the provider exposes delete. Public/uncleanable paths require an additional explicit `ORCH_CANARY_ALLOW_PUBLIC=1`.

No provider is marked LIVE merely because static/dry canary passed.

## Sandbox dependency note

The project test lock pins `pytest==8.3.5` and `pytest-asyncio==0.25.3`. Exact offline installation of those pins was not available in this sandbox. `pip check` reports only the pre-existing sandbox MoviePy/Pillow mismatch; Pillow is not a release dependency.

## Acceptance command

`scripts/check.sh` is now the canonical automated acceptance command; the underlying final audit is independently reproducible and completed with RC=0.


## Additional final-pass closure — 2026-10-02 14:00

The last independent pass additionally closed and regression-tested:

- active CI workflow YAML parsing and exact pytest/pytest-asyncio assertions;
- infra watchdog silent-exception paths;
- owner-specific LAN/VPN IP literals in active network deployment scripts;
- scheduler queue-state and thematic scheduling account scoping;
- scheduler account-aware EPS selection alongside the existing account-aware mutations.

Current verifier result: `scripts/final_audit.py` => `FINAL AUDIT: ALL AUTOMATED CHECKS PASSED`.
