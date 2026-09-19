from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


class ScheduleLong(BaseModel):
    type: str = "long_video"
    source: str = "videomaker"
    days: list[str]
    time: str
    is_cycle: bool = True
    exception_days: list[str] = Field(default_factory=list)


class ScheduleThematic(BaseModel):
    type: str = "shorts_thematic"
    source: str = "videomaker"
    default_time: str = "20:30"


class ScheduleStandalone(BaseModel):
    type: str = "shorts_standalone"
    source: str = "shortsmaker"
    days: list[str]
    times: list[str]
    exception_days: list[str] = Field(default_factory=list)


class PlatformCfg(BaseModel):
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
    jitter_seconds: int = 90
    warmup_days: int = 12
    warmup_daily_limit: int = 2
    warmup_after_pause_hours: int = 24
    on_serious_error: dict[str, Any] = Field(default_factory=lambda: {
        "action": "pause_platform", "pause_hours": 0, "notify": True
    })
    serious_errors: list[str] = Field(default_factory=list)
    auth_errors: list[str] = Field(default_factory=list)


class TelegramCfg(BaseModel):
    allowed_chat_ids: list[int] = Field(default_factory=list)


class ManualUploadsCfg(BaseModel):
    enabled: bool = True
    platforms: list[str] = Field(default_factory=list)
    lookback_days: int = 60
    page_size: int = 50
    confidence_high: float = 0.80
    confidence_medium: float = 0.55
    apply_description: bool = True
    rename_title: bool = False
    schedule_scan: str = "daily"
    claim_policy: str = "warn"
    placement_default: str = "end"


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
    manual_uploads: ManualUploadsCfg = Field(default_factory=ManualUploadsCfg)
    backup: BackupCfg = Field(default_factory=BackupCfg)
    engines: dict[str, str] = Field(default_factory=dict)
    reconciliation_interval_hours: int = 24
    timezone: str = "Europe/Moscow"
    watcher_interval_sec: int = 75
    status_sync_interval_sec: int = 180
    confirm_published_interval_sec: int = 120
    file_stability_cycles: int = 2

    @field_validator("platforms", mode="before")
    @classmethod
    def parse_platforms(cls, v: dict) -> dict:
        return {k: PlatformCfg(**val) if isinstance(val, dict) else val for k, val in v.items()}

    def engine_for(self, platform: str) -> str:
        """Publication engine for a platform (default: postiz)."""
        return self.engines.get(platform, "postiz")


def load_config(path: str | Path) -> AppConfig:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return AppConfig(**raw)
