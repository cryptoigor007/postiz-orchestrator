from __future__ import annotations
import os, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..messaging_http import NativeMessagingModule
from ..base import PlatformModule, PublishResult, PublishStatus, ModuleError, ModuleErrorCode, MediaSpec, PreparedMedia, PublishMeta

_MANIFEST = Path(__file__).with_name("manifest.yaml")


class BlueskyModule(NativeMessagingModule, PlatformModule):
    def __init__(self, **deps: Any) -> None:
        super().__init__(platform="bluesky", manifest_path=_MANIFEST, **deps)
        self.service = str(deps.get("service") or os.getenv("BLUESKY_SERVICE", "https://bsky.social")).rstrip("/")
        self.handle = str(deps.get("handle") or os.getenv("BLUESKY_HANDLE", "")).strip()
        self.app_password = str(deps.get("app_password") or os.getenv("BLUESKY_APP_PASSWORD", "")).strip()
        self._session: dict[str, Any] | None = None
        self._session_at = 0.0

    def _login(self, force: bool = False) -> dict[str, Any]:
        if self._session and not force and time.time() - self._session_at < 240:
            return self._session
        if not self.handle or not self.app_password:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "bluesky: BLUESKY_HANDLE and BLUESKY_APP_PASSWORD are required")
        resp = self._http.request(
            "POST", f"{self.service}/xrpc/com.atproto.server.createSession",
            json={"identifier": self.handle, "password": self.app_password}, idempotent=False,
        )
        data = self._json_or_error(resp)
        self._session, self._session_at = data, time.time()
        return data

    def _request_authed(self, method: str, url: str, **kwargs: Any):
        sess = self._login()
        headers = dict(kwargs.pop("headers", {}) or {})
        headers["Authorization"] = f"Bearer {sess.get('accessJwt', '')}"
        resp = self._http.request(method, url, headers=headers, **kwargs)
        if resp.status_code == 401:
            sess = self._login(force=True)
            headers["Authorization"] = f"Bearer {sess.get('accessJwt', '')}"
            resp = self._http.request(method, url, headers=headers, **kwargs)
        return resp

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        if media.kind == "text":
            return PreparedMedia(media.path, "text")
        if not Path(media.path).is_file():
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, f"bluesky: file not found: {media.path}")
        return PreparedMedia(media.path, media.kind)

    def _upload_blob(self, path: str) -> dict[str, Any]:
        p = Path(path)
        mime = "image/jpeg" if p.suffix.lower() in {".jpg", ".jpeg"} else "image/png" if p.suffix.lower() == ".png" else "application/octet-stream"
        resp = self._request_authed("POST", f"{self.service}/xrpc/com.atproto.repo.uploadBlob", headers={"Content-Type": mime}, data=p.read_bytes(), idempotent=False)
        return self._json_or_error(resp).get("blob") or {}

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        sess = self._login()
        extra = meta.extra or {}
        text = str(extra.get("status") or meta.description or meta.title or "").strip()
        if not text:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "bluesky: post text is required")
        record: dict[str, Any] = {
            "$type": "app.bsky.feed.post",
            "text": text,
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        alt = str(extra.get("alt") or meta.title or "")
        if media.kind == "image" and media.path:
            blob = self._upload_blob(media.path)
            record["embed"] = {"$type": "app.bsky.embed.images", "images": [{"alt": alt, "image": blob}]}
        resp = self._request_authed("POST", f"{self.service}/xrpc/com.atproto.repo.createRecord", json={"repo": sess.get("did"), "collection": "app.bsky.feed.post", "record": record}, idempotent=False)
        data = self._json_or_error(resp)
        uri = str(data.get("uri") or "")
        if not uri:
            raise ModuleError(ModuleErrorCode.FATAL, "bluesky: createRecord returned no URI")
        return PublishResult(external_id=uri, url=f"https://bsky.app/profile/{self.handle}/post/{uri.rsplit('/', 1)[-1]}", state="published")

    def get_status(self, external_id: str) -> PublishStatus:
        if not external_id:
            return PublishStatus(state="unknown")
        resp = self._request_authed("GET", f"{self.service}/xrpc/app.bsky.feed.getPosts", params={"uris": external_id})
        data = self._json_or_error(resp)
        posts = data.get("posts") or []
        if not posts:
            return PublishStatus(state="deleted")
        post = posts[0]
        return PublishStatus(state="published", url=str(post.get("uri") or ""), raw=post)

    def delete(self, external_id: str) -> bool:
        sess = self._login()
        parts = external_id.split("/")
        rkey = parts[-1] if parts else ""
        resp = self._request_authed("POST", f"{self.service}/xrpc/com.atproto.repo.deleteRecord", json={"repo": sess.get("did"), "collection": "app.bsky.feed.post", "rkey": rkey}, idempotent=False)
        self._json_or_error(resp) if resp.content else {}
        return True


def create_module(**deps: Any) -> BlueskyModule:
    return BlueskyModule(**deps)
