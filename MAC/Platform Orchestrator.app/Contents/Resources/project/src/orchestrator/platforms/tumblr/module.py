from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from ..base import (
    AuthStatus,
    MediaSpec,
    ModuleError,
    ModuleErrorCode,
    PlatformModule,
    PreparedMedia,
    PublishMeta,
    PublishResult,
    PublishStatus,
)
from ..manifest import load_manifest
from ...http_client import ModuleHttpClient

_MANIFEST = Path(__file__).with_name("manifest.yaml")


def _pct(value: Any) -> str:
    return quote(str(value), safe="~-._")


class TumblrModule(PlatformModule):
    """Tumblr v2 OAuth1a adapter for text posts and post lifecycle."""

    def __init__(self, **deps: Any) -> None:
        self.manifest = load_manifest(_MANIFEST)
        self.base = str(deps.get("base_url") or os.getenv("TUMBLR_API_BASE", "https://api.tumblr.com/v2")).rstrip("/")
        self.consumer_key = str(deps.get("consumer_key") or os.getenv("TUMBLR_CONSUMER_KEY", "")).strip()
        self.consumer_secret = str(deps.get("consumer_secret") or os.getenv("TUMBLR_CONSUMER_SECRET", "")).strip()
        self.token = str(deps.get("token") or os.getenv("TUMBLR_OAUTH_TOKEN", "")).strip()
        self.token_secret = str(deps.get("token_secret") or os.getenv("TUMBLR_OAUTH_TOKEN_SECRET", "")).strip()
        self.blog = str(deps.get("blog") or os.getenv("TUMBLR_BLOG", "")).strip()
        self._http = deps.get("http") or ModuleHttpClient(platform="tumblr", module_version=self.manifest.module_version)

    def _oauth_headers(self, method: str, url: str, params: dict[str, Any] | None = None) -> dict[str, str]:
        body_params = {str(k): str(v) for k, v in (params or {}).items()}
        oauth = {
            "oauth_consumer_key": self.consumer_key,
            "oauth_nonce": base64.urlsafe_b64encode(os.urandom(12)).decode().rstrip("="),
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": str(int(time.time())),
            "oauth_token": self.token,
            "oauth_version": "1.0",
        }
        all_params = {**body_params, **oauth}
        pairs = sorted((_pct(k), _pct(v)) for k, v in all_params.items())
        normalized = "&".join(f"{k}={v}" for k, v in pairs)
        base_string = "&".join([method.upper(), _pct(url), _pct(normalized)])
        signing_key = f"{_pct(self.consumer_secret)}&{_pct(self.token_secret)}"
        oauth["oauth_signature"] = base64.b64encode(
            hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
        ).decode()
        auth = "OAuth " + ", ".join(
            f'{_pct(k)}="{_pct(v)}"' for k, v in sorted(oauth.items())
        )
        return {"Authorization": auth}

    @staticmethod
    def _error(status_code: int, operation: str) -> ModuleError:
        if status_code in (401, 403):
            code = ModuleErrorCode.AUTH_EXPIRED
        elif status_code == 429:
            code = ModuleErrorCode.RATE_LIMIT
        elif status_code >= 500:
            code = ModuleErrorCode.TRANSIENT
        else:
            code = ModuleErrorCode.PLATFORM_REJECTED
        return ModuleError(code, f"Tumblr {operation} HTTP {status_code}", retryable=code in {ModuleErrorCode.RATE_LIMIT, ModuleErrorCode.TRANSIENT})

    def auth_status(self) -> AuthStatus:
        missing = self.validate_config({})
        if missing:
            return AuthStatus(False, account=self.blog or "tumblr", details="; ".join(missing))
        url = f"{self.base}/user/info"
        response = self._http.request("GET", url, headers=self._oauth_headers("GET", url))
        if response.status_code >= 400:
            return AuthStatus(False, account=self.blog or "tumblr", details=f"user/info HTTP {response.status_code}")
        data = response.json() if response.content else {}
        user = (data.get("response") or {}).get("user") or {}
        return AuthStatus(True, account=str(user.get("name") or self.blog or "tumblr"), details="user/info ok")

    def validate_config(self, cfg: dict[str, Any]) -> list[str]:
        return [
            name
            for name, value in (
                ("TUMBLR_CONSUMER_KEY", self.consumer_key),
                ("TUMBLR_CONSUMER_SECRET", self.consumer_secret),
                ("TUMBLR_OAUTH_TOKEN", self.token),
                ("TUMBLR_OAUTH_TOKEN_SECRET", self.token_secret),
                ("TUMBLR_BLOG", self.blog),
            )
            if not value
        ]

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        if (media.kind or "text") != "text":
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Tumblr: this native module currently supports text posts only")
        return PreparedMedia(path=media.path, kind="text")

    def _post_request(self, endpoint: str, body: dict[str, Any], operation: str):
        url = f"{self.base}/blog/{quote(self.blog, safe='')}/{endpoint}"
        response = self._http.request(
            "POST",
            url,
            headers={**self._oauth_headers("POST", url, body), "Content-Type": "application/x-www-form-urlencoded"},
            data=urlencode(body).encode(),
            idempotent=False,
        )
        if response.status_code >= 400:
            raise self._error(response.status_code, operation)
        payload = response.json() if response.content else {}
        meta = payload.get("meta") or {}
        if meta and int(meta.get("status") or 200) >= 400:
            raise self._error(int(meta["status"]), operation)
        return payload

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        if not self.blog:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "Tumblr: blog is required")
        body: dict[str, Any] = {
            "type": "text",
            "title": meta.title or "",
            "body": str(meta.description or ""),
        }
        extra = dict(meta.extra or {})
        if extra.get("tags") or meta.hashtags:
            body["tags"] = str(extra.get("tags") or meta.hashtags).replace(",", " ")
        payload = self._post_request("post", body, "publish")
        response = payload.get("response") or {}
        external_id = str(response.get("id") or response.get("id_string") or "")
        if not external_id:
            raise ModuleError(ModuleErrorCode.FATAL, "Tumblr: post response without id")
        return PublishResult(external_id=external_id, url=str(response.get("post_url") or ""), state="published")

    def update_metadata(self, external_id: str, patch: PublishMeta) -> bool:
        body: dict[str, Any] = {"id": str(external_id), "type": "text"}
        if patch.title:
            body["title"] = patch.title
        if patch.description:
            body["body"] = patch.description
        extra = dict(patch.extra or {})
        if extra.get("tags") or patch.hashtags:
            body["tags"] = str(extra.get("tags") or patch.hashtags).replace(",", " ")
        self._post_request("post/edit", body, "update")
        return True

    def get_status(self, external_id: str) -> PublishStatus:
        url = f"{self.base}/blog/{quote(self.blog, safe='')}/posts"
        params = {"id": str(external_id)}
        response = self._http.request("GET", url, headers=self._oauth_headers("GET", url, params), params=params)
        if response.status_code >= 400:
            if response.status_code == 404:
                return PublishStatus(state="deleted")
            raise self._error(response.status_code, "get post")
        payload = response.json() if response.content else {}
        posts = ((payload.get("response") or {}).get("posts") or [])
        if not posts:
            return PublishStatus(state="deleted")
        post = posts[0]
        return PublishStatus(state="published", url=str(post.get("post_url") or ""), raw=post)

    def delete(self, external_id: str) -> bool:
        body = {"id": str(external_id)}
        self._post_request("post/delete", body, "delete")
        return True


def create_module(**deps: Any) -> TumblrModule:
    return TumblrModule(**deps)
