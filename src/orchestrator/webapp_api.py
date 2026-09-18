from __future__ import annotations
import hashlib
import hmac
import json
import logging
import os
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from .watcher import WATCH_ROOTS_KEY

logger = logging.getLogger(__name__)

WEBAPP_DIR = Path(__file__).resolve().parents[2] / "webapp"
WEBAPP_BUILD = "3"


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
        is_api = qpath.startswith("/webapp/api/")

        # static (never intercept /webapp/api/*)
        if not is_api:
            if method == "GET" and qpath == "/webapp/diag":
                logger.warning(
                    "WEBAPP_DIAG href=%s tg=%s key=%s",
                    query.get("u"), query.get("tg"), query.get("k"),
                )
                return 204, b"", "text/plain"
            if method == "GET" and (
                qpath in ("/webapp", "/webapp/", "/webapp/index.html")
                or qpath.startswith("/webapp/k/")
            ):
                return self._file("index.html", "text/html; charset=utf-8")
            bprefix = f"/webapp/b/{WEBAPP_BUILD}"
            if method == "GET" and qpath in (bprefix, bprefix + "/"):
                return self._file("index.html", "text/html; charset=utf-8")
            if method == "GET" and qpath.startswith(bprefix + "/") and ".." not in qpath:
                bname = qpath[len(bprefix) + 1 :]
                if bname:
                    bctype = {
                        "css": "text/css; charset=utf-8",
                        "js": "application/javascript; charset=utf-8",
                        "html": "text/html; charset=utf-8",
                        "svg": "image/svg+xml",
                        "png": "image/png",
                    }.get(bname.rsplit(".", 1)[-1], "application/octet-stream")
                    return self._file(bname, bctype)
            if method == "GET" and qpath.startswith("/webapp/") and ".." not in qpath:
                name = qpath[len("/webapp/") :] or "index.html"
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
                return 200, {"roots": self._roots()}, "application/json"
            if method == "POST" and route == "roots":
                new = data.get("roots")
                if not isinstance(new, list):
                    return 400, {"error": "roots must be a list"}, "application/json"
                cleaned: list[str] = []
                for p in new:
                    target = Path(str(p)).expanduser()
                    if not target.is_dir():
                        return 400, {"error": f"not a directory: {p}"}, "application/json"
                    cleaned.append(str(target.resolve()))
                self.db.set_setting(WATCH_ROOTS_KEY, json.dumps(cleaned))
                return 200, {"ok": True, "roots": cleaned}, "application/json"
            if method == "GET" and route == "browse":
                target = query.get("path") or (self._roots()[0] if self._roots() else "/")
                base = Path(target).expanduser()
                if not base.is_dir():
                    return 400, {"error": "not a directory"}, "application/json"
                resolved = base.resolve()
                dirs = []
                try:
                    for child in sorted(resolved.iterdir()):
                        if child.is_dir() and not child.name.startswith("."):
                            dirs.append({"name": child.name, "path": str(child.resolve())})
                except PermissionError:
                    return 403, {"error": "permission denied"}, "application/json"
                parent = str(resolved.parent) if resolved.parent != resolved else None
                return 200, {
                    "path": str(resolved),
                    "parent": parent,
                    "dirs": dirs,
                    "selected": str(resolved) in self._roots(),
                }, "application/json"
            if method == "POST" and route == "scan":
                watcher = self.comps.get("watcher")
                if not watcher:
                    return 500, {"error": "watcher unavailable"}, "application/json"
                stats = watcher.scan()
                return 200, {
                    "ok": True,
                    "stats": stats,
                    "roots": [str(r) for r in watcher.effective_roots()],
                }, "application/json"
            return 404, {"error": "unknown route"}, "application/json"
        except Exception as e:
            logger.exception("webapp api")
            return 500, {"error": str(e)}, "application/json"

    def _metrics(self) -> dict:
        path = Path(self.db.path).parent / "metrics.json"
        if path.is_file():
            try:
                return json.loads(path.read_text())
            except Exception:
                pass
        return {"cycles": 0, "note": "no metrics yet"}

    def _roots(self) -> list[str]:
        raw = self.db.get_setting(WATCH_ROOTS_KEY)
        if raw:
            try:
                items = json.loads(raw)
                if isinstance(items, list):
                    return [str(x) for x in items]
            except Exception:
                logger.warning("invalid watch_roots setting")
        return []

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

    def _calendar(self) -> dict:
        rows = self.db.fetchall(
            """
            SELECT platform, postiz_scheduled_for, entity_type, entity_id, status
            FROM entity_platform_status
            WHERE postiz_scheduled_for IS NOT NULL
            ORDER BY postiz_scheduled_for LIMIT 200
            """
        )
        by: dict[str, list] = defaultdict(list)
        for r in rows:
            day = (r["postiz_scheduled_for"] or "")[:10]
            time = (r["postiz_scheduled_for"] or "")[11:16]
            by[day].append({
                "time": time,
                "platform": r["platform"],
                "entity_type": r["entity_type"],
                "entity_id": r["entity_id"],
                "status": r["status"],
            })
        days = [{"date": d, "items": by[d]} for d in sorted(by.keys())]
        return {"days": days}

    def _queue(self) -> dict:
        rows = self.db.fetchall(
            """
            SELECT entity_type, entity_id, platform, status, postiz_scheduled_for
            FROM entity_platform_status
            WHERE status IN ('ready', 'scheduled', 'updating')
            ORDER BY postiz_scheduled_for LIMIT 50
            """
        )
        return {"items": rows}

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
