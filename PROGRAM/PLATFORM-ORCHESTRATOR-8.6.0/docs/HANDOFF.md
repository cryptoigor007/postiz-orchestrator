# HANDOFF — CURRENT POSTIZ-FREE MODULAR ORCHESTRATOR

Дата: 2026-10-01

## 1. Current product

VideoMaker/ShortsMaker → Platform Orchestrator → native social/messaging provider modules.
Postiz is **not a runtime dependency** and is not required for publish/send operations.
Historical Postiz operations belong only to `docs/SESSION_LOG.md` and deprecated docs.

## 2. Current architecture

- Core: runner / publisher / scheduler / EPS / reconciliation / consistency.
- Reliability: durable jobs, publish attempts, transactional outbox, webhook inbox.
- Auth: unified account-scoped `auth_tokens` + optional strict token broker.
- Media: shared ModuleHttpClient / media transfer layer.
- Isolation: ProviderSupervisor, per-provider/account health, circuit breaker, alerts.
- Provider boundary: `src/orchestrator/platforms/<provider>`.

## 3. Data identity

EPS primary identity is `(entity_type, entity_id, platform, account_id)` (schema 22).
A provider account has its own connection/access/token state. Do not use a shared
provider token file for multiple accounts unless the explicit compatibility fallback is enabled.

## 4. Provider status model

Provider/module states are explicit:
`IMPLEMENTED`, `SCAFFOLD`, `PARTNER`, `FEASIBILITY`.
A module is live only after credentials/access, contract tests, live canary, reconciliation
and required review/audit are complete.

## 5. Fault isolation invariant

A failed provider/account must not stop unrelated providers/accounts. Failures are
classified, persisted and surfaced through provider/account health and actionable alerts.
Transient failures use backoff/circuit breakers; permanent access failures pause only
affected targets.

## 6. External access still required

The codebase cannot grant third-party API credentials or approvals. Remaining external
steps are documented in `docs/PLATFORM_SETUP.md` and the final roadmap: Meta App Review /
Advanced Access / Business Verification where applicable, TikTok Direct Post approval/audit,
YouTube compliance/quota, Viber commercial access, Rutube partner access, and real provider canaries.

## 7. Key files

- `src/orchestrator/platforms/` — provider modules.
- `src/orchestrator/provider_supervisor.py` — provider/account health.
- `src/orchestrator/auth_tokens.py` — token resolution.
- `src/orchestrator/outbox.py` — transactional outbox.
- `src/orchestrator/durable_jobs.py` — durable jobs.
- `src/orchestrator/webhook_ingress.py` — webhooks.
- `src/orchestrator/consistency.py` — consistency sweeper.
- `docs/provider-catalog.yaml` — canonical module IDs.
- `docs/PROVIDER-MATRIX.md` — provider coverage.
- `docs/FULL-SOCIAL-ORCHESTRATOR-ROADMAP-FINAL.md` — master implementation roadmap.

## 8. Safe checks

```bash
export PYTHONPATH=src:scripts
python3 -m pytest tests/ -q --tb=line
bash scripts/gate_platform_zero.sh
bash scripts/gate_social_architecture.sh
bash scripts/check.sh
```

## 9. Historical material

Older Postiz VM, n8n and legacy-engine details remain in `docs/SESSION_LOG.md` and deprecated
reports for forensic history only. They are not setup instructions and must not be restored
into production runtime.
