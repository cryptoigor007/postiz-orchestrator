from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.clock import FakeClock
from orchestrator.config import load_config
from orchestrator.db import Database
from orchestrator.watcher import Watcher


@pytest.fixture
def env(tmp_path):
    db = Database(tmp_path / "w.sqlite")
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    root = tmp_path / "content"
    series = root / "my_series"
    (series / "wide").mkdir(parents=True)
    (series / "vertical").mkdir(parents=True)
    (series / "shorts" / "short_001").mkdir(parents=True)
    wide = series / "wide" / "final_16x9.mp4"
    wide.write_bytes(b"fake" * 100)
    vert = series / "vertical" / "final_9x16.mp4"
    vert.write_bytes(b"fake" * 100)
    short_v = series / "shorts" / "short_001" / "clip.mp4"
    short_v.write_bytes(b"short" * 50)
    (series / "info_metadata.txt").write_text("Title here")
    return db, cfg, clock, root, series


def test_watcher_registers(env):
    db, cfg, clock, root, series = env
    w = Watcher(db, cfg, clock, [str(root)])
    # need several scans for all files to become stable
    for _ in range(4):
        w.scan()
    row = db.fetchone("SELECT * FROM long_videos")
    assert row is not None
    assert "my_series" in row["folder_path"]
    shorts = db.fetchall("SELECT * FROM shorts")
    assert len(shorts) >= 1


def test_watcher_parses_meta(env):
    db, cfg, clock, root, series = env
    (series / "info_metadata.txt").write_text(
        "series: my_series\n"
        "package_title: НАСТОЯЩИЙ ЗАГОЛОВОК\n"
        "package_hook: hook line\n"
        "package_hashtags: #tag1 #tag2\n",
        encoding="utf-8",
    )
    (series / "vertical" / "my_series_description.txt").write_text(
        "Настоящее описание", encoding="utf-8"
    )
    short = series / "shorts" / "short_001"
    (short / "short_001_title.txt").write_text("Куда пропали друзья?", encoding="utf-8")
    (short / "short_001_description.txt").write_text("Описание шортса", encoding="utf-8")
    (short / "short_001_hashtags.txt").write_text("#shorts #test", encoding="utf-8")
    (short / "short_001_hook.txt").write_text("Хук!", encoding="utf-8")
    (short / "short_001_upload.txt").write_text("upload info", encoding="utf-8")
    (short / "short_001_cover.jpg").write_bytes(b"jpg")
    w = Watcher(db, cfg, clock, [str(root)])
    for _ in range(4):
        w.scan()
    lv = db.fetchone("SELECT * FROM long_videos")
    assert lv["title_text"] == "НАСТОЯЩИЙ ЗАГОЛОВОК"
    assert lv["description_text"] == "Настоящее описание"
    assert lv["hashtags_text"] == "#tag1 #tag2"
    s = db.fetchone("SELECT * FROM shorts")
    assert s["title_text"] == "Куда пропали друзья?"
    assert s["description_text"] == "Описание шортса"
    assert s["hashtags_text"] == "#shorts #test"
    assert s["hook_text"] == "Хук!"
    assert s["upload_text"] == "upload info"
    assert s["cover_path"].endswith("short_001_cover.jpg")


def test_watcher_root_can_be_series(env):
    db, cfg, clock, root, series = env
    w = Watcher(db, cfg, clock, [str(series)])
    for _ in range(4):
        w.scan()
    lv = db.fetchone("SELECT * FROM long_videos")
    assert lv is not None
    shorts = db.fetchall("SELECT * FROM shorts")
    assert len(shorts) >= 1


def test_shorts_maker_layout(tmp_path):
    db = Database(tmp_path / "s.sqlite")
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    root = tmp_path / "content"
    d = root / "шортс" / "Ш 19 деньги"
    d.mkdir(parents=True)
    (d / "Ш 19 деньги_final.mp4").write_bytes(b"v" * 200)
    (d / "Ш 19 деньги_titles.txt").write_text(
        "--- КЛИП #1 ---\nЗаголовок: Что с тобой сделают деньги?\nОписание: Деньги раскрывают суть.",
        encoding="utf-8",
    )
    (d / "Ш 19 деньги_hooks.txt").write_text(
        "--- ХУК #1 (0.2с) ---\nДеньги меняют людей или нет?\n  Вариант 1: x", encoding="utf-8"
    )
    (d / "Ш 19 деньги_hashtags.txt").write_text("#деньги #психология", encoding="utf-8")
    (d / "Ш 19 деньги_final_cover.jpg").write_bytes(b"jpg")
    w = Watcher(db, cfg, clock, [str(root)])
    for _ in range(4):
        w.scan()
    s = db.fetchone("SELECT * FROM shorts")
    assert s is not None
    assert s["title_text"] == "Что с тобой сделают деньги?"
    assert s["description_text"] == "Деньги раскрывают суть."
    assert s["hashtags_text"] == "#деньги #психология"
    assert s["hook_text"] == "Деньги меняют людей или нет?"
    assert s["cover_path"].endswith("_final_cover.jpg")
    assert s["source"] == "shortsmaker"


def test_junk_and_no_video_skipped(tmp_path):
    db = Database(tmp_path / "j.sqlite")
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    root = tmp_path / "content"
    tmp = root / "_tmp"
    tmp.mkdir(parents=True)
    (tmp / "final_16x9.mp4").write_bytes(b"x" * 100)
    (root / ".Spotlight-V100").mkdir()
    (root / "$RECYCLE.BIN").mkdir()
    (root / "пустая_серия" / "vertical").mkdir(parents=True)  # нет видео
    w = Watcher(db, cfg, clock, [str(root)])
    for _ in range(4):
        w.scan()
    assert db.fetchone("SELECT * FROM long_videos") is None
    assert db.fetchone("SELECT * FROM shorts") is None


def test_platform_dirs_platform_paths(tmp_path):
    db = Database(tmp_path / "p.sqlite")
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    series = tmp_path / "series" / "ep1"
    (series / "youtube").mkdir(parents=True)
    (series / "telegram").mkdir(parents=True)
    (series / "youtube" / "final.mp4").write_bytes(b"y" * 150)
    (series / "telegram" / "final.mp4").write_bytes(b"t" * 150)
    (series / "info_metadata.txt").write_text("package_title: Заголовок", encoding="utf-8")
    w = Watcher(db, cfg, clock, [str(series.parent)])
    for _ in range(4):
        w.scan()
    lv = db.fetchone("SELECT * FROM long_videos")
    assert lv is not None
    import json as _json
    pmap = _json.loads(lv["platform_paths"])
    assert set(pmap) == {"youtube", "telegram"}
    assert pmap["youtube"].endswith("final.mp4")


def test_root_kind_series_skips_standalone(tmp_path):
    db = Database(tmp_path / "k.sqlite")
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    root = tmp_path / "content"
    # эпизод
    ep = root / "ep1"
    (ep / "vertical").mkdir(parents=True)
    (ep / "vertical" / "final_9x16.mp4").write_bytes(b"v" * 200)
    (ep / "shorts" / "short_001").mkdir(parents=True)
    (ep / "shorts" / "short_001" / "short_001.mp4").write_bytes(b"s" * 100)
    # standalone-шортс Shorts Maker
    sm = root / "шортс" / "Ш 1"
    sm.mkdir(parents=True)
    (sm / "Ш 1_final.mp4").write_bytes(b"f" * 150)
    (sm / "Ш 1_titles.txt").write_text("Заголовок: Тест", encoding="utf-8")
    db.set_setting("watch_roots", "[""{\"path\": \"" + str(root) + "\", \"kind\": \"series\"}""]")
    w = Watcher(db, cfg, clock, [])
    for _ in range(4):
        w.scan()
    assert db.fetchone("SELECT * FROM long_videos") is not None
    titles = [r["title_text"] for r in db.fetchall("SELECT title_text FROM shorts")]
    assert "Тест" not in titles  # standalone не взят


def test_root_kind_shorts_only(tmp_path):
    db = Database(tmp_path / "k2.sqlite")
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    root = tmp_path / "content"
    ep = root / "ep1"
    (ep / "vertical").mkdir(parents=True)
    (ep / "vertical" / "final_9x16.mp4").write_bytes(b"v" * 200)
    (ep / "shorts" / "short_001").mkdir(parents=True)
    (ep / "shorts" / "short_001" / "short_001.mp4").write_bytes(b"s" * 100)
    sm = root / "шортс" / "Ш 1"
    sm.mkdir(parents=True)
    (sm / "Ш 1_final.mp4").write_bytes(b"f" * 150)
    (sm / "Ш 1_titles.txt").write_text("Заголовок: Тест", encoding="utf-8")
    db.set_setting("watch_roots", "[""{\"path\": \"" + str(root) + "\", \"kind\": \"shorts\"}""]")
    w = Watcher(db, cfg, clock, [])
    for _ in range(4):
        w.scan()
    assert db.fetchone("SELECT * FROM long_videos") is None
    rows = db.fetchall("SELECT title_text, parent_video_id FROM shorts")
    assert any(r["title_text"] == "Тест" for r in rows)
    assert all(r["parent_video_id"] is None for r in rows)


def test_link_orphan_shorts(tmp_path):
    db = Database(tmp_path / "l.sqlite")
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    db.execute(
        "INSERT INTO long_videos (source, folder_path, title, created_at) "
        "VALUES ('videomaker', '/s1', 'S1', '2026-01-01T00:00:00+00:00')"
    )
    lv = db.fetchone("SELECT id FROM long_videos")
    db.execute(
        "INSERT INTO shorts (source, parent_video_id, folder_path, video_path, created_at) "
        "VALUES ('videomaker', NULL, '/s1/shorts/short_001', '/s1/shorts/short_001/a.mp4', "
        "'2026-01-01T00:00:00+00:00')"
    )
    w = Watcher(db, cfg, clock, [])
    linked = w._link_orphan_shorts()
    assert linked == 1
    row = db.fetchone("SELECT parent_video_id FROM shorts")
    assert row["parent_video_id"] == lv["id"]


def test_shorts_maker_description_and_cover(tmp_path):
    db = Database(tmp_path / "d.sqlite")
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    root = tmp_path / "content"
    d = root / "шортс" / "ш1"
    d.mkdir(parents=True)
    (d / "ш1_final.mp4").write_bytes(b"v" * 200)
    (d / "ш1_title.txt").write_text("Заголовок", encoding="utf-8")
    (d / "ш1_description.txt").write_text("Полное описание шортса", encoding="utf-8")
    (d / "ш1_final_cover.jpg").write_bytes(b"jpg")
    w = Watcher(db, cfg, clock, [str(root)])
    for _ in range(4):
        w.scan()
    s = db.fetchone("SELECT * FROM shorts")
    assert s["description_text"] == "Полное описание шортса"
    assert s["cover_path"] and s["cover_path"].endswith("ш1_final_cover.jpg")


def test_long_cover_detected(tmp_path):
    db = Database(tmp_path / "c.sqlite")
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    series = tmp_path / "content" / "s1"
    (series / "wide").mkdir(parents=True)
    (series / "wide" / "final_16x9.mp4").write_bytes(b"v" * 200)
    (series / "cover.jpg").write_bytes(b"jpg")
    w = Watcher(db, cfg, clock, [str(series.parent)])
    for _ in range(4):
        w.scan()
    lv = db.fetchone("SELECT * FROM long_videos")
    assert lv["cover_path"] and lv["cover_path"].endswith("cover.jpg")


def test_backfill_description(tmp_path):
    db = Database(tmp_path / "b.sqlite")
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    clock = FakeClock(datetime(2026, 3, 10, 12, 0, tzinfo=UTC))
    d = tmp_path / "content" / "s1"
    d.mkdir(parents=True)
    video = d / "s1.mp4"
    video.write_bytes(b"v" * 100)
    (d / "s1_description.txt").write_text("Описание из файла", encoding="utf-8")
    db.execute(
        "INSERT INTO shorts (source, folder_path, video_path, description_text, created_at) "
        "VALUES ('shortsmaker', ?, ?, '', '2026-01-01T00:00:00+00:00')",
        (str(d), str(video)),
    )
    w = Watcher(db, cfg, clock, [str(d)])
    assert w._backfill_descriptions() == 1
    row = db.fetchone("SELECT description_text FROM shorts")
    assert row["description_text"] == "Описание из файла"


def test_short_folder_suffix_files_named_by_video(env):
    """Папка short_002выст, а файлы-компаньоны названы short_002_* (как в реальных папках)."""
    db, cfg, clock, root, series = env
    d = series / "shorts" / "short_002выст"
    d.mkdir(parents=True)
    (d / "short_002.mp4").write_bytes(b"short" * 60)
    (d / "short_002_title.txt").write_text("Настоящий заголовок", encoding="utf-8")
    (d / "short_002_description.txt").write_text("Описание", encoding="utf-8")
    (d / "short_002_hashtags.txt").write_text("#tag1 #tag2", encoding="utf-8")
    (d / "short_002_hook.txt").write_text("Хук", encoding="utf-8")
    w = Watcher(db, cfg, clock, [str(root)])
    for _ in range(4):
        w.scan()
    row = db.fetchone(
        "SELECT * FROM shorts WHERE folder_path LIKE '%short_002выст%'")
    assert row is not None
    assert row["title_text"] == "Настоящий заголовок"
    assert row["description_text"] == "Описание"
    assert row["hashtags_text"] == "#tag1 #tag2"
    assert row["hook_text"] == "Хук"


def test_watcher_skips_archive_dirs(env):
    """Архивные папки (broll_downloads, ютюб и др.) не должны попадать в базу."""
    db, cfg, clock, root, series = env
    arch = root / "broll_downloads" / "ссд" / "тайный кризис человечества"
    (arch / "vertical").mkdir(parents=True)
    (arch / "wide").mkdir(parents=True)
    (arch / "wide" / "final_16x9.mp4").write_bytes(b"fake" * 100)
    (arch / "vertical" / "final_9x16.mp4").write_bytes(b"fake" * 100)
    (arch / "info_metadata.txt").write_text("Архив")
    yt = root / "ютюб" / "шортс" / "ш1 тест"
    yt.mkdir(parents=True)
    (yt / "short.mp4").write_bytes(b"short" * 60)
    w = Watcher(db, cfg, clock, [str(root)])
    for _ in range(4):
        w.scan()
    assert db.fetchone("SELECT COUNT(*) AS c FROM long_videos WHERE folder_path LIKE '%broll_downloads%'")["c"] == 0
    assert db.fetchone("SELECT COUNT(*) AS c FROM shorts WHERE folder_path LIKE '%ютюб%'")["c"] == 0


def test_watcher_accepts_old_files(env):
    """Файлы старше 30 дней тоже подхватываются (скан должен возвращать удалённое)."""
    import os
    import time

    db, cfg, clock, root, series = env
    d = series / "shorts" / "short_010"
    d.mkdir(parents=True)
    old = d / "short_010.mp4"
    old.write_bytes(b"short" * 60)
    (d / "short_010_title.txt").write_text("Старый шорт", encoding="utf-8")
    past = time.time() - 200 * 86400
    os.utime(old, (past, past))
    w = Watcher(db, cfg, clock, [str(root)])
    for _ in range(4):
        w.scan()
    assert db.fetchone(
        "SELECT COUNT(*) AS c FROM shorts WHERE folder_path LIKE '%short_010%'")["c"] == 1


def test_watcher_survives_permission_denied_dir(env):
    """Недоступная папка в дереве не должна ронять весь скан (PermissionError)."""
    import os
    import stat

    db, cfg, clock, root, series = env
    bad = series / "no_access"
    bad.mkdir()
    (bad / "vertical").mkdir()
    os.chmod(bad, 0)
    try:
        w = Watcher(db, cfg, clock, [str(root)])
        for _ in range(2):
            w.scan()  # не должно бросать
    finally:
        os.chmod(bad, stat.S_IRWXU)
    assert True


def test_scan_reports_checked_and_unstable(env):
    """Скан сообщает, сколько папок проверено и сколько пропущено из-за нестабильности."""
    db, cfg, clock, root, series = env
    w = Watcher(db, cfg, clock, [str(root)])
    first = w.scan()
    assert first["checked"] >= 1
    assert first["unstable"] >= 1  # первый проход: файлы ещё не стабильны
    second = w.scan()
    assert second["checked"] >= 1
