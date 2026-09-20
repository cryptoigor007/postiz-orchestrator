from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


class PlatformCfg(BaseModel):
    post_mode: str = "media"   # media | link (только ссылка на YouTube)
    video_variant: str = "wide"
    audio_profile: str = "default"
    enabled: bool = True
    daily_limit: int = 5
    integration_id: str = ""  # Postiz integrationId (required for live create)


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
    method: str = "VACUUM INTO"


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
    media: MediaCfg = Field(default_factory=MediaCfg)
    manual_uploads: ManualUploadsCfg = Field(default_factory=ManualUploadsCfg)
    backup: BackupCfg = Field(default_factory=BackupCfg)
    engines: dict[str, str] = Field(default_factory=dict)
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

    def engine_for(self, platform: str) -> str:
        """Publication engine for a platform (default: postiz)."""
        return self.engines.get(platform, "postiz")


def load_config(path: str | Path) -> AppConfig:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return AppConfig(**raw)
