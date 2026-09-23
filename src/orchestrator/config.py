from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class PlatformCfg(BaseModel):
    post_mode: str = "media"   # media | link (только ссылка на YouTube)
    video_variant: str = "wide"
    audio_profile: str = "default"
    enabled: bool = True
    daily_limit: int = 5
    integration_id: str = ""  # Postiz integrationId (required for live create)
    # Telegram: postiz — как раньше (превью ссылки под текстом); bot — отправляем сами
    # через Bot API, тогда карточка ролика стоит НАД текстом (link_preview_options).
    send_via: str = "postiz"           # postiz | bot
    publish_chat_id: str = ""          # канал для send_via=bot (id или @username)
    link_preview_above: bool = True    # превью над текстом (Bot API show_above_text)
    project: str = ""                  # проект (ниша) платформы; "" = основной/единственный


class ProjectCfg(BaseModel):
    """Проект = ниша со своими каналами во всех сетях (см. docs/PLAN-PROJECTS.md)."""

    title: str = ""
    series_ids: list[int] = Field(default_factory=list)   # серии videomaker этого проекта
    folders: list[str] = Field(default_factory=list)      # папки обычных шортсов проекта
    telegram_chat_ids: list[int] = Field(default_factory=list)  # куда слать уведомления проекта


def _norm_folder(p: str) -> str:
    return str(p or "").replace("\\", "/").rstrip("/")


class TailCfg(BaseModel):
    soft_enter_days: int = 5
    series_end_question_ttl_days: int = 10
    series_end_question_cooldown_days: int = 3
    use_all_short_slots: bool = True
    pause_standalone_during_tail: bool = True
    # backlog (неопубликованные шортсы серии)
    ask_minutes_before: int = 60      # спросить за N минут до слота серии
    reminder_minutes_before: int = 15 # напомнить за N минут до слота
    default_action: str = "distribute"  # distribute | wait


class LimitsCfg(BaseModel):
    max_posts_per_distribute: int = 12
    postiz_create_per_hour: int = 30
    max_shorts_per_long_video: int = 8
    overflow_move_files: bool = False  # true = физически переносить лишние шорты (по умолчанию нет)


class LinkUpdateCfg(BaseModel):
    release_url_timeout_min: int = 90
    missing_url_dialog_ttl_hours: int = 12
    missing_url_default_action: str = "post_without_link"
    placeholder_text: str = "Полное видео на канале"


class SafetyCfg(BaseModel):
    min_interval_minutes: int = 25
    conflict_window_minutes: int = 0  # 0 = использовать min_interval_minutes
    jitter_seconds: int = 90
    warmup_days: int = 12
    warmup_daily_limit: int = 2
    warmup_after_pause_hours: int = 24
    on_serious_error: dict[str, Any] = Field(default_factory=lambda: {
        "action": "pause_platform", "pause_hours": 0, "notify": True
    })
    serious_errors: list[str] = Field(default_factory=list)
    rate_limit_errors: list[str] = Field(default_factory=list)
    auth_errors: list[str] = Field(default_factory=list)


class TelegramCfg(BaseModel):
    allowed_chat_ids: list[int] = Field(default_factory=list)


class MediaCfg(BaseModel):
    symlink_mode: bool = True          # не копировать файлы сервера в Postiz (симлинк)
    local_prefix: str = "/mnt/video/"
    cache_dir: str = "/mnt/video/.orch_cache"
    telegram_max_mb: int = 0            # 0 = сжатие выключено (как просил пользователь)


class ManualUploadsCfg(BaseModel):
    enabled: bool = True
    platforms: list[str] = Field(default_factory=list)
    lookback_days: int = 60
    page_size: int = 50
    schedule_scan: str = "daily"


class BackupCfg(BaseModel):
    enabled: bool = True
    interval_hours: int = 6
    keep_days: int = 14
    method: str = "sqlite_backup"  # Connection.backup API (8.1.1+)


class TestPublishCfg(BaseModel):
    """Пробный (тестовый) пост: отдельный контур, не трогает боевые строки расписания."""
    enabled: bool = False
    default_delay_minutes: int = 1
    min_delay_minutes: int = 1
    max_delay_minutes: int = 120
    title_prefix: str = "[orch-test] "
    platforms: list[str] = Field(default_factory=list)      # allowlist платформ
    require_explicit_platforms: bool = True                 # true: только из allowlist
    allow_prod_channel: bool = False                        # разрешить боевой канал
    prod_integration_ids: list[str] = Field(default_factory=list)  # id боевых каналов
    test_integration_ids: list[str] = Field(default_factory=list)  # allowlist id для тестов
    skip_tail_side_effects: bool = True
    skip_thematic_cascade: bool = True
    zero_jitter: bool = True
    ignore_limits: bool = True   # P1.2: тест не жрёт daily_limit/min_interval, но пауза учитывается
    cleanup_after_hours: int = 24  # P1.3: авто-снятие тест-постов старше N часов


class AppConfig(BaseModel):
    schedules: dict[str, Any]
    platforms: dict[str, PlatformCfg]
    tail: TailCfg = Field(default_factory=TailCfg)
    limits: LimitsCfg = Field(default_factory=LimitsCfg)
    link_update: LinkUpdateCfg = Field(default_factory=LinkUpdateCfg)
    description_templates: dict[str, str] = Field(default_factory=lambda: {
        "thematic_short": "{description}\n\n▶ Полное видео: {link}",
        "thematic_short_no_link": "{description}\n\n▶ Полное видео на канале",
        "default": "{description}",
    })
    safety: SafetyCfg = Field(default_factory=SafetyCfg)
    telegram: TelegramCfg = Field(default_factory=TelegramCfg)
    projects: dict[str, ProjectCfg] = Field(default_factory=dict)
    # Проект по умолчанию: к нему относится контент, не привязанный ни к какому проекту
    # (весь текущий контент — «Точка наблюдения»). Пусто = такие сущности идут в платформы
    # без проекта и не попадают в проектные каналы.
    default_project: str = ""
    media: MediaCfg = Field(default_factory=MediaCfg)
    # reserved (не используется в коде, только для будущих фич):
    #   placement_default (D8) — экран выбора плейсмента не реализован;
    #   audio_profile (D9) — профиль звука зарезервирован.
    # manual_uploads.platforms=[] (F4) — скан всех поддерживаемых источников;
    #   непустой список ограничивает скан перечисленными платформами.
    manual_uploads: ManualUploadsCfg = Field(default_factory=ManualUploadsCfg)
    backup: BackupCfg = Field(default_factory=BackupCfg)
    engines: dict[str, str] = Field(default_factory=dict)
    test_publish: TestPublishCfg = Field(default_factory=TestPublishCfg)
    reconciliation_interval_hours: int = 24
    telegram_link_delay_min: int = 15
    timezone: str = "Europe/Moscow"
    watcher_interval_sec: int = 75
    status_sync_interval_sec: int = 180
    confirm_published_interval_sec: int = 120
    file_stability_cycles: int = 2
    watch_max_depth: int = 5
    watch_max_age_days: int = 3650  # 0/большое = не отсекать старое (иначе скан не вернёт удалённое)

    @field_validator("platforms", mode="before")
    @classmethod
    def parse_platforms(_cls, v: dict) -> dict:
        return {k: PlatformCfg(**val) if isinstance(val, dict) else val for k, val in v.items()}

    @model_validator(mode="after")
    def _check_projects(self) -> AppConfig:
        unknown = sorted({p.project for p in self.platforms.values()
                          if p.project and p.project not in self.projects})
        known_all = set(self.projects)
        if self.default_project and self.default_project not in known_all:
            raise ValueError(
                f"default_project={self.default_project!r} отсутствует в projects "
                f"({', '.join(sorted(known_all)) or 'нет'})"
            )
        if unknown:
            known = ", ".join(sorted(self.projects)) or "(нет)"
            raise ValueError(
                f"платформы ссылаются на неизвестный проект: {', '.join(unknown)}; "
                f"известные проекты: {known}"
            )
        return self

    def project_of_series(self, series_id: int | None) -> str:
        """Проект серии videomaker (пустая строка — не привязана ни к какому проекту)."""
        if series_id is None:
            return ""
        for name, prj in self.projects.items():
            if series_id in list(prj.series_ids or []):
                return name
        return ""

    def project_of_folder(self, folder: str | None) -> str:
        """Проект по папке (сама папка или вложенная в неё)."""
        f = _norm_folder(folder or "")
        if not f:
            return ""
        for name, prj in self.projects.items():
            for root in list(prj.folders or []):
                r = _norm_folder(root)
                if r and (f == r or f.startswith(r + "/")):
                    return name
        return ""

    def project_title(self, project: str) -> str:
        prj = self.projects.get(project or "")
        title = (prj.title if prj else "") or ""
        return title or (project or "Основной")

    def platforms_of_project(self, project: str) -> list[str]:
        return [k for k, p in self.platforms.items() if (p.project or "") == (project or "")]

    def resolve_project(self, *, series_id: int | None = None,
                        series_folder: str | None = None, folder: str | None = None) -> str:
        """Проект сущности: серия → папка серии → своя папка (первое совпадение).

        Для шортса серии `series_folder` — папка фильма-родителя, `folder` — его собственная
        папка: так тематический шортс попадает в проект своей серии, а не папки шортсов.
        """
        return (self.project_of_series(series_id)
                or self.project_of_folder(series_folder)
                or self.project_of_folder(folder)
                or self.default_project)

    def platform_matches_project(self, platform: str, *, series_id: int | None = None,
                                series_folder: str | None = None,
                                folder: str | None = None) -> bool:
        """Публиковать ли сущность в эту платформу с учётом проекта.

        Платформа без проекта — как раньше, принимает всё. Платформа проекта берёт
        только сущности этого проекта (серия из `series_ids` или папка из `folders`).
        """
        pcfg = self.platforms.get(platform)
        if pcfg is None:
            return False
        want = pcfg.project or ""
        if not want:
            return True
        return self.resolve_project(series_id=series_id, series_folder=series_folder,
                                    folder=folder) == want

    def engine_for(self, platform: str) -> str:
        """Publication engine for a platform (default: postiz)."""
        return self.engines.get(platform, "postiz")


def load_config(path: str | Path) -> AppConfig:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return AppConfig(**raw)
