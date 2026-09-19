from __future__ import annotations

import re
from datetime import UTC, datetime
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
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
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


def _within_lookback(published_at: str | None, days: int, now: Any) -> bool:
    if not published_at:
        return True
    dt = _parse(published_at)
    if dt is None:
        return True
    try:
        now_dt = now if getattr(now, "tzinfo", None) else now.replace(tzinfo=UTC)
    except Exception:
        now_dt = now
    return (now_dt - dt).total_seconds() <= days * 86400


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


class ManualUploadsService:
    """Scan -> match -> confirm/reject for manually uploaded videos."""

    def __init__(self, db: Any, cfg: Any, clock: Any):
        self.db = db
        self.cfg = cfg
        self.clock = clock

    def _known_ids(self, platform: str) -> set[str]:
        ids = {r["postiz_post_id"] for r in self.db.fetchall(
            "SELECT postiz_post_id FROM entity_platform_status "
            "WHERE platform=? AND postiz_post_id IS NOT NULL", (platform,))}
        ids |= {r["platform_video_id"] for r in self.db.fetchall(
            "SELECT platform_video_id FROM platform_uploads "
            "WHERE platform=? AND origin='postiz'", (platform,))}
        return ids

    def _entities(self, platform: str) -> list[dict]:
        out: list[dict] = []
        longs = self.db.fetchall(
            """
            SELECT lv.id, COALESCE(lv.title_text, lv.title) AS title, lv.created_at
            FROM long_videos lv
            WHERE NOT EXISTS (
                SELECT 1 FROM entity_platform_status eps
                WHERE eps.entity_type='long_video' AND eps.entity_id=lv.id
                  AND eps.platform=? AND eps.status IN ('scheduled','published'))
            """, (platform,))
        for r in longs:
            out.append({"_type": "long_video", "_id": r["id"],
                        "title": r["title"], "created_at": r["created_at"]})
        shorts = self.db.fetchall(
            """
            SELECT s.id, COALESCE(s.title_text, s.folder_path) AS title, s.created_at
            FROM shorts s
            WHERE NOT EXISTS (
                SELECT 1 FROM entity_platform_status eps
                WHERE eps.entity_type='short' AND eps.entity_id=s.id
                  AND eps.platform=? AND eps.status IN ('scheduled','published'))
            """, (platform,))
        for r in shorts:
            out.append({"_type": "short", "_id": r["id"],
                        "title": r["title"], "created_at": r["created_at"]})
        return out

    def scan_all(self, sources: dict) -> dict:
        """Scan every source that supports listing; return per-platform stats."""
        page = getattr(self.cfg.manual_uploads, "page_size", 50)
        stats: dict = {}
        for platform, src in (sources or {}).items():
            caps = getattr(src, "capabilities", lambda: {})()
            if not caps.get("list", False):
                stats[platform] = {"skipped": "engine does not support listing uploads"}
                continue
            try:
                try:
                    uploads = src.list_uploads({"max_results": page})
                except TypeError:
                    uploads = src.list_uploads()
            except Exception as e:
                stats[platform] = {"error": str(e)}
                continue
            stats[platform] = self.scan(platform, uploads, engine=self.cfg.engine_for(platform))
        return stats

    def candidates(self, upload_id: int) -> list[dict]:
        up = self.db.get_upload(upload_id)
        if not up:
            return []
        scored = []
        for e in self._entities(up["platform"]):
            s, why = match_score(up, e)
            scored.append((s, e, why))
        scored.sort(key=lambda x: -x[0])
        res = []
        for s, e, why in scored[:5]:
            if s <= 0:
                continue
            res.append({"entity_type": e["_type"], "entity_id": e["_id"],
                        "title": e["title"], "score": round(s, 3), "reasons": why})
        return res

    def scan(self, platform: str, uploads: list[dict], engine: str = "direct") -> dict:
        known = self._known_ids(platform)
        lookback = getattr(self.cfg.manual_uploads, "lookback_days", 0) or 0
        stats = {"found": 0, "manual": 0, "postiz": 0, "suggested": 0}
        for u in uploads:
            ext = str(u.get("external_id") or "")
            if not ext:
                continue
            if lookback and not _within_lookback(u.get("published_at"), lookback, self.clock.now()):
                continue
            origin = "postiz" if ext in known else "manual"
            row = self.db.upsert_upload(
                engine=engine, platform=platform, external_id=ext,
                url=u.get("url"), title=u.get("title"), description=u.get("description"),
                published_at=u.get("published_at"), duration_sec=u.get("duration_sec"),
                width=u.get("width"), height=u.get("height"),
                thumbnail_url=u.get("thumbnail_url"), origin=origin,
            )
            stats["found"] += 1
            stats[origin] += 1
            if origin == "manual" and row["match_status"] == "unmatched":
                cands = self.candidates(row["id"])
                if cands:
                    best = cands[0]
                    self.db.set_upload_match(
                        row["id"], best["entity_type"], best["entity_id"],
                        best["score"], "suggested")
                    stats["suggested"] += 1
        return stats

    def confirm(self, upload_id: int, entity_type: str, entity_id: int,
                confidence: float | None = None, apply_edits: bool = False,
                engine: Any = None) -> bool:
        row = self.db.get_upload(upload_id)
        if not row:
            return False
        if confidence is None:
            confidence = row.get("confidence")
        self.db.set_upload_match(upload_id, entity_type, entity_id, confidence, "confirmed")
        now = self.clock.now().isoformat()
        self.db.execute(
            """
            INSERT INTO entity_platform_status
                (entity_type, entity_id, platform, status, published_at, release_url)
            VALUES (?, ?, ?, 'published', ?, ?)
            ON CONFLICT(entity_type, entity_id, platform) DO UPDATE SET
                status='published',
                published_at=excluded.published_at,
                release_url=COALESCE(excluded.release_url, entity_platform_status.release_url)
            """,
            (entity_type, entity_id, row["platform"], now, row.get("url")),
        )
        if apply_edits and engine is not None:
            try:
                ok = engine.update_metadata(
                    str(row["platform_video_id"]),
                    {"description": row.get("description") or ""},
                )
                if not ok:
                    self.db.execute("UPDATE platform_uploads SET edit_error=? WHERE id=?",
                                    ("update_metadata failed", upload_id))
            except Exception as e:  # keep the match, record the edit failure
                self.db.execute("UPDATE platform_uploads SET edit_error=? WHERE id=?",
                                (str(e), upload_id))
        self.db.log(entity_type, entity_id, row["platform"], "manual_confirmed",
                    str(row["platform_video_id"]))
        return True

    def reject(self, upload_id: int) -> bool:
        self.db.set_upload_match(upload_id, None, None, None, "rejected")
        return True

    def ignore(self, upload_id: int) -> bool:
        self.db.set_upload_match(upload_id, None, None, None, "ignored")
        return True
