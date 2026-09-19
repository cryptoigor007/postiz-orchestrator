from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import sqlite3
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from . import sched_settings
from .watcher import WATCH_ROOTS_KEY

logger = logging.getLogger(__name__)

WEBAPP_DIR = Path(__file__).resolve().parents[2] / "webapp"
WEBAPP_BUILD = "45"


def validate_init_data(init_data: str, bot_token: str) -> dict[str, Any] | None:
    """Validate Telegram WebApp initData. Returns parsed dict or None."""
    if init_data == "dev" and os.getenv("WEBAPP_DEV", "").lower() in ("1", "true", "yes"):
        return {"user": {"id": 0, "first_name": "Dev"}, "dev": True}
    if not init_data or not bot_token:
        return None
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            return None
        check = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, received_hash):
            return None
        if "user" in parsed:
            parsed["user"] = json.loads(parsed["user"])
        return parsed
    except Exception:
        logger.exception("initData validation failed")
        return None


class WebAppAPI:
    def __init__(self, comps: dict[str, Any]):
        self.comps = comps
        self.cfg = comps["cfg"]
        self.db = comps["db"]
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self._rl: dict[str, deque] = {}

    def _auth(self, headers: dict[str, str], query: dict[str, str] | None = None) -> dict[str, Any] | None:
        access_key = os.getenv("WEBAPP_ACCESS_KEY", "").strip()
        if access_key:
            provided = (
                headers.get("X-Webapp-Key")
                or headers.get("x-webapp-key")
                or (query or {}).get("key")
                or ""
            )
            if provided and hmac.compare_digest(provided, access_key):
                return {"user": {"id": "access-key"}, "access_key": True}
        init = headers.get("X-Telegram-Init-Data") or headers.get("x-telegram-init-data") or ""
        data = validate_init_data(init, self.token)
        if not data:
            return None
        # whitelist
        allowed = self.cfg.telegram.allowed_chat_ids
        user = data.get("user") or {}
        uid = user.get("id")
        if data.get("dev"):
            return data
        if allowed and uid not in allowed:
            return None
        return data

    def handle(self, method: str, path: str, headers: dict, body: bytes) -> tuple[int, dict | bytes, str]:
        """Return (status, payload, content_type)."""
        split = urlsplit(path)
        qpath = split.path
        query = dict(parse_qsl(split.query))
        logger.info(
            "WEBAPP_REQ %s %s ua=%s ip=%s",
            method, path,
            (headers.get("User-Agent") or headers.get("user-agent") or "")[:70],
            headers.get("X-Forwarded-For") or headers.get("x-forwarded-for") or "",
        )
        is_api = qpath.startswith("/webapp/api/")

        # static (never intercept /webapp/api/*)
        if not is_api:
            if method == "GET" and qpath == "/webapp/diag":
                logger.warning(
                    "WEBAPP_DIAG href=%s tg=%s key=%s",
                    query.get("u"), query.get("tg"), query.get("k"),
                )
                return 204, b"", "text/plain"
            if method == "GET":
                bprefix = f"/webapp/b/{WEBAPP_BUILD}"
                last = qpath.rstrip("/").rsplit("/", 1)[-1]
                is_asset = "." in last
                is_page = (not is_asset) and (
                    qpath in ("/webapp", "/webapp/", "/webapp/index.html")
                    or qpath.startswith("/webapp/k/")
                    or qpath == bprefix
                    or qpath.startswith(bprefix + "/")
                )
                if is_page:
                    return (
                        200,
                        self._compose_index(self._key_from_request(qpath, query)),
                        "text/html; charset=utf-8",
                    )
                for prefix in (bprefix + "/", "/webapp/"):
                    if qpath.startswith(prefix) and ".." not in qpath:
                        name = qpath[len(prefix):]
                        if name and "." in name.rsplit("/", 1)[-1]:
                            ctype = {
                                "css": "text/css; charset=utf-8",
                                "js": "application/javascript; charset=utf-8",
                                "html": "text/html; charset=utf-8",
                                "svg": "image/svg+xml",
                                "png": "image/png",
                            }.get(name.rsplit(".", 1)[-1], "application/octet-stream")
                            return self._file(name, ctype)
            return 404, {"error": "not found"}, "application/json"

        auth = self._auth(headers, query)
        if not auth:
            return 401, {"error": "unauthorized"}, "application/json"
        if self._rate_limited(headers):
            return 429, {"error": "too many requests"}, "application/json"

        route = qpath[len("/webapp/api/") :].strip("/")
        data = {}
        if body:
            try:
                data = json.loads(body.decode() or "{}")
            except Exception:
                data = {}

        try:
            if method == "GET" and route == "version":
                from . import __version__
                return 200, {"version": __version__}, "application/json"
            if method == "GET" and route == "metrics":
                return 200, self._metrics(), "application/json"
            if method == "GET" and route == "status":
                return 200, self._status(), "application/json"
            if method == "GET" and route == "calendar":
                return 200, self._calendar(), "application/json"
            if method == "GET" and route == "queue":
                return 200, self._queue(), "application/json"
            if method == "GET" and route == "platforms":
                return 200, self._platforms(), "application/json"
            if method == "GET" and route == "tail":
                return 200, self._tail(), "application/json"
            if method == "GET" and route == "failed":
                return 200, self._failed(), "application/json"
            if method == "POST" and route == "pause":
                for p in self.cfg.platforms:
                    self.comps["safety"].pause_platform(p, "webapp")
                return 200, {"ok": True}, "application/json"
            if method == "POST" and route == "resume":
                for p in self.cfg.platforms:
                    self.comps["safety"].resume_platform(p)
                return 200, {"ok": True}, "application/json"
            if method == "POST" and route == "resume_platform":
                p = (data.get("platform") or "").strip()
                if p not in self.cfg.platforms:
                    return 400, {"error": "unknown platform"}, "application/json"
                self.comps["safety"].resume_platform(p)
                return 200, {"ok": True}, "application/json"
            if method == "POST" and route == "distribute":
                n = self.comps["scheduler"].schedule_long_videos()
                return 200, {"ok": True, "count": n}, "application/json"
            if method == "POST" and route == "series_end":
                p = (data.get("platform") or "youtube").strip()
                enable = bool(data.get("enable"))
                self.db.execute(
                    "UPDATE platform_queue_state SET series_tail_mode=?, "
                    "pending_series_end_question=0, updated_at=? WHERE platform=?",
                    (1 if enable else 0, self.comps["clock"].now().isoformat(), p),
                )
                return 200, {"ok": True, "tail": enable}, "application/json"
            if method == "POST" and route == "force_link":
                ok = self.comps["link_upd"].force_update(
                    int(data["entity_id"]),
                    str(data["platform"]),
                    str(data["url"]),
                )
                return (200, {"ok": True}, "application/json") if ok else (
                    400, {"error": "failed"}, "application/json"
                )
            if method == "GET" and route == "roots":
                return 200, {
                    "roots": self._roots(),
                    "items": self._root_items(),
                    "browse_roots": [str(r) for r in self._browse_roots()],
                }, "application/json"
            if method == "POST" and route == "roots":
                source = data.get("items")
                if source is None:
                    source = data.get("roots")
                if not isinstance(source, list):
                    return 400, {"error": "items must be a list"}, "application/json"
                allowed = self._browse_roots()
                cleaned: list[dict[str, str]] = []
                for item in source:
                    if isinstance(item, dict):
                        raw_path = item.get("path")
                        kind = str(item.get("kind") or "auto").strip().lower()
                    else:
                        raw_path = item
                        kind = "auto"
                    if kind not in ("auto", "series", "shorts"):
                        return 400, {"error": f"bad kind: {kind}"}, "application/json"
                    target = Path(str(raw_path or "")).expanduser()
                    if not target.is_dir():
                        return 400, {"error": f"not a directory: {raw_path}"}, "application/json"
                    rp = target.resolve()
                    if not any(rp == r or r in rp.parents for r in allowed):
                        return 400, {"error": f"outside allowed root: {raw_path}"}, "application/json"
                    cleaned.append({"path": str(rp), "kind": kind})
                self.db.set_setting(WATCH_ROOTS_KEY, json.dumps(cleaned, ensure_ascii=False))
                return 200, {"ok": True, "items": cleaned,
                             "roots": [it["path"] for it in cleaned]}, "application/json"
            if method == "GET" and route == "schedule_settings":
                settings = sched_settings.load_schedule_settings(self.db)
                groups = sched_settings.load_groups(self.db)
                platforms = list(self.cfg.platforms.keys())
                effective = {}
                for p in platforms:
                    effective[p] = {
                        "long": sched_settings.effective(self.db, self.cfg, p, "long"),
                        "thematic": sched_settings.effective(self.db, self.cfg, p, "thematic"),
                        "standalone": sched_settings.effective(self.db, self.cfg, p, "standalone"),
                        "daily_limit": sched_settings.effective_daily_limit(self.db, self.cfg, p),
                    }
                return 200, {
                    "settings": settings,
                    "groups": groups,
                    "platforms": platforms,
                    "mode": sched_settings.scheduling_mode(self.db),
                    "effective": effective,
                }, "application/json"
            if method == "POST" and route == "schedule_settings":
                payload = data.get("settings")
                ok, msg = sched_settings.validate_schedule_settings(payload)
                if not ok:
                    return 400, {"error": msg}, "application/json"
                known = list(self.cfg.platforms.keys())
                for key in payload:
                    if key.startswith("group:"):
                        if key[6:] not in {g["name"] for g in sched_settings.load_groups(self.db)}:
                            return 400, {"error": f"unknown group: {key[6:]}"}, "application/json"
                    elif key not in known:
                        return 400, {"error": f"unknown platform: {key}"}, "application/json"
                sched_settings.save_schedule_settings(self.db, payload)
                return 200, {"ok": True}, "application/json"
            if method == "POST" and route == "queue/edit":
                etype = str(data.get("entity_type") or "").strip()
                platform_sel = str(data.get("platform") or "").strip()
                try:
                    eid = int(data.get("entity_id") or 0)
                except Exception:
                    eid = 0
                if etype not in ("long_video", "short") or not eid:
                    return 400, {"error": "entity_type/entity_id required"}, "application/json"
                table = "long_videos" if etype == "long_video" else "shorts"
                title = str(data.get("title") or "")
                desc = str(data.get("description") or "")
                tags = str(data.get("hashtags") or "")
                self.db.execute(
                    f"UPDATE {table} SET title_text=?, description_text=?, hashtags_text=? "
                    "WHERE id=?",
                    (title[:200], desc, tags, eid),
                )
                sql = ("SELECT platform, postiz_post_id, postiz_scheduled_for, status "
                       "FROM entity_platform_status WHERE entity_type=? AND entity_id=? "
                       "AND status IN ('scheduled','updating','ready','error')")
                params: list = [etype, eid]
                if platform_sel:
                    sql += " AND platform=?"
                    params.append(platform_sel)
                rows = self.db.fetchall(sql, tuple(params))
                postiz = self.comps.get("postiz")
                sch = self.comps.get("scheduler")
                pub = getattr(sch, "publisher", None)
                updated = 0
                recreated = 0
                for r in rows:
                    plat = r["platform"]
                    pid = r.get("postiz_post_id")
                    if pid and postiz is not None:
                        try:
                            if hasattr(postiz, "delete_post"):
                                postiz.delete_post(str(pid))
                            elif hasattr(postiz, "set_status"):
                                postiz.set_status(str(pid), "draft")
                        except Exception:
                            logger.warning("queue edit: не удалось отменить %s", pid, exc_info=True)
                    self.db.execute(
                        "UPDATE entity_platform_status SET status='ready', postiz_post_id=NULL, "
                        "last_error=NULL WHERE entity_type=? AND entity_id=? AND platform=?",
                        (etype, eid, plat),
                    )
                    self.db.log(etype, eid, plat, "queue_edit", "")
                    updated += 1
                    if pub is None:
                        continue
                    entity = self.db.fetchone(f"SELECT * FROM {table} WHERE id=?", (eid,))
                    if not entity:
                        continue
                    pcfg = self.cfg.platforms.get(plat)
                    path = None
                    if sch is not None and hasattr(sch, "_pick_path"):
                        try:
                            if etype == "long_video":
                                path = sch._pick_path(entity, plat, pcfg)
                            else:
                                path = sch._pick_path(entity, plat) or entity.get("video_path")
                        except Exception:
                            path = entity.get("video_path")
                    if not path:
                        path = entity.get("video_path") or entity.get("vertical_path")                             or entity.get("wide_path")
                    when = r.get("postiz_scheduled_for")
                    sched_dt = None
                    new_date = str(data.get("date") or "").strip()
                    new_time = str(data.get("time") or "").strip()
                    if new_date and new_time:
                        try:
                            from datetime import date as _date

                            from .slots import local_to_utc, parse_time
                            y, m, d = (int(x) for x in new_date.split("-"))
                            sched_dt = local_to_utc(_date(y, m, d), parse_time(new_time),
                                                    self.cfg.timezone)
                        except Exception:
                            sched_dt = None
                    if sched_dt is None and when:
                        from datetime import datetime as _dt
                        try:
                            sched_dt = _dt.fromisoformat(str(when))
                        except Exception:
                            sched_dt = None
                    content = {"title": title, "description": desc, "hashtags": tags}
                    try:
                        post = pub.publish(etype, eid, plat, path, content, sched_dt)
                        if post:
                            recreated += 1
                        elif sched_dt is not None:
                            self.db.execute(
                                "UPDATE entity_platform_status SET postiz_scheduled_for=? "
                                "WHERE entity_type=? AND entity_id=? AND platform=?",
                                (sched_dt.isoformat(), etype, eid, plat),
                            )
                    except Exception:
                        logger.exception("queue edit: пересоздание не удалось (%s/%s %s)",
                                         etype, eid, plat)
                return 200, {"ok": True, "updated": updated, "recreated": recreated}, \
                    "application/json"
            if method == "POST" and route == "queue/restore":
                etype = str(data.get("entity_type") or "").strip()
                try:
                    eid = int(data.get("entity_id") or 0)
                except Exception:
                    eid = 0
                if etype in ("long_video", "short") and eid:
                    before = self.db.fetchone(
                        "SELECT COUNT(*) AS c FROM entity_platform_status WHERE status='skipped' "
                        "AND entity_type=? AND entity_id=?", (etype, eid))
                    self.db.execute(
                        "UPDATE entity_platform_status SET status='ready', postiz_post_id=NULL, "
                        "last_error=NULL WHERE status='skipped' AND entity_type=? AND entity_id=?",
                        (etype, eid))
                else:
                    before = self.db.fetchone(
                        "SELECT COUNT(*) AS c FROM entity_platform_status WHERE status='skipped'")
                    self.db.execute(
                        "UPDATE entity_platform_status SET status='ready', postiz_post_id=NULL, "
                        "last_error=NULL WHERE status='skipped'")
                return 200, {"ok": True, "restored": (before or {}).get("c", 0)}, "application/json"
            if method == "POST" and route == "queue/remove":
                etype = str(data.get("entity_type") or "").strip()
                platform = str(data.get("platform") or "").strip()
                series = bool(data.get("series"))
                try:
                    eid = int(data.get("entity_id") or 0)
                except Exception:
                    eid = 0
                if etype not in ("long_video", "short") or not eid:
                    return 400, {"error": "entity_type/entity_id required"}, "application/json"
                sql = ("SELECT platform, postiz_post_id, status FROM entity_platform_status "
                       "WHERE entity_type=? AND entity_id=? AND status IN "
                       "('scheduled','updating','ready','error')")
                params: list = [etype, eid]
                if platform:
                    sql += " AND platform=?"
                    params.append(platform)
                rows = list(self.db.fetchall(sql, tuple(params)))
                if series and etype == "long_video":
                    child_sql = ("SELECT s.id AS entity_id, eps.platform, eps.postiz_post_id, "
                                 "eps.status FROM shorts s "
                                 "JOIN entity_platform_status eps "
                                 "  ON eps.entity_type='short' AND eps.entity_id = s.id "
                                 "WHERE s.parent_video_id=? "
                                 "AND eps.status IN ('scheduled','updating','ready','error')")
                    child_params: list = [eid]
                    if platform:
                        child_sql += " AND eps.platform=?"
                        child_params.append(platform)
                    for c in self.db.fetchall(child_sql, tuple(child_params)):
                        rows.append({"platform": c["platform"],
                                     "postiz_post_id": c["postiz_post_id"],
                                     "status": c["status"],
                                     "_child_short": c["entity_id"]})
                postiz = self.comps.get("postiz")
                removed = 0
                for r in rows:
                    pid = r.get("postiz_post_id")
                    if pid and postiz is not None:
                        deleted = False
                        if hasattr(postiz, "delete_post"):
                            try:
                                postiz.delete_post(str(pid))
                                deleted = True
                            except Exception:
                                logger.warning("queue remove: delete failed %s", pid, exc_info=True)
                        if not deleted and hasattr(postiz, "set_status"):
                            try:
                                postiz.set_status(str(pid), "draft")
                            except Exception:
                                logger.warning("queue remove: draft failed %s", pid, exc_info=True)
                    child_id = r.get("_child_short")
                    if child_id is not None:
                        self.db.execute(
                            "UPDATE entity_platform_status SET status='skipped', "
                            "last_error='removed_by_user' WHERE entity_type='short' "
                            "AND entity_id=? AND platform=?",
                            (child_id, r["platform"]),
                        )
                        self.db.log("short", child_id, r["platform"], "queue_remove", str(pid or ""))
                    else:
                        self.db.execute(
                            "UPDATE entity_platform_status SET status='skipped', "
                            "last_error='removed_by_user' WHERE entity_type=? AND entity_id=? "
                            "AND platform=?",
                            (etype, eid, r["platform"]),
                        )
                        self.db.log(etype, eid, r["platform"], "queue_remove", str(pid or ""))
                    removed += 1
                return 200, {"ok": True, "removed": removed,
                             "platforms": [r["platform"] for r in rows]}, "application/json"
            if method == "POST" and route == "queue/edit":
                etype = str(data.get("entity_type") or "").strip()
                platform_sel = str(data.get("platform") or "").strip()
                try:
                    eid = int(data.get("entity_id") or 0)
                except Exception:
                    eid = 0
                if etype not in ("long_video", "short") or not eid:
                    return 400, {"error": "entity_type/entity_id required"}, "application/json"
                table = "long_videos" if etype == "long_video" else "shorts"
                title = str(data.get("title") or "")
                desc = str(data.get("description") or "")
                tags = str(data.get("hashtags") or "")
                self.db.execute(
                    f"UPDATE {table} SET title_text=?, description_text=?, hashtags_text=? "
                    "WHERE id=?",
                    (title[:200], desc, tags, eid),
                )
                sql = ("SELECT platform, postiz_post_id, postiz_scheduled_for, status "
                       "FROM entity_platform_status WHERE entity_type=? AND entity_id=? "
                       "AND status IN ('scheduled','updating','ready','error')")
                params: list = [etype, eid]
                if platform_sel:
                    sql += " AND platform=?"
                    params.append(platform_sel)
                rows = self.db.fetchall(sql, tuple(params))
                postiz = self.comps.get("postiz")
                sch = self.comps.get("scheduler")
                pub = getattr(sch, "publisher", None)
                updated = 0
                recreated = 0
                for r in rows:
                    plat = r["platform"]
                    pid = r.get("postiz_post_id")
                    if pid and postiz is not None:
                        try:
                            if hasattr(postiz, "delete_post"):
                                postiz.delete_post(str(pid))
                            elif hasattr(postiz, "set_status"):
                                postiz.set_status(str(pid), "draft")
                        except Exception:
                            logger.warning("queue edit: не удалось отменить %s", pid, exc_info=True)
                    self.db.execute(
                        "UPDATE entity_platform_status SET status='ready', postiz_post_id=NULL, "
                        "last_error=NULL WHERE entity_type=? AND entity_id=? AND platform=?",
                        (etype, eid, plat),
                    )
                    self.db.log(etype, eid, plat, "queue_edit", "")
                    updated += 1
                    if pub is None:
                        continue
                    entity = self.db.fetchone(f"SELECT * FROM {table} WHERE id=?", (eid,))
                    if not entity:
                        continue
                    pcfg = self.cfg.platforms.get(plat)
                    path = None
                    if sch is not None and hasattr(sch, "_pick_path"):
                        try:
                            if etype == "long_video":
                                path = sch._pick_path(entity, plat, pcfg)
                            else:
                                path = sch._pick_path(entity, plat) or entity.get("video_path")
                        except Exception:
                            path = entity.get("video_path")
                    if not path:
                        path = entity.get("video_path") or entity.get("vertical_path")                             or entity.get("wide_path")
                    when = r.get("postiz_scheduled_for")
                    sched_dt = None
                    new_date = str(data.get("date") or "").strip()
                    new_time = str(data.get("time") or "").strip()
                    if new_date and new_time:
                        try:
                            from datetime import date as _date

                            from .slots import local_to_utc, parse_time
                            y, m, d = (int(x) for x in new_date.split("-"))
                            sched_dt = local_to_utc(_date(y, m, d), parse_time(new_time),
                                                    self.cfg.timezone)
                        except Exception:
                            sched_dt = None
                    if sched_dt is None and when:
                        from datetime import datetime as _dt
                        try:
                            sched_dt = _dt.fromisoformat(str(when))
                        except Exception:
                            sched_dt = None
                    content = {"title": title, "description": desc, "hashtags": tags}
                    try:
                        post = pub.publish(etype, eid, plat, path, content, sched_dt)
                        if post:
                            recreated += 1
                        elif sched_dt is not None:
                            self.db.execute(
                                "UPDATE entity_platform_status SET postiz_scheduled_for=? "
                                "WHERE entity_type=? AND entity_id=? AND platform=?",
                                (sched_dt.isoformat(), etype, eid, plat),
                            )
                    except Exception:
                        logger.exception("queue edit: пересоздание не удалось (%s/%s %s)",
                                         etype, eid, plat)
                return 200, {"ok": True, "updated": updated, "recreated": recreated}, \
                    "application/json"
            if method == "POST" and route == "queue/restore":
                etype = str(data.get("entity_type") or "").strip()
                try:
                    eid = int(data.get("entity_id") or 0)
                except Exception:
                    eid = 0
                if etype in ("long_video", "short") and eid:
                    before = self.db.fetchone(
                        "SELECT COUNT(*) AS c FROM entity_platform_status WHERE status='skipped' "
                        "AND entity_type=? AND entity_id=?", (etype, eid))
                    self.db.execute(
                        "UPDATE entity_platform_status SET status='ready', postiz_post_id=NULL, "
                        "last_error=NULL WHERE status='skipped' AND entity_type=? AND entity_id=?",
                        (etype, eid))
                else:
                    before = self.db.fetchone(
                        "SELECT COUNT(*) AS c FROM entity_platform_status WHERE status='skipped'")
                    self.db.execute(
                        "UPDATE entity_platform_status SET status='ready', postiz_post_id=NULL, "
                        "last_error=NULL WHERE status='skipped'")
                return 200, {"ok": True, "restored": (before or {}).get("c", 0)}, "application/json"
            if method == "POST" and route == "queue/remove":
                etype = str(data.get("entity_type") or "").strip()
                platform = str(data.get("platform") or "").strip()
                try:
                    eid = int(data.get("entity_id") or 0)
                except Exception:
                    eid = 0
                if etype not in ("long_video", "short") or not eid:
                    return 400, {"error": "entity_type/entity_id required"}, "application/json"
                sql = ("SELECT platform, postiz_post_id, status FROM entity_platform_status "
                       "WHERE entity_type=? AND entity_id=? AND status IN "
                       "('scheduled','updating','ready','error')")
                params: list = [etype, eid]
                if platform:
                    sql += " AND platform=?"
                    params.append(platform)
                rows = list(self.db.fetchall(sql, tuple(params)))
                # каскад: удаление фильма убирает и его шортсы (все платформы или выбранную)
                if etype == "long_video":
                    child_sql = ("SELECT s.id AS entity_id, eps.platform, eps.postiz_post_id, "
                                 "eps.status FROM shorts s "
                                 "JOIN entity_platform_status eps "
                                 "  ON eps.entity_type='short' AND eps.entity_id = s.id "
                                 "WHERE s.parent_video_id=? "
                                 "AND eps.status IN ('scheduled','updating','ready','error')")
                    child_params: list = [eid]
                    if platform:
                        child_sql += " AND eps.platform=?"
                        child_params.append(platform)
                    for c in self.db.fetchall(child_sql, tuple(child_params)):
                        rows.append({"platform": c["platform"],
                                     "postiz_post_id": c["postiz_post_id"],
                                     "status": c["status"],
                                     "_child_short": c["entity_id"]})
                postiz = self.comps.get("postiz")
                removed = 0
                for r in rows:
                    child_id = r.get("_child_short")
                    if child_id is not None:
                        pid = r.get("postiz_post_id")
                        if pid and postiz is not None and hasattr(postiz, "set_status"):
                            try:
                                postiz.set_status(str(pid), "draft")
                            except Exception:
                                logger.warning("queue remove: не удалось отменить %s", pid,
                                               exc_info=True)
                        self.db.execute(
                            "UPDATE entity_platform_status SET status='skipped', "
                            "last_error='removed_by_user' WHERE entity_type='short' "
                            "AND entity_id=? AND platform=?",
                            (child_id, r["platform"]),
                        )
                        self.db.log("short", child_id, r["platform"], "queue_remove", str(pid or ""))
                        removed += 1
                        continue
                    pid = r.get("postiz_post_id")
                    if pid and postiz is not None and hasattr(postiz, "set_status"):
                        try:
                            postiz.set_status(str(pid), "draft")
                        except Exception:
                            logger.warning("queue remove: не удалось перевести %s в draft", pid,
                                           exc_info=True)
                    self.db.execute(
                        "UPDATE entity_platform_status SET status='skipped', "
                        "last_error='removed_by_user' WHERE entity_type=? AND entity_id=? "
                        "AND platform=?",
                        (etype, eid, r["platform"]),
                    )
                    self.db.log(etype, eid, r["platform"], "queue_remove", str(pid or ""))
                    removed += 1
                return 200, {"ok": True, "removed": removed,
                             "platforms": [r["platform"] for r in rows]}, "application/json"
            if method == "POST" and route == "scheduling_mode":
                mode = str(data.get("mode") or "").strip().lower()
                if mode not in ("auto", "manual"):
                    return 400, {"error": "mode must be auto or manual"}, "application/json"
                sched_settings.set_scheduling_mode(self.db, mode)
                return 200, {"ok": True, "mode": mode}, "application/json"
            if method == "POST" and route == "groups":
                payload = data.get("groups")
                ok, msg = sched_settings.validate_groups(payload, list(self.cfg.platforms.keys()))
                if not ok:
                    return 400, {"error": msg}, "application/json"
                sched_settings.save_groups(self.db, payload)
                return 200, {"ok": True, "groups": payload}, "application/json"
            if method == "GET" and route == "browse":
                roots = self._browse_roots()
                metas = [self._root_meta(r) for r in roots]
                available = [Path(m["path"]) for m in metas if m["available"]]
                root = available[0] if available else roots[0]
                sel = query.get("root")
                if sel:
                    rp = Path(sel).expanduser()
                    rp = rp.resolve() if rp.is_dir() else None
                    if rp in roots:
                        root = rp
                target = query.get("path") or str(root)
                base = Path(target).expanduser()
                base = base.resolve() if base.is_dir() else root
                if base != root and root not in base.parents:
                    base = root
                dirs = []
                warning = ""
                try:
                    children = sorted(base.iterdir())
                except PermissionError:
                    return 403, {"error": "permission denied"}, "application/json"
                except OSError:
                    children = []
                    warning = "папка недоступна (диск отключён?)"
                for child in children:
                    if not child.is_dir() or child.name.startswith("."):
                        continue
                    try:
                        dirs.append({"name": child.name, "path": str(child.resolve())})
                    except (PermissionError, OSError):
                        continue
                cur = next((m for m in metas if m["path"] == str(root)), None)
                if cur and not cur["available"]:
                    warning = cur["note"]
                return 200, {
                    "path": str(base),
                    "parent": str(base.parent) if base != root else None,
                    "root": str(root),
                    "roots": [str(r) for r in roots],
                    "roots_meta": metas,
                    "warning": warning,
                    "dirs": dirs,
                    "selected": str(base) in self._roots(),
                }, "application/json"
            if method == "POST" and route == "scan":
                watcher = self.comps.get("watcher")
                if not watcher:
                    return 500, {"error": "watcher unavailable"}, "application/json"
                stats = watcher.scan()
                roots = [str(r) for r in watcher.effective_roots()]

                def _under(path: str) -> bool:
                    return any(path == r or path.startswith(r.rstrip("/") + "/") for r in roots)

                longs = self.db.fetchall("SELECT folder_path FROM long_videos")
                shorts_rows = self.db.fetchall("SELECT folder_path FROM shorts")
                totals = {
                    "long": sum(1 for r in longs if _under(r["folder_path"] or "")),
                    "shorts": sum(1 for r in shorts_rows if _under(r["folder_path"] or "")),
                }
                skipped = self.db.fetchone(
                    "SELECT COUNT(*) AS c FROM entity_platform_status WHERE status='skipped'")
                last = self.db.fetchone(
                    "SELECT MAX(postiz_scheduled_for) AS m FROM entity_platform_status "
                    "WHERE status IN ('scheduled','updating','ready')")
                return 200, {
                    "ok": True,
                    "stats": stats,
                    "totals": totals,
                    "skipped": (skipped or {}).get("c", 0),
                    "last_scheduled": (last or {}).get("m") if last else None,
                    "roots": roots,
                }, "application/json"
            if route == "manual/plan" and method == "GET":
                return 200, self._manual_plan(), "application/json"
            if route == "manual/uploads" and method == "GET":
                manual = self.comps.get("manual")
                if not manual:
                    return 500, {"error": "manual service unavailable"}, "application/json"
                rows = self.db.list_uploads(
                    status=query.get("status"), platform=query.get("platform")
                )
                out = []
                for r in rows:
                    item = {k: r.get(k) for k in (
                        "id", "engine", "platform", "platform_video_id", "url", "title",
                        "published_at", "origin", "match_status", "confidence",
                        "matched_entity_type", "matched_entity_id", "claim_status")}
                    item["candidates"] = (
                        manual.candidates(r["id"])
                        if r["match_status"] in ("unmatched", "suggested") else []
                    )
                    out.append(item)
                return 200, {"items": out}, "application/json"
            if route == "manual/scan" and method == "POST":
                manual = self.comps.get("manual")
                sources = self.comps.get("manual_sources") or {}
                if not manual:
                    return 500, {"error": "manual service unavailable"}, "application/json"
                want = data.get("platform")
                targets = [want] if want else list(sources.keys())
                stats: dict = {}
                for p in targets:
                    src = sources.get(p)
                    if not src:
                        stats[p] = {"error": "no source configured"}
                        continue
                    caps = getattr(src, "capabilities", lambda: {})()
                    if not caps.get("list", False):
                        stats[p] = {"skipped": "engine does not support listing uploads"}
                        continue
                    try:
                        uploads = src.list_uploads()
                    except Exception as e:
                        stats[p] = {"error": str(e)}
                        continue
                    stats[p] = manual.scan(p, uploads, engine=self.cfg.engine_for(p))
                self.db.set_setting("manual_last_scan", json.dumps(
                    {"at": self.comps["clock"].now().isoformat(), "stats": stats}))
                return 200, {"ok": True, "stats": stats}, "application/json"
            if route.startswith("manual/uploads/") and method in ("GET", "POST"):
                manual = self.comps.get("manual")
                if not manual:
                    return 500, {"error": "manual service unavailable"}, "application/json"
                seg = route.split("/")
                try:
                    uid = int(seg[2])
                except (IndexError, ValueError):
                    return 400, {"error": "bad upload id"}, "application/json"
                action = seg[3] if len(seg) > 3 else ""
                if action == "candidates" and method == "GET":
                    return 200, {"items": manual.candidates(uid)}, "application/json"
                row = self.db.get_upload(uid)
                if not row:
                    return 404, {"error": "upload not found"}, "application/json"
                sources = self.comps.get("manual_sources") or {}
                engine = sources.get(row["platform"])
                if action in ("confirm", "reassign") and method == "POST":
                    et = data.get("entity_type")
                    eid = data.get("entity_id")
                    if not et or eid is None:
                        return 400, {"error": "entity_type/entity_id required"}, "application/json"
                    try:
                        ok = manual.confirm(
                            uid, et, int(eid),
                            apply_edits=bool(data.get("apply_edits")) if action == "confirm" else False,
                            engine=engine,
                        )
                    except sqlite3.IntegrityError:
                        return 409, {
                            "error": "this entity is already linked to another upload on this platform"
                        }, "application/json"
                    return 200, {"ok": ok}, "application/json"
                if action == "reject" and method == "POST":
                    return 200, {"ok": manual.reject(uid)}, "application/json"
                if action == "ignore" and method == "POST":
                    return 200, {"ok": manual.ignore(uid)}, "application/json"
                if action == "claim-mark" and method == "POST":
                    claimed = bool(data.get("claimed", True))
                    self.db.execute(
                        "UPDATE platform_uploads SET claim_status=?, claim_info=? WHERE id=?",
                        ("claimed" if claimed else "none", "manual", uid))
                    return 200, {"ok": True}, "application/json"
                if action == "claim-action" and method == "POST":
                    act = data.get("action")
                    if act == "delete":
                        if engine is not None:
                            try:
                                engine.delete(str(row["platform_video_id"]))
                            except Exception as e:
                                return 500, {"error": str(e)}, "application/json"
                        self.db.execute(
                            "UPDATE platform_uploads SET claim_status='none', claim_info='deleted' WHERE id=?",
                            (uid,))
                    elif act == "keep":
                        self.db.execute(
                            "UPDATE platform_uploads SET claim_status='claimed', claim_info='kept' WHERE id=?",
                            (uid,))
                    else:
                        self.db.execute(
                            "UPDATE platform_uploads SET claim_status='none', claim_info='ignored' WHERE id=?",
                            (uid,))
                    return 200, {"ok": True}, "application/json"
                return 404, {"error": "unknown manual action"}, "application/json"
            if method == "GET" and route == "backlog":
                bl = self.comps.get("backlog")
                if not bl:
                    return 500, {"error": "backlog unavailable"}, "application/json"
                out = []
                for p, pcfg in self.cfg.platforms.items():
                    if not getattr(pcfg, "enabled", False):
                        continue
                    st = bl._state(p) or {}
                    out.append({
                        "platform": p,
                        "count": bl.has_backlog(p),
                        "awaiting": bool(st.get("pending_series_end_question")),
                        "slot": st.get("pending_series_end_at"),
                        "tail_mode": bool(st.get("series_tail_mode")),
                    })
                return 200, {"platforms": out}, "application/json"
            if method == "POST" and route == "backlog/answer":
                bl = self.comps.get("backlog")
                p = (data.get("platform") or "").strip()
                ans = (data.get("answer") or "").strip()
                if not bl or p not in self.cfg.platforms or ans not in ("distribute", "wait", "skip"):
                    return 400, {"error": "platform/answer invalid"}, "application/json"
                if ans == "distribute" and data.get("from_date"):
                    n = bl.scheduler.schedule_backlog(p, start_date=str(data["from_date"])) \
                        if bl.scheduler else 0
                    bl.db.execute(
                        "UPDATE platform_queue_state SET pending_series_end_question=0, "
                        "pending_series_end_at=NULL, series_tail_mode=1 WHERE platform=?", (p,))
                    bl.db.log("system", None, p, "backlog_distribute", str(n))
                else:
                    n = bl.resolve(p, ans)
                return 200, {"ok": True, "scheduled": n}, "application/json"
            if method == "POST" and route == "sync":
                ss = self.comps.get("status_sync")
                n = ss.sync() if ss else 0
                n2 = ss.sync(fresh_only=True) if ss else 0
                lu = self.comps.get("link_upd")
                if lu:
                    lu.check_missing_urls()
                return 200, {"ok": True, "updates": (n or 0) + (n2 or 0)}, "application/json"
            if method == "POST" and route == "reconcile":
                rec = self.comps.get("recon")
                return 200, {"ok": True, "result": rec.run() if rec else {}}, "application/json"
            if method == "POST" and route == "backup":
                from .backup import run_backup

                bdir = Path(self.db.path).parent.parent / "backups"
                p = run_backup(self.db, self.cfg, bdir)
                return 200, {"ok": True, "path": str(p) if p else None}, "application/json"
            if method == "POST" and route == "schedule":
                sc = self.comps.get("scheduler")
                sd = str(data.get("start_date") or "").strip() or None
                if sd:
                    import re as _re
                    if not _re.fullmatch(r"\d{4}-\d{2}-\d{2}", sd):
                        return 400, {"error": "start_date must be YYYY-MM-DD"}, "application/json"
                n = sc.schedule_long_videos(start_date=sd) if sc else 0
                n2 = sc.schedule_standalone_shorts(self.comps.get("tail"), start_date=sd) if sc else 0
                return 200, {"ok": True, "long": n, "standalone": n2, "start_date": sd}, "application/json"
            if method == "POST" and route == "pause_platform":
                p = (data.get("platform") or "").strip()
                if p not in self.cfg.platforms:
                    return 400, {"error": "unknown platform"}, "application/json"
                self.comps["safety"].pause_platform(p, "webapp")
                return 200, {"ok": True}, "application/json"
            return 404, {"error": "unknown route"}, "application/json"
        except Exception as e:
            logger.exception("webapp api")
            return 500, {"error": str(e)}, "application/json"

    def _metrics(self) -> dict:
        path = Path(self.db.path).parent / "metrics.json"
        data: dict = {"cycles": 0, "note": "no metrics yet"}
        if path.is_file():
            try:
                data = json.loads(path.read_text())
            except Exception:
                pass
        live: dict = {}
        try:
            rows = self.db.fetchall(
                "SELECT status, COUNT(*) AS c FROM entity_platform_status GROUP BY status"
            )
            counts = {r["status"]: r["c"] for r in rows}
            live = {
                "queue": sum(counts.get(s, 0) for s in ("ready", "scheduled", "updating")),
                "published": counts.get("published", 0),
                "failed": sum(counts.get(s, 0) for s in ("failed", "error")),
            }
        except Exception:
            logger.debug("live metrics failed", exc_info=True)
        data["live"] = live
        return data

    def _rate_limited(self, headers: dict[str, str]) -> bool:
        try:
            limit = int(os.getenv("WEBAPP_RATE_LIMIT", "120"))
        except ValueError:
            limit = 120
        if limit <= 0:
            return False
        ident = (
            headers.get("X-Webapp-Key") or headers.get("x-webapp-key")
            or headers.get("X-Telegram-Init-Data") or headers.get("x-telegram-init-data")
            or headers.get("X-Forwarded-For") or "local"
        )
        now = time.monotonic()
        dq = self._rl.setdefault(ident, deque())
        while dq and now - dq[0] > 60:
            dq.popleft()
        if len(dq) >= limit:
            return True
        dq.append(now)
        return False

    def _browse_roots(self) -> list[Path]:
        raw = os.getenv("WEBAPP_BROWSE_ROOT", "/mnt/video")
        out: list[Path] = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                p = Path(part).expanduser().resolve()
            except Exception:
                continue
            if p.is_dir():
                out.append(p)
        return out or [Path("/")]

    def _key_from_request(self, qpath: str, query: dict[str, str]) -> str:
        k = query.get("key")
        if k:
            return k
        m = re.match(r"^/webapp/k/([^/]+)", qpath)
        return m.group(1) if m else ""

    def _manual_plan(self) -> dict:
        rows = self.db.list_uploads()
        by_status: dict[str, int] = {}
        by_platform: dict[str, int] = {}
        for r in rows:
            by_status[r["match_status"]] = by_status.get(r["match_status"], 0) + 1
            by_platform[r["platform"]] = by_platform.get(r["platform"], 0) + 1
        last = None
        raw = self.db.get_setting("manual_last_scan")
        if raw:
            try:
                last = json.loads(raw)
            except Exception:
                last = None
        return {"total": len(rows), "by_status": by_status,
                "by_platform": by_platform,
                "platforms": sorted((self.comps.get("manual_sources") or {}).keys()),
                "last_scan": last}

    def _roots(self) -> list[str]:
        return [it["path"] for it in self._root_items()]

    def _root_items(self) -> list[dict[str, str]]:
        raw = self.db.get_setting(WATCH_ROOTS_KEY)
        out: list[dict[str, str]] = []
        if raw:
            try:
                items = json.loads(raw)
            except Exception:
                items = None
                logger.warning("invalid watch_roots setting")
            if isinstance(items, list):
                for x in items:
                    if isinstance(x, dict) and x.get("path"):
                        kind = str(x.get("kind") or "auto").lower()
                        out.append({"path": str(x["path"]),
                                    "kind": kind if kind in ("auto", "series", "shorts") else "auto"})
                    elif isinstance(x, (str, Path)):
                        out.append({"path": str(x), "kind": "auto"})
        return out

    @staticmethod
    def _mount_source(path: Path) -> str:
        try:
            for line in Path("/proc/mounts").read_text().splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[1].replace("\\040", " ") == str(path):
                    return parts[0]
        except OSError:
            pass
        return ""

    def _root_meta(self, path: Path) -> dict:
        """Доступность корня обзора: диск может быть отключён (stale mount)."""
        meta = {"path": str(path), "available": True, "note": ""}
        if not path.is_dir():
            meta.update(available=False, note="папка недоступна")
            return meta
        if os.path.ismount(path):
            src = self._mount_source(path)
            if src.startswith("/dev/") and not Path(src).exists():
                meta.update(available=False, note="диск отключён — подключи его или выбери другой корень")
        return meta

    def _compose_index(self, key: str = "") -> bytes:
        """Self-contained page: inline CSS/JS so nothing can be cached separately."""
        try:
            html = (WEBAPP_DIR / "index.html").read_text(encoding="utf-8")
            css = (WEBAPP_DIR / "styles.css").read_text(encoding="utf-8")
            js = (WEBAPP_DIR / "app.js").read_text(encoding="utf-8")
        except OSError:
            return (WEBAPP_DIR / "index.html").read_bytes()
        html = re.sub(
            r'<link rel="stylesheet" href="styles\.css\?v=\d+"\s*/?>',
            f"<style>\n{css}\n</style>",
            html,
        )
        html = re.sub(
            r'<script src="app\.js\?v=\d+"></script>',
            "<script>window.__WEBAPP_KEY__=" + json.dumps(key) + ";</script>\n"
            f"<script>\n{js}\n</script>",
            html,
        )
        return html.encode("utf-8")

    def _file(self, name: str, ctype: str) -> tuple[int, bytes, str]:
        path = WEBAPP_DIR / name
        if not path.is_file():
            return 404, {"error": "file not found"}, "application/json"
        return 200, path.read_bytes(), ctype

    def _status(self) -> dict:
        rows = self.db.fetchall(
            "SELECT status, COUNT(*) AS cnt FROM entity_platform_status GROUP BY status"
        )
        counts = {r["status"]: r["cnt"] for r in rows}
        platforms = []
        for name, p in self.cfg.platforms.items():
            st = self.db.fetchone(
                "SELECT is_paused FROM platform_safety_state WHERE platform=?",
                (name,),
            )
            platforms.append({
                "name": name,
                "enabled": p.enabled,
                "daily_limit": p.daily_limit,
                "paused": bool(st and st["is_paused"]),
            })
        return {"counts": counts, "platforms": platforms}

    def _to_local(self, value: str) -> tuple[str, str]:
        """ISO (UTC) -> (локальная дата, HH:MM) в таймзоне конфига."""
        from datetime import UTC
        from datetime import datetime as _dt

        from .slots import get_tz
        try:
            dt = _dt.fromisoformat(str(value).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            local = dt.astimezone(get_tz(self.cfg.timezone))
            return local.date().isoformat(), local.strftime("%H:%M")
        except Exception:
            raw = str(value)
            return raw[:10], raw[11:16]

    def _calendar(self) -> dict:
        entries: list[dict] = []
        seen: set[str] = set()
        rows = self.db.fetchall(
            """
            SELECT eps.platform, eps.postiz_post_id, eps.postiz_scheduled_for,
                   eps.entity_type, eps.entity_id, eps.status,
                   COALESCE(lv.title_text, lv.title, sh.title_text) AS title
            FROM entity_platform_status eps
            LEFT JOIN long_videos lv
                   ON eps.entity_type='long_video' AND lv.id = eps.entity_id
            LEFT JOIN shorts sh
                   ON eps.entity_type='short' AND sh.id = eps.entity_id
            WHERE eps.postiz_scheduled_for IS NOT NULL
              AND eps.status NOT IN ('skipped')
            ORDER BY eps.postiz_scheduled_for LIMIT 500
            """
        )
        for r in rows:
            pid = r.get("postiz_post_id")
            if pid:
                seen.add(str(pid))
            date_l, time_l = self._to_local(r["postiz_scheduled_for"])
            kind = "Фильм" if r["entity_type"] == "long_video" else "Шортс"
            title = (r.get("title") or "").strip() or f'{kind} #{r["entity_id"]}'
            entries.append({
                "scheduled_for": r["postiz_scheduled_for"] or "",
                "date": date_l,
                "time": time_l,
                "platform": r["platform"],
                "title": f"{kind}: {title}"[:140],
                "status": r["status"],
                "source": "db",
            })
        postiz = self.comps.get("postiz")
        if postiz is not None and hasattr(postiz, "list_scheduled"):
            try:
                for p in postiz.list_scheduled():
                    state = str(getattr(p, "status", "") or "").lower()
                    if state in ("draft", "drafts"):
                        continue
                    if str(p.id) in seen:
                        continue
                    seen.add(str(p.id))
                    content = p.content.get("text") if isinstance(p.content, dict) else ""
                    iso = p.scheduled_for.isoformat() if p.scheduled_for else ""
                    date_l, time_l = self._to_local(iso)
                    entries.append({
                        "scheduled_for": iso,
                        "date": date_l,
                        "time": time_l,
                        "platform": p.platform,
                        "title": (content or "").strip().splitlines()[0][:90]
                                 or f"Postiz {str(p.id)[:8]}",
                        "status": state,
                        "source": "postiz",
                        "url": p.release_url,
                    })
            except Exception:
                logger.debug("postiz calendar failed", exc_info=True)
        by: dict[str, list] = defaultdict(list)
        for e in entries:
            d = e.get("date") or ""
            if d:
                by[d].append(e)
        days = []
        for d in sorted(by):
            items = sorted(by[d], key=lambda x: x.get("time") or "")
            days.append({"date": d, "count": len(items), "items": items})
        return {"days": days, "total": len(entries)}

    def _queue(self) -> dict:
        rows = self.db.fetchall(
            """
            SELECT eps.entity_type, eps.entity_id, eps.platform, eps.status,
                   eps.postiz_scheduled_for,
                   COALESCE(lv.title_text, lv.title, sh.title_text) AS title,
                   COALESCE(lv.description_text, sh.description_text) AS description_text,
                   COALESCE(lv.hashtags_text, sh.hashtags_text) AS hashtags_text
            FROM entity_platform_status eps
            LEFT JOIN long_videos lv
                   ON eps.entity_type='long_video' AND lv.id = eps.entity_id
            LEFT JOIN shorts sh
                   ON eps.entity_type='short' AND sh.id = eps.entity_id
            WHERE eps.status IN ('ready', 'scheduled', 'updating')
            ORDER BY eps.postiz_scheduled_for LIMIT 50
            """
        )
        items = []
        for r in rows:
            kind = "Фильм" if r["entity_type"] == "long_video" else "Шортс"
            date_l, time_l = self._to_local(r["postiz_scheduled_for"] or "")
            title = (r.get("title") or "").strip() or f"{kind} #{r['entity_id']}"
            items.append({
                "entity_type": r["entity_type"],
                "entity_id": r["entity_id"],
                "platform": r["platform"],
                "status": r["status"],
                "postiz_scheduled_for": r["postiz_scheduled_for"],
                "date": date_l,
                "time": time_l,
                "title": f"{kind}: {title}"[:140],
                "title_text": (r.get("title") or "").strip(),
                "description_text": r.get("description_text") or "",
                "hashtags_text": r.get("hashtags_text") or "",
            })
        return {"items": items}

    def _platforms(self) -> dict:
        return self._status()

    def _tail(self) -> dict:
        rows = self.db.fetchall(
            "SELECT platform, series_tail_mode FROM platform_queue_state"
        )
        return {
            "items": [
                {"platform": r["platform"], "tail": bool(r["series_tail_mode"])}
                for r in rows
            ]
        }

    def _failed(self) -> dict:
        rows = self.db.fetchall(
            """
            SELECT entity_type, entity_id, platform, status, last_error
            FROM entity_platform_status
            WHERE status IN ('failed', 'error')
            LIMIT 50
            """
        )
        return {"items": rows}
