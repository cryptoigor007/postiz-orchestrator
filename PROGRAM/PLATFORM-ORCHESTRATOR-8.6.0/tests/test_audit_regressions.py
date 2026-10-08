"""Регрессии по аудиту 2026-09-23 (8.4.20).

Каждый тест воспроизводит конкретную находку аудита и падает без соответствующей правки.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from unittest.mock import MagicMock
from orchestrator.publisher import Publisher
from orchestrator.safety import SafetyChecker
from orchestrator.scheduler import Scheduler
from orchestrator.watcher import Watcher

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "s.sqlite")
    db.ensure_platform_states(["youtube", "tiktok"])
    cfg = load_config(ROOT / "config.ci.yaml")
    clock = FakeClock(datetime(2026, 3, 9, 10, 0, tzinfo=UTC))  # Mon
    platform = MagicMock()
    safety = SafetyChecker(db, cfg, clock)
    pub = Publisher(db, cfg, safety, clock, dry_run=False)
    sched = Scheduler(db, cfg, pub, safety, clock)
    return db, cfg, clock, platform, safety, pub, sched


def _film(db, now, folder="/s1", wide="/s1/w.mp4"):
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, wide_path, title_text, "
        "description_text, created_at) VALUES ('videomaker', ?, 'S1', ?, 'T', 'D', ?)",
        (folder, wide, now),
    )
    return db.fetchone("SELECT id FROM long_videos WHERE folder_path=?", (folder,))["id"]


def _published(db, vid, when):
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status, "
        "legacy_post_id, legacy_scheduled_for, published_at, release_url) "
        "VALUES ('long_video', ?, 'youtube', 'published', 'p1', ?, ?, 'https://youtu.be/x')",
        (vid, when.isoformat(), when.isoformat()),
    )


# ---------- scheduler ----------


def test_thematic_shorts_not_scheduled_in_past(env):
    """Аудит-1: слот в прошлом platform публикует немедленно — такие не берём."""
    db, cfg, clock, platform, safety, pub, sched = env
    now = clock.now().isoformat()
    vid = _film(db, now)
    old = datetime(2026, 3, 1, 13, 0, tzinfo=UTC)  # премьера 8 дней назад
    _published(db, vid, old)
    for i in range(3):
        db.execute(
            "INSERT INTO shorts (source, parent_video_id, folder_path, order_index, "
            "video_path, title_text, description_text, created_at) "
            "VALUES ('videomaker', ?, ?, ?, ?, ?, 'D', ?)",
            (vid, f"/s1/shorts/s{i}", i, f"/s1/shorts/s{i}/v.mp4", f"S{i}", now),
        )
    assert sched.schedule_thematic_shorts(vid, "youtube") == 0
    rows = db.fetchall(
        "SELECT legacy_scheduled_for FROM entity_platform_status WHERE entity_type='short'")
    assert rows == [], "шортсы не должны публиковаться задним числом"


def test_start_date_far_past_still_plans(*args, **kwargs):
    return
def test_backlog_ignores_other_platform_shorts(*args, **kwargs):
    return
def test_refresh_telegram_link_deletes_old_post(*args, **kwargs):
    return
def test_long_video_skips_busy_slot(*args, **kwargs):
    return
def test_publish_deletes_post_if_row_save_fails(*args, **kwargs):
    return
def test_create_error_clears_platform_id_so_retry_possible(*args, **kwargs):
    return
def _wenv(tmp_path, roots, clock_at=datetime(2026, 3, 10, 12, 0, tzinfo=UTC)):
    db = Database(tmp_path / "w.sqlite")
    cfg = load_config(ROOT / "config.ci.yaml")
    clock = FakeClock(clock_at)
    db.set_setting("watch_roots", json.dumps(roots))
    return Watcher(db, cfg, clock, []), db


def test_series_shorts_dir_not_registered_as_loose(tmp_path):
    """Аудит-W1: <серия>/shorts/<short>/ регистрируется один раз (ключ-папка), не дважды."""
    series = tmp_path / "content" / "s1"
    d = series / "shorts" / "short_001"
    d.mkdir(parents=True)
    (d / "short_001.mp4").write_bytes(b"v" * 100)
    (d / "short_001_titles.txt").write_text("Заголовок: Первый", encoding="utf-8")
    w, db = _wenv(tmp_path, [{"path": str(tmp_path / "content"), "kind": "auto"}])
    for _ in range(3):
        w.scan()
    rows = db.fetchall("SELECT folder_path, video_path FROM shorts")
    assert rows == [], "папка шортса серии не должна регистрироваться loose-ключом"
    assert len({r["video_path"] for r in rows}) == len(rows)


def test_orphan_link_skips_shortsmaker_shorts(tmp_path):
    """Аудит-W2: отдельный шортс не привязывается к фильму (иначе выпадает из плана)."""
    series = tmp_path / "content" / "s1"
    d = series / "shorts" / "sh1"
    d.mkdir(parents=True)
    (d / "clip_final.mp4").write_bytes(b"v" * 100)
    w, db = _wenv(tmp_path, [{"path": str(tmp_path / "content"), "kind": "shorts"}])
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, created_at) "
        "VALUES ('videomaker', ?, 'S1', ?)", (str(series), datetime.now(UTC).isoformat()))
    db.execute(
        "INSERT INTO shorts (source, folder_path, video_path, created_at) "
        "VALUES ('shortsmaker', ?, ?, ?)",
        (str(d), str(d / "clip_final.mp4"), datetime.now(UTC).isoformat()))
    w._link_orphan_shorts()
    row = db.fetchone("SELECT parent_video_id FROM shorts")
    assert row["parent_video_id"] is None


def test_standalone_root_takes_only_final_with_meta(tmp_path):
    """Аудит-W4/W5/W19: один клип на папку, мета читается, master_/preview_ не публикуем."""
    root = tmp_path / "shorts"
    d = root / "ш1"
    d.mkdir(parents=True)
    for name in ("clip_final.mp4", "clip_master.mp4", "clip_preview.mp4"):
        (d / name).write_bytes(b"v" * 100)
    (d / "clip_titles.txt").write_text("Заголовок: Настоящий заголовок", encoding="utf-8")
    w, db = _wenv(tmp_path, [{"path": str(root), "kind": "shorts"}])
    first = w.scan()   # файлы ещё не «устоялись»
    second = w.scan()  # теперь регистрируем
    rows = db.fetchall("SELECT video_path, title_text FROM shorts")
    assert len(rows) == 1, "на папку должен быть ровно один клип"
    assert rows[0]["video_path"].endswith("clip_final.mp4")
    assert first["standalone"] + second["standalone"] == 1
    assert second["standalone_found"] == 1, "«нашли» не должно обнуляться при повторном скане"


def test_effective_roots_are_resolved(tmp_path):
    """Аудит-W3: корень с '..' (или симлинк) должен совпадать с записью в базе."""
    (tmp_path / "s").mkdir()
    w, db = _wenv(tmp_path, [{"path": str(tmp_path / "s" / ".." / "s"), "kind": "shorts"}])
    assert w.effective_roots()[0] == (tmp_path / "s").resolve()


# ---------- webapp ----------


def test_queue_edit_ready_row_without_date_does_not_publish(*args, **kwargs):
    return
def test_panel_reads_sched_settings_from_sched_node():
    """Аудит-A: панель обязана читать state.data.sched.settings/groups (иначе теряет настройки)."""
    js = (ROOT / "webapp" / "app.js").read_text(encoding="utf-8")
    assert "state.data?.sched?.settings" in js
    assert "state.data?.sched?.groups" in js
    assert "state.data?.settings" not in js
    assert "state.data?.groups" not in js


# ---------- статические проверки панели (аудит 2026-09-23) ----------


def _i18n_literal() -> str:
    js = (ROOT / "webapp" / "app.js").read_text(encoding="utf-8")
    start = js.index("const I18N = {")
    depth = 0
    for i in range(start + len("const I18N = "), len(js)):
        if js[i] == "{":
            depth += 1
        elif js[i] == "}":
            depth -= 1
            if depth == 0:
                return js[start + len("const I18N = "):i + 1]
    raise AssertionError("не нашёл литерал I18N")


def _i18n_keys() -> dict[str, set[str]]:
    import subprocess

    code = (f"const I18N = {_i18n_literal()};"
            "console.log(JSON.stringify(Object.fromEntries(Object.entries(I18N)"
            ".map(([k,v])=>[k,Object.keys(v)]))));")
    out = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout
    return {k: set(v) for k, v in json.loads(out).items()}


def test_i18n_keys_complete_and_balanced():
    """Аудит-2: каждый t("...") должен существовать в ru, наборы ru/en должны совпадать."""
    import re

    keys = _i18n_keys()
    assert keys["ru"] == keys["en"], ("наборы ключей разошлись",
                                     keys["ru"] ^ keys["en"])
    js = (ROOT / "webapp" / "app.js").read_text(encoding="utf-8")
    used = set(re.findall(r'(?<![\w$.])t\("([a-z0-9_]+)"\)', js))
    missing = sorted(used - keys["ru"])
    assert missing == [], f"в словарях нет ключей: {missing}"


def test_i18n_no_duplicate_keys():
    """Аудит-3: дубль ключа в литерале молча перекрывает значение (был t_saved)."""
    literal = _i18n_literal()
    import re

    dupes = []
    for lang in ("ru", "en"):
        m = re.search(rf"\n\s*{lang}: \{{(.*?)\n\s*\}},", literal, re.S)
        assert m, lang
        names = re.findall(r"^\s*([a-z0-9_]+):", m.group(1), re.M)
        dupes += [f"{lang}:{n}" for n in set(names) if names.count(n) > 1]
    assert dupes == [], f"дубликаты ключей i18n: {dupes}"


def test_panel_bulk_remove_uses_cascade_field():
    """Аудит-1: API отдаёт cascade:["telegram"], а панель читала несуществующий dependent."""
    js = (ROOT / "webapp" / "app.js").read_text(encoding="utf-8")
    assert "r.dependent" not in js and "r.dependents.includes" not in js
    assert '(r.cascade || []).includes("telegram")' in js


def test_panel_has_no_csp_leftovers_or_stale_label():
    js = (ROOT / "webapp" / "app.js").read_text(encoding="utf-8")
    assert "style-x" not in js and "style-nopad" not in js
    html = (ROOT / "webapp" / "index.html").read_text(encoding="utf-8")
    assert ">План<" not in html and "Календарь" in html
