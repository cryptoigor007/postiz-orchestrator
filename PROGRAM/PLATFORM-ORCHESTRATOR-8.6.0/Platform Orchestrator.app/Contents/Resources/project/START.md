# Platform Orchestrator — quick start

**STATUS=HARD_CUT** · module path only · Postiz VM **not** required

## One-click install & run

**macOS preferred:** double-click `Platform Orchestrator.app`. The first launch may show a normal Gatekeeper warning for an externally downloaded an app distributed without Apple Developer ID signing/notarization; use Finder **Open** once after verifying the archive checksum. The app stores runtime/user state under `~/Library/Application Support/Platform Orchestrator/`.


```bash
# Linux / macOS (from repo root)
chmod +x install.sh start.sh START.command
./install.sh              # install + smoke + start daemon :8080
# only prepare, no daemon:
./install.sh --no-start
# start later:
./start.sh
```

| OS | One-click |
|----|-----------|
| Linux / macOS | `./install.sh` (install + start) / `./install.sh --no-start` (prepare only) / `./start.sh` (start) |
| macOS Finder | double-click `Platform Orchestrator.app` (preferred) or `START.command` |
| Windows | `install.bat` (install) → `start.bat` (start) |
| systemd (Linux) | `sudo ./install.sh --systemd --prod` |

After start:

- Panel: http://127.0.0.1:8080/webapp/
- Health: http://127.0.0.1:8080/health (db + tokens deep)

## Production tokens (after install)

1. Edit `config.yaml` — enable platforms, folders, timezone  
2. Put `tokens/*.json` (chmod 600) — see `docs/PLATFORM_SETUP.md`  
3. Optional: `.env` — `WEBAPP_ACCESS_KEY`, `ORCH_PUBLIC_BASE_URL`, Telegram  

## Quality

```bash
make gate    # or: bash scripts/gate_platform_zero.sh
make test
make check
```

## Docs

- `docs/PLATFORM_SETUP.md` — platforms
- `API-AND-LAUNCH-GUIDE-2026-10-03.md` and `docs/API-APPROVAL-MASTER-2026-10-03.md` — authoritative launch + API/Developer Access playbook for all 42 providers
- `deploy/README.md` — systemd / ops  
- `LAUNCH.txt` — double-click notes

## OAuth redirect URI (required)

Set in Google / Meta / TikTok developer console:

```
{ORCH_PUBLIC_BASE_URL}/webapp/api/oauth/callback/{provider}
```

Example: `https://orch.example.com/webapp/api/oauth/callback/youtube`

Callback is public (CSRF via OAuth `state`); tokens saved to `tokens/{provider}.json` (chmod 600).

First boot: `ORCH_READ_ONLY=1` or `--dry-run`, then STAGE one YT + one TG live.

