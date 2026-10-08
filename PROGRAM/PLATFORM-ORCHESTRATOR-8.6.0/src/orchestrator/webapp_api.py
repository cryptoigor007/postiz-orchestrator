from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import sqlite3
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from . import sched_settings
from .metrics import sanitize_metrics
from .watcher import WATCH_ROOTS_KEY


def _addr_is_public(addr: str) -> bool:
    """Публичный ли IP (private/loopback/link-local/reserved/multicast/unspecified/CGNAT)."""
    import ipaddress
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
            or ip.is_multicast or ip.is_unspecified):
        return False
    if ip.version == 4 and ip in ipaddress.ip_network("100.64.0.0/10"):
        return False  # CGNAT
    if ip.version == 6 and ip in ipaddress.ip_network("fec0::/10"):
        return False  # site-local (deprecated, но блокируем)
    return True


def _hostname_ok(host: str) -> bool:
    """Отклоняем localhost/числовые литералы/userinfo — до DNS."""
    import re as _re
    h = (host or "").strip().lower().rstrip(".")
    if not h:
        return False
    if h == "localhost" or h.endswith(".localhost") or h.endswith(".local"):
        return False
    if ":" in h:  # raw IPv6 literal — не принимаем, требуем hostname
        return False
    if _re.fullmatch(r"0[xX][0-9a-fA-F]+", h):  # 0x7f000001
        return False
    if _re.fullmatch(r"\d+", h):  # decimal IP (2130706433)
        return False
    if _re.fullmatch(r"0[0-7]*(\.[0-7]+){3}", h):  # octal IP
        return False
    if _re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", h):  # dotted-quad IP literal (в т.ч. 127.0.0.1)
        return False
    return True


def _resolve_and_pin(host: str) -> list[str]:
    """Все A/AAAA хоста обязаны быть публичными; возвращаем список IP для pin-connect."""
    import socket
    infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    ips: list[str] = []
    for _fam, _t, _p, _c, sa in infos or []:
        addr = sa[0]
        if not _addr_is_public(str(addr)):
            raise ValueError(f"address not public: {addr}")
        if str(addr) not in ips:
            ips.append(str(addr))
    if not ips:
        raise ValueError("no addresses")
    return ips


def _fetch_image_pinned(url: str, max_bytes: int = 25 * 1024 * 1024,
                        max_hops: int = 3) -> tuple[bytes, str, str]:
    """GET картинки с pin по IP (anti DNS-rebinding), ручной redirect, stream cap.

    Возвращает (blob, content_type, final_url). Бросает ValueError с понятной причиной.
    """
    import socket
    import ssl
    from urllib.parse import urljoin, urlsplit

    for _hop in range(max_hops + 1):
        u = urlsplit(url)
        if u.scheme not in ("http", "https"):
            raise ValueError("scheme not allowed")
        if u.username or u.password:
            raise ValueError("userinfo not allowed")
        host = u.hostname or ""
        if not _hostname_ok(host):
            raise ValueError("host not allowed")
        port = u.port or (443 if u.scheme == "https" else 80)
        ips = _resolve_and_pin(host)  # проверка ВСЕХ адресов + pin

        sock = None
        last_err: Exception | None = None
        for ip in ips:  # коннектимся только к проверенному IP (без повторного resolve)
            try:
                sock = socket.create_connection((ip, port), timeout=10)
                break
            except OSError as e:  # noqa: PERF203
                last_err = e
                sock = None
        if sock is None:
            raise ValueError(f"connect failed: {last_err}")

        try:
            if u.scheme == "https":
                sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
            path = u.path or "/"
            if u.query:
                path += "?" + u.query
            req = (f"GET {path} HTTP/1.1\r\nHost: {host}\r\n"
                   "User-Agent: orchestrator-cover/1.0\r\nAccept: image/*\r\n"
                   "Connection: close\r\n\r\n")
            sock.sendall(req.encode())
            head_buf = b""
            while b"\r\n\r\n" not in head_buf:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                head_buf += chunk
                if len(head_buf) > 65536:
                    raise ValueError("headers too large")
            head, _sep, body = head_buf.partition(b"\r\n\r\n")
            lines = head.split(b"\r\n")
            if not lines or len(lines[0].split()) < 2:
                raise ValueError("bad response")
            status = int(lines[0].split()[1])
            hdrs: dict[str, str] = {}
            for ln in lines[1:]:
                k, _c, v = ln.partition(b":")
                hdrs[k.strip().lower().decode("latin-1")] = v.strip().decode("latin-1")
            if status in (301, 302, 303, 307, 308):
                loc = hdrs.get("location") or ""
                if not loc:
                    raise ValueError("redirect without location")
                url = urljoin(url, loc)  # следующий хоп проверится заново
                continue
            if status != 200:
                raise ValueError(f"http {status}")
            ctype = (hdrs.get("content-type") or "").split(";")[0].strip().lower()
            clen = hdrs.get("content-length") or ""
            if clen.isdigit() and int(clen) > max_bytes:
                raise ValueError("image too large")
            buf = bytearray(body)
            if len(buf) > max_bytes:
                raise ValueError("image too large")
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
                if len(buf) > max_bytes:  # stream cap: обрыв, не копим RAM
                    raise ValueError("image too large")
            return bytes(buf), ctype, url
        finally:
            try:
                sock.close()
            except Exception:
                logger.debug("image socket close failed", exc_info=True)
    raise ValueError("too many redirects")


def _host_is_public(host: str) -> bool:
    """True, если все адреса хоста — публичные (совместимость; см. _resolve_and_pin)."""
    try:
        _resolve_and_pin(host)
        return True
    except (OSError, ValueError):
        return False


IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
_SCHEDULE_LOCK = threading.Lock()  # одна раскладка за раз (защита от двойного запуска)


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

_YT_ID_RE = re.compile(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{6,})")


def _youtube_id_from_url(url: str) -> str:
    """N1: id видео из release_url (watch?v=…, youtu.be/…, shorts/…)."""
    m = _YT_ID_RE.search(url or "")
    return m.group(1) if m else ""


logger = logging.getLogger(__name__)

WEBAPP_DIR = Path(__file__).resolve().parents[2] / "webapp"
WEBAPP_BUILD = "844"  # cache-bust; bump with major.minor (no dots — path safety)


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
        # P0.5: freshness auth_date (по умолчанию 24ч) — защита от replay старого initData
        try:
            max_age = int(os.getenv("ORCH_WEBAPP_INIT_MAX_AGE_SEC", "86400"))
        except ValueError:
            max_age = 86400
        if max_age > 0:
            raw_date = str(parsed.get("auth_date") or "").strip()
            if not raw_date.isdigit():
                return None  # Telegram всегда присылает auth_date; отсутствие — отклоняем
            age = time.time() - int(raw_date)
            if age > max_age or age < -300:  # допускаем небольшой clock-skew вперёд
                logger.warning("initData stale: age=%.0fs > %ss", age, max_age)
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
        self._tls = threading.local()  # per-request nonce для CSP

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
        # F6c: клиент присылает lang=ru|en — серверные подписи сущностей локализуются
        _lang = str(query.get("lang") or "ru").lower()
        self._tls.lang = _lang if _lang in ("ru", "en") else "ru"
        # A4: не светим ?key=… в логах (access log/журнал видит URL)
        _safe_path = re.sub(r"(key=)[^&\s]+", r"\1***", path)
        # P2-3: legacy-форма /webapp/k/<key>/… тоже не должна светить ключ в логах
        _safe_path = re.sub(r"(/webapp/k/)[^/\s]+", r"\1***", _safe_path)
        logger.info(
            "WEBAPP_REQ %s %s request_id=%s ua=%s ip=%s",
            method, _safe_path, headers.get("X-Request-Id") or headers.get("x-request-id") or "",
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
                    re.sub(r"(key=)[^&\s]+", r"\1***", str(query.get("u") or "")),
                    query.get("tg"), query.get("k"),
                )
                return 204, b"", "text/plain"
            if method == "GET":
                bprefix = f"/webapp/b/{WEBAPP_BUILD}"
                last = qpath.rstrip("/").rsplit("/", 1)[-1]
                is_asset = "." in last
                # 10.4: /webapp/k/<key>/ only if ORCH_LEGACY_PATH_KEY=1
                _legacy_path_key = os.getenv("ORCH_LEGACY_PATH_KEY", "").strip().lower() in (
                    "1", "true", "yes", "on",
                )
                is_page = (not is_asset) and (
                    qpath in ("/webapp", "/webapp/", "/webapp/index.html")
                    or (_legacy_path_key and qpath.startswith("/webapp/k/"))
                    or qpath == bprefix
                    or qpath.startswith(bprefix + "/")
                )
                if is_page:
                    import secrets as _secrets

                    from . import http_server as _hs
                    nonce = _secrets.token_urlsafe(16)
                    self._tls.nonce = nonce
                    _hs._webapp_nonce.value = nonce
                    return (
                        200,
                        self._compose_index(self._key_from_request(qpath, query), nonce),
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

        route_early = qpath[len("/webapp/api/") :].strip("/") if is_api else ""
        # N1: OAuth provider redirect has no Telegram initData — allow callback publicly (CSRF via state).
        _oauth_public = (
            is_api
            and method == "GET"
            and route_early.startswith("oauth/callback/")
        )
        if _oauth_public:
            provider = route_early.split("/")[-1]
            params = dict(query or {})
            data_early: dict = {}
            if body:
                try:
                    data_early = json.loads(body.decode() or "{}")
                except Exception:
                    data_early = {}
            if isinstance(data_early, dict) and data_early:
                params.update({k: v for k, v in data_early.items() if v})
            return 200, self._oauth_callback(provider, params), "application/json"

        auth_query = query
        if qpath == "/webapp/api/cover/thumb":
            # Thumbnail bytes must authenticate through headers/initData, never a URL access key.
            auth_query = {k: v for k, v in query.items() if k != "key"}
        auth = self._auth(headers, auth_query)
        if not auth:
            return 401, {"error": "unauthorized"}, "application/json"
        # R2: bucket считается по уже валидированному auth (uid после HMAC), не по сырому заголовку
        if self._rate_limited(headers, auth):
            return 429, {"error": "too many requests"}, "application/json"

        route = qpath[len("/webapp/api/") :].strip("/")
        # R13: read-only mode blocks mutating API routes
        import os as _os
        _ro = _os.getenv("ORCH_READ_ONLY", "").strip() in ("1", "true", "yes") or bool(getattr(self.cfg, "read_only", False))
        if _ro and method in ("POST", "PUT", "DELETE", "PATCH"):
            # read-only: ЛЮБАЯ мутация запрещена (раньше список был неполным:
            # distribute/sync/reconcile/backup/scheduling_mode/pause_platform/queue/*/
            # series_end/manual/*/roots проходили и меняли состояние)
            return 403, {"error": "read_only"}, "application/json"

        data = {}
        if body:
            try:
                data = json.loads(body.decode() or "{}")
            except Exception:
                data = {}

        try:
            if method == "GET" and route == "version":
                from . import __version__
                return 200, {"version": __version__, "build": WEBAPP_BUILD}, "application/json"
            if method == "GET" and route == "metrics":
                return 200, self._metrics(), "application/json"
            if method == "GET" and route == "status":
                return 200, self._status(), "application/json"
            # F7 OAuth PKCE
            if method == "GET" and route.startswith("oauth/") and route.endswith("/start"):
                provider = route.split("/")[1] if "/" in route else ""
                return 200, self._oauth_start(provider, account_hint=str(query.get("account_id") or "")), "application/json"
            if method == "GET" and route.startswith("oauth/callback/"):
                provider = route.split("/")[-1]
                # OAuth providers redirect with code/state in query string (GET body empty)
                params = dict(query or {})
                if isinstance(data, dict) and data:
                    params.update({k: v for k, v in data.items() if v})
                return 200, self._oauth_callback(provider, params), "application/json"
            if method == "GET" and route == "calendar":
                return 200, self._calendar(), "application/json"
            if method == "GET" and route in ("inventory", "remote_inventory"):
                return 200, self._remote_inventory(), "application/json"
            if method == "POST" and route == "inventory/scan":
                return 200, self._inventory_scan(), "application/json"
            if method == "POST" and route in ("inventory/claim", "inventory/link", "inventory/ignore"):
                return 200, self._inventory_action(route.split("/")[-1], data if isinstance(data, dict) else {}), "application/json"
            if method == "GET" and route == "ops":
                return 200, self._ops_status(), "application/json"
            if method == "GET" and route == "ops/outbox/dead":
                outbox = self.comps.get("outbox")
                return 200, {"items": outbox.dead(limit=int(query.get("limit") or 100)) if outbox else [],
                             "count": len(outbox.dead(limit=int(query.get("limit") or 100))) if outbox else 0}, "application/json"
            if method == "POST" and route.startswith("ops/outbox/replay/"):
                outbox = self.comps.get("outbox")
                try:
                    event_id = int(route.rsplit("/", 1)[-1])
                except ValueError:
                    return 400, {"error": "invalid outbox id"}, "application/json"
                ok = bool(outbox and outbox.replay(event_id))
                return (200 if ok else 404), {"ok": ok, "id": event_id}, "application/json"
            if method == "GET" and route == "queue":
                return 200, self._queue(), "application/json"
            if method == "GET" and route == "projects":
                return 200, self._projects(), "application/json"
            if method == "GET" and route == "platforms":
                return 200, self._platforms(), "application/json"
            if method == "GET" and route == "accounts/checklist":
                from .connection_control import ConnectionControl
                from .accounts.store import PlatformAccountStore
                cc = ConnectionControl(self.db, self.comps.get("module_registry"), self.comps.get("token_lifecycle"), PlatformAccountStore(self.db))
                return 200, cc.as_dict(cc.checklist(str(query.get("provider") or ""), str(query.get("account_id") or ""))), "application/json"
            if method == "POST" and route == "accounts/disconnect":
                from .connection_control import ConnectionControl
                from .accounts.store import PlatformAccountStore
                cc = ConnectionControl(self.db, self.comps.get("module_registry"), self.comps.get("token_lifecycle"), PlatformAccountStore(self.db))
                return 200, {"ok": cc.disconnect(str(data.get("account_id") or ""))}, "application/json"
            if method == "GET" and route == "platform_capabilities":
                return 200, self._platform_capabilities(), "application/json"
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
            if method == "POST" and route == "cross_post":
                # G4: enqueue same entity onto selected platforms as ready (+ optional promo kind)
                etype = str(data.get("entity_type") or "").strip()
                try:
                    eid = int(data.get("entity_id") or 0)
                except Exception:
                    eid = 0
                plats = data.get("platforms") or []
                if not isinstance(plats, list):
                    plats = [plats]
                plats = [str(p).strip() for p in plats if str(p).strip()]
                ck = str(data.get("content_kind") or "video_native").strip() or "video_native"
                if etype not in ("long_video", "short") or not eid or not plats:
                    return 400, {"error": "entity_type, entity_id, platforms required"}, "application/json"
                # entity must exist
                table = "long_videos" if etype == "long_video" else "shorts"
                try:
                    exists = self.db.fetchone(f"SELECT id FROM {table} WHERE id=?", (eid,))
                except Exception:
                    logger.exception("cross_post entity lookup failed %s/%s", table, eid)
                    return 503, {"error": "entity lookup failed"}, "application/json"
                if not exists:
                    return 400, {"error": "entity not found"}, "application/json"
                known = set(self.cfg.platforms.keys()) if self.cfg else set()
                created = []
                errors = []
                for plat in plats:
                    if known and plat not in known:
                        continue
                    pc = self.cfg.platforms.get(plat) if self.cfg else None
                    if pc is not None and not bool(getattr(pc, "enabled", True) if not isinstance(pc, dict) else pc.get("enabled", True)):
                        continue
                    try:
                        self.db.execute(
                            "INSERT OR IGNORE INTO entity_platform_status "
                            "(entity_type, entity_id, platform, status, content_kind, source) "
                            "VALUES (?, ?, ?, 'ready', ?, 'cross_post')",
                            (etype, eid, plat, ck),
                        )
                        created.append(plat)
                    except Exception as exc:
                        logger.exception("cross_post insert failed %s/%s/%s", etype, eid, plat)
                        errors.append({"platform": plat, "error": str(exc)})
                return 200, {"ok": not errors, "platforms": created, "errors": errors, "content_kind": ck}, "application/json"
            if method == "POST" and route == "distribute":

                n = self.comps["scheduler"].schedule_long_videos(
                    scope_roots=self._scan_roots())
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
                try:
                    fid = int(data.get("entity_id") or 0)
                except Exception:
                    fid = 0
                fplat = str(data.get("platform") or "").strip()
                furl = str(data.get("url") or "").strip()
                ftype = str(data.get("entity_type") or "").strip() or None
                link_upd = self.comps.get("link_upd")
                if link_upd is None:
                    return 503, {"error": "link_updater unavailable"}, "application/json"
                if not fid or not fplat or not furl:
                    return 400, {"error": "entity_type/entity_id/platform/url required"}, \
                        "application/json"
                if not re.match(r"^https?://", furl, re.I):
                    return 400, {"error": "url must be http(s)"}, "application/json"
                ok = link_upd.force_update(fid, fplat, furl, entity_type=ftype)
                return (200, {"ok": True}, "application/json") if ok else (
                    400, {"error": "force_link_failed"}, "application/json"
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
                    if not allowed:
                        return 400, {"error": "no browse roots configured"}, "application/json"
                    if not self._path_under_roots(rp, allowed):
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
                account_id, account_error = self._resolve_eps_account(data, etype, eid, platform_sel) if platform_sel else ("", None)
                if account_error:
                    return account_error
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
                # E7 content_kind on EPS row for this platform (or all if empty)
                ck = str(data.get("content_kind") or "").strip()
                if ck and platform_sel:
                    try:
                        self.db.set_content_kind(etype, eid, platform_sel, ck, account_id=account_id)
                    except Exception:
                        try:
                            self.db.execute(
                                "UPDATE entity_platform_status SET content_kind=? "
                                "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                                (ck, etype, eid, platform_sel, account_id),
                            )
                        except Exception:
                            logger.exception("content_kind fallback update failed %s/%s/%s", etype, eid, platform_sel)
                # G6 placement: start|middle|end on entity meta (long_videos/shorts column if present)
                placement = str(data.get("placement") or "").strip().lower()
                if placement in ("start", "middle", "end", "default"):
                    try:
                        self.db.execute(
                            f"UPDATE {table} SET placement=? WHERE id=?",
                            (placement if placement != "default" else None, eid),
                        )
                    except Exception:
                        # column may not exist yet — migrate lightly
                        try:
                            self.db.execute(f"ALTER TABLE {table} ADD COLUMN placement TEXT")
                            self.db.execute(
                                f"UPDATE {table} SET placement=? WHERE id=?",
                                (placement if placement != "default" else None, eid),
                            )
                        except Exception:
                            logger.exception("placement migration/update failed %s/%s", table, eid)
                sql = (
                    "SELECT platform, "
                    "external_id AS external_id, "
                    "scheduled_for AS scheduled_for, "
                    "status "
                    "FROM entity_platform_status WHERE entity_type=? AND entity_id=? "
                    "AND status IN ('scheduled','updating','ready','error')"
                )
                params: list = [etype, eid]
                if platform_sel:
                    sql += " AND platform=? AND account_id=?"
                    params.extend([platform_sel, account_id])
                rows = self.db.fetchall(sql, tuple(params))
                sch = self.comps.get("scheduler")
                pub = getattr(sch, "publisher", None) if sch else self.comps.get("publisher")
                updated = 0
                recreated = 0
                for r in rows:
                    plat = r["platform"]
                    pid = r.get("external_id")
                    if pid and pub is not None and hasattr(pub, "cancel_or_delete"):
                        try:
                            pub.cancel_or_delete(plat, str(pid))
                        except Exception:
                            logger.warning("queue edit: cancel failed %s", pid, exc_info=True)
                    self.db.execute(
                        "UPDATE entity_platform_status SET status='ready', "
                        "external_id=NULL, last_error=NULL "
                        "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                        (etype, eid, plat, r.get("account_id") or account_id),
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
                    when = r.get("scheduled_for")
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
                    if sched_dt is None and not (r.get("external_id") and r.get("status") == "scheduled"):
                        # у строки нет времени: контент обновили, но пересоздавать нечего —
                        # иначе module публикует пост немедленно (сейчас!)
                        continue
                    content = {"title": title, "description": desc, "hashtags": tags,
                               "cover": cover}
                    _tcfg = self.cfg.platforms.get("telegram")
                    _bot_tg = bool(plat == "telegram" and _tcfg
                                   and str(getattr(_tcfg, "send_via", "bot") or "bot").lower() == "bot")
                    if _bot_tg:
                        # Telegram отправляет наш бот: правим контент/время строки, пост не
                        # пересоздаём — иначе в канале появится второй пост
                        if sched_dt is not None:
                            self.db.execute(
                                "UPDATE entity_platform_status SET scheduled_for=? "
                                "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                                (sched_dt.isoformat(), etype, eid, plat, r.get("account_id") or account_id),
                            )
                        continue
                    try:
                        post = pub.publish(etype, eid, plat, path, content, sched_dt)
                        if post:
                            recreated += 1
                        elif sched_dt is not None:
                            self.db.execute(
                                "UPDATE entity_platform_status SET scheduled_for=? "
                                "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                                (sched_dt.isoformat(), etype, eid, plat, r.get("account_id") or account_id),
                            )
                    except Exception:
                        logger.exception("queue edit: пересоздание не удалось (%s/%s %s)",
                                         etype, eid, plat)
                return 200, {"ok": True, "updated": updated, "recreated": recreated}, \
                    "application/json"
            if method == "POST" and route == "queue/cleanup_orphans":
                # Legacy IDs are migration-only and are never read or mutated by the runtime.
                # This endpoint now validates canonical rows only.
                known = {
                    r["external_id"] for r in self.db.fetchall(
                        "SELECT external_id FROM entity_platform_status "
                        "WHERE external_id IS NOT NULL AND external_id != ''"
                    )
                }
                known |= self._active_test_post_ids()
                logger.info("cleanup_orphans: canonical remote ids tracked=%s", len(known))
                return 200, {"ok": True, "deleted": 0, "legacy_runtime_reads": 0}, "application/json"
            if method == "POST" and route == "queue/restore":
                etype = str(data.get("entity_type") or "").strip()
                try:
                    eid = int(data.get("entity_id") or 0)
                except Exception:
                    eid = 0
                if etype in ("long_video", "short") and eid:
                    platform_for_restore = str(data.get("platform") or "").strip()
                    account_id = str(data.get("account_id") or "").strip()
                    if platform_for_restore:
                        account_id, account_error = self._resolve_eps_account(data, etype, eid, platform_for_restore)
                        if account_error:
                            return account_error
                    if platform_for_restore and account_id is not None:
                        where = "status='skipped' AND entity_type=? AND entity_id=? AND platform=? AND account_id=?"
                        params = (etype, eid, platform_for_restore, account_id)
                    elif account_id:
                        where = "status='skipped' AND entity_type=? AND entity_id=? AND account_id=?"
                        params = (etype, eid, account_id)
                    else:
                        where = "status='skipped' AND entity_type=? AND entity_id=?"
                        params = (etype, eid)
                    before = self.db.fetchone(
                        f"SELECT COUNT(*) AS c FROM entity_platform_status WHERE {where}", params)
                    self.db.execute(
                        "UPDATE entity_platform_status SET status='ready', external_id=NULL, external_sub_id=NULL, external_url=NULL, "
                        "last_error=NULL, deleted_at=NULL, deleted_reason=NULL, cascade_from=NULL "
                        f"WHERE {where}", params)
                elif data.get("all"):
                    if not bool(data.get("confirm_all")):
                        return 400, {"error": "confirm_all_required", "message": "Global restore requires explicit confirm_all=true"}, "application/json"
                    account_id = str(data.get("account_id") or "").strip()
                    if account_id:
                        before = self.db.fetchone("SELECT COUNT(*) AS c FROM entity_platform_status WHERE status='skipped' AND account_id=?", (account_id,))
                        self.db.execute(
                            "UPDATE entity_platform_status SET status='ready', external_id=NULL, external_sub_id=NULL, external_url=NULL, last_error=NULL, deleted_at=NULL, deleted_reason=NULL, cascade_from=NULL WHERE status='skipped' AND account_id=?", (account_id,))
                    else:
                        before = self.db.fetchone("SELECT COUNT(*) AS c FROM entity_platform_status WHERE status='skipped'")
                        self.db.execute(
                            "UPDATE entity_platform_status SET status='ready', external_id=NULL, external_sub_id=NULL, external_url=NULL, last_error=NULL, deleted_at=NULL, deleted_reason=NULL, cascade_from=NULL WHERE status='skipped'")
                    self.db.log("system", None, account_id or "", "trash_restore_all", f"account_scoped={bool(account_id)}")
                else:
                    # P2-4: раньше невалидный entity_id (0/"abc") попадал в else и восстанавливал ВСЁ.
                    return 400, {"error": "entity_type/entity_id or all=true required"}, "application/json"
                return 200, {"ok": True, "restored": (before or {}).get("c", 0)}, "application/json"
            if method == "GET" and route == "trash":
                # Корзина: всё, что помечено skipped (мягкое удаление), с группировкой на клиенте.
                rows = self.db.fetchall(
                    """
                    SELECT eps.entity_type, eps.entity_id, eps.platform, eps.account_id, eps.status,
                           eps.deleted_at, eps.deleted_reason, eps.cascade_from,
                           eps.scheduled_for AS scheduled_for,
                           COALESCE(lv.title_text, lv.title, sh.title_text) AS title,
                           sh.parent_video_id AS parent_id
                    FROM entity_platform_status eps
                    LEFT JOIN long_videos lv
                           ON eps.entity_type='long_video' AND lv.id=eps.entity_id
                    LEFT JOIN shorts sh
                           ON eps.entity_type='short' AND sh.id=eps.entity_id
                    WHERE eps.status='skipped'
                    ORDER BY (eps.deleted_at IS NULL), eps.deleted_at DESC,
                             eps.entity_type, eps.entity_id
                    LIMIT 500
                    """
                )
                items = []
                for r in rows:
                    kind = self._kind_label(r["entity_type"])
                    title = (r.get("title") or "").strip() or f'{kind} #{r["entity_id"]}'
                    items.append({
                        "key": f'{r["entity_type"]}|{r["entity_id"]}|{r["platform"]}|{r.get("account_id") or ""}',
                        "entity_type": r["entity_type"],
                        "entity_id": r["entity_id"],
                        "platform": r["platform"],
                        "account_id": r.get("account_id") or "",
                        "title": title,
                        "deleted_at": r["deleted_at"],
                        "deleted_reason": r["deleted_reason"],
                        "cascade_from": r["cascade_from"],
                        "scheduled_for": r["scheduled_for"],
                        "parent_id": r["parent_id"],
                    })
                total_row = self.db.fetchone(
                    "SELECT COUNT(*) AS c FROM entity_platform_status WHERE status='skipped'")
                total = int((total_row or {}).get("c") or 0)
                return 200, {"items": items, "total": total, "shown": len(items)}, \
                    "application/json"
            if method == "POST" and route in ("trash/restore", "trash/purge"):
                ids = data.get("ids") or []
                all_flag = bool(data.get("all"))
                if all_flag:
                    if not bool(data.get("confirm_all")):
                        return 400, {"error": "confirm_all_required", "message": "Global trash operation requires explicit confirm_all=true"}, "application/json"
                    account_id_filter = str(data.get("account_id") or "").strip()
                    if account_id_filter:
                        rows = self.db.fetchall("SELECT entity_type, entity_id, platform, account_id FROM entity_platform_status WHERE status='skipped' AND account_id=?", (account_id_filter,))
                    else:
                        rows = self.db.fetchall("SELECT entity_type, entity_id, platform, account_id FROM entity_platform_status WHERE status='skipped'")
                elif isinstance(ids, list) and ids:
                    rows = []
                    for item in ids:
                        parts = str(item).split("|")
                        if len(parts) in (3, 4) and parts[0] in ("long_video", "short"):
                            try:
                                etype, eid, platform = parts[0], int(parts[1]), parts[2]
                                if len(parts) == 4:
                                    rows.append({"entity_type": etype, "entity_id": eid, "platform": platform, "account_id": parts[3]})
                                else:
                                    candidates = self.db.fetchall(
                                        "SELECT DISTINCT account_id FROM entity_platform_status WHERE entity_type=? AND entity_id=? AND platform=? AND status='skipped'",
                                        (etype, eid, platform),
                                    )
                                    accounts = [str(c.get("account_id") or "") for c in candidates]
                                    if len(accounts) == 1:
                                        rows.append({"entity_type": etype, "entity_id": eid, "platform": platform, "account_id": accounts[0]})
                            except (TypeError, ValueError):
                                continue
                else:
                    return 400, {"error": "ids or all=true required"}, "application/json"
                n = 0
                affected: set[tuple[str, int]] = set()
                for r in rows:
                    if route == "trash/restore":
                        n += self.db.execute(
                            "UPDATE entity_platform_status SET status='ready', "
                            "last_error=NULL, deleted_at=NULL, deleted_reason=NULL, cascade_from=NULL "
                            "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=? AND status='skipped'",
                            (r["entity_type"], r["entity_id"], r["platform"], r.get("account_id") or "")) or 0
                    else:
                        n += self.db.execute(
                            "DELETE FROM entity_platform_status "
                            "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=? AND status='skipped'",
                            (r["entity_type"], r["entity_id"], r["platform"], r.get("account_id") or "")) or 0
                        affected.add((str(r["entity_type"]), int(r["entity_id"])))
                gone = 0
                if route == "trash/purge":
                    # «Удалить навсегда» убирает сущность и из базы (файлы на диске не трогаем)
                    gone = self._purge_from_base(affected)
                self.db.log("system", None, "",
                            "trash_restore" if route == "trash/restore" else "trash_purge",
                            f"n={n}" + (f" entities={gone}" if route == "trash/purge" else ""))
                key = "restored" if route == "trash/restore" else "purged"
                return 200, {"ok": True, key: n, "entities": gone}, "application/json"
            if method == "POST" and route == "queue/remove":
                etype = str(data.get("entity_type") or "").strip()
                if etype not in ("long_video", "short"):
                    return 400, {"error": "entity_type required"}, "application/json"
                try:
                    eid = int(data.get("entity_id") or 0)
                except Exception:
                    eid = 0
                if not eid:
                    return 400, {"error": "entity_id required"}, "application/json"
                platform = str(data.get("platform") or "").strip()
                if platform not in ("", "youtube", "telegram"):
                    return 400, {"error": "platform must be youtube|telegram|empty"}, \
                        "application/json"
                # with_shorts: новое окно передаёт явно. Legacy: platform-scoped шорты не трогает;
                # «везде» без keep_shorts — фильм + шорты.
                if "with_shorts" in data:
                    with_shorts = bool(data.get("with_shorts"))
                elif platform:
                    with_shorts = False
                else:
                    with_shorts = not bool(data.get("keep_shorts"))
                also_youtube = bool(data.get("also_youtube"))
                account_id = str(data.get("account_id") or "").strip()
                if platform:
                    account_id, account_error = self._resolve_eps_account(data, etype, eid, platform)
                    if account_error:
                        return account_error
                plan = self._delete_plan(etype, eid, platform, also_youtube, with_shorts, account_id=account_id)
                if data.get("plan_only"):
                    return 200, {
                        "ok": True, "plan_only": True,
                        "blocked": plan["blocked"],
                        "count": len(plan["targets"]),
                        "targets": [
                            {"entity_type": et, "entity_id": ei, "platform": p, "account_id": aid, "status": st}
                            for et, ei, p, aid, st in plan["targets"]
                        ],
                    }, "application/json"
                if not plan["targets"]:
                    return 200, {"ok": True, "removed": 0, "blocked": [], "note": "already"}, \
                        "application/json"
                if plan["blocked"]:
                    return 200, {"ok": True, "removed": 0, "blocked": plan["blocked"]}, \
                        "application/json"
                reason = str(data.get("reason") or ("platform" if platform else "everywhere"))
                cascade_from = "youtube" if platform == "youtube" else ""
                self._kill_targets(plan["targets"])
                now = self._now_iso()
                removed = 0
                for et, ei, p, aid, _st in plan["targets"]:
                    # F3: инициатор (YouTube-строка) не помечается каскадом — только Telegram
                    cf = cascade_from if p == "telegram" else ""
                    # N1-b: повторное удаление не затирает метку «снято с платформы»
                    # (SQLite в SET видит старые значения строки)
                    self.db.execute(
                        "UPDATE entity_platform_status SET status='skipped', "
                        "deleted_at=COALESCE(deleted_at, ?), "
                        "deleted_reason=CASE WHEN deleted_reason='detached' "
                        "  THEN 'detached' ELSE ? END, "
                        "cascade_from=CASE WHEN deleted_reason='detached' "
                        "  THEN cascade_from ELSE ? END, "
                        "last_error=NULL "
                        "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                        (now, reason, cf, et, ei, p, aid))
                    self.db.log(et, ei, p, "queue_delete", reason)
                    removed += 1
                guard = self.comps.get("guard")
                if guard is not None and hasattr(guard, "invalidate"):
                    guard.invalidate()
                dependents: dict[str, int] = {}
                if etype == "long_video" and not with_shorts:
                    cnt = self.db.fetchone(
                        "SELECT COUNT(DISTINCT s.id) AS c FROM shorts s "
                        "JOIN entity_platform_status e ON e.entity_type='short' "
                        "  AND e.entity_id=s.id "
                        "WHERE s.parent_video_id=? AND e.status IN "
                        "  ('ready','scheduled','updating')", (eid,))
                    if cnt and cnt["c"]:
                        dependents["shorts"] = int(cnt["c"])
                logger.info("queue remove: %s#%s platform=%r -> trashed=%s blocked=%s",
                            etype, eid, platform, removed, plan["blocked"])
                return 200, {"ok": True, "removed": removed, "blocked": [],
                             "cascade": (["telegram"] if platform == "youtube" else []),
                             "dependents": dependents}, "application/json"
            if method == "POST" and route == "queue/detach":
                etype = str(data.get("entity_type") or "").strip()
                platform = str(data.get("platform") or "").strip()
                try:
                    eid = int(data.get("entity_id") or 0)
                except Exception:
                    eid = 0
                if etype not in ("long_video", "short") or not eid or not platform:
                    return 400, {"error": "entity_type/entity_id/platform required"}, \
                        "application/json"
                account_id, account_error = self._resolve_eps_account(data, etype, eid, platform)
                if account_error:
                    return account_error
                row = self.db.fetchone(
                    "SELECT status, release_url, "
                    "external_id AS external_id "
                    "FROM entity_platform_status "
                    "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                    (etype, eid, platform, account_id),
                )
                if not row:
                    return 404, {"error": "not found"}, "application/json"
                if (row["status"] or "") != "published":
                    return 400, {"error": "not_published"}, "application/json"
                # 1) detach: module.delete(external_id) first; fallback manual_sources+release_url
                if platform == "telegram":
                    pid = row.get("external_id")
                    logger.info("queue detach: telegram local clear id=%s", pid)
                else:
                    pid = row.get("external_id")
                    deleted_remote = False
                    reg = (self.comps or {}).get("module_registry")
                    mod = None
                    if reg is not None:
                        try:
                            if hasattr(reg, "has") and reg.has(platform):
                                mod = reg.create(platform)
                            elif hasattr(reg, "get"):
                                mod = reg.get(platform)
                        except Exception:
                            mod = None
                    if mod is not None and hasattr(mod, "delete") and pid:
                        try:
                            from orchestrator.platforms.base import NotSupported
                            # UX-04: refuse detach when platform cannot remote-delete
                            man = getattr(mod, "manifest", None)
                            caps = dict(getattr(man, "capabilities", {}) or {}) if man else {}
                            if man is not None and caps.get("delete") is False:
                                return 400, {"error": "detach_unavailable",
                                             "reason": "delete_not_supported"}, "application/json"
                            mod.delete(str(pid))
                            deleted_remote = True
                        except Exception as ex:
                            from orchestrator.platforms.base import NotSupported
                            if isinstance(ex, NotSupported) or type(ex).__name__ == "NotSupported":
                                return 400, {"error": "detach_unavailable",
                                             "reason": "delete_not_supported"}, "application/json"
                            logger.warning("queue detach: module delete failed %s %s",
                                           platform, pid, exc_info=True)
                            return 502, {"error": "detach_failed"}, "application/json"
                    if not deleted_remote:
                        sources = (self.comps or {}).get("manual_sources") or {}
                        eng = sources.get(platform)
                        vid = _youtube_id_from_url(str(row.get("release_url") or ""))
                        if eng is None or not hasattr(eng, "delete") or not vid:
                            return 400, {"error": "detach_unavailable"}, "application/json"
                        try:
                            eng.delete(vid)
                        except Exception:
                            logger.warning("queue detach: %s %s не снят", platform, vid, exc_info=True)
                            return 502, {"error": "detach_failed"}, "application/json"
                # 2) в корзину (восстановимо; файлы не трогаем)
                now = self._now_iso()
                self.db.execute(
                    "UPDATE entity_platform_status SET status='skipped', "
                    "external_id=NULL, "
                    "release_url=NULL, deleted_at=?, deleted_reason='detached', "
                    "cascade_from=NULL, last_error=NULL "
                    "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                    (now, etype, eid, platform, account_id))
                self.db.log(etype, eid, platform, "queue_detach", platform)
                return 200, {"ok": True, "detached": 1}, "application/json"
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
                if not roots:
                    return 403, {"error": "no browse roots configured"}, "application/json"
                metas = [self._root_meta(r) for r in roots]
                available = [Path(m["path"]) for m in metas if m["available"]]
                root = available[0] if available else roots[0]
                sel = query.get("root")
                if sel:
                    try:
                        rp = Path(sel).expanduser().resolve()
                    except Exception:
                        rp = None
                    if rp is not None and rp in roots:
                        root = rp
                target = query.get("path") or str(root)
                try:
                    base = Path(target).expanduser().resolve()
                except Exception:
                    base = root
                if not base.is_dir():
                    base = root
                for r in roots:
                    try:
                        if base == r or base.is_relative_to(r):
                            root = r
                            break
                    except (ValueError, TypeError):
                        continue
                if not self._path_under_roots(base, roots):
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

                if not roots:
                    return 403, {"error": "no browse roots configured"}, "application/json"

                target = query.get("path") or str(roots[0])
                try:
                    base = Path(target).expanduser().resolve()
                except Exception:
                    base = roots[0]
                if not (self._path_under_roots(base, roots) and base.exists()):
                    base = roots[0]
                if not self._path_under_roots(base, roots):
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
                parent = str(base.parent) if base != base.parent and self._path_under_roots(base.parent, roots) else None
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
                    # SSRF: pin по проверенному IP (anti-rebinding), ручной redirect ≤3,
                    # stream cap 25 MiB до чтения тела в память
                    try:
                        blob, ctype, final_url = _fetch_image_pinned(url)
                        ext = {"image/png": ".png", "image/jpeg": ".jpg",
                               "image/webp": ".webp"}.get(
                                   ctype, Path(urlsplit(final_url).path).suffix.lower())
                        if ext not in IMG_EXTS:
                            ext = ".jpg"
                    except ValueError as e:
                        msg = str(e)
                        if "too large" in msg:
                            return 413, {"error": "image too large (>25MB)"}, "application/json"
                        if "not allowed" in msg or "scheme" in msg or "no addresses" in msg:
                            return 400, {"error": f"url not allowed: {msg}"}, "application/json"
                        return 502, {"error": f"download failed: {msg}"}, "application/json"
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
                if not roots:
                    return 403, {"error": "no browse roots configured"}, "application/json"
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
                stats = {"long": 0, "shorts": 0, "standalone": 0, "standalone_found": 0,
                         "checked": 0, "unstable": 0, "no_final": 0}
                passes = max(2, int(getattr(self.cfg, "file_stability_cycles", 2)))
                jobs = self.comps.get("jobs")
                job = jobs.start("scan", "Сканирование папок", passes) if jobs is not None else None
                # эти значения — снимок состояния, а не «сколько сделано за проход»:
                # суммировать их по проходам нельзя (иначе «проверено папок» удваивается)
                snapshots = ("standalone_found", "checked", "unstable", "no_final")
                last: dict = {}
                for _ in range(passes):
                    if job is not None and job.cancelled:
                        break
                    st = watcher.scan()
                    last = st
                    for k in stats:
                        if k in snapshots:
                            continue
                        stats[k] += int(st.get(k, 0) or 0)
                if last:
                    for k in snapshots:
                        if k in last:
                            stats[k] = int(last.get(k, 0) or 0)
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
                missing = 0
                for r in longs + shorts_rows:
                    fp = str(r["folder_path"] or "").split("::")[0]
                    if _under(fp) and fp and not Path(fp).exists():
                        missing += 1
                skipped = self.db.fetchone(
                    "SELECT COUNT(*) AS c FROM entity_platform_status WHERE status='skipped'")
                last = self.db.fetchone(
                    "SELECT MAX(scheduled_for) AS m "
                    "FROM entity_platform_status "
                    "WHERE entity_type='long_video' "
                    "AND status IN ('scheduled','updating','ready')")
                return 200, {
                    "ok": True,
                    "stats": stats,
                    "totals": totals,
                    "skipped": (skipped or {}).get("c", 0),
                    "last_scheduled": (last or {}).get("m") if last else None,
                    "roots": roots,
                    "checked": int(stats.get("checked", 0) or 0),
                    "unstable": int(stats.get("unstable", 0) or 0),
                    "no_final": int(stats.get("no_final", 0) or 0),
                    "missing": missing,
                    "at": self._now_iso(),
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
                    account_rows = self.db.fetchall(
                        "SELECT DISTINCT account_id FROM entity_platform_status "
                        "WHERE platform=? AND account_id IS NOT NULL AND account_id!=''", (p,))
                    accounts = sorted({str(r.get("account_id") or "").strip() for r in account_rows or [] if str(r.get("account_id") or "").strip()})
                    if not accounts:
                        aid = str(getattr(pcfg, "account_id", "") or "").strip()
                        accounts = [aid]
                    for aid in accounts or [""]:
                        st = bl._state(p, aid) or {}
                        out.append({
                            "platform": p,
                            "account_id": aid,
                            "count": bl.has_backlog(p, aid),
                            "awaiting": bool(st.get("pending_backlog_question")),
                            "slot": st.get("pending_backlog_at"),
                            "tail_mode": bool(st.get("series_tail_mode")),
                        })
                return 200, {"platforms": out}, "application/json"
            if method == "POST" and route == "backlog/answer":
                bl = self.comps.get("backlog")
                p = (data.get("platform") or "").strip()
                ans = (data.get("answer") or "").strip()
                if not bl or p not in self.cfg.platforms or ans not in ("distribute", "wait", "skip"):
                    return 400, {"error": "platform/answer invalid"}, "application/json"
                account_id, account_error = self._resolve_backlog_account(p, data.get("account_id"))
                if account_error:
                    return account_error
                if ans == "distribute" and data.get("from_date"):
                    n = bl.scheduler.schedule_backlog(p, account_id=account_id, start_date=str(data["from_date"])) \
                        if bl.scheduler else 0
                    aid = account_id or ""
                    if aid:
                        bl.db.execute(
                            "UPDATE platform_queue_account_state SET pending_backlog_question=0, "
                            "pending_backlog_at=NULL, series_tail_mode=1 WHERE platform=? AND account_id=?", (p, aid))
                    else:
                        bl.db.execute(
                            "UPDATE platform_queue_state SET pending_backlog_question=0, "
                            "pending_backlog_at=NULL, series_tail_mode=1 WHERE platform=?", (p,))
                    bl.db.log("system", None, p, "backlog_distribute", f"account={aid} n={n}")
                else:
                    n = bl.resolve(p, ans, account_id=account_id)
                return 200, {"ok": True, "scheduled": n, "account_id": account_id}, "application/json"
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
            if route in ("test/schedule", "test/status", "test/cancel"):
                from .test_publish import (
                    TestPublishError,
                    cancel_test_post,
                    schedule_test_post,
                    test_recent,
                )
                tcfg = self.cfg.test_publish
                if method == "GET" and route == "test/status":
                    return 200, {
                        "enabled": bool(tcfg.enabled),
                        "default_delay_minutes": tcfg.default_delay_minutes,
                        "min_delay_minutes": tcfg.min_delay_minutes,
                        "max_delay_minutes": tcfg.max_delay_minutes,
                        "platforms": list(tcfg.platforms or []),
                        "title_prefix": tcfg.title_prefix,
                        "require_explicit_platforms": tcfg.require_explicit_platforms,
                        "allow_prod_channel": tcfg.allow_prod_channel,
                        "recent": test_recent(self.db, 10),
                    }, "application/json"
                if method != "POST":
                    return 404, {"error": "unknown route"}, "application/json"
                try:
                    if route == "test/schedule":
                        platforms = data.get("platforms") or []
                        platform = str(data.get("platform") or "").strip()
                        if not platform and isinstance(platforms, list) and platforms:
                            platform = str(platforms[0])
                        if not platform:
                            return 400, {"error": "platform required"}, "application/json"
                        try:
                            entity_id = int(data.get("entity_id") or 0)
                        except Exception:
                            entity_id = 0
                        if not entity_id:
                            return 400, {"error": "entity_id required"}, "application/json"
                        res = schedule_test_post(
                            self.comps, platform=platform,
                            entity_type=str(data.get("entity_type") or "short").strip(),
                            entity_id=entity_id,
                            delay_minutes=data.get("delay_minutes"),
                            scheduled_for=data.get("scheduled_for"),
                            dry_run=bool(data.get("dry_run")),
                        )
                        return 200, res, "application/json"
                    pid = str(
                        data.get("external_id") or ""
                    ).strip()
                    if not pid:
                        return 400, {"error": "external_id required"}, "application/json"
                    return 200, cancel_test_post(self.comps, external_id=pid), "application/json"
                except TestPublishError as e:
                    _m = self.comps.get("metrics")
                    if _m is not None and hasattr(_m, "incr"):
                        try:
                            _m.incr("test_rejected")
                        except Exception:
                            logger.debug("metrics test_rejected increment failed", exc_info=True)
                    return e.code, {"error": str(e)}, "application/json"
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

                if not _SCHEDULE_LOCK.acquire(blocking=False):
                    return 200, {"ok": True, "busy": True, "started": False}, "application/json"
                jobs = self.comps.get("jobs")
                job = jobs.start("schedule", "Планирование публикаций") if jobs is not None else None
                before = self._sched_snapshot()

                def _run():
                    try:
                        if sc is not None:
                            sc.job = job
                        roots = self._scan_roots()
                        sc.schedule_long_videos(start_date=sd, scope_roots=roots)
                        sc.schedule_standalone_shorts(self.comps.get("tail"),
                                                      start_date=sd, scope_roots=roots)
                        pubs = self.db.fetchall(
                            "SELECT entity_id, platform FROM entity_platform_status "
                            "WHERE entity_type='long_video' "
                            "AND status IN ('published','scheduled')"
                        )
                        for r in pubs:
                            sc.schedule_thematic_shorts(r["entity_id"], r["platform"],
                                                        scope_roots=roots)
                        sc.schedule_telegram_links()
                        sc.refresh_telegram_links()
                        sc.send_due_telegram_posts()
                        self._send_schedule_summary(before)
                        if job is not None:
                            job.finish("done", "Готово")
                    except Exception as e:
                        logger.exception("async schedule failed")
                        if job is not None:
                            job.finish("failed", str(e)[:200])
                    finally:
                        _SCHEDULE_LOCK.release()

                if data.get("async"):
                    import threading
                    threading.Thread(target=_run, daemon=True).start()
                    return 200, {"ok": True, "started": True, "start_date": sd,
                                 "shorts_start_date": shr}, "application/json"
                try:
                    roots = self._scan_roots()
                    n = sc.schedule_long_videos(start_date=sd, scope_roots=roots) if sc else 0
                    n2 = sc.schedule_standalone_shorts(
                        self.comps.get("tail"), start_date=sd, scope_roots=roots) if sc else 0
                    nt = 0
                    if sc:
                        pubs = self.db.fetchall(
                            "SELECT entity_id, platform FROM entity_platform_status "
                            "WHERE entity_type='long_video' "
                            "AND status IN ('published','scheduled')"
                        )
                        for r in pubs:
                            nt += sc.schedule_thematic_shorts(
                                r["entity_id"], r["platform"], scope_roots=roots)
                        sc.schedule_telegram_links()
                        sc.refresh_telegram_links()
                        sc.send_due_telegram_posts()
                    self._send_schedule_summary(before)
                finally:
                    _SCHEDULE_LOCK.release()
                return 200, {"ok": True, "long": n, "standalone": n2, "thematic": nt, "start_date": sd,
                             "shorts_start_date": shr}, "application/json"
            if method == "POST" and route == "pause_platform":
                p = (data.get("platform") or "").strip()
                if p not in self.cfg.platforms:
                    return 400, {"error": "unknown platform"}, "application/json"
                self.comps["safety"].pause_platform(p, "webapp")
                return 200, {"ok": True}, "application/json"
            return 404, {"error": "unknown route"}, "application/json"
        except Exception as e:
            from .platforms.base import NotSupported
            if isinstance(e, NotSupported):
                logger.info("webapp api not supported: %s", e)
                return 501, {
                    "error": "engine_not_implemented",
                    "detail": str(e),
                    "method": getattr(e, "method", ""),
                }, "application/json"
            logger.exception("webapp api")
            return 500, {"error": str(e)}, "application/json"

    def _metrics(self) -> dict:
        path = Path(self.db.path).parent / "metrics.json"
        data: dict = {"cycles": 0, "note": "no metrics yet"}
        if path.is_file():
            try:
                data = json.loads(path.read_text())
            except Exception:
                logger.warning("metrics.json unreadable: %s", path, exc_info=True)
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
            try:
                live["outbox_dead"] = int(self.db.fetchone("SELECT COUNT(*) AS c FROM outbox_events WHERE status='dead'").get("c") or 0)
                live["durable_jobs_dead"] = int(self.db.fetchone("SELECT COUNT(*) AS c FROM durable_jobs WHERE status='dead'").get("c") or 0)
            except Exception:
                logger.debug("ops dead-count metrics failed", exc_info=True)
        except Exception:
            logger.debug("live metrics failed", exc_info=True)
        data["live"] = live
        return sanitize_metrics(data)

    def _active_test_post_ids(self) -> set[str]:
        """external_id тестовых постов, которые ещё не отменены (test_scheduled без test_cancelled)."""
        scheduled: set[str] = set()
        for r in self.db.fetchall(
                "SELECT details FROM publish_log WHERE action='test_scheduled'"):
            pid = (r["details"] or "").strip().split(" ", 1)[0]
            if pid:
                scheduled.add(pid)
        cancelled: set[str] = set()
        for r in self.db.fetchall(
                "SELECT details FROM publish_log WHERE action='test_cancelled'"):
            pid = (r["details"] or "").strip()
            if pid:
                cancelled.add(pid)
        return scheduled - cancelled

    def _rate_limited(self, headers: dict[str, str], auth: dict[str, Any] | None = None) -> bool:
        try:
            limit = int(os.getenv("WEBAPP_RATE_LIMIT", "120"))
        except ValueError:
            limit = 120
        if limit <= 0:
            return False
        xff = headers.get("X-Forwarded-For") or headers.get("x-forwarded-for") or ""
        client_ip = xff.split(",")[0].strip() if xff else ""
        uid = ""
        if auth and not auth.get("access_key"):
            user_id = (auth.get("user") or {}).get("id")
            if user_id:
                uid = f"tg:{user_id}"
        key_hdr = ""
        if auth and auth.get("access_key"):
            key_hdr = headers.get("X-Webapp-Key") or headers.get("x-webapp-key") or ""
        ident = key_hdr or uid or client_ip or "local"
        now = time.time()
        cutoff = now - 60.0
        with self.db.transaction() as conn:
            row = conn.execute("SELECT window_started_at, request_count FROM webapp_rate_limits WHERE identity=?", (ident,)).fetchone()
            if row is None or float(row[0]) <= cutoff:
                conn.execute(
                    "INSERT INTO webapp_rate_limits(identity,window_started_at,request_count,updated_at) VALUES(?,?,1,?) "
                    "ON CONFLICT(identity) DO UPDATE SET window_started_at=excluded.window_started_at,request_count=1,updated_at=excluded.updated_at",
                    (ident, now, self._utc_now()),
                )
                return False
            if int(row[1] or 0) >= limit:
                conn.execute("UPDATE webapp_rate_limits SET updated_at=? WHERE identity=?", (self._utc_now(), ident))
                return True
            conn.execute("UPDATE webapp_rate_limits SET request_count=request_count+1,updated_at=? WHERE identity=?", (self._utc_now(), ident))
            return False

    @staticmethod
    def _utc_now() -> str:
        from datetime import datetime, UTC
        return datetime.now(UTC).isoformat()

    def _kind_label(self, entity_type: str) -> str:
        lang = getattr(self._tls, "lang", "ru")
        if entity_type == "long_video":
            return "Film" if lang == "en" else "Фильм"
        return "Short" if lang == "en" else "Шортс"

    def _scan_roots(self) -> list:
        """«Папки для сканирования»: планируем только то, что лежит в них."""
        watcher = self.comps.get("watcher")
        if watcher is None or not hasattr(watcher, "effective_roots"):
            return []
        try:
            return [str(r) for r in watcher.effective_roots()]
        except Exception:
            logger.exception("effective_roots failed")
            return []

    def _now_iso(self) -> str:
        clk = self.comps.get("clock")
        if clk is not None and hasattr(clk, "now"):
            return clk.now().isoformat()
        from datetime import UTC, datetime
        return datetime.now(UTC).isoformat()

    def _purge_from_base(self, affected: set[tuple[str, int]]) -> int:
        """Убирает из базы сущности, у которых не осталось строк очереди.

        Вызывается только «удалить навсегда» из корзины: пользователь ждёт, что удалённое
        уходит и из базы. Файлы на диске не трогаем — если папка в «Папках для сканирования»,
        следующий скан зарегистрирует её заново.
        """
        gone = 0
        for etype, eid in sorted(affected):
            left = self.db.fetchone(
                "SELECT COUNT(*) AS c FROM entity_platform_status "
                "WHERE entity_type=? AND entity_id=?", (etype, eid))
            if left and int(left.get("c") or 0) > 0:
                continue  # у сущности остались строки очереди (другая платформа) — не трогаем
            if etype == "long_video":
                for o in self.db.fetchall(
                    "SELECT id FROM shorts WHERE parent_video_id=? AND NOT EXISTS ("
                    "SELECT 1 FROM entity_platform_status eps WHERE eps.entity_type='short' "
                    "AND eps.entity_id=shorts.id)", (eid,)
                ):
                    gone += self.db.execute("DELETE FROM shorts WHERE id=?", (o["id"],)) or 0
                    self.db.log("short", int(o["id"]), "", "entity_purged", f"film={eid}")
                self.db.execute(
                    "UPDATE shorts SET parent_video_id=NULL WHERE parent_video_id=?", (eid,))
                gone += self.db.execute("DELETE FROM long_videos WHERE id=?", (eid,)) or 0
                self.db.execute(
                    "UPDATE platform_queue_state SET active_long_video_id=NULL "
                    "WHERE active_long_video_id=?", (eid,))
            else:
                gone += self.db.execute("DELETE FROM shorts WHERE id=?", (eid,)) or 0
            self.db.log(etype, eid, "", "entity_purged", "trash")
        return gone

    def _delete_plan(
        self,
        etype: str,
        eid: int,
        platform: str,
        also_youtube: bool = False,
        with_shorts: bool = False,
        account_id: str = "",
    ) -> dict[str, Any]:
        """Что будет удалено — без изменений в БД (для интерактивного окна).

        Направление решает каскад: с YouTube Telegram уходит автоматически;
        с Telegram YouTube — только по явному also_youtube.
        """
        entities: list[tuple[str, int]] = [(etype, eid)]
        if etype == "long_video" and with_shorts:
            for r in self.db.fetchall(
                    "SELECT id FROM shorts WHERE parent_video_id=?", (eid,)):
                entities.append(("short", int(r["id"])))
        targets: list[tuple[str, int, str, str, str]] = []
        seen: set[tuple[str, int, str, str]] = set()
        for et, ei in entities:
            rows = self.db.fetchall(
                "SELECT platform, account_id, status FROM entity_platform_status "
                "WHERE entity_type=? AND entity_id=?", (et, ei))
            by_plat = {(str(r["platform"]), str(r.get("account_id") or "")): (r["status"] or "") for r in rows}
            if platform == "youtube":
                wanted = ["youtube", "telegram"]
            elif platform == "telegram":
                wanted = ["telegram", "youtube"] if also_youtube else ["telegram"]
            else:
                wanted = sorted({p for p, _aid in by_plat})
            for p in wanted:
                all_candidates = [(aid, st) for (pp, aid), st in by_plat.items() if pp == p]
                if not all_candidates:
                    continue
                preferred = account_id if p == platform and account_id else str(getattr(self.cfg.platforms.get(p), "account_id", "") or "")
                if preferred:
                    preferred_candidates = [(aid, st) for aid, st in all_candidates if aid == preferred]
                    if preferred_candidates:
                        candidates = preferred_candidates
                    elif len(all_candidates) == 1:
                        candidates = all_candidates  # unambiguous legacy/single-account row
                    else:
                        candidates = []  # configured account absent + real ambiguity -> fail closed
                else:
                    candidates = all_candidates
                if len(candidates) > 1:
                    continue  # ambiguous account: fail closed rather than mutating multiple EPS rows
                for aid, st in candidates:
                    key = (et, ei, p, aid)
                    if key not in seen:
                        seen.add(key)
                        targets.append((et, ei, p, aid, st))
        blocked = [f"{et}#{ei}:{p}[{aid}]" for et, ei, p, aid, st in targets if st == "published"]
        return {"targets": targets, "blocked": blocked}

    def _kill_targets(self, targets: list[tuple[str, int, str, str, str]]) -> None:
        """Best-effort remote cancel via module publisher (platform client removed)."""
        pub = self.comps.get("publisher")
        if pub is None:
            sch = self.comps.get("scheduler")
            pub = getattr(sch, "publisher", None) if sch else None
        for et, ei, plat, aid, _st in targets:
            for r in self.db.fetchall(
                    "SELECT external_id FROM entity_platform_status "
                "WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?",
                (et, ei, plat, aid)):
                pid = r.get("external_id")
                if not pid:
                    continue
                try:
                    if pub is not None and hasattr(pub, "cancel_or_delete"):
                        pub.cancel_or_delete(plat, str(pid))
                except Exception:
                    logger.warning("queue remove: cancel %s failed", pid, exc_info=True)

    def _browse_roots(self) -> list[Path]:
        """Configured browse roots only. Empty → deny all (no fallback to /)."""
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
        return out

    def _path_under_roots(self, path: Path, roots: list[Path] | None = None) -> bool:
        """True if resolved path is equal to or under one of the allowed roots."""
        roots = roots if roots is not None else self._browse_roots()
        if not roots:
            return False
        try:
            rp = path.expanduser().resolve()
        except Exception:
            return False
        for r in roots:
            try:
                if rp == r or rp.is_relative_to(r):
                    return True
            except (ValueError, TypeError):
                continue
        return False

    def _key_from_request(self, qpath: str, query: dict[str, str]) -> str:
        k = query.get("key")
        if k:
            return k
        m = re.match(r"^/webapp/k/([^/]+)", qpath) if os.getenv("ORCH_LEGACY_PATH_KEY", "").strip().lower() in ("1", "true", "yes", "on") else None
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
            "WHERE external_id IS NOT NULL AND external_id != ''")
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
        except OSError as exc:
            logger.debug("path root stat failed: %s", type(exc).__name__)
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

    def _compose_index(self, key: str = "", nonce: str = "") -> bytes:
        """Self-contained page: inline CSS/JS so nothing can be cached separately.

        CSP (A2): и script, и style подписаны per-request nonce; 'unsafe-inline' не используется —
        инлайн-стилей в разметке нет (утилитарные классы), динамика ставится через CSSOM.
        """
        try:
            html = (WEBAPP_DIR / "index.html").read_text(encoding="utf-8")
            css = (WEBAPP_DIR / "styles.css").read_text(encoding="utf-8")
            js = (WEBAPP_DIR / "app.js").read_text(encoding="utf-8")
        except OSError:
            return (WEBAPP_DIR / "index.html").read_bytes()
        _n = f' nonce="{nonce}"' if nonce else ""
        html = re.sub(
            r'<link rel="stylesheet" href="styles\.css\?v=\d+"\s*/?>',
            lambda m: f"<style{_n}>\n{css}\n</style>",
            html,
        )
        html = re.sub(
            r'<script src="app\.js\?v=\d+"></script>',
            lambda m: (f'<script{_n}>window.__WEBAPP_KEY__=' + json.dumps(key) + ";</script>\n"
                       f"<script{_n}>\n{js}\n</script>"),
            html,
        )
        return html.encode("utf-8")

    def _file(self, name: str, ctype: str) -> tuple[int, bytes, str]:
        # P0 (8.4.5): имя приходит из URL. Без containment-проверки абсолютный путь
        # ("/webapp/b/<build>//etc/host.conf" → name "/etc/host.conf") выходил за WEBAPP_DIR,
        # потому что Path("/base") / "/etc/x" == "/etc/x" — это отдавало .env/БД/ключи без ключа.
        base = WEBAPP_DIR.resolve()
        path = (base / name.lstrip("/")).resolve()
        if base not in path.parents or not path.is_file():
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


    def _remote_inventory(self) -> dict:
        """F11 Remote Inventory UI data."""
        try:
            rows = self.db.fetchall(
                "SELECT id, platform, external_id, url, title, status, published_at, "
                "scheduled_for, privacy, first_seen_at, last_seen_at FROM remote_uploads "
                "ORDER BY last_seen_at DESC LIMIT 200"
            )
        except Exception:
            rows = []
        items = []
        for r in rows or []:
            match = None
            try:
                match = self.db.fetchone(
                    "SELECT decision, entity_type, entity_id, score FROM remote_upload_matches "
                    "WHERE remote_upload_id=? ORDER BY id DESC LIMIT 1",
                    (r["id"],),
                )
            except Exception:
                logger.debug("remote upload match lookup failed", exc_info=True)
            if match and match.get("decision") == "claimed":
                badge = "ORCHESTRATOR"
            elif match and match.get("decision") == "pending_review":
                badge = "PARTIAL"
            elif r.get("visibility") in ("private", "not_visible", "hidden"):
                badge = "NOT VISIBLE VIA API"
            elif r.get("origin") == "manual" or r.get("source") == "manual":
                badge = "MANUAL"
            else:
                badge = "PLATFORM"
            items.append({
                "id": r["id"],
                "platform": r["platform"],
                "external_id": r["external_id"],
                "url": r.get("url"),
                "title": r.get("title"),
                "status": r.get("status"),
                "badge": badge,
                "match": dict(match) if match else None,
            })
        scans = []
        try:
            scans = self.db.fetchall(
                "SELECT id, platform, status, partial, error, started_at, finished_at, items_seen "
                "FROM remote_scans ORDER BY id DESC LIMIT 20"
            )
        except Exception:
            logger.warning("remote scan inventory lookup failed", exc_info=True)
        return {"items": items, "scans": [dict(s) for s in (scans or [])]}

    def _inventory_scan(self) -> dict:
        svc = self.comps.get("remote_scan") or self.comps.get("manual")
        if svc is None:
            return {"ok": False, "error": "scan service unavailable"}
        try:
            if hasattr(svc, "scan_all"):
                n = svc.scan_all()
            elif hasattr(svc, "run"):
                n = svc.run()
            else:
                n = 0
            return {"ok": True, "scanned": n}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _inventory_action(self, action: str, data: dict) -> dict:
        rid = data.get("id") or data.get("remote_upload_id")
        if not rid:
            return {"ok": False, "error": "id required"}
        decision = {"claim": "claimed", "link": "linked", "ignore": "ignored"}.get(action, action)
        try:
            self.db.execute(
                "INSERT INTO remote_upload_matches "
                "(remote_upload_id, entity_type, entity_id, score, decision, decided_at, decided_by) "
                "VALUES (?, ?, ?, 0, ?, datetime('now'), 'webapp')",
                (rid, data.get("entity_type"), data.get("entity_id"), decision),
            )
            return {"ok": True, "decision": decision}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _ops_status(self) -> dict:
        """F12 Ops: auth_status, YT quota buckets, pause state."""
        platforms = {}
        cfg = self.comps.get("cfg")
        for name in (cfg.platforms.keys() if cfg else []):
            paused = False
            try:
                row = self.db.fetchone(
                    "SELECT paused_until, pause_reason FROM platform_safety_state WHERE platform=?",
                    (name,),
                )
                if row and row.get("paused_until"):
                    paused = True
            except Exception:
                logger.debug("ops pause state lookup failed for %s", name, exc_info=True)
            auth = {"ok": None, "details": "n/a"}
            try:
                from .platforms import default_registry, resolve_engine
                eng = str(cfg.engine_for(name) or "")
                resolved = resolve_engine(eng)
                if resolved.kind == "module" and resolved.module_id:
                    reg = default_registry()
                    if reg.has(resolved.module_id):
                        mod = reg.create(resolved.module_id, cfg=cfg, dry_run=True, http=None)
                        st = mod.auth_status()
                        auth = {"ok": st.ok, "account": getattr(st, "account", ""), "details": getattr(st, "details", "")}
            except Exception as e:
                auth = {"ok": False, "details": str(e)}
            platforms[name] = {"paused": paused, "auth": auth}
        # YT two-bucket display (config/safety — not cost_upload 1600)
        quota = {
            "upload_bucket": 100,
            "general_bucket": 10000,
            "note": "two-bucket YT accounting; posts_per_day is separate safety cap",
        }
        daily = {}
        try:
            for name, pc in (cfg.platforms.items() if cfg else []):
                daily[name] = int(getattr(pc, "daily_limit", 0) or 0)
        except Exception:
            logger.debug("ops daily limits calculation failed", exc_info=True)
        quota["daily_limits"] = daily
        accounts = []
        try:
            accounts = self.db.fetchall(
                "SELECT id, platform, name, username, enabled, auth_provider FROM platform_accounts LIMIT 50"
            )
        except Exception:
            logger.warning("ops platform_accounts lookup failed", exc_info=True)
        return {
            "platforms": platforms,
            "quota_youtube": quota,
            "accounts": [dict(a) for a in (accounts or [])],
        }



    def _oauth_token_saver(self, provider: str, result: Any, account_hint: str = "") -> None:
        """Persist account-scoped OAuth token through the canonical lifecycle store."""
        from .token_lifecycle import TokenLifecycleStore
        import time as _time
        prov = (provider or "").strip().lower()
        hint = str(account_hint or "").strip()
        if not hint:
            raise ValueError("OAuth account_id is required for account-scoped token persistence")
        store = TokenLifecycleStore(os.getenv("TOKENS_DIR", "tokens"), db=self.db)
        store.rotate(
            prov, hint,
            access_token=str(getattr(result, "access_token", "") or ""),
            refresh_token=str(getattr(result, "refresh_token", "") or ""),
            expires_at=_time.time() + float(getattr(result, "expires_in", 0) or 3600),
            metadata={"token_type": str(getattr(result, "token_type", "Bearer") or "Bearer"), "scope": str(getattr(result, "scope", "") or "")},
        )

    def _oauth_start(self, provider: str, account_hint: str = "") -> dict:
        from .oauth.web import start
        from .oauth.manager import OAuthManager
        result = start(self.db, provider, token_saver=self._oauth_token_saver, account_hint=account_hint)
        return result

    def _oauth_callback(self, provider: str, params: dict) -> dict:
        from .oauth.web import callback
        return callback(self.db, provider, params, token_saver=self._oauth_token_saver)


    def _calendar(self) -> dict:
        """Calendar: statuses scheduled|scheduled_platform|uploaded_inbox|
        waiting_manual_publish|publishing|published|failed|claimed_skipped (+ legacy).
        Fields: external_id, external_sub_id, external_url, scheduled_for, source, status.
        """
        entries: list[dict] = []
        seen: set[str] = set()
        rows = self.db.fetchall(
            """
            SELECT eps.entity_type, eps.entity_id, eps.platform, eps.status,
                   eps.scheduled_for AS scheduled_for,
                   eps.external_id AS external_id,
                   eps.external_sub_id AS external_sub_id,
                   COALESCE(eps.external_url, eps.release_url) AS external_url,
                   COALESCE(eps.source, '') AS source,
                   eps.release_url
            FROM entity_platform_status eps
            WHERE eps.status IN (
                'scheduled', 'scheduled_platform', 'uploaded_inbox',
                'waiting_manual_publish', 'publishing', 'published',
                'failed', 'error', 'claimed_skipped', 'updating', 'ready'
            )
              AND COALESCE(eps.scheduled_for, eps.published_at) IS NOT NULL
            ORDER BY COALESCE(eps.scheduled_for, eps.published_at)
            """
        )
        lv, sh = self._project_lookup()
        for r in rows:
            sched = r.get("scheduled_for") or ""
            eid_key = f'{r["platform"]}:{r["entity_type"]}:{r["entity_id"]}:{r.get("external_id") or ""}'
            if eid_key in seen:
                continue
            seen.add(eid_key)
            date_l, time_l = self._to_local(str(sched) if sched else "")
            kind = "long" if r["entity_type"] == "long_video" else "short"
            # title from entity tables best-effort
            title = ""
            try:
                if r["entity_type"] == "long_video":
                    er = self.db.fetchone(
                        "SELECT COALESCE(title_text, title, folder_path) AS t FROM long_videos WHERE id=?",
                        (r["entity_id"],),
                    )
                else:
                    er = self.db.fetchone(
                        "SELECT COALESCE(title_text, folder_path) AS t FROM shorts WHERE id=?",
                        (r["entity_id"],),
                    )
                title = (er["t"] if er else "") or ""
            except Exception:
                title = ""
            st = (r.get("status") or "").strip()
            # normalize error -> failed for API contract
            if st == "error":
                st = "failed"
            src_badge = (r.get("source") or "orchestrator").upper()
            if src_badge in ("MODULE", "ORCHESTRATOR", ""):
                src_badge = "ORCHESTRATOR"
            elif src_badge in ("MANUAL", "LEGACY"):
                src_badge = "MANUAL"
            else:
                src_badge = "PLATFORM"
            entries.append({
                "scheduled_for": sched,
                "external_id": r.get("external_id") or "",
                "external_sub_id": r.get("external_sub_id") or "",
                "external_url": r.get("external_url") or r.get("release_url") or "",
                "source": (r.get("source") or "orchestrator"),
                "source_badge": src_badge,
                "date": date_l,
                "time": time_l,
                "platform": r["platform"],
                "title": f"{kind}: {title}"[:140],
                "status": st,
                "entity_type": r["entity_type"],
                "entity_id": r["entity_id"],
                "project": self._project_of(r["entity_type"], r["entity_id"], lv, sh),
            })
        from collections import defaultdict
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

    def _project_lookup(self) -> tuple[dict, dict]:
        """Карты id->папка, чтобы определить проект строки без запроса на каждую строку."""
        lv = {r["id"]: r.get("folder_path")
              for r in self.db.fetchall("SELECT id, folder_path FROM long_videos")}
        sh = {r["id"]: (r.get("folder_path"), r.get("parent_video_id"))
              for r in self.db.fetchall("SELECT id, folder_path, parent_video_id FROM shorts")}
        return lv, sh

    def _project_of(self, etype: str, eid: int, lv: dict, sh: dict) -> str:
        if etype == "long_video":
            return self.cfg.resolve_project(series_id=eid, folder=lv.get(eid))
        folder, parent = sh.get(eid, (None, None))
        return self.cfg.resolve_project(
            series_id=parent, series_folder=(lv.get(parent) if parent else None), folder=folder)

    def _projects(self) -> dict:
        """Проекты (ниши): названия, платформы и счётчики по статусам."""
        lv, sh = self._project_lookup()
        counts: dict[str, dict[str, int]] = {}
        rows = self.db.fetchall(
            "SELECT entity_type, entity_id, status FROM entity_platform_status "
            "WHERE status IN ('ready','scheduled','updating','publishing','published',"
            "'failed','error')")
        for r in rows:
            bucket = counts.setdefault(self._project_of(r["entity_type"], r["entity_id"], lv, sh), {})
            bucket[r["status"]] = bucket.get(r["status"], 0) + 1
        items = []
        for pid in (self.cfg.projects or {}):
            items.append({
                "id": pid,
                "title": self.cfg.project_title(pid),
                "platforms": self.cfg.platforms_of_project(pid),
                "counts": counts.get(pid, {}),
            })
        if counts.get(""):
            items.append({"id": "", "title": "Без проекта",
                          "platforms": self.cfg.platforms_of_project(""),
                          "counts": counts.get("", {})})
        return {"items": items, "default": self.cfg.default_project or ""}

    def _resolve_eps_account(self, data: dict, entity_type: str, entity_id: int, platform: str):
        """Resolve an EPS account deterministically; fail closed on ambiguity."""
        requested = str(data.get("account_id") or "").strip()
        rows = self.db.fetchall(
            "SELECT DISTINCT account_id FROM entity_platform_status "
            "WHERE entity_type=? AND entity_id=? AND platform=?",
            (entity_type, entity_id, platform),
        )
        accounts = [str(r.get("account_id") or "") for r in rows]
        if requested:
            if requested not in accounts:
                return None, (404, {"error": "account_not_found", "account_id": requested}, "application/json")
            return requested, None
        if len(accounts) == 1:
            return accounts[0], None
        if len(accounts) > 1:
            return None, (409, {"error": "account_id_required", "accounts": accounts}, "application/json")
        return "", None

    def _resolve_backlog_account(self, platform: str, requested: str = ""):
        requested = str(requested or "").strip()
        rows = self.db.fetchall(
            "SELECT DISTINCT account_id FROM entity_platform_status "
            "WHERE platform=? AND account_id IS NOT NULL AND account_id!=''",
            (platform,),
        )
        accounts = sorted({str(r.get("account_id") or "").strip() for r in rows or [] if str(r.get("account_id") or "").strip()})
        if requested:
            if accounts and requested not in accounts:
                return None, (404, {"error": "account_not_found", "account_id": requested}, "application/json")
            return requested, None
        if len(accounts) > 1:
            return None, (409, {"error": "account_id_required", "accounts": accounts}, "application/json")
        if len(accounts) == 1:
            return accounts[0], None
        cfg = self.cfg.platforms.get(platform)
        return str(getattr(cfg, "account_id", "") or "").strip(), None

    def _queue(self) -> dict:
        tg_cfg = self.cfg.platforms.get("telegram")
        tg_account_id = str(getattr(tg_cfg, "account_id", "") or "") if tg_cfg else ""
        rows = self.db.fetchall(
            """
            SELECT eps.entity_type, eps.entity_id, eps.platform, eps.account_id, eps.status,
                   eps.last_error,
                   COALESCE(eps.content_kind, '') AS content_kind,
                   eps.scheduled_for AS scheduled_for,
                   COALESCE(lv.title_text, lv.title, sh.title_text) AS title,
                   COALESCE(lv.description_text, sh.description_text) AS description_text,
                   COALESCE(lv.hashtags_text, sh.hashtags_text) AS hashtags_text,
                   COALESCE(lv.cover_path, sh.cover_path) AS cover_path,
                   COALESCE(lv.placement, sh.placement, '') AS placement,
                   COALESCE(lv.vertical_path, lv.wide_path, sh.video_path) AS video_path,
                   EXISTS (SELECT 1 FROM entity_platform_status t
                           WHERE t.entity_type = eps.entity_type
                             AND t.entity_id = eps.entity_id
                             AND t.platform = 'telegram'
                             AND (t.account_id = ?
                                  OR (eps.account_id = '' AND t.account_id = ''))) AS has_tg
            FROM entity_platform_status eps
            LEFT JOIN long_videos lv
                   ON eps.entity_type='long_video' AND lv.id = eps.entity_id
            LEFT JOIN shorts sh
                   ON eps.entity_type='short' AND sh.id = eps.entity_id
            WHERE eps.status IN ('ready', 'scheduled', 'updating', 'publishing')
            ORDER BY eps.scheduled_for LIMIT 300
            """,
            (tg_account_id,),
        )
        lv, sh = self._project_lookup()
        items = []
        for r in rows:
            kind = self._kind_label(r["entity_type"])
            date_l, time_l = self._to_local(r["scheduled_for"] or "")
            title = (r.get("title") or "").strip() or f"{kind} #{r['entity_id']}"
            items.append({
                "entity_type": r["entity_type"],
                "entity_id": r["entity_id"],
                "platform": r["platform"],
                "account_id": r.get("account_id") or "",
                "status": r["status"],
                "scheduled_for": r["scheduled_for"],
                "date": date_l,
                "time": time_l,
                "title": f"{kind}: {title}"[:140],
                "title_text": (r.get("title") or "").strip(),
                "description_text": r.get("description_text") or "",
                "hashtags_text": r.get("hashtags_text") or "",
                "cover_path": r.get("cover_path") or "",
                "content_kind": r.get("content_kind") or "video_native",
                "placement": r.get("placement") or "",
                "waiting": (r.get("last_error") or "") == "waiting_for_youtube",
                "covers": self._cover_candidates(r.get("video_path") or ""),
                "video_path": r.get("video_path") or "",
                "has_tg": bool(r.get("has_tg")),
                "project": self._project_of(r["entity_type"], r["entity_id"], lv, sh),
            })
        return {"items": items}


    def _platform_capabilities(self) -> dict:
        """UX-02: capability matrix for UI (hide delete/schedule if unsupported)."""
        items: list[dict] = []
        plats_cfg = getattr(self.cfg, "platforms", {}) or {}
        if not isinstance(plats_cfg, dict):
            try:
                plats_cfg = dict(plats_cfg)
            except Exception:
                plats_cfg = {}
        mods = self.comps.get("modules") or {}
        if not isinstance(mods, dict):
            mods = {}
        names = sorted(set(list(plats_cfg.keys()) + list(mods.keys())))
        for name in names:
            entry: dict = {
                "platform": name,
                "enabled": False,
                "capabilities": {
                    "publish": False,
                    "schedule_publish": False,
                    "delete": False,
                    "update_metadata": False,
                    "video": False,
                    "image": False,
                    "text": False,
                    "content_kinds": [],
                },
                "module_version": "",
                "content_kind_default": "",
            }
            pc = plats_cfg.get(name)
            if pc is not None:
                entry["enabled"] = bool(getattr(pc, "enabled", False) if not isinstance(pc, dict) else pc.get("enabled", False))
                ck = getattr(pc, "content_kind_default", "") if not isinstance(pc, dict) else pc.get("content_kind_default", "")
                entry["content_kind_default"] = str(ck or "")
            mod = mods.get(name)
            man = getattr(mod, "manifest", None) if mod is not None else None
            if man is not None:
                entry["module_version"] = str(getattr(man, "module_version", "") or "")
                caps = dict(getattr(man, "capabilities", {}) or {})
                entry["capabilities"] = {
                    "publish": bool(caps.get("publish")),
                    "schedule_publish": bool(caps.get("schedule_publish")),
                    "delete": bool(caps.get("delete")),
                    "update_metadata": bool(caps.get("update_metadata")),
                    "video": bool(caps.get("video")),
                    "image": bool(caps.get("image")),
                    "text": bool(caps.get("text")),
                    "content_kinds": list(caps.get("content_kinds") or []),
                }
            items.append(entry)
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
        lv, sh = self._project_lookup()
        items = [dict(r) | {"project": self._project_of(r["entity_type"], r["entity_id"], lv, sh)}
                 for r in rows]
        return {"items": items}
