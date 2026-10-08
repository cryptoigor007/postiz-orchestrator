# Platform Orchestrator 8.6 — Canonical Residual / Verification

Дата: 2026-10-02.

Этот файл — единый текущий residual для 8.6.0 HARD_CUT.
`IMPLEMENTED` / `IMPLEMENTED_NATIVE` означает наличие кода в заявленном scope, а не LIVE.
LIVE требует credentials/access + real-account canary в окружении владельца.

## Code-level reviewer backlog — закрыт

Закрыты все подтверждённые code-level пункты из FINAL-VERIFIED reviewer report и последующих проходов:

- BUG-01/02/04: durable unknown-handler fail/retry; outbox `pending|published|dead`, dead не reclaim, max attempts, replay/dead API.
- BUG-03 / R-03: `publish.completed` имеет явный **audit-only** контракт (`audit_log` + `metrics`), что является осознанной продуктовой политикой.
- BUG-05/06 + R-02: local schedule требует lease и atomic `content_revision + distribution_target` до provider side-effect.
- BUG-14/28: deploy исключает `tokens/`, owner-specific private IP literals удалены из active tooling.
- BUG-15/16/17 и R-01/R-13/R-14/R-29/R-30: runtime EPS mutations, claims, recovery, Instagram finalize, `set_content_kind`, link updater, Telegram scheduler и bot dialog account-scoped.
- R-09: все ready/due EPS consumers учитывают `next_retry_at`.
- R-04/R-15/V-12: status-sync и reconciliation различают operational failure от remote-missing и не поднимают ложный `missing_on_platform` streak.
- R-22/V-29: webhook без `external_id` не может стать `done`; retry/dead policy fail-closed.
- R-23/V-05/V-16: ScheduleGuard и safety limits account-scoped при multi-account; platform-level legacy scope сохраняется только при отсутствии account-scoped context, а ambiguous multi-account calls fail-closed.
- R-24: remote inventory failure = `REMOTE_INVENTORY_UNAVAILABLE`, не пустой inventory.
- V-06: глобальные restore/trash actions требуют явного `confirm_all=true`, ведут audit log; account-scoped вариант доступен без global scope.
- V-07: отдельный regression на `next_retry_at`.
- V-08: exact pytest/test-asyncio pins закреплены в test lock и CI.
- V-09: Instagram finalize SELECT/UPDATE account-scoped.
- V-17: WebApp rate limit хранится в SQLite, а не только в process memory.
- V-19: MediaTransfer DNS-rebinding SSRF закрыт pinned-IP connect path.
- V-20/V-21: backlog/manual-upload state и scans account-scoped.
- V-04/V-13: runtime `bare except: pass` = **0**; provider list/partial paths логируют диагностическую причину.
- Test-theater cleanup: tautological `assert True` = **0**.
- SQLite resource hygiene: managed connections, socket/server cleanup, strict warnings clean.
- Provider catalog contract: runtime loader теперь сохраняет `live_status`, `publish_semantics`, `live_requirements`.
- Live-canary code path: static/dry 42/42 и explicit live-write harness с двойным opt-in + cleanup.
- Schema restore drill: current **SCHEMA_VERSION=28** проверяется на backup copy.

## External / owner-environment boundary

1. **Real-account live canary:** code-level harness готов и fail-closed; фактическая публикация на реальных YT/TG/Meta аккаунтах здесь не выполнялась.
2. **Provider approvals/access:** Meta App Review/Advanced Access, WABA, TikTok audit/access, credentials, external webhook endpoints — owner environment.
3. **Production deployment:** systemd/VM/HTTPS/real secrets must be validated on the owner host.
4. **Exact dependency matrix:** CI/test lock pins `pytest==8.3.5` and `pytest-asyncio==0.25.3`; this sandbox cannot install the pinned matrix offline. Local suite was run on the available environment.
5. **Ruff:** not installed in this sandbox; all parse/compile/gate/static checks pass independently.

## Coverage

Latest completed full-suite branch coverage run:

- Statements: **63.93%** (12,031 / 17,620 statements)
- Branches: **51.59%** (3,204 / 6,210 branches)
- Coverage varies by surface; large provider/live/tools paths remain intentionally lower.

Coverage is a verification metric, not an assertion that undiscovered runtime defects are impossible. Critical reviewer regressions are covered explicitly; low-coverage surfaces are primarily large operational/provider/live paths.

## Provider semantics

- Instagram: public media path + Meta access/review required; no LIVE claim before real canary.
- TikTok: `IMPLEMENTED_INBOX`; inbox/manual handoff is distinct from feed publication; Direct Post remains approval-dependent.
- Telegram: bot publish supported; platform scheduling and remote inventory are intentionally unsupported/not advertised.
- All catalog entries remain `live_status: NOT_LIVE`.

## Final verification baseline — 2026-10-02

- Full pytest: **953 passed, 5 skipped, 0 failed**.
- Collected tests: **958**.
- Strict pytest (`PYTHONWARNINGS=error --strict-markers --strict-config`): **953 passed, 5 skipped**.
- Platform gate: **126/126 passed**.
- Social architecture gate: **PASS**.
- Capability audit: **42/42**.
- Dry/static provider canary: **42/42**.
- Catalog ↔ manifests: **42/42**.
- Python source AST + compile: **169/169**.
- Runtime source `bare except: pass`: **0**.
- Test `assert True` tautologies: **0**.
- YAML/JSON/TOML parse: **PASS**.
- JavaScript syntax: **PASS**.
- Shell syntax: **PASS**.
- EPS account-scope review: **0** unscoped non-administrative runtime mutations; explicit global restore is guarded by `confirm_all` and audit log.
- Active credential/query-key scan: **0**.
- Owner-specific active IP scan: **0**.
- Schema: **28**.
- Live providers declared: **0/42**.

This residual intentionally does not convert external production work into a false "done" state.


## Additional final-pass closure — 2026-10-02 14:00

The last independent pass additionally closed and regression-tested:

- active CI workflow YAML parsing and exact pytest/pytest-asyncio assertions;
- infra watchdog silent-exception paths;
- owner-specific LAN/VPN IP literals in active network deployment scripts;
- scheduler queue-state and thematic scheduling account scoping;
- scheduler account-aware EPS selection alongside the existing account-aware mutations.

Current verifier result: `scripts/final_audit.py` => `FINAL AUDIT: ALL AUTOMATED CHECKS PASSED`.


## Reviewer checklist closure — 2026-10-02

See `docs/FINAL-CHECKLIST-CLOSURE-2026-10-02.md` for the item-by-item V-01…V-26 status matrix.
