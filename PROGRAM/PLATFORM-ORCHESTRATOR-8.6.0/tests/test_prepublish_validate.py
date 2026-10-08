"""Pre-publish validation hooks (media.prepublish_validate)."""
from __future__ import annotations

from pathlib import Path

from orchestrator.config import load_config
from orchestrator.media import prepublish_validate


def test_prepublish_missing_file(tmp_path: Path):
    cfg = load_config("config.ci.yaml")
    probs = prepublish_validate(str(tmp_path / "nope.mp4"), "telegram", cfg)
    assert probs


def test_prepublish_ok_small(tmp_path: Path):
    cfg = load_config("config.ci.yaml")
    f = tmp_path / "a.mp4"
    f.write_bytes(b"0" * 1024)
    probs = prepublish_validate(str(f), "telegram", cfg, content_kind="video_native")
    assert probs == []


def test_prepublish_promo_youtube():
    cfg = load_config("config.ci.yaml")
    probs = prepublish_validate("", "youtube", cfg, content_kind="promo_text")
    assert any("promo_text" in p for p in probs)
