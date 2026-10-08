"""VK API client — dry-run + mockable live path."""
from __future__ import annotations

import time
from typing import Any

from ...http_client import ModuleHttpClient, mask_secrets
from ..base import ModuleError, ModuleErrorCode
from ..errors import message_for

API = "https://api.vk.com/method"


def _map(status: int, body: str, code: int | None = None) -> ModuleError:
    t = (body or "").lower()
    d = mask_secrets((body or "")[:300])
    # VK flood / rate: error codes 6, 9, 29
    if code in (6, 9, 29) or status == 429:
        m, a = message_for(ModuleErrorCode.RATE_LIMIT, d)
        return ModuleError(ModuleErrorCode.RATE_LIMIT, m, action=a, retryable=True)
    if status in (401, 403) or code in (5, 15, 17):
        m, a = message_for(ModuleErrorCode.AUTH_REQUIRED, d)
        return ModuleError(ModuleErrorCode.AUTH_REQUIRED, m, action=a)
    m, a = message_for(ModuleErrorCode.PLATFORM_REJECTED, d)
    return ModuleError(ModuleErrorCode.PLATFORM_REJECTED, m, action=a)


class VKApi:
    def __init__(
        self,
        access_token: str,
        *,
        group_id: str = "",
        http: ModuleHttpClient | None = None,
        dry_run: bool = False,
        api_version: str = "5.199",
    ) -> None:
        self.token = (access_token or "").strip()
        self.group_id = str(group_id or "").lstrip("-")
        self.dry_run = dry_run
        self.api_version = api_version
        self._http = http or ModuleHttpClient(platform="vk", module_version="0.1.0")
        self._n = 0

    def _call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.dry_run:
            self._n += 1
            return {"response": {"dry_run": True, "method": method, "n": self._n}}
        p = dict(params or {})
        p["access_token"] = self.token
        p["v"] = self.api_version
        resp = self._http.request("POST", f"{API}/{method}", data=p)
        data = resp.json() if resp.content else {}
        if resp.status_code >= 400:
            raise _map(resp.status_code, resp.text)
        if isinstance(data, dict) and "error" in data:
            err = data["error"]
            code = int(err.get("error_code") or 0)
            raise _map(resp.status_code, str(err.get("error_msg") or err), code=code)
        return data if isinstance(data, dict) else {}

    def video_save(self, title: str = "", description: str = "", wallpost: int = 0) -> dict[str, Any]:
        if self.dry_run:
            self._n += 1
            return {
                "upload_url": f"https://example.vk/upload/{self._n}",
                "video_id": self._n,
                "owner_id": f"-{self.group_id}" if self.group_id else "1",
            }
        params: dict[str, Any] = {
            "name": (title or "video")[:128],
            "description": (description or "")[:5000],
            "wallpost": wallpost,
        }
        if self.group_id:
            params["group_id"] = self.group_id
        data = self._call("video.save", params)
        return data.get("response") or data

    def wall_post(
        self,
        message: str = "",
        attachments: str = "",
        publish_date: int | None = None,
    ) -> dict[str, Any]:
        if self.dry_run:
            self._n += 1
            return {"post_id": self._n, "owner_id": f"-{self.group_id}" if self.group_id else "1"}
        params: dict[str, Any] = {"message": message or ""}
        if attachments:
            params["attachments"] = attachments
        if publish_date:
            params["publish_date"] = int(publish_date)
        if self.group_id:
            params["owner_id"] = f"-{self.group_id}"
            params["from_group"] = 1
        data = self._call("wall.post", params)
        return data.get("response") or data

    def photos_get_wall_upload_server(self) -> dict[str, Any]:
        if self.dry_run:
            return {"upload_url": "https://example.vk/photo_upload"}
        params: dict[str, Any] = {}
        if self.group_id:
            params["group_id"] = self.group_id
        data = self._call("photos.getWallUploadServer", params)
        return data.get("response") or data

    def upload_photo_file(self, upload_url: str, path: str) -> dict[str, Any]:
        """POST image bytes to VK wall photo upload_url."""
        if self.dry_run:
            self._n += 1
            return {
                "server": 1,
                "photo": f'{{"photo":"dry{self._n}"}}',
                "hash": f"dryhash{self._n}",
            }
        from pathlib import Path as P

        p = P(path)
        if not p.is_file():
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, f"file not found: {path}")
        with open(p, "rb") as fh:
            resp = self._http.request(
                "POST",
                upload_url,
                files={"photo": (p.name, fh, "image/jpeg")},
                upload=True,
                idempotent=False,
            )
        if resp.status_code >= 400:
            raise _map(resp.status_code, resp.text)
        data = resp.json() if resp.content else {}
        return data if isinstance(data, dict) else {}

    def photos_save_wall_photo(
        self, photo: str, server: int | str, hash_: str
    ) -> list[dict[str, Any]]:
        """Finalize wall photo after upload; returns list with owner_id/id."""
        if self.dry_run:
            self._n += 1
            oid = f"-{self.group_id}" if self.group_id else "1"
            return [{"id": self._n, "owner_id": int(oid) if str(oid).lstrip("-").isdigit() else 1}]
        params: dict[str, Any] = {
            "photo": photo,
            "server": server,
            "hash": hash_,
        }
        if self.group_id:
            params["group_id"] = self.group_id
        data = self._call("photos.saveWallPhoto", params)
        resp = data.get("response") or data
        if isinstance(resp, list):
            return resp
        if isinstance(resp, dict):
            return [resp]
        return []

    def upload_wall_photo(self, path: str) -> str:
        """Full wall-photo pipeline → attachment string photo{owner}_{id}."""
        server_info = self.photos_get_wall_upload_server()
        upload_url = str(server_info.get("upload_url") or "")
        if not upload_url and not self.dry_run:
            raise ModuleError(ModuleErrorCode.PLATFORM_REJECTED, "no wall photo upload_url")
        up = self.upload_photo_file(upload_url or "https://example.vk/photo_upload", path)
        saved = self.photos_save_wall_photo(
            str(up.get("photo") or ""),
            up.get("server") or 0,
            str(up.get("hash") or ""),
        )
        if not saved:
            if self.dry_run:
                self._n += 1
                oid = f"-{self.group_id}" if self.group_id else "1"
                return f"photo{oid}_{self._n}"
            raise ModuleError(ModuleErrorCode.PLATFORM_REJECTED, "photos.saveWallPhoto empty")
        item = saved[0]
        oid = item.get("owner_id")
        pid = item.get("id")
        return f"photo{oid}_{pid}"

    def video_delete(self, owner_id: str, video_id: str) -> bool:
        if self.dry_run:
            return True
        self._call("video.delete", {"owner_id": owner_id, "video_id": video_id})
        return True

    def wall_delete(self, owner_id: str, post_id: str) -> bool:
        if self.dry_run:
            return True
        self._call("wall.delete", {"owner_id": owner_id, "post_id": post_id})
        return True


    def wall_edit(self, owner_id: str, post_id: str, *, message: str = "", attachments: str = "") -> bool:
        params: dict[str,Any] = {"owner_id": owner_id, "post_id": post_id, "message": message}
        if attachments: params["attachments"] = attachments
        if self.group_id: params["from_group"] = 1
        self._call("wall.edit", params)
        return True

    def wall_get_by_id(self, posts: str) -> list[dict[str,Any]]:
        if self.dry_run:
            return [{"id":1,"owner_id":int(f"-{self.group_id}" if self.group_id else "1"),"text":"dry"}]
        data=self._call("wall.getById", {"posts": posts})
        resp=data.get("response") or data
        return list(resp or [])

    def video_get(self, videos: str) -> list[dict[str, Any]]:
        if self.dry_run:
            return [{"id": 1, "title": "dry", "player": "https://vk.com/video_dry"}]
        data = self._call("video.get", {"videos": videos})
        resp = data.get("response") or {}
        items = resp.get("items") if isinstance(resp, dict) else resp
        return list(items or [])

    def upload_video_file(self, upload_url: str, path: str) -> dict[str, Any]:
        """POST video bytes to VK upload_url returned by video.save."""
        if self.dry_run:
            self._n += 1
            return {"size": 1, "video_id": self._n, "owner_id": f"-{self.group_id}" if self.group_id else "1"}
        from pathlib import Path as P
        p = P(path)
        if not p.is_file():
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, f"file not found: {path}")
        # Multipart field name is typically "video_file"
        with open(p, "rb") as fh:
            resp = self._http.request(
                "POST",
                upload_url,
                files={"video_file": (p.name, fh, "video/mp4")},
                upload=True,
                idempotent=False,
            )
        if resp.status_code >= 400:
            raise _map(resp.status_code, resp.text)
        data = resp.json() if resp.content else {}
        return data if isinstance(data, dict) else {}
