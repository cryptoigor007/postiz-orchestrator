# Verification Checklist — 8.6.0 Final

## Automated checks
- [x] `bash scripts/check.sh` — completed successfully
- [x] `pytest -q` — **953 passed, 5 skipped**
- [x] `pytest --collect-only` — **958 tests collected**
- [x] strict pytest — **953 passed, 5 skipped** with warnings as errors / strict markers / strict config
- [x] platform gate — **126/126**
- [x] social architecture gate — **PASS**
- [x] capability audit — **42/42**
- [x] dry/static provider canary — **42/42**
- [x] runtime bare `except: pass` — **0**
- [x] test `assert True` tautologies — **0**
- [x] AST + compile — **169/169 Python source modules**
- [x] YAML/JSON/TOML parse — **PASS**
- [x] JavaScript syntax — **PASS**
- [x] Shell syntax — **PASS**
- [x] schema version — **28**
- [x] current schema restore drill — **PASS**
- [x] active credential/query-key scan — **0**
- [x] owner-specific active IP scan — **0**

## Coverage
- [x] branch coverage run completed
- [x] 17,598 statements / 6,202 branches
- [x] 64.03% combined coverage / 51.74% branch coverage
- [!] not 100% branch execution; live/external and large operational surfaces remain partially covered

## External owner environment
- [ ] real-account canary YT + TG + Meta
- [ ] Meta App Review / Advanced Access
- [ ] WABA production access
- [ ] TikTok Direct Post production audit/access
- [ ] real production deploy/HTTPS/webhooks

These unchecked items require the owner environment and are not silently converted into PASS.
