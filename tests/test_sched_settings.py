from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator import sched_settings as ss
from orchestrator.config import load_config
from orchestrator.db import Database

CFG = Path(__file__).resolve().parents[1] / "config.yaml"


def _env(tmp_path):
    db = Database(tmp_path / "s.sqlite")
    cfg = load_config(CFG)
    return db, cfg


def test_effective_defaults(tmp_path):
    db, cfg = _env(tmp_path)
    long = ss.effective(db, cfg, "telegram", "long")
    assert long["days"] == ["tue", "fri"] and long["time"] == "16:00"
    th = ss.effective(db, cfg, "telegram", "thematic")
    assert th["time"] == "20:30"
    sa = ss.effective(db, cfg, "telegram", "standalone")
    assert sa["days"] and sa["times"]
    assert ss.effective_daily_limit(db, cfg, "telegram") == cfg.platforms["telegram"].daily_limit


def test_platform_override(tmp_path):
    db, cfg = _env(tmp_path)
    ss.save_schedule_settings(db, {
        "youtube": {"long": {"days": ["sun"], "time": "11:15"},
                    "thematic": {"time": "19:00"},
                    "standalone": {"days": ["mon"], "times": ["10:00"]},
                    "daily_limit": 3},
    })
    long = ss.effective(db, cfg, "youtube", "long")
    assert long["days"] == ["sun"] and long["time"] == "11:15"
    assert ss.effective(db, cfg, "youtube", "thematic")["time"] == "19:00"
    eff_sa = ss.effective(db, cfg, "youtube", "standalone")
    assert eff_sa["days"] == ["mon"] and eff_sa["times"] == ["10:00"]
    assert ss.effective_daily_limit(db, cfg, "youtube") == 3
    # другая платформа не затронута
    assert ss.effective(db, cfg, "telegram", "long")["time"] == "16:00"


def test_group_override_wins(tmp_path):
    db, cfg = _env(tmp_path)
    ss.save_groups(db, [{"name": "Основные", "platforms": ["youtube", "telegram"]}])
    ss.save_schedule_settings(db, {
        "telegram": {"long": {"time": "10:00"}},
        "group:Основные": {"long": {"time": "18:45"}, "thematic": {"time": "21:15"}},
    })
    assert ss.effective(db, cfg, "telegram", "long")["time"] == "18:45"
    assert ss.effective(db, cfg, "youtube", "long")["time"] == "18:45"
    assert ss.effective(db, cfg, "youtube", "thematic")["time"] == "21:15"


def test_validation(tmp_path):
    ok, _ = ss.validate_schedule_settings({"youtube": {"long": {"days": ["sun"], "time": "09:05"}}})
    assert ok
    bad, msg = ss.validate_schedule_settings({"youtube": {"long": {"time": "25:00"}}})
    assert not bad and "time" in msg
    bad, _ = ss.validate_schedule_settings({"youtube": {"standalone": {"days": ["xxx"]}}})
    assert not bad
    bad, _ = ss.validate_schedule_settings({"youtube": {"daily_limit": 999}})
    assert not bad
    ok, _ = ss.validate_groups([{"name": "A", "platforms": ["youtube"]}], ["youtube", "telegram"])
    assert ok
    bad, _ = ss.validate_groups([{"name": "A", "platforms": ["myspace"]}], ["youtube"])
    assert not bad
    bad, _ = ss.validate_groups([{"name": "A", "platforms": ["youtube"]},
                                 {"name": "A", "platforms": ["youtube"]}], ["youtube"])
    assert not bad


def test_scheduling_mode(tmp_path):
    db, cfg = _env(tmp_path)
    assert ss.scheduling_mode(db) == "manual"  # по умолчанию спрашиваем
    ss.set_scheduling_mode(db, "auto")
    assert ss.scheduling_mode(db) == "auto"
    ss.set_scheduling_mode(db, "wat")
    assert ss.scheduling_mode(db) == "manual"
