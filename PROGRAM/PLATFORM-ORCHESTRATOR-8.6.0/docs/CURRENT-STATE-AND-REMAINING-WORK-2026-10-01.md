# Platform Orchestrator — Historical Current-State Snapshot

> Historical source snapshot preserved for traceability. The authoritative current release audit is `FINAL-ARCHIVE-REPORT-2026-10-01.md` and the functional reference is `docs/FUNCTIONAL-REFERENCE-2026-10-01.md`.

Date: 2026-10-01

## Authoritative verification update — 2026-10-02

The historical figures below are retained for traceability. The current release tree received a final independent deep audit after the HARD_CUT correctness/security fixes:

- **916 passed / 5 skipped / 0 failed** (`pytest -q`).
- **921 tests collected**.
- `scripts/check.sh`: **ALL CHECKS PASSED**.
- Platform gate: **126/126**.
- Provider capability audit: **42 modules / 0 errors**.
- Catalog ↔ manifest: **42/42**.
- Python: **362/362 AST + compile clean**.
- Orchestrator imports: **167/167 clean**.
- YAML parse: **48/48 clean**.
- `node --check webapp/app.js`: **OK**.
- Coverage over `src/orchestrator`: **68.09% statements / 51.47% branches**; this is not full branch execution.
- Provider `live_status` remains `NOT_LIVE` for all 42 modules; real-account canary/production access is not available inside this sandbox.
- Final audit additionally closed the OAuth token-path traversal, remote SSH voice-path injection, Meta refresh parameter mismatch, and Telegram multi-account claims UI regression.

The current canonical residual is `docs/RESIDUAL-8.6.md`. Remaining limitations are explicit multi-account helper/UI mutations, external provider approvals/credentials/canaries, the five environment-only skipped tests, partial branch coverage, and inability to instantiate the exact declared pytest upper-bound dependency matrix in the offline sandbox.

## 1. Canonical source chosen

The canonical base for this archive is `platform-orchestrator-SOCIAL-FULL-CURRENT-2026-10-01(1).zip`.

The uploaded `CURRENT-STATE-AND-REMAINING-WORK-2026-10-01(1).md` already reported a verified baseline of 818 passed, 5 skipped, 0 failed; both hard gates were passing; and the project contained 42 executable module IDs with 42 manifests. The same source explicitly warns that the snapshot is an implementation/preparation state, not proof of third-party production approval.

The older `FULL-PREP-FINAL` archive contains older versions of multiple runtime files and was therefore not used as the merge base. The `THIRD-1of3` archive matches the current code tree closely, but it does not add anything required to supersede `FULL-CURRENT`.

## 2. Archive hygiene

- Runtime/test caches (`__pycache__`, `.pyc`, `.pytest_cache`) were removed from the final archive.
- The supplied current-state report is preserved under `archive/reports/` as the historical source snapshot.
- The canonical current report is this file plus `docs/CURRENT-STATE-AND-REMAINING-WORK-2026-10-01.md`.
- No production credentials were introduced.
- Final tree contains 42 executable provider modules and 42 manifests.

## 3. Four easiest buildable modules completed in this pass

The selection was based on the project's own remaining-provider estimate: Tumblr (140 LOC), Dev.to (160 LOC), Listmonk (180 LOC), and WordPress (180 LOC) were among the smallest remaining backlogs. Medium was deliberately excluded even though its estimate was also 180 LOC because the published Medium API documentation states that the API is no longer supported and that new integrations are not allowed; the final archive therefore reclassifies Medium as feasibility-gated instead of pretending it is production-ready.

### Tumblr

Implemented/closed in code:
- OAuth1a configuration and error normalization.
- Native text publish.
- Post status reconciliation.
- Metadata update via the post-edit endpoint.
- Delete lifecycle.
- Strict text-only capability declaration; image publishing is no longer falsely advertised.

Manifest version: `0.2.0`.

### Dev.to

Implemented/closed in code:
- API-key authentication/config validation.
- Article publish and draft handling.
- Correct Forem article payload structure, including tags and optional metadata.
- Metadata update through `PUT /api/articles/{id}`.
- Published-article status lookup.
- Authenticated remote inventory through `/api/articles/me/all`.
- Delete capability removed from the manifest because the current Forem API reference does not expose a general article DELETE endpoint.

Manifest version: `0.2.0`.

### Listmonk

Implemented/closed in code:
- BasicAuth/token authentication.
- Campaign creation.
- Draft/scheduled/running status transition.
- Campaign metadata update through `PUT /api/campaigns/{id}`.
- Authoritative status reconciliation.
- Delete lifecycle.
- Native scheduled-list enumeration is not claimed; the orchestrator remains the scheduler owner.

Manifest version: `0.2.0`.

### WordPress

Implemented/closed in code:
- Application Password authentication/config validation.
- Post publish.
- Metadata update.
- Status reconciliation.
- Remote inventory reconciliation with page/date filters.
- Delete lifecycle.

Manifest version: `0.2.0`.

## 4. Medium correction

Medium is not counted as a production-capable native provider in this final archive. The module remains in the source tree for historical/feasibility purposes, but its manifest is now `access_state: FEASIBILITY` and publishing capabilities are disabled. This matches Medium's current published documentation, which says the API is no longer supported and that new integrations are not permitted.

## 5. Documentation consistency fixes

- Provider catalog: Medium changed from `IMPLEMENTED_NATIVE` to `FEASIBILITY`.
- Provider matrix: Medium changed from `NATIVE_CODE` to `FEASIBILITY`.
- Roadmap: Medium changed from `Native` to `Feasibility-gated`.
- The four completed providers now have dedicated native-code status text in their module docs.
- Stale module-document status headers were normalized against the current manifest state so they no longer universally claim `SCAFFOLD ONLY`.

## 6. Verification results

Baseline before this pass:
- 818 passed / 5 skipped / 0 failed.
- `gate_platform_zero.sh`: PASS (126 tests).
- `gate_social_architecture.sh`: PASS.

Final after this pass:
- **822 passed / 5 skipped / 0 failed**.
- `gate_platform_zero.sh`: **PASS (126 tests)**.
- `gate_social_architecture.sh`: **PASS**.
- New batch tests: **4 passed**.

The final increase from 818 to 822 is four new focused contract tests for the four completed modules.

## 7. Final measured tree

- Core Python outside `platforms/`: **15,655 LOC**.
- Provider Python: **7,517 LOC**.
- Tests: **14,945 LOC**.
- Core + provider Python + tests: **38,117 LOC**.
- Provider manifests: **42**.
- Executable provider modules: **42**.
- Final archive file count: **614** files, excluding generated caches.

These are measured values from the final tree, not estimates.

## 8. What this does not prove

The archive is a tested implementation/preparation snapshot. It does not prove live production approval or successful canary publishing on third-party accounts. Real credentials, permissions, partner contracts, provider reviews, HTTPS/webhook endpoints, and real-account canaries remain external dependencies where applicable.

## 9. Remaining project work

The larger Core backlog from the source snapshot remains relevant: transactional outbox integration, durable worker recovery, publish-attempt repair, MediaTransferManager, provider isolation/health control, token lifecycle, OAuth connection state, immutable revision/distribution integration, webhook/event integration, scheduler restart/DST safety, centralized HTTP/security boundary, observability/deployment hardening, module SDK/versioning, and common provider contract/canary tooling.

The source snapshot estimated the remaining project at approximately 35–40% Core reliability/data/auth/jobs/media/scheduler/security/observability, 42–48% native provider completion and missing provider modules, 8–12% contract/canary tooling, and 5–8% operations/deployment/access/docs. Those are engineering estimates, not measured completion percentages.

## 10. External API references checked for this pass

- Tumblr API: https://www.tumblr.com/docs/api
- Forem / Dev.to API v1: https://developers.forem.com/api/v1
- Listmonk Campaign API: https://listmonk.app/docs/apis/campaigns/
- WordPress REST API — Posts: https://developer.wordpress.org/rest-api/reference/posts/
- Medium API documentation: https://github.com/Medium/medium-api-docs
