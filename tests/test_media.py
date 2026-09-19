from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.config import load_config
from orchestrator.media import make_media, maybe_compress

CFG = Path(__file__).resolve().parents[1] / "config.yaml"


def test_maybe_compress_disabled_by_default(tmp_path):
    cfg = load_config(CFG)
    f = tmp_path / "small.mp4"
    f.write_bytes(b"x" * 1024)
    assert cfg.media.telegram_max_mb == 0
    assert maybe_compress(str(f), "telegram", cfg) == str(f)


def test_make_media_symlink_mode(tmp_path, monkeypatch):
    cfg = load_config(CFG)
    cfg.media.local_prefix = str(tmp_path) + "/"
    cfg.media.symlink_mode = True
    f = tmp_path / "video.mp4"
    f.write_bytes(b"x" * 1024)

    class Broker:
        def symlink(self, src):
            return {"media_id": "abc", "path": "https://host/uploads/x.mp4"}

    class Postiz:
        def upload_media(self, path, platform):  # pragma: no cover
            raise AssertionError("не должен вызываться в symlink-режиме")

    media = make_media(str(f), "telegram", cfg, Postiz(), Broker())
    assert media.id == "abc" and media.path.endswith("x.mp4")


def test_make_media_fallback_upload(tmp_path):
    cfg = load_config(CFG)
    cfg.media.symlink_mode = False
    f = tmp_path / "video.mp4"
    f.write_bytes(b"x" * 1024)

    class Postiz:
        def upload_media(self, path, platform):
            from orchestrator.postiz import MediaRef
            return MediaRef(id="up1", path="https://host/uploads/up1.mp4")

    media = make_media(str(f), "telegram", cfg, Postiz(), None)
    assert media.id == "up1"
