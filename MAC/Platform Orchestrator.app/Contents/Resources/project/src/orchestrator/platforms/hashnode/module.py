from __future__ import annotations

import os
from pathlib import Path
from typing import Any

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
    RemoteItem,
    RemotePage,
)
from ..manifest import load_manifest
from ...http_client import ModuleHttpClient

_MANIFEST = Path(__file__).with_name("manifest.yaml")


class HashnodeModule(PlatformModule):
    """Hashnode GraphQL publishing adapter for Pro publications."""

    _ENDPOINT = "https://gql.hashnode.com"

    def __init__(self, *, token: str = "", publication_id: str = "", http=None, dry_run: bool = False, **_: Any) -> None:
        self.manifest = load_manifest(_MANIFEST)
        self.token = str(token or os.getenv("HASHNODE_API_TOKEN", "")).strip()
        self.publication_id = str(publication_id or os.getenv("HASHNODE_PUBLICATION_ID", "")).strip()
        self._dry_run = bool(dry_run)
        self._http = http or ModuleHttpClient(platform="hashnode", module_version=self.manifest.module_version)

    def _require_token(self) -> str:
        if not self.token:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "Hashnode: HASHNODE_API_TOKEN is required")
        return self.token

    def _request(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        token = self._require_token()
        r = self._http.request(
            "POST",
            self._ENDPOINT,
            headers={"Authorization": token, "Content-Type": "application/json", "Accept": "application/json"},
            json={"query": query, "variables": variables or {}},
            idempotent=False,
        )
        if r.status_code >= 400:
            code = ModuleErrorCode.AUTH_EXPIRED if r.status_code in (401, 403) else ModuleErrorCode.RATE_LIMIT if r.status_code == 429 else ModuleErrorCode.TRANSIENT if r.status_code >= 500 else ModuleErrorCode.FATAL
            raise ModuleError(code, f"Hashnode GraphQL HTTP {r.status_code}", retryable=code in {ModuleErrorCode.RATE_LIMIT, ModuleErrorCode.TRANSIENT})
        payload = r.json() if r.content else {}
        errors = payload.get("errors") or []
        if errors:
            msg = str((errors[0] or {}).get("message") or "GraphQL error")
            up = msg.upper()
            if "PRO PLAN" in up or "UPGRADE" in up or "FORBIDDEN" in up:
                code = ModuleErrorCode.REVIEW_REQUIRED
            elif "UNAUTHENTICATED" in up or "UNAUTHORIZED" in up or "INVALID API" in up:
                code = ModuleErrorCode.AUTH_EXPIRED
            elif "RATE" in up or "THROTTL" in up:
                code = ModuleErrorCode.RATE_LIMIT
            else:
                code = ModuleErrorCode.PLATFORM_REJECTED
            raise ModuleError(code, f"Hashnode GraphQL: {msg}", retryable=code == ModuleErrorCode.RATE_LIMIT)
        return dict(payload.get("data") or {})

    def auth_status(self) -> AuthStatus:
        if self._dry_run:
            return AuthStatus(True, account="hashnode", details="dry-run")
        try:
            data = self._request("query { me { id username name publications(first: 10) { edges { node { id title url } } } } }")
            me = data.get("me") or {}
            if not me:
                return AuthStatus(False, account="hashnode", details="me returned null")
            pubs = ((me.get("publications") or {}).get("edges") or [])
            if not self.publication_id and pubs:
                self.publication_id = str(((pubs[0] or {}).get("node") or {}).get("id") or "")
            return AuthStatus(True, account=str(me.get("username") or me.get("name") or "hashnode"), details=f"publications={len(pubs)}")
        except ModuleError as exc:
            return AuthStatus(False, account="hashnode", details=exc.message)

    def validate_config(self, cfg: dict[str, Any]) -> list[str]:
        errs: list[str] = []
        if not self.token and not self._dry_run:
            errs.append("hashnode: HASHNODE_API_TOKEN is required")
        if not self.publication_id and not self._dry_run:
            errs.append("hashnode: HASHNODE_PUBLICATION_ID is required")
        return errs

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        return PreparedMedia(path=media.path, kind="text")

    @staticmethod
    def _tags(value: str) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        for raw in str(value or "").split():
            slug = raw.lstrip("#").strip().lower()
            if slug:
                out.append({"slug": slug})
        return out[:15]

    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult:
        if self._dry_run:
            return PublishResult(external_id="dry-hashnode", state="published")
        content = str((meta.extra or {}).get("content_markdown") or (meta.extra or {}).get("content") or meta.description or "").strip()
        title = str(meta.title or "").strip()
        if not self.publication_id:
            self.auth_status()
        if not self.publication_id:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "Hashnode: publication id is required")
        if not title or not content:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Hashnode: title and contentMarkdown are required")
        mutation = """
        mutation PublishPost($input: PublishPostInput!) {
          publishPost(input: $input) { post { id slug url } }
        }
        """
        inp: dict[str, Any] = {"publicationId": self.publication_id, "title": title, "contentMarkdown": content}
        if meta.hashtags:
            inp["tags"] = self._tags(meta.hashtags)
        extra = dict(meta.extra or {})
        for key in ("subtitle", "coverImage", "slug", "originalArticleURL", "metaTitle", "metaDescription", "ogImage"):
            if extra.get(key) is not None:
                inp[key] = str(extra[key])
        data = self._request(mutation, {"input": inp})
        post = ((data.get("publishPost") or {}).get("post") or {})
        rid = str(post.get("id") or "")
        if not rid:
            raise ModuleError(ModuleErrorCode.FATAL, "Hashnode: publish returned no post id")
        return PublishResult(external_id=rid, url=str(post.get("url") or ""), state="published")

    def update_metadata(self, external_id: str, patch: PublishMeta) -> bool:
        if self._dry_run:
            return True
        inp: dict[str, Any] = {"id": str(external_id)}
        if patch.title:
            inp["title"] = patch.title
        if patch.description:
            inp["contentMarkdown"] = patch.description
        if patch.hashtags:
            inp["tags"] = self._tags(patch.hashtags)
        extra = dict(patch.extra or {})
        for key in ("subtitle", "coverImage", "slug", "originalArticleURL", "metaTitle", "metaDescription", "ogImage", "disableComments", "isDelisted", "enableToc"):
            if extra.get(key) is not None:
                inp[key] = extra[key]
        if len(inp) == 1:
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Hashnode: update patch is empty")
        data = self._request("mutation UpdatePost($input: UpdatePostInput!) { updatePost(input: $input) { post { id } } }", {"input": inp})
        return bool((data.get("updatePost") or {}).get("post"))

    def delete(self, external_id: str) -> bool:
        if self._dry_run:
            return True
        data = self._request("mutation RemovePost($input: RemovePostInput!) { removePost(input: $input) { post { id } } }", {"input": {"id": str(external_id)}})
        return bool((data.get("removePost") or {}).get("post"))

    def get_status(self, external_id: str) -> PublishStatus:
        if self._dry_run:
            return PublishStatus(state="published")
        data = self._request("query Post($id: ID!) { post(id: $id) { id title url publishedAt updatedAt preferences { isDelisted } } }", {"id": str(external_id)})
        post = data.get("post")
        if not post:
            return PublishStatus(state="deleted")
        if ((post.get("preferences") or {}).get("isDelisted")):
            return PublishStatus(state="published", url=str(post.get("url") or ""), raw=post)
        return PublishStatus(state="published", url=str(post.get("url") or ""), raw=post)

    def list_remote_items(self, *, kinds=None, since=None, until=None, limit: int = 50, cursor: str | None = None) -> RemotePage:
        if self._dry_run:
            return RemotePage(items=[])
        if not self.publication_id:
            self.auth_status()
        if not self.publication_id:
            raise ModuleError(ModuleErrorCode.AUTH_REQUIRED, "Hashnode: publication id is required")
        query = """
        query PublicationPosts($id: ObjectId!, $first: Int!, $after: String) {
          publication(id: $id) {
            posts(first: $first, after: $after) {
              edges { cursor node { id title url brief publishedAt canonicalUrl } }
              pageInfo { hasNextPage endCursor }
            }
          }
        }
        """
        data = self._request(query, {"id": self.publication_id, "first": min(max(int(limit), 1), 50), "after": cursor})
        pub = data.get("publication") or {}
        conn = pub.get("posts") or {}
        items: list[RemoteItem] = []
        for edge in conn.get("edges") or []:
            post = (edge or {}).get("node") or {}
            if not post.get("id"):
                continue
            items.append(RemoteItem(platform="hashnode", external_id=str(post["id"]), url=str(post.get("url") or ""), title=str(post.get("title") or ""), description=str(post.get("brief") or ""), published_at=str(post.get("publishedAt") or "") or None, media_type="text", raw=post))
        page = conn.get("pageInfo") or {}
        return RemotePage(items=items, next_cursor=str(page.get("endCursor") or "") if page.get("hasNextPage") else None)


def create_module(**deps: Any) -> HashnodeModule:
    return HashnodeModule(**deps)
