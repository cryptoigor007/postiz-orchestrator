from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from ..base import (
    AuthStatus,
    MediaSpec,
    ModuleError,
    ModuleErrorCode,
    NotSupported,
    PlatformModule,
    PreparedMedia,
    PublishMeta,
    PublishResult,
    PublishStatus,
    RemoteItem,
    RemotePage,
)
from ..manifest import load_manifest
from ...http_client import ModuleHttpClient

_MANIFEST = Path(__file__).with_name("manifest.yaml")


class WeChatModule(PlatformModule):
    """WeChat Official Account server-side article publication module."""

    def __init__(self, **deps: Any) -> None:
        self.manifest = load_manifest(_MANIFEST)
        self.base = str(deps.get("base_url") or os.getenv("WECHAT_API_BASE", "https://api.weixin.qq.com")).rstrip("/")
        self.app_id = str(deps.get("app_id") or os.getenv("WECHAT_APP_ID", "")).strip()
        self.app_secret = str(deps.get("app_secret") or os.getenv("WECHAT_APP_SECRET", "")).strip()
        self._token_value = str(deps.get("access_token") or os.getenv("WECHAT_ACCESS_TOKEN", "")).strip()
        self._token_expires_at = float(deps.get("access_token_expires_at") or 0)
        self._http = deps.get("http") or ModuleHttpClient(platform="wechat", module_version=self.manifest.module_version)

    def validate_config(self, cfg: dict[str, Any]) -> list[str]:
        if self._token_value:
            return []
        errors: list[str] = []
        if not self.app_id:
            errors.append("wechat: WECHAT_APP_ID is required")
        if not self.app_secret:
            errors.append("wechat: WECHAT_APP_SECRET is required")
        return errors

    @staticmethod
    def _error(errcode: int, errmsg: str, operation: str) -> ModuleError:
        if errcode in (40001, 40014, 42001):
            code = ModuleErrorCode.AUTH_EXPIRED
        elif errcode in (48001, 48004):
            code = ModuleErrorCode.REVIEW_REQUIRED
        elif errcode in (45009, 45011):
            code = ModuleErrorCode.QUOTA
        elif errcode in (45009, 45038):
            code = ModuleErrorCode.RATE_LIMIT
        elif errcode >= 50000:
            code = ModuleErrorCode.TRANSIENT
        else:
            code = ModuleErrorCode.PLATFORM_REJECTED
        return ModuleError(code, f"WeChat {operation} errcode={errcode}: {errmsg}", retryable=code in {ModuleErrorCode.RATE_LIMIT, ModuleErrorCode.TRANSIENT, ModuleErrorCode.AUTH_EXPIRED})

    def _json(self, method: str, path: str, *, token: bool = True, **kwargs: Any):
        params = dict(kwargs.pop("params", {}) or {})
        if token:
            params["access_token"] = self._access_token()
        return self._http.request(method, f"{self.base}{path}", params=params, **kwargs)

    def _access_token(self, force: bool = False) -> str:
        if self._token_value and not force and time.time() < self._token_expires_at - 300:
            return self._token_value
        if not self.app_id or not self.app_secret:
            if self._token_value:
                return self._token_value
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "WeChat: configure WECHAT_APP_ID/WECHAT_APP_SECRET or WECHAT_ACCESS_TOKEN")
        response = self._http.request(
            "GET",
            f"{self.base}/cgi-bin/token",
            params={"grant_type": "client_credential", "appid": self.app_id, "secret": self.app_secret},
        )
        data = response.json() if response.content else {}
        if response.status_code >= 400 or int(data.get("errcode") or 0) != 0:
            raise self._error(int(data.get("errcode") or response.status_code or 500), str(data.get("errmsg") or "token request failed"), "access token")
        token = str(data.get("access_token") or "")
        if not token:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "WeChat: token endpoint returned no access_token")
        self._token_value = token
        self._token_expires_at = time.time() + float(data.get("expires_in") or 7200)
        return token

    def _check_response(self, response: Any, operation: str) -> dict[str, Any]:
        data = response.json() if response.content else {}
        errcode = int(data.get("errcode") or 0)
        if response.status_code >= 400 or errcode != 0:
            if errcode in (40001, 40014, 42001) and self.app_id and self.app_secret:
                self._token_value = ""
            raise self._error(errcode or response.status_code, str(data.get("errmsg") or "HTTP error"), operation)
        return data

    def auth_status(self) -> AuthStatus:
        try:
            token = self._access_token()
            response = self._http.request("GET", f"{self.base}/cgi-bin/draft/count", params={"access_token": token})
            data = self._check_response(response, "draft/count")
            return AuthStatus(True, account=self.app_id or "wechat", details=f"draft_count={data.get('total', 0)}")
        except ModuleError as exc:
            return AuthStatus(False, account=self.app_id or "wechat", details=exc.message)

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        if (media.kind or "text") != "text":
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "WeChat Official Account: this module publishes HTML articles only")
        return PreparedMedia(path=media.path, kind="text")

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        extra = dict(meta.extra or {})
        title = str(extra.get("wechat_title") or meta.title or "").strip()
        content = str(extra.get("content_html") or extra.get("content") or meta.description or "").strip()
        thumb_media_id = str(extra.get("thumb_media_id") or extra.get("cover_media_id") or "").strip()
        if not title or not content:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "WeChat: title and HTML content are required")
        if not thumb_media_id:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "WeChat: thumb_media_id is required for a news draft")
        article = {
            "article_type": "news",
            "title": title,
            "author": str(extra.get("author") or ""),
            "digest": str(extra.get("digest") or meta.description or "")[:128],
            "content": content,
            "content_source_url": str(extra.get("content_source_url") or ""),
            "thumb_media_id": thumb_media_id,
            "need_open_comment": int(bool(extra.get("need_open_comment", False))),
            "only_fans_can_comment": int(bool(extra.get("only_fans_can_comment", False))),
        }
        response = self._json("POST", "/cgi-bin/draft/add", headers={"Content-Type": "application/json"}, json={"articles": [article]}, idempotent=False)
        data = self._check_response(response, "draft/add")
        media_id = str(data.get("media_id") or "")
        if not media_id:
            raise ModuleError(ModuleErrorCode.FATAL, "WeChat: draft/add returned no media_id")
        response = self._json("POST", "/cgi-bin/freepublish/submit", headers={"Content-Type": "application/json"}, json={"media_id": media_id}, idempotent=False)
        data = self._check_response(response, "freepublish/submit")
        publish_id = str(data.get("publish_id") or "")
        if not publish_id:
            raise ModuleError(ModuleErrorCode.FATAL, "WeChat: freepublish/submit returned no publish_id")
        return PublishResult(external_id=publish_id, state="uploaded", url="")

    def get_status(self, external_id: str) -> PublishStatus:
        response = self._json("POST", "/cgi-bin/freepublish/get", headers={"Content-Type": "application/json"}, json={"publish_id": str(external_id)})
        data = self._check_response(response, "freepublish/get")
        status = int(data.get("publish_status") if data.get("publish_status") is not None else -1)
        if status == 0:
            article_url = ""
            detail = data.get("article_detail") or {}
            items = detail.get("item") or []
            if items and isinstance(items[0], dict):
                article_url = str(items[0].get("article_url") or "")
            return PublishStatus(state="published", url=article_url, raw=data)
        if status in (1,):
            return PublishStatus(state="processing", raw=data)
        if status == 5:
            return PublishStatus(state="deleted", raw=data)
        if status in (2, 3, 4, 6):
            return PublishStatus(state="failed", error=str(data.get("fail_reason") or data.get("errmsg") or "publish failed"), raw=data)
        return PublishStatus(state="unknown", raw=data)

    def delete(self, external_id: str) -> bool:
        # The published-content delete endpoint expects article_id, not publish_id.
        raw = str(external_id).strip()
        if raw.startswith("publish:"):
            publish_id = raw.split(":", 1)[1].strip()
            status = self.get_status(publish_id)
            article_id = str(status.raw.get("article_id") or "")
            if not article_id:
                detail = status.raw.get("article_detail") or {}
                items = detail.get("item") or []
                if items and isinstance(items[0], dict):
                    article_id = str(items[0].get("article_id") or "")
            if not article_id:
                raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "WeChat: publish id has not produced an article_id yet")
        else:
            article_id = raw.removeprefix("article:").strip()
        if not article_id:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "WeChat: article_id is required for delete")
        response = self._json("POST", "/cgi-bin/freepublish/delete", headers={"Content-Type": "application/json"}, json={"article_id": article_id}, idempotent=False)
        self._check_response(response, "freepublish/delete")
        return True

    def list_remote_items(self, *, kinds=None, since=None, until=None, limit: int = 50, cursor: str | None = None) -> RemotePage:
        offset = int(cursor or 0) if str(cursor or "").isdigit() else 0
        response = self._json("POST", "/cgi-bin/freepublish/batchget", headers={"Content-Type": "application/json"}, json={"offset": offset, "count": min(max(1, int(limit)), 20)}, idempotent=False)
        data = self._check_response(response, "freepublish/batchget")
        rows = data.get("item") or []
        items: list[RemoteItem] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            content = row.get("content") or {}
            articles = content.get("news_item") or []
            first = articles[0] if articles else {}
            items.append(
                RemoteItem(
                    platform="wechat",
                    external_id=str(row.get("article_id") or row.get("media_id") or ""),
                    url=str(first.get("url") or ""),
                    title=str(first.get("title") or ""),
                    description=str(first.get("digest") or ""),
                    published_at=None,
                    status="published",
                    media_type="text",
                    raw=row,
                )
            )
        total_count = int(data.get("total_count") or 0)
        next_offset = offset + len(rows)
        next_cursor = str(next_offset) if rows and next_offset < total_count else None
        return RemotePage(items=items, next_cursor=next_cursor)

    def update_metadata(self, external_id: str, patch: PublishMeta) -> bool:
        raise NotSupported("update_metadata: published WeChat articles are managed through draft media_id before publication")


def create_module(**deps: Any) -> WeChatModule:
    return WeChatModule(**deps)
