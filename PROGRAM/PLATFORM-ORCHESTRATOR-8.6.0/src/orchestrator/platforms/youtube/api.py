"""Низкоуровневый клиент YouTube Data API v3.

Resumable upload, thumbnails, status, ошибки → ModuleErrorCode.
См. docs/modules/MODULE_YOUTUBE.txt §2, §9.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from ...http_client import ModuleHttpClient
from ..base import ModuleError, ModuleErrorCode

logger = logging.getLogger(__name__)

API = "https://www.googleapis.com/youtube/v3"
UPLOAD_API = "https://www.googleapis.com/upload/youtube/v3"

# Размер чанка resumable (по гайду Google: 256 KiB кратно, у нас 8 MiB).
CHUNK_SIZE = 8 * 1024 * 1024


def _rfc3339(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def map_youtube_error(
    status: int,
    body: dict[str, Any] | str | None,
    *,
    context: str = "",
) -> ModuleError:
    """Маппинг HTTP/API ошибок YouTube в единую таксономию (MODULE_YOUTUBE §9)."""
    reason = ""
    message = ""
    if isinstance(body, dict):
        err = body.get("error") or {}
        if isinstance(err, dict):
            message = str(err.get("message") or "")
            errors = err.get("errors") or []
            if errors and isinstance(errors[0], dict):
                reason = str(errors[0].get("reason") or "")
        else:
            message = str(err)
    elif body:
        message = str(body)[:500]

    low_msg = (message + " " + reason).lower()
    ctx = f" ({context})" if context else ""
    ctx_l = (context or "").lower()

    # Специфичные 403 раньше auth (иначе forbidden на thumbnail → AUTH).
    if status == 403 and (
        "quotaexceeded" in low_msg
        or reason == "quotaExceeded"
        or "daily limit" in low_msg
    ):
        return ModuleError(
            ModuleErrorCode.QUOTA,
            f"YouTube: суточная квота API исчерпана{ctx}.",
            action="пауза до сброса квоты (обычно 00:00 PT); снизить число загрузок",
            retryable=False,
        )

    if status in (403, 429) and (
        "ratelimit" in low_msg
        or "rate limit" in low_msg
        or "uploadlimitexceeded" in low_msg
        or reason in ("rateLimitExceeded", "userRateLimitExceeded", "uploadLimitExceeded")
    ):
        return ModuleError(
            ModuleErrorCode.RATE_LIMIT,
            f"YouTube: лимит частоты запросов{ctx}.",
            action="backoff по Retry-After; повторить позже",
            retryable=True,
        )

    if status == 403 and (
        "not verified" in low_msg
        or "account is not verified" in low_msg
        or "channelnotverified" in low_msg
        or reason == "accountNotVerified"
        or ("thumbnail" in ctx_l and reason == "forbidden")
    ):
        return ModuleError(
            ModuleErrorCode.PLATFORM_REJECTED,
            f"YouTube: канал не верифицирован — обложка недоступна{ctx}. "
            "Видео уже загружено, обложка пропущена.",
            action="подтвердите канал телефоном в YouTube Studio",
            retryable=False,
        )

    if status in (401, 403) and (
        "invalid_grant" in low_msg
        or "invalid credentials" in low_msg
        or "autherror" in low_msg
        or "unauthorized" in low_msg
        or reason in ("authError", "unauthorized")
    ):
        if "invalid_grant" in low_msg:
            return ModuleError(
                ModuleErrorCode.AUTH_REQUIRED,
                f"YouTube: refresh-токен недействителен{ctx}. "
                "Переподключите канал (OAuth).",
                action="переподключить YouTube в панели / передать новый refresh",
                retryable=False,
            )
        return ModuleError(
            ModuleErrorCode.AUTH_EXPIRED,
            f"YouTube: токен истёк или отозван{ctx}.",
            action="авто-refresh; если не помогло — переподключить канал",
            retryable=True,
        )

    if "invalid_grant" in low_msg:
        return ModuleError(
            ModuleErrorCode.AUTH_REQUIRED,
            f"YouTube: refresh-токен недействителен{ctx}. "
            "Переподключите канал (OAuth).",
            action="переподключить YouTube в панели / передать новый refresh",
            retryable=False,
        )

    if status == 400 or reason in (
        "invalidVideoMetadata",
        "invalidTitle",
        "invalidDescription",
        "invalidCategoryId",
        "mediaBodyRequired",
        "invalidFileFormat",
    ):
        return ModuleError(
            ModuleErrorCode.MEDIA_INVALID,
            f"YouTube: невалидные метаданные или файл{ctx}: {message or reason}",
            action="проверьте title/description/файл (mp4 H.264+AAC)",
            retryable=False,
        )

    if status == 404 or reason == "videoNotFound":
        return ModuleError(
            ModuleErrorCode.FATAL,
            f"YouTube: видео не найдено{ctx}.",
            action="проверьте external_id; возможно уже удалено",
            retryable=False,
        )

    if status >= 500 or status == 0:
        return ModuleError(
            ModuleErrorCode.TRANSIENT,
            f"YouTube: временная ошибка сервера ({status}){ctx}: {message or reason}",
            action="повтор с backoff",
            retryable=True,
        )

    return ModuleError(
        ModuleErrorCode.FATAL,
        f"YouTube: ошибка {status}{ctx}: {message or reason or 'unknown'}",
        action="см. логи; при повторении — алерт владельцу",
        retryable=False,
    )


class YouTubeApi:
    """Клиент Data API v3. Токен — через token_provider() (брокер / локальный store)."""

    def __init__(
        self,
        token_provider: Callable[[], str],
        http: ModuleHttpClient | None = None,
        *,
        category_id: str = "22",
        made_for_kids: bool = False,
    ) -> None:
        self._token_provider = token_provider
        self.http = http or ModuleHttpClient(platform="youtube", module_version="2.1.1")
        self.category_id = category_id
        self.made_for_kids = made_for_kids

    def _auth_headers(self) -> dict[str, str]:
        token = self._token_provider()
        if not token:
            raise ModuleError(
                ModuleErrorCode.AUTH_REQUIRED,
                "YouTube: нет access-токена.",
                action="подключите канал / проверьте token-broker",
            )
        return {"Authorization": f"Bearer {token}"}

    def _parse_error(self, resp: httpx.Response, context: str = "") -> ModuleError:
        try:
            body: dict[str, Any] | str | None = resp.json()
        except Exception:
            body = resp.text[:500] if resp.text else None
        return map_youtube_error(resp.status_code, body, context=context)

    def channels_mine(self) -> dict[str, Any]:
        """GET /channels?part=snippet,contentDetails&mine=true."""
        url = f"{API}/channels"
        resp = self.http.request(
            "GET",
            url,
            headers=self._auth_headers(),
            params={"part": "snippet,contentDetails", "mine": "true"},
            idempotent=True,
        )
        if resp.status_code >= 400:
            raise self._parse_error(resp, "channels.mine")
        return resp.json() if resp.content else {}

    def videos_list(self, video_ids: list[str], part: str = "snippet,status,processingDetails,contentDetails") -> dict[str, Any]:
        if not video_ids:
            return {"items": []}
        url = f"{API}/videos"
        resp = self.http.request(
            "GET",
            url,
            headers=self._auth_headers(),
            params={"part": part, "id": ",".join(video_ids[:50])},
            idempotent=True,
        )
        if resp.status_code >= 400:
            raise self._parse_error(resp, "videos.list")
        return resp.json() if resp.content else {}

    def videos_update(
        self,
        video_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        category_id: str | None = None,
        privacy_status: str | None = None,
        publish_at: datetime | None = None,
        clear_publish_at: bool = False,
    ) -> dict[str, Any]:
        """PUT /videos?part=snippet,status — правка метаданных / privacy / publishAt."""
        body: dict[str, Any] = {"id": video_id}
        parts: list[str] = []
        if any(x is not None for x in (title, description, tags, category_id)):
            sn: dict[str, Any] = {}
            if title is not None:
                sn["title"] = title[:100]
            if description is not None:
                sn["description"] = description[:5000]
            if tags is not None:
                sn["tags"] = tags
            if category_id is not None:
                sn["categoryId"] = category_id
            body["snippet"] = sn
            parts.append("snippet")
        if privacy_status is not None or publish_at is not None or clear_publish_at:
            st: dict[str, Any] = {}
            if privacy_status is not None:
                st["privacyStatus"] = privacy_status
            if publish_at is not None:
                st["publishAt"] = _rfc3339(publish_at)
                st["privacyStatus"] = st.get("privacyStatus") or "private"
            if clear_publish_at:
                # YouTube не принимает null publishAt: передаём private
                # БЕЗ поля publishAt — слот снимается, видео остаётся скрытым.
                st["privacyStatus"] = privacy_status or "private"
                st.pop("publishAt", None)
            body["status"] = st
            parts.append("status")
        if not parts:
            return {}
        url = f"{API}/videos"
        resp = self.http.request(
            "PUT",
            url,
            headers={**self._auth_headers(), "Content-Type": "application/json"},
            params={"part": ",".join(parts)},
            json=body,
            idempotent=True,
        )
        if resp.status_code >= 400:
            raise self._parse_error(resp, "videos.update")
        return resp.json() if resp.content else {}

    def videos_delete(self, video_id: str) -> bool:
        url = f"{API}/videos"
        resp = self.http.request(
            "DELETE",
            url,
            headers=self._auth_headers(),
            params={"id": video_id},
            idempotent=True,
        )
        if resp.status_code in (200, 204):
            return True
        if resp.status_code == 404:
            return True  # уже нет
        raise self._parse_error(resp, "videos.delete")

    def thumbnails_set(self, video_id: str, image_path: str) -> dict[str, Any]:
        """POST upload/youtube/v3/thumbnails/set — обложка.

        При «account not verified» — PLATFORM_REJECTED, видео уже есть.
        """
        path = Path(image_path)
        if not path.is_file():
            raise ModuleError(
                ModuleErrorCode.MEDIA_INVALID,
                f"YouTube: файл обложки не найден: {image_path}",
                action="проверьте путь к jpg/png ≤ 2 МБ",
            )
        size = path.stat().st_size
        if size > 2 * 1024 * 1024:
            raise ModuleError(
                ModuleErrorCode.MEDIA_INVALID,
                f"YouTube: обложка > 2 МБ ({size} байт)",
                action="сожмите обложку до ≤ 2 МБ",
            )
        suffix = path.suffix.lower()
        ctype = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
        data = path.read_bytes()
        url = f"{UPLOAD_API}/thumbnails/set"
        resp = self.http.request(
            "POST",
            url,
            headers={
                **self._auth_headers(),
                "Content-Type": ctype,
                "Content-Length": str(len(data)),
            },
            params={"videoId": video_id},
            data=data,
            idempotent=True,
            upload=True,
        )
        if resp.status_code >= 400:
            raise self._parse_error(resp, "thumbnails.set")
        return resp.json() if resp.content else {}


    def search_list(
        self,
        *,
        for_mine: bool = True,
        q: str | None = None,
        max_results: int = 50,
        page_token: str | None = None,
        published_after: str | None = None,
        published_before: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "part": "snippet",
            "type": "video",
            "maxResults": max(1, min(50, int(max_results))),
            "forMine": "true" if for_mine else "false",
        }
        if q:
            params["q"] = q
        if page_token:
            params["pageToken"] = page_token
        if published_after:
            params["publishedAfter"] = published_after
        if published_before:
            params["publishedBefore"] = published_before
        resp = self.http.request(
            "GET", f"{API}/search", headers=self._auth_headers(), params=params, idempotent=True,
        )
        if resp.status_code >= 400:
            raise self._parse_error(resp, "search.list")
        return resp.json() if resp.content else {}

    def playlist_items_list(
        self,
        playlist_id: str,
        *,
        max_results: int = 50,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "part": "snippet,contentDetails,status",
            "playlistId": playlist_id,
            "maxResults": max(1, min(50, int(max_results))),
        }
        if page_token:
            params["pageToken"] = page_token
        resp = self.http.request(
            "GET", f"{API}/playlistItems", headers=self._auth_headers(), params=params, idempotent=True,
        )
        if resp.status_code >= 400:
            raise self._parse_error(resp, "playlistItems.list")
        return resp.json() if resp.content else {}

    def resumable_upload(
        self,
        video_path: str,
        *,
        title: str,
        description: str = "",
        tags: list[str] | None = None,
        category_id: str | None = None,
        privacy_status: str = "private",
        publish_at: datetime | None = None,
        notify_progress: Callable[[int, int], None] | None = None,
        resume_dir: str | Path | None = None,
    ) -> dict[str, Any]:
        """Resumable upload videos.insert.

        Возвращает полный ответ videos resource (с id).
        videoId известен СРАЗУ после финализации — до thumbnails.set.

        resume_dir: если задан — сохраняет session URL + offset между процессами
        (03§2.3). После успеха файл сессии удаляется.
        """
        path = Path(video_path)
        if not path.is_file():
            raise ModuleError(
                ModuleErrorCode.MEDIA_INVALID,
                f"YouTube: видеофайл не найден: {video_path}",
                action="проверьте путь к mp4",
            )
        file_size = path.stat().st_size
        if file_size <= 0:
            raise ModuleError(
                ModuleErrorCode.MEDIA_INVALID,
                "YouTube: пустой видеофайл",
                action="проверьте файл на диске",
            )

        # --- optional resume between processes (03§2.3) ---
        session_path: Path | None = None
        upload_url: str | None = None
        sent = 0
        if resume_dir:
            rd = Path(resume_dir)
            rd.mkdir(parents=True, exist_ok=True)
            key = hashlib.sha256(
                f"{path.resolve()}|{file_size}|{title}".encode()
            ).hexdigest()[:32]
            session_path = rd / f"yt_upload_{key}.json"
            if session_path.is_file():
                try:
                    prev = json.loads(session_path.read_text(encoding="utf-8"))
                    if (
                        int(prev.get("file_size") or 0) == file_size
                        and prev.get("upload_url")
                    ):
                        upload_url = str(prev["upload_url"])
                        sent = int(prev.get("sent") or 0)
                        logger.info(
                            "youtube resumable resume from %s bytes (session %s)",
                            sent,
                            session_path.name,
                        )
                except (OSError, json.JSONDecodeError, ValueError, TypeError) as e:
                    logger.warning("youtube resume session ignore: %s", e)
                    upload_url = None
                    sent = 0

        # 1) Инициализация resumable-сессии (если нет сохранённой)
        meta: dict[str, Any] = {
            "snippet": {
                "title": (title or "untitled")[:100],
                "description": (description or "")[:5000],
                "categoryId": category_id or self.category_id,
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": self.made_for_kids,
            },
        }
        if tags:
            meta["snippet"]["tags"] = tags[:30]
        if publish_at is not None:
            meta["status"]["publishAt"] = _rfc3339(publish_at)
            meta["status"]["privacyStatus"] = "private"

        if not upload_url:
            init_headers = {
                **self._auth_headers(),
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Length": str(file_size),
                "X-Upload-Content-Type": "video/mp4",
            }
            init_url = f"{UPLOAD_API}/videos"
            init_resp = self.http.request(
                "POST",
                init_url,
                headers=init_headers,
                params={"uploadType": "resumable", "part": "snippet,status"},
                json=meta,
                idempotent=False,  # создание сессии — не ретраим слепо
                upload=True,
            )
            if init_resp.status_code not in (200, 201):
                raise self._parse_error(init_resp, "videos.insert.init")
            upload_url = init_resp.headers.get("location") or init_resp.headers.get("Location")
            if not upload_url:
                raise ModuleError(
                    ModuleErrorCode.FATAL,
                    "YouTube: resumable init без Location",
                    action="повторите; проверьте квоту и scopes",
                )
            if session_path is not None:
                try:
                    session_path.write_text(
                        json.dumps(
                            {
                                "upload_url": upload_url,
                                "file_size": file_size,
                                "sent": 0,
                                "title": title[:100],
                            },
                            ensure_ascii=False,
                        ),
                        encoding="utf-8",
                    )
                    os.chmod(session_path, 0o600)
                except OSError as e:
                    logger.warning("youtube resume session save failed: %s", e)

        # 2) Загрузка чанками
        with path.open("rb") as fh:
            if sent > 0:
                fh.seek(sent)
            while sent < file_size:
                chunk = fh.read(CHUNK_SIZE)
                if not chunk:
                    break
                start = sent
                end = sent + len(chunk) - 1
                headers = {
                    **self._auth_headers(),
                    "Content-Type": "video/mp4",
                    "Content-Length": str(len(chunk)),
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                }
                # PUT на upload_url — идемпотентен по Content-Range
                resp = self.http.request(
                    "PUT",
                    upload_url,
                    headers=headers,
                    data=chunk,
                    idempotent=True,
                    upload=True,
                )
                # 308 Resume Incomplete — норма для промежуточных чанков
                if resp.status_code in (200, 201):
                    # финальный ответ — resource
                    data = resp.json() if resp.content else {}
                    if not data.get("id"):
                        raise ModuleError(
                            ModuleErrorCode.FATAL,
                            "YouTube: upload завершён без video id",
                            action="проверьте ответ API",
                        )
                    # YT§9: uploadStatus=rejected без HTTP-ошибки
                    st = (data.get("status") or {})
                    upload_status = str(st.get("uploadStatus") or "").lower()
                    if upload_status in ("rejected", "failed"):
                        reason = st.get("rejectionReason") or upload_status
                        if session_path is not None:
                            session_path.unlink(missing_ok=True)
                        raise ModuleError(
                            ModuleErrorCode.PLATFORM_REJECTED,
                            f"YouTube: загрузка отклонена ({reason}).",
                            action="проверьте файл/метаданные; см. YouTube Studio",
                            retryable=False,
                        )
                    if session_path is not None:
                        try:
                            session_path.unlink(missing_ok=True)
                        except OSError as exc:
                            logger.debug("youtube resume session cleanup failed: %s", type(exc).__name__)
                    if notify_progress:
                        notify_progress(file_size, file_size)
                    return data
                if resp.status_code == 308:
                    sent = end + 1
                    if session_path is not None:
                        try:
                            session_path.write_text(
                                json.dumps(
                                    {
                                        "upload_url": upload_url,
                                        "file_size": file_size,
                                        "sent": sent,
                                        "title": title[:100],
                                    },
                                    ensure_ascii=False,
                                ),
                                encoding="utf-8",
                            )
                        except OSError as exc:
                            logger.debug("youtube resume session cleanup failed: %s", type(exc).__name__)
                    if notify_progress:
                        notify_progress(sent, file_size)
                    continue
                raise self._parse_error(resp, "videos.insert.chunk")

        raise ModuleError(
            ModuleErrorCode.FATAL,
            "YouTube: upload завершился без финального 200",
            action="повторите; проверьте сеть и квоту",
        )
