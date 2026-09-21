# Changelog

## 8.1.2 — Final parity polish

### Fixed
- Restored `scripts/ssd_copy_verify.sh` (was missing vs upstream)
- `BackupCfg.method` label → `sqlite_backup` (matches Connection.backup API)
- `gui_check.sh` no longer uses `/webapp/k/` path key by default
- Baseline `Content-Security-Policy` on HTML responses
- version 8.1.2 / WEBAPP_BUILD=812

# Changelog

## 8.1.1 — Stage polish (§10 checklist)

### Fixed
- **10.1**: backup via `sqlite3.Connection.backup()` (no `VACUUM INTO` f-string)
- **10.2**: cloudflared menu URL without `?key=` by default (`ORCH_WEBAPP_URL_WITH_KEY=1` = legacy)
- **10.3**: Postiz TLS verify **ON** by default; `POSTIZ_INSECURE_TLS=1` for lab
- **10.4**: `/webapp/k/<key>/` only when `ORCH_LEGACY_PATH_KEY=1`
- **docs**: `.env.example` security hints; `STAGE_ACCEPTANCE.md` for ops checklist

# Changelog

## 8.1.0 — Deep residual closure

### Fixed
- **R5**: log orphan media ids after CREATE fail (uploaded media without post)
- **R7**: media `_cached_size` wired + bounded cache
- **R2**: watcher `_size_cache` hard-capped (10k entries)
- **L14**: `posts_today` resets on timezone calendar day change in `record_post`
- **publisher**: deduped create-retry block; reserve always released to `error` on fail
- **version**: 8.1.0 / WEBAPP_BUILD=81

# Changelog

## 8.0.0 — Full residual closure (P2/Q)

### Fixed
- **README**: engines description aligned with §6 (manual_uploads only, not main Publisher)
- **S8**: broker SQL alphanumeric whitelist (no free-form injection)
- **S16**: rate-limit uses first X-Forwarded-For hop only
- **S17**: MCP servers refuse start without token when `ORCH_MCP_REQUIRE_TOKEN=1`
- **S19**: metrics payload sanitized (strip token/secret keys)
- **R3**: partial UNIQUE index on `postiz_post_id` (schema v12)
- **R9**: schedule_guard TTL via `ORCH_GUARD_TTL_SEC` (default 86400)
- **R13**: read_only blocks mutating webapp API routes
- **L9**: overflow move batch hard-capped (200)
- **L30**: `exception_days` respected in `can_schedule`
- **XSS**: `esc()` on error messages in webapp
- **Q CORS**: optional `ORCH_CORS_ORIGIN`
- **Q**: bare `except:` → `except Exception:` across orchestrator
- **version**: `__version__=8.0.0`, `WEBAPP_BUILD=80`

### Prior waves (summary)
- **7.5.2 A**: S1–S7, S11, R1', CREATE-flow integrity
- **7.6.0 B**: L1–L8, L12, L46 scheduling truth
- **7.7.0 C**: L17–L21, L28–L29, L43–L45 tail/links/honesty
- **7.8.0–7.9.0 D+**: L38, R6, R8, S14, S18, D9, soft-enter, compress TG limit

### Residual runtime risks (cannot close in static code alone)
- Postiz OAuth / state machine on live API
- Multi-host SQLite writers without external lock
- SMB/network FS races for in-flight encodes
- Historical secrets in git history (rotate keys operationally)
- Full CSP on every innerHTML title field (partial esc only)

