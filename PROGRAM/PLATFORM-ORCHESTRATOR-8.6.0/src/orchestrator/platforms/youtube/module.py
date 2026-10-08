"""Модуль YouTube: реализация PlatformModule.

Эталон для остальных платформ. См. docs/modules/MODULE_YOUTUBE.txt.
Ошибка thumbnails.set НЕ теряет videoId/release_url (регресс 24.09).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ...http_client import ModuleHttpClient
from ..base import (
    AuthStatus,
    ClaimsResult,
    MediaSpec,
    ModuleError,
    ModuleErrorCode,
    PlatformModule,
    PreparedMedia,
    PublishMeta,
    PublishResult,
    PublishStatus,
    QuotaSnapshot,
    RemoteItem,
    RemotePage,
    UploadResult,
)
from ..manifest import ModuleManifest, load_manifest
from .api import YouTubeApi
from .token_store import make_token_provider

logger = logging.getLogger(__name__)

_MANIFEST_PATH = Path(__file__).with_name("manifest.yaml")


def _tags_from_meta(meta: PublishMeta) -> list[str]:
    raw = (meta.hashtags or "").replace("#", " ").replace(",", " ")
    tags = [t.strip() for t in raw.split() if t.strip()]
    extra = meta.extra or {}
    if isinstance(extra.get("tags"), list):
        tags.extend(str(x).strip() for x in extra["tags"] if str(x).strip())
    # YouTube: суммарно ≤ 500 символов
    out: list[str] = []
    total = 0
    for t in tags:
        if total + len(t) + 1 > 500:
            break
        out.append(t[:100])
        total += len(t) + 1
    return out[:30]


def _thumb_path(meta: PublishMeta, media: PreparedMedia) -> str | None:
    extra = meta.extra or {}
    for key in ("thumbnail", "thumbnail_path", "cover", "cover_path"):
        val = extra.get(key)
        if val and Path(str(val)).is_file():
            return str(val)
    notes_extra = getattr(media, "extra", None) or {}
    if isinstance(notes_extra, dict):
        for key in ("thumbnail", "thumbnail_path"):
            val = notes_extra.get(key)
            if val and Path(str(val)).is_file():
                return str(val)
    return None


class YouTubeModule(PlatformModule):
    """Прямой модуль YouTube Data API v3 (early_upload + publishAt)."""

    def __init__(
        self,
        token_provider: Callable[[], str],
        *,
        http: ModuleHttpClient | None = None,
        category_id: str = "22",
        made_for_kids: bool = False,
        dry_run: bool = False,
        account_label: str = "",
        resume_dir: str | Path | None = None,
    ) -> None:
        self.manifest: ModuleManifest = load_manifest(_MANIFEST_PATH)
        self._token_provider = token_provider
        self._http = http or ModuleHttpClient(
            platform="youtube",
            module_version=self.manifest.module_version,
        )
        self._api = YouTubeApi(
            token_provider,
            http=self._http,
            category_id=category_id,
            made_for_kids=made_for_kids,
        )
        self._dry_run = dry_run
        self._account_label = account_label
        self._category_id = category_id
        self._made_for_kids = made_for_kids
        self._resume_dir = Path(resume_dir) if resume_dir else None

    # ---- обязательное ----

    def auth_status(self) -> AuthStatus:
        if self._dry_run:
            return AuthStatus(ok=True, account="dry-run", details="dry-run mode")
        try:
            data = self._api.channels_mine()
            items = data.get("items") or []
            if not items:
                return AuthStatus(
                    ok=False,
                    details="токен есть, но каналов не найдено — проверьте scopes",
                )
            sn = items[0].get("snippet") or {}
            title = sn.get("title") or items[0].get("id") or ""
            return AuthStatus(
                ok=True,
                account=str(title),
                scopes=list(self.manifest.auth.get("scopes") or []),
                details="channels.mine ok",
            )
        except ModuleError as e:
            return AuthStatus(
                ok=False,
                details=f"{e.code.value}: {e.message}",
            )
        except Exception as e:
            logger.exception("youtube auth_status failed")
            return AuthStatus(ok=False, details=str(e)[:200])

    def validate_config(self, cfg: dict[str, Any]) -> list[str]:
        errs: list[str] = []
        mod = (cfg or {}).get("module") or {}
        if not isinstance(mod, dict):
            return errs
        cat = mod.get("category_id")
        if cat is not None and not str(cat).isdigit():
            errs.append("platforms.youtube.module.category_id должен быть числовой строкой")
        return errs

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        path = Path(media.path)
        if self._dry_run:
            return PreparedMedia(path=str(path), kind=media.kind or "video", notes=["dry_run"])
        if not path.is_file():
            raise ModuleError(
                ModuleErrorCode.MEDIA_INVALID,
                f"YouTube: файл не найден: {media.path}",
                action="проверьте путь к видео на диске",
            )
        size = path.stat().st_size
        max_mb = ((self.manifest.media.get("video") or {}).get("max_mb") or 256000)
        if size > int(max_mb) * 1024 * 1024:
            raise ModuleError(
                ModuleErrorCode.MEDIA_INVALID,
                f"YouTube: файл слишком большой ({size} байт)",
                action=f"лимит {max_mb} МБ",
            )
        if size <= 0:
            raise ModuleError(
                ModuleErrorCode.MEDIA_INVALID,
                "YouTube: пустой файл",
                action="проверьте исходник VideoMaker",
            )
        notes: list[str] = []
        suffix = path.suffix.lower()
        if suffix not in (".mp4", ".mov", ".mpeg", ".mpg"):
            notes.append(f"нестандартный контейнер {suffix}; ожидается mp4")
        return PreparedMedia(path=str(path), kind=media.kind or "video", notes=notes)

    def upload(
        self,
        media: PreparedMedia,
        meta: PublishMeta,
        when: datetime | None = None,
    ) -> UploadResult:
        """Ранняя загрузка: private + publishAt → videoId и URL сразу."""
        if self._dry_run:
            fake_id = f"dryrun_{abs(hash(media.path)) % 10**10}"
            return UploadResult(
                external_id=fake_id,
                url=f"https://youtu.be/{fake_id}",
                state="scheduled" if when else "uploaded",
            )

        tags = _tags_from_meta(meta)
        privacy = "private"
        publish_at = when
        if when is not None and when.tzinfo is None:
            publish_at = when.replace(tzinfo=UTC)

        resource = self._api.resumable_upload(
            media.path,
            title=meta.title or Path(media.path).stem,
            description=meta.description or "",
            tags=tags,
            category_id=self._category_id,
            privacy_status=privacy,
            publish_at=publish_at,
            resume_dir=self._resume_dir,
        )
        video_id = str(resource.get("id") or "")
        if not video_id:
            raise ModuleError(
                ModuleErrorCode.FATAL,
                "YouTube: upload без video id",
                action="повторите; проверьте ответ API",
            )
        url = f"https://youtu.be/{video_id}"

        # Обложка — ПОСЛЕ фиксации videoId (регресс 24.09: не терять ссылку)
        thumb = _thumb_path(meta, media)
        if thumb:
            try:
                self._api.thumbnails_set(video_id, thumb)
            except ModuleError as e:
                if e.code == ModuleErrorCode.PLATFORM_REJECTED:
                    # канал не верифицирован — видео остаётся, обложка пропущена
                    logger.warning(
                        "youtube thumbnail skipped for %s: %s",
                        video_id,
                        e.message,
                    )
                elif e.code in (
                    ModuleErrorCode.MEDIA_INVALID,
                    ModuleErrorCode.AUTH_EXPIRED,
                    ModuleErrorCode.TRANSIENT,
                ):
                    logger.warning(
                        "youtube thumbnail failed for %s (%s): %s — video kept",
                        video_id,
                        e.code.value,
                        e.message,
                    )
                else:
                    # Не роняем upload: videoId уже есть
                    logger.exception(
                        "youtube thumbnail unexpected for %s: %s", video_id, e
                    )
            except Exception:
                logger.exception(
                    "youtube thumbnail unexpected for %s — video kept", video_id
                )

        state = "scheduled" if publish_at else "uploaded"
        return UploadResult(external_id=video_id, url=url, state=state)

    def schedule_publish(self, external_id: str, when: datetime) -> bool:
        if self._dry_run:
            return True
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        self._api.videos_update(
            external_id,
            privacy_status="private",
            publish_at=when,
        )
        return True

    def clear_schedule(self, external_id: str) -> bool:
        """Снять publishAt: видео остаётся private (YT§6.1)."""
        if self._dry_run:
            return True
        self._api.videos_update(
            external_id,
            privacy_status="private",
            clear_publish_at=True,
        )
        return True

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        """Немедленная публикация (at_slot / test): public без publishAt."""
        if self._dry_run:
            fake_id = f"dryrun_pub_{abs(hash(media.path)) % 10**10}"
            return PublishResult(
                external_id=fake_id,
                url=f"https://youtu.be/{fake_id}",
                state="published",
            )
        tags = _tags_from_meta(meta)
        resource = self._api.resumable_upload(
            media.path,
            title=meta.title or Path(media.path).stem,
            description=meta.description or "",
            tags=tags,
            category_id=self._category_id,
            privacy_status="public",
            publish_at=None,
            resume_dir=self._resume_dir,
        )
        video_id = str(resource.get("id") or "")
        if not video_id:
            raise ModuleError(
                ModuleErrorCode.FATAL,
                "YouTube: publish без video id",
                action="повторите",
            )
        url = f"https://youtu.be/{video_id}"
        thumb = _thumb_path(meta, media)
        if thumb:
            try:
                self._api.thumbnails_set(video_id, thumb)
            except ModuleError as e:
                logger.warning(
                    "youtube thumbnail on publish %s: %s — video kept",
                    video_id,
                    e.message,
                )
            except Exception:
                logger.exception("youtube thumbnail on publish %s — video kept", video_id)
        return PublishResult(external_id=video_id, url=url, state="published")

    def update_metadata(self, external_id: str, patch: PublishMeta) -> bool:
        if self._dry_run:
            return True
        tags = _tags_from_meta(patch) if (patch.hashtags or patch.extra) else None
        self._api.videos_update(
            external_id,
            title=patch.title or None,
            description=patch.description if patch.description != "" else None,
            tags=tags,
            category_id=self._category_id,
        )
        thumb = None
        extra = patch.extra or {}
        for key in ("thumbnail", "thumbnail_path", "cover", "cover_path"):
            if extra.get(key) and Path(str(extra[key])).is_file():
                thumb = str(extra[key])
                break
        if thumb:
            try:
                self._api.thumbnails_set(external_id, thumb)
            except ModuleError as e:
                logger.warning(
                    "youtube update thumbnail %s: %s", external_id, e.message
                )
        return True

    def delete(self, external_id: str) -> bool:
        if self._dry_run:
            return True
        return self._api.videos_delete(external_id)

    def get_status(self, external_id: str) -> PublishStatus:
        if self._dry_run:
            return PublishStatus(state="published", url=f"https://youtu.be/{external_id}")
        data = self._api.videos_list([external_id])
        items = data.get("items") or []
        if not items:
            return PublishStatus(state="deleted", error="videoNotFound")
        item = items[0]
        st = item.get("status") or {}
        privacy = (st.get("privacyStatus") or "").lower()
        upload_status = (st.get("uploadStatus") or "").lower()
        pub_at = st.get("publishAt")
        url = f"https://youtu.be/{external_id}"

        proc = item.get("processingDetails") or {}
        proc_status = (proc.get("processingStatus") or "").lower()
        failure_reason = proc.get("processingFailureReason") or proc.get("processingFailureReasonDetails")
        if upload_status in ("rejected", "failed") or proc_status in ("failed", "terminated"):
            reason = st.get("rejectionReason") or failure_reason or upload_status or proc_status
            return PublishStatus(
                state="failed",
                url=url,
                error=str(reason),
            )
        if upload_status in ("uploaded", "processed") and privacy == "public":
            return PublishStatus(state="published", url=url)
        if privacy == "private" and pub_at:
            return PublishStatus(state="scheduled", url=url)
        if privacy == "private":
            return PublishStatus(state="uploaded", url=url)
        if privacy == "unlisted":
            return PublishStatus(state="published", url=url)
        # processing / upload lifecycle
        if proc_status in ("processing", "succeeded") and privacy not in ("public", "unlisted"):
            return PublishStatus(state="processing", url=url, raw={"processing_status": proc_status})
        return PublishStatus(state="processing", url=url)


    def list_remote_items(
        self,
        *,
        kinds: set[str] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> RemotePage:
        """List channel videos (published/scheduled/private via videos.list + search)."""
        kinds = set(kinds or {"published", "scheduled", "private", "processing"})
        items: list[RemoteItem] = []
        notes: list[str] = []
        # Search for mine → ids, then videos.list for status/privacy
        try:
            params_since = since.strftime("%Y-%m-%dT%H:%M:%SZ") if since else None
            params_until = until.strftime("%Y-%m-%dT%H:%M:%SZ") if until else None
            data = self._api.search_list(
                for_mine=True,
                max_results=min(50, max(1, limit)),
                page_token=cursor,
                published_after=params_since,
                published_before=params_until,
            )
        except Exception as e:
            logger.warning("youtube search.list failed: %s", type(e).__name__)
            notes.append(f"search.list failed: {type(e).__name__}")
            return RemotePage(items=[], partial=True, notes=notes)
        ids = []
        for it in data.get("items") or []:
            vid = ((it.get("id") or {}) if isinstance(it.get("id"), dict) else {}).get("videoId")
            if not vid and isinstance(it.get("id"), str):
                vid = it["id"]
            if vid:
                ids.append(vid)
        next_cursor = data.get("nextPageToken")
        if not ids:
            return RemotePage(items=[], next_cursor=next_cursor, partial=False, notes=notes)
        try:
            detail = self._api.videos_list(ids)
        except Exception as e:
            logger.warning("youtube videos.list failed: %s", type(e).__name__)
            notes.append(f"videos.list failed: {type(e).__name__}")
            return RemotePage(items=[], next_cursor=next_cursor, partial=True, notes=notes)
        for v in detail.get("items") or []:
            vid = v.get("id") or ""
            sn = v.get("snippet") or {}
            st = v.get("status") or {}
            cd = v.get("contentDetails") or {}
            privacy = str(st.get("privacyStatus") or "unknown").lower()
            publish_at = st.get("publishAt")
            published_at = sn.get("publishedAt")
            status = "published"
            if privacy == "private" and publish_at:
                status = "scheduled"
            elif privacy == "private":
                status = "private"
            elif privacy == "unlisted":
                status = "published"
            if status == "published" and "published" not in kinds:
                if not (status in kinds):
                    continue
            if status not in kinds and privacy not in kinds:
                # allow kinds private/scheduled/published
                if status == "scheduled" and "scheduled" not in kinds:
                    continue
                if status == "private" and "private" not in kinds:
                    continue
                if status == "published" and "published" not in kinds:
                    continue
            duration = None
            dur = cd.get("duration") or ""
            # ISO8601 duration PT#M#S rough parse optional skip
            items.append(RemoteItem(
                platform="youtube",
                external_id=vid,
                url=f"https://youtu.be/{vid}" if vid else "",
                title=str(sn.get("title") or ""),
                description=str(sn.get("description") or "")[:500],
                published_at=published_at,
                scheduled_for=publish_at,
                privacy=privacy,
                status=status,
                duration_sec=duration,
                media_type="video",
                raw={"id": vid, "privacy": privacy},
            ))
        return RemotePage(
            items=items[:limit],
            next_cursor=next_cursor,
            partial=False,
            notes=notes,
        )

    def get_quota(self) -> QuotaSnapshot:
        """Two-bucket snapshot from config defaults (live remaining unknown without quota API)."""
        lim = (self.manifest.limits or {}).get("quota") or {}
        upload = lim.get("upload_bucket") or {"default_daily_limit": 100, "cost_per_call": 1}
        general = lim.get("general_bucket") or {"default_daily_limit": 10000}
        return QuotaSnapshot(
            unit="api_units",
            remaining=None,
            limit=int(general.get("default_daily_limit") or lim.get("per_day") or 10000),
            buckets={
                "upload": {
                    "limit": int(upload.get("default_daily_limit") or 100),
                    "cost_per_call": int(upload.get("cost_per_call") or 1),
                },
                "general": {
                    "limit": int(general.get("default_daily_limit") or 10000),
                    "costs": dict(general.get("costs") or {}),
                },
            },
            raw={"note": "YouTube does not expose remaining units via public API; defaults from config"},
        )


    def check_claims(self, external_id: str) -> ClaimsResult:
        """Content ID публичным API недоступен → supported=false (ручной чекпойнт ядра)."""
        return ClaimsResult(supported=False, status="unknown", details="Content ID API недоступен")


def create_youtube_module(**deps: Any) -> YouTubeModule:
    """Фабрика для реестра: deps из load_modules (token_provider, http, cfg, ...).

    token_provider: явный callable, иначе YouTubeTokenStore
    (YT_TOKENS_PATH / tokens/youtube.json + YT_CLIENT_* из env).
    """
    cfg = deps.get("cfg") or {}
    yt_cfg: dict[str, Any] = {}
    if isinstance(cfg, dict):
        yt_cfg = ((cfg.get("platforms") or {}).get("youtube") or {})
    elif hasattr(cfg, "platforms"):
        plat = getattr(cfg, "platforms", {}) or {}
        yt_cfg = plat.get("youtube") if isinstance(plat, dict) else {}
    mod = (yt_cfg.get("module") or {}) if isinstance(yt_cfg, dict) else {}

    tokens_path = deps.get("tokens_path") or mod.get("tokens_path")
    token_provider = make_token_provider(
        token_provider=deps.get("token_provider") if callable(deps.get("token_provider")) else None,
        tokens_path=tokens_path,
        client_id=str(mod.get("client_id") or ""),
        client_secret=str(mod.get("client_secret") or ""),
        http=deps.get("http"),  # type: ignore[arg-type]
    )
    resume = deps.get("resume_dir") or mod.get("resume_dir")
    return YouTubeModule(
        token_provider,
        http=deps.get("http"),  # type: ignore[arg-type]
        category_id=str(mod.get("category_id") or "22"),
        made_for_kids=bool(mod.get("made_for_kids", False)),
        dry_run=bool(deps.get("dry_run", False)),
        account_label=str(mod.get("account") or ""),
        resume_dir=resume,
    )
