# STAGE ACCEPTANCE — Platform Orchestrator (ABSOLUTE / HARD_CUT)

**Code version:** core 8.6.0 · SCHEMA_VERSION 20  
**Gate:** `bash scripts/gate_platform_zero.sh` must PASS on host  
**Pytest:** `PYTHONPATH=src:scripts python -m pytest tests/ -q` → 0 failed

## Owner sign-off (host)

1. [ ] Linux only; SQLite on **local disk** (not NFS)
2. [ ] Single instance (pidfile); no second daemon on same DB
3. [ ] `config`: only youtube + telegram enabled for 14-day trial
4. [ ] Tokens in `tokens/` mode 0600; WEBAPP_ACCESS_KEY set; webapp not open :8080 to WAN
5. [ ] YT: one channel e2e — publish + schedule + delete path
6. [ ] TG: link-mode / compress for large files; WebApp from phone (safe-area)
7. [ ] Backup timer + watchdog enabled (deploy/)
8. [ ] Meta/TikTok/VK/X/Rutube remain **disabled** until App Review / partner access
9. [ ] 14 days YT+TG without Postiz publish — then Postiz VM may be powered off

## External blockers (not code)

- Meta App Review · TikTok Content Posting audit · VK flood e2e · X API tier · Rutube partner

Sign-off is **host owner** responsibility. Code readiness ≠ production enable for Review platforms.
