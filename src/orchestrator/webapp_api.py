from __future__ import annotations

import base64
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

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def _is_image_bytes(blob: bytes) -> bool:
    if len(blob) < 12:
        return False
    if blob[:3] == b"\xff\xd8\xff":
        return True
    if blob[:8] == b"\x89PNG\r\n\x1a\n":
        return True
    if blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
        return True
    return False

logger = logging.getLogger(__name__)

WEBAPP_DIR = Path(__file__).resolve().parents[2] / "webapp"
WEBAPP_BUILD = "68"


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
        if is_api and len(body or b"") > 50 * 1024 * 1024:
            return 413, {"error": "request body too large (max 50MB)"}, "application/json"

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
            if method == "GET" and route == "job":
                jobs = self.comps.get("jobs")
                snap = jobs.snapshot() if jobs is not None else None
                return 200, {"job": snap}, "application/json"
            if method == "POST" and route == "job/cancel":
                jobs = self.comps.get("jobs")
                ok = jobs.cancel() if jobs is not None else False
                return 200, {"ok": ok}, "application/json"
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
                cover = str(data.get("cover") or "").strip()
                if cover and not Path(cover).is_file():
                    return 400, {"error": "cover file not found"}, "application/json"
                self.db.execute(
                    f"UPDATE {table} SET title_text=?, description_text=?, hashtags_text=?, "
                    "cover_path=? WHERE id=?",
                    (title[:200], desc, tags, (cover or None), eid),
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
                    content = {"title": title, "description": desc, "hashtags": tags,
                               "cover": cover}
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
                keep_shorts = bool(data.get("keep_shorts"))
                try:
                    eid = int(data.get("entity_id") or 0)
                except Exception:
                    eid = 0
                if etype not in ("long_video", "short") or not eid:
                    return 400, {"error": "entity_type/entity_id required"}, "application/json"
                if not self.db.fetchone(
                        "SELECT 1 FROM entity_platform_status WHERE entity_type=? AND entity_id=? "
                        "LIMIT 1", (etype, eid)):
                    logger.info("queue remove: %s#%s уже удалено", etype, eid)
                    return 200, {"ok": True, "removed": 0, "blocked": [],
                                 "note": "already"}, "application/json"
                postiz = self.comps.get("postiz")

                def _kill_posts(*targets: tuple[str, int]) -> None:
                    if postiz is None:
                        return
                    pids: list[str] = []
                    for t, i in targets:
                        for r in self.db.fetchall(
                                "SELECT postiz_post_id FROM entity_platform_status "
                                "WHERE entity_type=? AND entity_id=?", (t, i)):
                            pid = r.get("postiz_post_id")
                            if pid:
                                pids.append(str(pid))
                    if not pids:
                        return
                    from concurrent.futures import ThreadPoolExecutor

                    def _one(pid: str) -> None:
                        try:
                            if hasattr(postiz, "delete_post"):
                                postiz.delete_post(pid)
                            elif hasattr(postiz, "set_status"):
                                postiz.set_status(pid, "draft")
                        except Exception:
                            logger.warning("queue remove: удаление поста %s не удалось", pid,
                                           exc_info=True)

                    with ThreadPoolExecutor(max_workers=8) as ex:
                        list(ex.map(_one, pids))

                guard = self.comps.get("guard")
                if guard is not None and hasattr(guard, "invalidate"):
                    guard.invalidate()
                removed = 0
                blocked: list[str] = []
                if etype == "long_video":
                    shorts_ids = [r["id"] for r in self.db.fetchall(
                        "SELECT id FROM shorts WHERE parent_video_id=?", (eid,))]
                    rows = self.db.fetchall(
                        "SELECT status FROM entity_platform_status "
                        "WHERE entity_type='long_video' AND entity_id=?", (eid,))
                    published = any((r["status"] or "") == "published" for r in rows)
                    for sid in shorts_ids:
                        srows = self.db.fetchall(
                            "SELECT status FROM entity_platform_status "
                            "WHERE entity_type='short' AND entity_id=?", (sid,))
                        if any((r["status"] or "") == "published" for r in srows):
                            published = True
                    if published:
                        blocked.append(f"long_video#{eid}")
                    elif keep_shorts:
                        # удаляем только фильм; шортсы остаются (отвязываем)
                        _kill_posts(("long_video", eid))
                        self.db.execute(
                            "DELETE FROM entity_platform_status "
                            "WHERE entity_type='long_video' AND entity_id=?", (eid,))
                        self.db.execute(
                            "UPDATE shorts SET parent_video_id=NULL WHERE parent_video_id=?",
                            (eid,))
                        self.db.execute("DELETE FROM long_videos WHERE id=?", (eid,))
                        self.db.log("long_video", eid, "", "queue_delete", "keep_shorts")
                        removed += 1
                    else:
                        _kill_posts(*[("short", sid) for sid in shorts_ids])
                        for sid in shorts_ids:
                            self.db.execute(
                                "DELETE FROM entity_platform_status "
                                "WHERE entity_type='short' AND entity_id=?", (sid,))
                            self.db.execute("DELETE FROM shorts WHERE id=?", (sid,))
                            self.db.log("short", sid, "", "queue_delete", "hard")
                            removed += 1
                        _kill_posts(("long_video", eid))
                        self.db.execute(
                            "DELETE FROM entity_platform_status "
                            "WHERE entity_type='long_video' AND entity_id=?", (eid,))
                        self.db.execute("DELETE FROM long_videos WHERE id=?", (eid,))
                        self.db.log("long_video", eid, "", "queue_delete", "hard")
                        removed += 1
                else:
                    rows = self.db.fetchall(
                        "SELECT status FROM entity_platform_status "
                        "WHERE entity_type='short' AND entity_id=?", (eid,))
                    if any((r["status"] or "") == "published" for r in rows):
                        blocked.append(f"short#{eid}")
                    else:
                        _kill_posts(("short", eid))
                        self.db.execute(
                            "DELETE FROM entity_platform_status "
                            "WHERE entity_type='short' AND entity_id=?", (eid,))
                        self.db.execute("DELETE FROM shorts WHERE id=?", (eid,))
                        self.db.log("short", eid, "", "queue_delete", "hard")
                        removed += 1
                logger.info("queue remove: %s#%s removed=%s blocked=%s",
                            etype, eid, removed, blocked)
                return 200, {"ok": True, "removed": removed, "blocked": blocked}, \
                    "application/json"
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
                # если путь внутри другого разрешённого корня — переключаемся на него
                # (раньше дерево залипало на первом корне и «не открывалось»)
                for r in roots:
                    if base == r or r in base.parents:
                        root = r
                        break
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
            if method == "GET" and route in ("cover/list", "cover/thumb"):
                roots = self._browse_roots()

                def _allowed(p: Path) -> bool:
                    try:
                        rp = p.resolve()
                    except Exception:
                        return False
                    return any(rp == r or r in rp.parents for r in roots)

                target = query.get("path") or str(roots[0])
                base = Path(target).expanduser()
                base = base.resolve() if _allowed(base) and base.exists() else roots[0]
                if not _allowed(base):
                    return 403, {"error": "path not allowed"}, "application/json"
                if route == "cover/thumb":
                    if not base.is_file() or base.suffix.lower() not in IMG_EXTS:
                        return 404, {"error": "not an image"}, "application/json"
                    try:
                        if base.stat().st_size > 25 * 1024 * 1024:
                            return 413, {"error": "too large"}, "application/json"
                        blob = base.read_bytes()
                    except OSError:
                        return 404, {"error": "read failed"}, "application/json"
                    ctype = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                             ".png": "image/png", ".webp": "image/webp"}.get(
                                 base.suffix.lower(), "application/octet-stream")
                    return 200, blob, ctype
                dirs: list[dict] = []
                images: list[dict] = []
                warning = ""
                try:
                    children = sorted(base.iterdir())
                except PermissionError:
                    return 403, {"error": "permission denied"}, "application/json"
                except OSError:
                    children = []
                    warning = "папка недоступна"
                for child in children:
                    if child.name.startswith("."):
                        continue
                    try:
                        if child.is_dir():
                            dirs.append({"name": child.name, "path": str(child.resolve())})
                        elif child.is_file() and child.suffix.lower() in IMG_EXTS:
                            images.append({"name": child.name, "path": str(child.resolve()),
                                           "size": child.stat().st_size})
                    except OSError:
                        continue
                parent = str(base.parent) if base != base.parent and _allowed(base.parent) else None
                return 200, {
                    "path": str(base), "parent": parent,
                    "roots": [str(r) for r in roots],
                    "dirs": dirs, "images": images[:400], "warning": warning,
                }, "application/json"

            if method == "POST" and route == "cover/frames":
                etype = str(data.get("entity_type") or "").strip()
                try:
                    eid = int(data.get("entity_id") or 0)
                except Exception:
                    eid = 0
                if etype not in ("long_video", "short") or not eid:
                    return 400, {"error": "entity_type/entity_id required"}, "application/json"
                if etype == "short":
                    row = self.db.fetchone(
                        "SELECT video_path FROM shorts WHERE id=?", (eid,))
                else:
                    row = self.db.fetchone(
                        "SELECT COALESCE(vertical_path, wide_path) AS video_path "
                        "FROM long_videos WHERE id=?", (eid,))
                video = (row or {}).get("video_path") if row else None
                if not video or not Path(str(video)).is_file():
                    return 400, {"error": "video file not found"}, "application/json"
                import shutil as _shutil
                import subprocess as _sp
                if not _shutil.which("ffmpeg") or not _shutil.which("ffprobe"):
                    return 500, {"error": "ffmpeg/ffprobe not installed"}, "application/json"
                try:
                    dur_out = _sp.run(
                        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                         "-of", "default=nw=1:nk=1", str(video)],
                        capture_output=True, text=True, timeout=60)
                    duration = float((dur_out.stdout or "0").strip() or 0)
                except Exception:
                    duration = 0.0
                if duration <= 1:
                    return 400, {"error": "cannot read video duration"}, "application/json"
                try:
                    count = max(2, min(12, int(data.get("count") or 6)))
                except Exception:
                    count = 6
                covers = self._covers_dir()
                if covers is None:
                    return 500, {"error": "cannot create covers dir"}, "application/json"
                stamp = time.strftime("%Y%m%d-%H%M%S")
                outdir = covers / f"{etype}_{eid}_frames_{stamp}"
                try:
                    outdir.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    return 500, {"error": f"cannot create frames dir: {e}"}, "application/json"
                frames: list[dict] = []
                # кадры по всей длине, кроме самых краёв (там часто чёрное/титры)
                for i in range(count):
                    frac = 0.12 + (0.80 - 0.12) * (i / max(1, count - 1))
                    ts = max(0.5, duration * frac)
                    dst = outdir / f"frame_{i + 1:02d}.jpg"
                    try:
                        _sp.run(
                            ["ffmpeg", "-v", "error", "-ss", f"{ts:.2f}", "-i", str(video),
                             "-frames:v", "1", "-q:v", "3",
                             "-vf", "scale='min(1920,iw)':-2", "-y", str(dst)],
                            capture_output=True, timeout=120)
                    except Exception:
                        continue
                    if dst.is_file() and dst.stat().st_size > 200:
                        frames.append({"name": dst.name, "path": str(dst),
                                       "at": round(ts, 1)})
                if not frames:
                    return 500, {"error": "no frames extracted"}, "application/json"
                return 200, {"ok": True, "dir": str(outdir), "frames": frames,
                             "duration": round(duration, 1)}, "application/json"

            if method == "POST" and route in ("cover/upload", "cover/fetch"):
                etype = str(data.get("entity_type") or "").strip()
                try:
                    eid = int(data.get("entity_id") or 0)
                except Exception:
                    eid = 0
                if etype not in ("long_video", "short") or not eid:
                    return 400, {"error": "entity_type/entity_id required"}, "application/json"
                blob: bytes | None = None
                ext = ".jpg"
                if route == "cover/upload":
                    raw = str(data.get("data") or "")
                    m = re.match(r"^data:image/(png|jpe?g|webp);base64,(.+)$", raw, re.S)
                    if m:
                        ext = {"png": ".png", "jpg": ".jpg", "jpeg": ".jpg", "webp": ".webp"}[m.group(1)]
                        payload = m.group(2)
                    else:
                        payload = raw
                        e = Path(str(data.get("filename") or "")).suffix.lower()
                        ext = e if e in IMG_EXTS else ".jpg"
                    try:
                        blob = base64.b64decode(payload, validate=False)
                    except Exception:
                        return 400, {"error": "bad base64"}, "application/json"
                else:
                    url = str(data.get("url") or "").strip()
                    if not re.match(r"^https?://", url, re.I):
                        return 400, {"error": "http(s) url required"}, "application/json"
                    try:
                        import httpx
                        with httpx.Client(timeout=25.0, follow_redirects=True) as c:
                            r = c.get(url, headers={"User-Agent": "orchestrator-cover/1.0"})
                            r.raise_for_status()
                            blob = r.content
                            ctype = (r.headers.get("content-type") or "").split(";")[0].strip().lower()
                            ext = {"image/png": ".png", "image/jpeg": ".jpg",
                                   "image/webp": ".webp"}.get(
                                       ctype, Path(urlsplit(url).path).suffix.lower())
                            if ext not in IMG_EXTS:
                                ext = ".jpg"
                    except Exception as e:
                        return 502, {"error": f"download failed: {e}"}, "application/json"
                if blob is None or len(blob) < 32:
                    return 400, {"error": "empty image"}, "application/json"
                if len(blob) > 25 * 1024 * 1024:
                    return 413, {"error": "image too large (>25MB)"}, "application/json"
                if not _is_image_bytes(blob):
                    return 400, {"error": "not an image"}, "application/json"
                covers = self._covers_dir()
                if covers is None:
                    return 500, {"error": "cannot create covers dir"}, "application/json"
                stamp = time.strftime("%Y%m%d-%H%M%S")
                dst = covers / f"{etype}_{eid}_{stamp}_{os.urandom(2).hex()}{ext}"
                try:
                    dst.write_bytes(blob)
                except OSError as e:
                    return 500, {"error": f"save failed: {e}"}, "application/json"
                return 200, {"ok": True, "path": str(dst), "size": len(blob)}, "application/json"

            if method == "GET" and route == "browse/search":
                q = (query.get("q") or "").strip().lower()
                if len(q) < 2:
                    return 400, {"error": "query too short (min 2 chars)"}, "application/json"
                roots = self._browse_roots()
                sel = query.get("root")
                if sel:
                    rp = Path(sel).expanduser()
                    try:
                        rp = rp.resolve()
                    except Exception:
                        rp = None
                    if rp in roots:
                        roots = [rp]
                try:
                    limit = max(1, min(100, int(query.get("limit") or 50)))
                except Exception:
                    limit = 50
                results: list[dict] = []
                for root in roots:
                    if not root.is_dir():
                        continue
                    base_depth = len(root.parts)
                    for dirpath, dirnames, _files in os.walk(root):
                        d = Path(dirpath)
                        if len(d.parts) - base_depth > 5:
                            dirnames[:] = []
                            continue
                        dirnames[:] = [x for x in dirnames if not x.startswith(".")]
                        for name in dirnames:
                            if q in name.lower():
                                full = d / name
                                results.append({"name": name, "path": str(full),
                                                "root": str(root)})
                                if len(results) >= limit:
                                    break
                        if len(results) >= limit:
                            break
                    if len(results) >= limit:
                        break
                return 200, {"q": q, "items": results[:limit]}, "application/json"

            if method == "POST" and route == "scan":
                watcher = self.comps.get("watcher")
                if not watcher:
                    return 500, {"error": "watcher unavailable"}, "application/json"
                stats = {"long": 0, "shorts": 0, "standalone": 0}
                passes = max(2, int(getattr(self.cfg, "file_stability_cycles", 2)))
                jobs = self.comps.get("jobs")
                job = jobs.start("scan", "Сканирование папок", passes) if jobs is not None else None
                for _ in range(passes):
                    if job is not None and job.cancelled:
                        break
                    st = watcher.scan()
                    for k in stats:
                        stats[k] += int(st.get(k, 0) or 0)
                    if job is not None:
                        job.tick(1, "Поиск фильмов и шортсов")
                if job is not None:
                    job.finish("done", "Сканирование завершено")
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
                import re as _re

                sc = self.comps.get("scheduler")
                sd = str(data.get("start_date") or "").strip() or None
                shr = str(data.get("shorts_start_date") or "").strip() or None
                for name, val in (("start_date", sd), ("shorts_start_date", shr)):
                    if val and not _re.fullmatch(r"\d{4}-\d{2}-\d{2}", val):
                        return 400, {"error": f"{name} must be YYYY-MM-DD"}, "application/json"
                if shr is not None:
                    sched_settings.set_shorts_start_date(self.db, shr or "")
                guard = self.comps.get("guard")
                if guard is not None and hasattr(guard, "invalidate"):
                    guard.invalidate()

                jobs = self.comps.get("jobs")
                job = jobs.start("schedule", "Планирование публикаций") if jobs is not None else None
                before = self._sched_snapshot()

                def _run():
                    try:
                        if sc is not None:
                            sc.job = job
                        sc.schedule_long_videos(start_date=sd)
                        sc.schedule_standalone_shorts(self.comps.get("tail"), start_date=sd)
                        sc.schedule_telegram_links()
                        self._send_schedule_summary(before)
                        if job is not None:
                            job.finish("done", "Готово")
                    except Exception as e:
                        logger.exception("async schedule failed")
                        if job is not None:
                            job.finish("failed", str(e)[:200])

                if data.get("async"):
                    import threading
                    threading.Thread(target=_run, daemon=True).start()
                    return 200, {"ok": True, "started": True, "start_date": sd,
                                 "shorts_start_date": shr}, "application/json"
                n = sc.schedule_long_videos(start_date=sd) if sc else 0
                n2 = sc.schedule_standalone_shorts(self.comps.get("tail"), start_date=sd) if sc else 0
                self._send_schedule_summary(before)
                return 200, {"ok": True, "long": n, "standalone": n2, "start_date": sd,
                             "shorts_start_date": shr}, "application/json"
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

    def _sched_snapshot(self) -> set:
        rows = self.db.fetchall(
            "SELECT entity_type, entity_id, platform FROM entity_platform_status "
            "WHERE postiz_post_id IS NOT NULL AND postiz_post_id != ''")
        return {(r["entity_type"], r["entity_id"], r["platform"]) for r in rows}

    def _schedule_summary(self, before: set) -> str:
        after = self._sched_snapshot()
        added = after - before
        add_yt = [t for t in added if t[2] == "youtube"]
        add_yt_films = [t for t in add_yt if t[0] == "long_video"]
        add_yt_shorts = [t for t in add_yt if t[0] == "short"]
        add_other = [t for t in added if t[2] != "youtube"]
        lines = ["📋 Раскладка очереди — итог", ""]
        if added:
            lines.append(f"✅ Добавлено: {len(added)}")
            if add_yt:
                lines.append(f"• YouTube: {len(add_yt)} (фильмы: {len(add_yt_films)}, "
                             f"шортсы: {len(add_yt_shorts)})")
            if add_other:
                by_p: dict[str, int] = {}
                for t in add_other:
                    by_p[t[2]] = by_p.get(t[2], 0) + 1
                lines.append("• " + ", ".join(f"{k}: {v}" for k, v in sorted(by_p.items())))
        else:
            lines.append("✅ Добавлено: 0 (новых подходящих материалов нет)")
        tg_row = self.db.fetchone(
            "SELECT COUNT(*) AS c FROM entity_platform_status "
            "WHERE platform='telegram' AND status='ready' AND last_error='waiting_for_youtube'")
        if tg_row and tg_row["c"]:
            lines.append(f"• Telegram-ссылки в плане: {tg_row['c']} (опубликуются после премьер)")

        films = self.db.fetchall(
            "SELECT lv.id, lv.title_text FROM long_videos lv WHERE NOT EXISTS ("
            "SELECT 1 FROM entity_platform_status e WHERE e.entity_type='long_video' "
            "AND e.entity_id=lv.id AND e.status IN ('scheduled','published','updating'))")
        shorts = self.db.fetchall(
            "SELECT s.id, s.title_text, TRIM(COALESCE(s.hashtags_text,'')) AS tags "
            "FROM shorts s WHERE NOT EXISTS ("
            "SELECT 1 FROM entity_platform_status e WHERE e.entity_type='short' "
            "AND e.entity_id=s.id AND e.status IN ('scheduled','published','updating'))")
        if films or shorts:
            lines.append("")
            lines.append(f"⏳ Не добавлено: {len(films) + len(shorts)}")
            if films:
                lines.append(f"• Фильмы: {len(films)} — нет свободных слотов в расписании")
            if shorts:
                lines.append(f"• Шортсы: {len(shorts)} — нет свободных слотов (ждут «Остаток»)")
            no_tags = [x for x in shorts if not x["tags"]]
            if no_tags:
                names = ", ".join((x["title_text"] or f"#{x['id']}")[:22] for x in no_tags[:5])
                lines.append(f"• Без хештегов: {len(no_tags)} — {names}")
        return "\n".join(lines)

    def _send_schedule_summary(self, before: set) -> None:
        try:
            tg = self.comps.get("tg")
            if tg is not None:
                tg.broadcast(self._schedule_summary(before))
        except Exception:
            logger.warning("schedule summary send failed", exc_info=True)

    def _covers_dir(self) -> Path | None:
        """Папка для файлов обложек (по умолчанию /mnt/video/.covers)."""
        env_root = os.getenv("ORCH_COVERS_DIR", "").strip()
        cands = [Path(env_root)] if env_root else []
        cands += [Path("/mnt/video/.covers"), Path("/mnt/video/ssd_backup/.covers")]
        for cand in cands:
            try:
                cand.mkdir(parents=True, exist_ok=True)
                if os.access(cand, os.W_OK):
                    return cand
            except OSError:
                continue
        return None

    def _cover_candidates(self, video_path: str) -> list[str]:
        """Картинки-обложки рядом с видео (в папке и на уровень выше)."""
        if not video_path:
            return []
        try:
            vp = Path(video_path)
        except Exception:
            return []
        out: list[str] = []
        bases = [vp.parent, vp.parent.parent]
        for i, base in enumerate(bases):
            if not base.is_dir():
                continue
            try:
                for f in sorted(base.iterdir()):
                    if not f.is_file():
                        continue
                    if f.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
                        continue
                    if f.name.startswith("._"):
                        continue
                    if i == 0 or "cover" in f.name.lower() or "облож" in f.name.lower():
                        out.append(str(f.resolve()))
            except OSError:
                continue
        # папки с обложками рядом (например, «обложки для ютюб»)
        for base in bases[:1]:
            parent = base.parent
            if not parent.is_dir():
                continue
            try:
                for d in sorted(parent.iterdir()):
                    if not d.is_dir():
                        continue
                    low = d.name.lower()
                    if "cover" not in low and "облож" not in low:
                        continue
                    for f in sorted(d.iterdir()):
                        if (f.is_file() and not f.name.startswith("._")
                                and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")):
                            out.append(str(f.resolve()))
            except OSError:
                continue
        seen: list[str] = []
        for p in out:
            if p not in seen:
                seen.append(p)
        return seen[:30]

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
            lambda m: f"<style>\n{css}\n</style>",
            html,
        )
        html = re.sub(
            r'<script src="app\.js\?v=\d+"></script>',
            lambda m: ("<script>window.__WEBAPP_KEY__=" + json.dumps(key) + ";</script>\n"
                       f"<script>\n{js}\n</script>"),
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
                   eps.last_error, eps.postiz_scheduled_for,
                   COALESCE(lv.title_text, lv.title, sh.title_text) AS title,
                   COALESCE(lv.description_text, sh.description_text) AS description_text,
                   COALESCE(lv.hashtags_text, sh.hashtags_text) AS hashtags_text,
                   COALESCE(lv.cover_path, sh.cover_path) AS cover_path,
                   COALESCE(lv.vertical_path, lv.wide_path, sh.video_path) AS video_path,
                   EXISTS (SELECT 1 FROM entity_platform_status t
                           WHERE t.entity_type = eps.entity_type
                             AND t.entity_id = eps.entity_id
                             AND t.platform = 'telegram') AS has_tg
            FROM entity_platform_status eps
            LEFT JOIN long_videos lv
                   ON eps.entity_type='long_video' AND lv.id = eps.entity_id
            LEFT JOIN shorts sh
                   ON eps.entity_type='short' AND sh.id = eps.entity_id
            WHERE eps.status IN ('ready', 'scheduled', 'updating')
            ORDER BY eps.postiz_scheduled_for LIMIT 300
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
                "cover_path": r.get("cover_path") or "",
                "waiting": (r.get("last_error") or "") == "waiting_for_youtube",
                "covers": self._cover_candidates(r.get("video_path") or ""),
                "video_path": r.get("video_path") or "",
                "has_tg": bool(r.get("has_tg")),
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
