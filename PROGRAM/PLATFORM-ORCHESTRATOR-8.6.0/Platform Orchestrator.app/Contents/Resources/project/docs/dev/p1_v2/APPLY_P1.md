# P1 v2 — применение

```bash
cd ~/orch-work && git pull && ./scripts/check.sh   # baseline зелёный

cp /path/to/delivery_p1_v2/p1/link_updater.py   src/orchestrator/
cp /path/to/delivery_p1_v2/p1/infra_watchdog.py scripts/
cp /path/to/delivery_p1_v2/tests/test_link_updater_force.py tests/

./scripts/check.sh
# ALL CHECKS PASSED →
git add src/orchestrator/link_updater.py scripts/infra_watchdog.py tests/test_link_updater_force.py
git commit -m "fix(P1): force_update any entity_type; watchdog waiting/fail alerts (real schema)"
git push
# deploy по AGENTS.md после зелёного check
```

Опционально env:
- `ORCH_DB` — путь к sqlite (default `/opt/orchestrator/data/orchestrator.db`)
- `ORCH_WAITING_YT_MIN` — порог минут (default 30)
- `INFRA_ALERT_COOLDOWN` — уже был

Не включать module:youtube в прод до P5.
