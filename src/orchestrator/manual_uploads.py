from __future__ import annotations
import re
from datetime import datetime, timezone
from typing import Any

_WORD = re.compile(r"[^\w]+", re.UNICODE)


def normalize_title(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(_WORD.sub(" ", value.lower()).split())


def title_similarity(a: str | None, b: str | None) -> float:
    ta = set(normalize_title(a).split())
    tb = set(normalize_title(b).split())
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _date_score(a: str | None, b: str | None) -> float | None:
    da, db = _parse(a), _parse(b)
    if not da or not db:
        return None
    days = abs((da - db).total_seconds()) / 86400
    return max(0.0, 1.0 - days / 30.0)


def _dur_score(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or a <= 0 or b <= 0:
        return None
    gap = max(10.0, 0.05 * max(a, b))
    return max(0.0, 1.0 - abs(a - b) / gap)


def match_score(upload: dict[str, Any], entity: dict[str, Any]) -> tuple[float, dict]:
    parts: list[tuple[float, float]] = []
    why: dict[str, float] = {}

    if upload.get("title") and entity.get("title"):
        s = title_similarity(upload["title"], entity["title"])
        parts.append((0.5, s))
        why["title"] = round(s, 3)

    ds = _date_score(upload.get("published_at"), entity.get("created_at"))
    if ds is not None:
        parts.append((0.3, ds))
        why["date"] = round(ds, 3)

    dus = _dur_score(upload.get("duration_sec"), entity.get("duration_sec"))
    if dus is not None:
        parts.append((0.2, dus))
        why["duration"] = round(dus, 3)

    if not parts:
        return 0.0, why
    weight = sum(w for w, _ in parts)
    score = sum(w * s for w, s in parts) / weight
    return score, why
