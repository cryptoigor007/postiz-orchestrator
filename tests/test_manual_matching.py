from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.manual_uploads import match_score, title_similarity


def test_title_similarity():
    assert title_similarity("Серия 1 — Победа!", "Серия 1 Победа") > 0.6
    assert title_similarity("abc", "xyz") == 0.0


def test_match_score_high_same_title_and_date():
    up = {"title": "Серия 1 Победа", "published_at": "2026-09-10T10:00:00+00:00",
          "duration_sec": 200}
    en = {"title": "Серия 1 Победа", "created_at": "2026-09-10T09:00:00+00:00",
          "duration_sec": 201}
    score, why = match_score(up, en)
    assert score >= 0.8
    assert "title" in why


def test_match_score_low_when_different():
    up = {"title": "Совсем другое", "published_at": "2026-01-01T00:00:00+00:00"}
    en = {"title": "Серия 1", "created_at": "2026-09-10T00:00:00+00:00"}
    score, _ = match_score(up, en)
    assert score < 0.55


def test_match_score_handles_missing_duration():
    up = {"title": "X", "published_at": "2026-09-10T10:00:00+00:00", "duration_sec": None}
    en = {"title": "X", "created_at": "2026-09-10T09:00:00+00:00"}
    score, why = match_score(up, en)
    assert score > 0.8
