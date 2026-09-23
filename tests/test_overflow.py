from pathlib import Path


def test_overflow_does_not_move_files_by_default(tmp_path):
    """Лишние шорты серии не переносятся физически — файлы остаются на месте."""
    from datetime import UTC, datetime

    from orchestrator.clock import FakeClock
    from orchestrator.config import load_config
    from orchestrator.db import Database
    from orchestrator.overflow import move_excess_shorts

    db = Database(tmp_path / "o.sqlite")
    cfg = load_config(Path(__file__).resolve().parents[1] / "config.yaml")
    clock = FakeClock(datetime(2026, 3, 20, 12, 0, tzinfo=UTC))
    cfg.limits.max_shorts_per_long_video = 1
    series = tmp_path / "series"
    (series / "shorts").mkdir(parents=True)
    db.execute("INSERT INTO long_videos (source, folder_path, title, created_at) "
               "VALUES ('videomaker', ?, 'F', ?)", (str(series), clock.now().isoformat()))
    fid = db.fetchone("SELECT id FROM long_videos ORDER BY id DESC")["id"]
    ids = []
    for i in (1, 2):
        d = series / "shorts" / f"short_{i:03d}"
        d.mkdir(parents=True)
        (d / f"short_{i:03d}.mp4").write_bytes(b"x" * 100)
        db.execute("INSERT INTO shorts (source, parent_video_id, folder_path, video_path, "
                   "title_text, created_at) VALUES ('videomaker', ?, ?, ?, 's', ?)",
                   (fid, str(d), str(d / f"short_{i:03d}.mp4"), clock.now().isoformat()))
        ids.append(db.fetchone("SELECT id FROM shorts ORDER BY id DESC")["id"])
    moved = move_excess_shorts(db, cfg, clock, fid)
    assert moved == 1
    assert (series / "shorts" / "short_002" / "short_002.mp4").is_file(), "файл не должен переноситься"
    assert not (series / "shorts_overflow").exists()
    row = db.fetchone("SELECT status FROM entity_platform_status "
                      "WHERE entity_type='short' AND entity_id=? AND platform='youtube'", (ids[1],))
    assert row["status"] == "skipped"
