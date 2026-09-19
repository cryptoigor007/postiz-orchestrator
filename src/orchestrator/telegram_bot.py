from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from .clock import Clock
from .config import AppConfig
from .db import Database

logger = logging.getLogger(__name__)


def split_text(text: str, limit: int = 3800) -> list[str]:
    """Разбивает длинный текст по строкам на части (лимит Telegram 4096)."""
    text = text or ""
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    cur = ""
    for line in text.splitlines():
        while len(line) > limit:
            if cur:
                parts.append(cur)
                cur = ""
            parts.append(line[:limit])
            line = line[limit:]
        if len(cur) + len(line) + 1 > limit:
            parts.append(cur)
            cur = line
        else:
            cur = (cur + "\n" + line) if cur else line
    if cur:
        parts.append(cur)
    return parts


class TelegramNotifier:
    """Abstract notifier + command router. Real transport plugged later."""

    def __init__(self, cfg: AppConfig, db: Database, clock: Clock):
        self.cfg = cfg
        self.db = db
        self.clock = clock
        self._owner_chat_id: int | None = None
        self._handlers: dict[str, Callable] = {}
        self._pending_dialogs: dict[int, dict[str, Any]] = {}
        self.transport = None

    def is_allowed(self, chat_id: int) -> bool:
        allowed = self.cfg.telegram.allowed_chat_ids
        if not allowed:
            if self._owner_chat_id is None:
                self._owner_chat_id = chat_id
                return True
            return chat_id == self._owner_chat_id
        return chat_id in allowed

    def send(self, chat_id: int, text: str, reply_markup: dict | None = None) -> None:
        if not self.is_allowed(chat_id):
            logger.warning("Blocked message to unauthorized chat %s", chat_id)
            return
        chunks = split_text(text, 3800)
        for i, chunk in enumerate(chunks):
            markup = reply_markup if i == len(chunks) - 1 else None
            if self.transport:
                self.transport.send_message(chat_id, chunk, markup)
            else:
                logger.info("[TG -> %s] %s", chat_id, chunk[:200])

    def broadcast(self, text: str) -> None:
        targets = self.cfg.telegram.allowed_chat_ids or (
            [self._owner_chat_id] if self._owner_chat_id else []
        )
        for cid in targets:
            if cid:
                self.send(cid, text)

    def register(self, command: str, handler: Callable) -> None:
        self._handlers[command.lstrip("/")] = handler

    def handle_update(self, chat_id: int, text: str) -> str | None:
        if not self.is_allowed(chat_id):
            return "Access denied"

        text = (text or "").strip()
        if chat_id in self._pending_dialogs:
            return self._resolve_dialog(chat_id, text)

        if not text.startswith("/"):
            return "✅ Принято. Список команд: /help"
        parts = text.split(maxsplit=1)
        cmd = parts[0].lstrip("/").split("@")[0]
        arg = parts[1] if len(parts) > 1 else ""
        handler = self._handlers.get(cmd)
        if not handler:
            return f"Неизвестная команда: /{cmd}. Список: /help"
        return handler(chat_id, arg)

    def ask_series_end(self, platform: str) -> None:
        self.broadcast(
            f"Series soft-end on {platform}. Enter tail mode? Reply: yes / no"
        )

    def ask_missing_url(self, entity_id: int, platform: str, chat_id: int | None = None) -> None:
        dialog = {
            "type": "missing_url",
            "entity_id": entity_id,
            "platform": platform,
            "expires": self.clock.now().timestamp()
            + self.cfg.link_update.missing_url_dialog_ttl_hours * 3600,
        }
        targets = [chat_id] if chat_id else (
            self.cfg.telegram.allowed_chat_ids
            or ([self._owner_chat_id] if self._owner_chat_id else [])
        )
        for cid in targets:
            if cid:
                self._pending_dialogs[cid] = dialog
                self.send(
                    cid,
                    f"No release_url for long_video #{entity_id} on {platform}.\n"
                    f"Send URL or 'skip' (default: {self.cfg.link_update.missing_url_default_action})",
                )

    def _resolve_dialog(self, chat_id: int, text: str) -> str:
        dlg = self._pending_dialogs.get(chat_id)
        if not dlg:
            return "No pending dialog"
        if self.clock.now().timestamp() > dlg["expires"]:
            del self._pending_dialogs[chat_id]
            return "Dialog expired"
        if dlg["type"] == "missing_url":
            return self._handle_missing_url(chat_id, dlg, text)
        if dlg["type"] == "series_end":
            return self._handle_series_end(chat_id, dlg, text)
        return "Unknown dialog"

    def _handle_missing_url(self, chat_id: int, dlg: dict, text: str) -> str:
        del self._pending_dialogs[chat_id]
        platform = dlg["platform"]
        eid = dlg["entity_id"]
        if text.lower() in ("skip", "без ссылки", "no"):
            self.db.execute(
                "UPDATE entity_platform_status SET release_url=NULL, link_updated_at=? "
                "WHERE entity_type='long_video' AND entity_id=? AND platform=?",
                (self.clock.now().isoformat(), eid, platform),
            )
            return f"Will post without link (video #{eid} / {platform})"
        if text.startswith("http://") or text.startswith("https://"):
            self.db.execute(
                "UPDATE entity_platform_status SET release_url=?, link_updated_at=? "
                "WHERE entity_type='long_video' AND entity_id=? AND platform=?",
                (text.strip(), self.clock.now().isoformat(), eid, platform),
            )
            return f"URL saved for video #{eid} / {platform}"
        return "Send valid http(s) URL or 'skip'"

    def _handle_series_end(self, chat_id: int, dlg: dict, text: str) -> str:
        del self._pending_dialogs[chat_id]
        platform = dlg["platform"]
        if text.lower() in ("yes", "да", "y"):
            self.db.execute(
                "UPDATE platform_queue_state SET series_tail_mode=1, updated_at=? WHERE platform=?",
                (self.clock.now().isoformat(), platform),
            )
            return f"Tail mode ON for {platform}"
        self.db.execute(
            "UPDATE platform_queue_state SET series_tail_mode=0, pending_series_end_question=0, "
            "updated_at=? WHERE platform=?",
            (self.clock.now().isoformat(), platform),
        )
        return f"Tail mode OFF for {platform}"


def setup_commands(bot: TelegramNotifier, components: dict) -> None:
    db: Database = components["db"]
    cfg: AppConfig = components["cfg"]
    safety = components["safety"]
    scheduler = components["scheduler"]
    clock: Clock = components["clock"]

    def cmd_status(chat_id: int, arg: str) -> str:
        rows = db.fetchall(
            "SELECT platform, status, COUNT(*) AS cnt FROM entity_platform_status GROUP BY platform, status"
        )
        if not rows:
            return "No entities"
        lines = [f"{r['platform']} {r['status']}: {r['cnt']}" for r in rows]
        return "Status:\n" + "\n".join(lines)

    def cmd_pause(chat_id: int, arg: str) -> str:
        for p in cfg.platforms:
            safety.pause_platform(p, "manual")
        return "All platforms paused"

    def cmd_resume(chat_id: int, arg: str) -> str:
        for p in cfg.platforms:
            safety.resume_platform(p)
        return "All platforms resumed"

    def cmd_resume_platform(chat_id: int, arg: str) -> str:
        p = arg.strip().lower()
        if p not in cfg.platforms:
            return f"Unknown platform: {p}"
        safety.resume_platform(p)
        return f"Resumed {p}"

    def _fmt_local(iso: str) -> str:
        from datetime import UTC, datetime
        from zoneinfo import ZoneInfo
        try:
            dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt.astimezone(ZoneInfo(cfg.timezone)).strftime("%d.%m %H:%M")
        except Exception:
            return str(iso or "")[:16]

    def _upcoming_rows(limit: int = 30) -> list[dict]:
        return db.fetchall(
            """
            SELECT eps.entity_type, eps.entity_id, eps.platform, eps.status,
                   eps.postiz_scheduled_for,
                   COALESCE(lv.title_text, lv.title, sh.title_text) AS title
            FROM entity_platform_status eps
            LEFT JOIN long_videos lv
                   ON eps.entity_type='long_video' AND lv.id = eps.entity_id
            LEFT JOIN shorts sh
                   ON eps.entity_type='short' AND sh.id = eps.entity_id
            WHERE eps.status IN ('ready', 'scheduled') AND eps.postiz_scheduled_for IS NOT NULL
            ORDER BY eps.postiz_scheduled_for LIMIT ?
            """,
            (limit,),
        )

    def _item_lines(limit: int = 30, max_groups: int = 14) -> list[str]:
        """Строки «когда · Фильм/Шортс: название · платформы» (одна на видео-время)."""
        rows = _upcoming_rows(limit)
        grouped: dict[tuple, dict] = {}
        for r in rows:
            when = _fmt_local(r["postiz_scheduled_for"])
            key = (r["entity_type"], r["entity_id"], when)
            kind = "Фильм" if r["entity_type"] == "long_video" else "Шортс"
            title = (r.get("title") or "").strip() or f"#{r['entity_id']}"
            g = grouped.setdefault(key, {"when": when, "label": f"{kind}: {title}", "plats": []})
            g["plats"].append(r["platform"])
        out = []
        for g in list(grouped.values())[:max_groups]:
            plats = ", ".join(dict.fromkeys(g["plats"]))
            out.append(f"{g['when']} · {g['label']} · {plats}")
        return out

    def cmd_queue(chat_id: int, arg: str) -> str:
        lines = _item_lines(limit=30)
        if not lines:
            return "Очередь пуста."
        return "Очередь публикаций:\n" + "\n".join(lines)

    def cmd_failed(chat_id: int, arg: str) -> str:
        rows = db.fetchall(
            """
            SELECT eps.entity_type, eps.entity_id, eps.platform, eps.last_error,
                   COALESCE(lv.title_text, lv.title, sh.title_text) AS title
            FROM entity_platform_status eps
            LEFT JOIN long_videos lv
                   ON eps.entity_type='long_video' AND lv.id = eps.entity_id
            LEFT JOIN shorts sh
                   ON eps.entity_type='short' AND sh.id = eps.entity_id
            WHERE eps.status IN ('failed','error') LIMIT 20
            """
        )
        if not rows:
            return "Ошибок нет."
        out = ["Ошибки публикаций:"]
        for r in rows:
            kind = "Фильм" if r["entity_type"] == "long_video" else "Шортс"
            title = (r.get("title") or "").strip() or f"#{r['entity_id']}"
            out.append(f"{kind}: {title} · {r['platform']} · {r['last_error'] or '—'}")
        return "\n".join(out)

    def cmd_tail(chat_id: int, arg: str) -> str:
        rows = db.fetchall(
            "SELECT platform, series_tail_mode FROM platform_queue_state"
        )
        return "\n".join(
            f"{r['platform']}: tail={'ON' if r['series_tail_mode'] else 'OFF'}" for r in rows
        )

    def cmd_platforms(chat_id: int, arg: str) -> str:
        lines = []
        for name, p in cfg.platforms.items():
            st = db.fetchone(
                "SELECT is_paused, pause_reason FROM platform_safety_state WHERE platform=?",
                (name,),
            )
            paused = "PAUSED" if st and st["is_paused"] else "ok"
            lines.append(f"{name}: enabled={p.enabled} limit={p.daily_limit} {paused}")
        return "\n".join(lines)

    def cmd_distribute(chat_id: int, arg: str) -> str:
        n = scheduler.schedule_long_videos()
        return f"Distributed long videos: {n}"

    def cmd_calendar(chat_id: int, arg: str) -> str:
        lines = _item_lines(limit=60, max_groups=20)
        if not lines:
            return "Календарь пуст."
        return "Ближайшие публикации:\n" + "\n".join(lines)

    def cmd_series_end(chat_id: int, arg: str) -> str:
        p = arg.strip().lower() or "youtube"
        bot._pending_dialogs[chat_id] = {
            "type": "series_end",
            "platform": p,
            "expires": clock.now().timestamp() + 86400,
        }
        return f"Enter tail mode for {p}? yes / no"

    def cmd_force_link_update(chat_id: int, arg: str) -> str:
        parts = arg.split()
        if len(parts) < 3:
            return "Usage: /force_link_update <entity_id> <platform> <url>"
        eid, platform, url = int(parts[0]), parts[1], parts[2]
        link_upd = components.get("link_upd")
        if not link_upd:
            return "LinkUpdater not available"
        ok = link_upd.force_update(eid, platform, url)
        return "OK" if ok else "Failed"

    def cmd_reload_config(chat_id: int, arg: str) -> str:
        from .reload import reload_config
        path = arg.strip() or "config.yaml"
        new_cfg, msg = reload_config(path, cfg)
        if new_cfg is None:
            return f"Reload failed (kept old): {msg}"
        components["cfg"] = new_cfg
        return "Config reloaded"

    def cmd_next_video(chat_id: int, arg: str) -> str:
        platform = arg.strip() or None
        sql = (
            "SELECT entity_id, platform, postiz_scheduled_for FROM entity_platform_status "
            "WHERE entity_type='long_video' AND status='scheduled' "
        )
        params: tuple = ()
        if platform:
            sql += "AND platform=? "
            params = (platform,)
        sql += "ORDER BY postiz_scheduled_for LIMIT 5"
        rows = db.fetchall(sql, params)
        if not rows:
            return "No scheduled long videos"
        return "\n".join(
            f"#{r['entity_id']} {r['platform']} {r['postiz_scheduled_for']}" for r in rows
        )

    def cmd_next_short(chat_id: int, arg: str) -> str:
        platform = arg.strip() or None
        sql = (
            "SELECT entity_id, platform, postiz_scheduled_for FROM entity_platform_status "
            "WHERE entity_type='short' AND status='scheduled' "
        )
        params: tuple = ()
        if platform:
            sql += "AND platform=? "
            params = (platform,)
        sql += "ORDER BY postiz_scheduled_for LIMIT 5"
        rows = db.fetchall(sql, params)
        if not rows:
            return "No scheduled shorts"
        return "\n".join(
            f"#{r['entity_id']} {r['platform']} {r['postiz_scheduled_for']}" for r in rows
        )


    def ask_backlog(self, platform: str, count: int) -> None:
        text = (f"Серия закончилась? Не опубликовано шортсов: {count} ({platform}).\n"
                f"Если не ответить до слота — распределю остаток автоматически.")
        markup = {"inline_keyboard": [[
            {"text": "Распределить остаток", "callback_data": f"backlog_distribute {platform}"},
            {"text": "Ждать ещё", "callback_data": f"backlog_wait {platform}"},
            {"text": "Не публиковать", "callback_data": f"backlog_skip {platform}"},
        ]]}
        self.broadcast_markup(text, markup)

    def remind_backlog(self, platform: str, count: int) -> None:
        text = f"⚠️ ВАЖНО: серия закончилась, остаток {count} шортсов ({platform}) не распределён. Отвечай!"
        markup = {"inline_keyboard": [[
            {"text": "Распределить остаток", "callback_data": f"backlog_distribute {platform}"},
            {"text": "Ждать ещё", "callback_data": f"backlog_wait {platform}"},
            {"text": "Не публиковать", "callback_data": f"backlog_skip {platform}"},
        ]]}
        self.broadcast_markup(text, markup)

    def backlog_distributed(self, platform: str, n: int) -> None:
        self.broadcast(f"Остаток распределён ({platform}): {n} шортсов поставлено в план.")

    def broadcast_markup(self, text: str, reply_markup: dict) -> None:
        targets = self.cfg.telegram.allowed_chat_ids or (
            [self._owner_chat_id] if self._owner_chat_id else []
        )
        for cid in targets:
            if not cid:
                continue
            if not self.is_allowed(cid):
                continue
            if self.transport:
                self.transport.send_message(cid, text, reply_markup)
            else:
                logger.info("[TG-markup -> %s] %s", cid, text[:200])

    def cmd_app(chat_id: int, arg: str) -> str:
        import os
        url = os.getenv("WEBAPP_PUBLIC_URL", "").rstrip("/")
        if not url:
            return "Задайте WEBAPP_PUBLIC_URL (например https://host/webapp/)"
        # Client apps open via menu button; here we return the link
        return f"Откройте панель:\n{url}/\n\n(В BotFather: Menu Button → Web App → этот URL)"

    def cmd_backlog_distribute(chat_id: int, arg: str) -> str:
        m = components.get("backlog")
        if not m:
            return "Менеджер остатка недоступен"
        p = (arg or "").strip() or next(iter(cfg.platforms), "")
        n = m.resolve(p, "distribute")
        return f"Остаток распределён ({p}): {n}"

    def cmd_backlog_wait(chat_id: int, arg: str) -> str:
        m = components.get("backlog")
        p = (arg or "").strip() or next(iter(cfg.platforms), "")
        if m:
            m.resolve(p, "wait")
        return f"Ждём новую серию ({p})."

    def cmd_backlog_skip(chat_id: int, arg: str) -> str:
        m = components.get("backlog")
        p = (arg or "").strip() or next(iter(cfg.platforms), "")
        if m:
            m.resolve(p, "skip")
        return f"Остаток не публикуем ({p})."

    def cmd_help(chat_id: int, arg: str) -> str:
        return (
            "Команды:\n"
            "/app — открыть панель\n"
            "/status — статус и счётчики\n"
            "/queue — очередь публикаций\n"
            "/calendar — календарь\n"
            "/failed — ошибки публикаций\n"
            "/platforms — платформы и лимиты\n"
            "/pause, /resume — пауза / возобновить всё\n"
            "/distribute — разложить по слотам\n"
            "/tail — остаток шортсов серии"
        )

    bot.register("help", cmd_help)
    bot.register("backlog_distribute", cmd_backlog_distribute)
    bot.register("backlog_wait", cmd_backlog_wait)
    bot.register("backlog_skip", cmd_backlog_skip)
    bot.register("app", cmd_app)
    bot.register("status", cmd_status)
    bot.register("pause", cmd_pause)
    bot.register("resume", cmd_resume)
    bot.register("resume_platform", cmd_resume_platform)
    bot.register("queue", cmd_queue)
    bot.register("failed", cmd_failed)
    bot.register("tail", cmd_tail)
    bot.register("platforms", cmd_platforms)
    bot.register("distribute", cmd_distribute)
    bot.register("calendar", cmd_calendar)
    bot.register("series_end", cmd_series_end)
    bot.register("force_link_update", cmd_force_link_update)
    bot.register("reload_config", cmd_reload_config)
    bot.register("next_video", cmd_next_video)
    bot.register("next_short", cmd_next_short)
