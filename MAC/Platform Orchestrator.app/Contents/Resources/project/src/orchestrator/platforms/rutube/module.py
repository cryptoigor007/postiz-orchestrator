from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from ..base import AuthStatus, MediaSpec, ModuleError, ModuleErrorCode, NotSupported, PlatformModule, PreparedMedia, PublishMeta, PublishStatus, RemotePage
from ..manifest import load_manifest

_MANIFEST = Path(__file__).with_name("manifest.yaml")


class RutubePartnerModule(PlatformModule):
    """Explicit partner-gated Rutube adapter.

    Rutube documents automatic upload API access as a partner capability. Without
    a live partner contract, endpoint/schema credentials are intentionally not
    fabricated and the module remains non-publishing.
    """

    def __init__(self, *, partner_token: str = "", partner_base_url: str = "", account_label: str = "", dry_run: bool = True, **_: Any) -> None:
        self.manifest = load_manifest(_MANIFEST)
        self._partner_token = str(partner_token or "").strip()
        self._partner_base_url = str(partner_base_url or "").strip()
        self._account_label = account_label or "rutube"
        self._dry_run = bool(dry_run)

    def auth_status(self) -> AuthStatus:
        if not self._partner_token or not self._partner_base_url:
            return AuthStatus(False, account=self._account_label, details="Rutube partner API contract/base URL/token required")
        return AuthStatus(False, account=self._account_label, details="Partner transport is not activated until the Rutube API contract is provisioned")

    def validate_config(self, cfg: dict[str, Any]) -> list[str]:
        return ["rutube: partner API credentials and endpoint contract must be provisioned by Rutube"]

    def prepare(self, media: MediaSpec) -> PreparedMedia:
        if str(media.kind or "video").lower() != "video":
            raise ModuleError(ModuleErrorCode.MEDIA_INVALID, "Rutube: only native video is supported")
        return PreparedMedia(path=media.path or "", kind="video")

    def publish(self, media: PreparedMedia, meta: PublishMeta):
        raise NotSupported("publish")

    def schedule_publish(self, external_id: str, when: datetime) -> bool:
        raise NotSupported("schedule_publish")

    def delete(self, external_id: str) -> bool:
        raise NotSupported("delete")

    def get_status(self, external_id: str) -> PublishStatus:
        raise NotSupported("get_status")

    def list_remote_items(self, *, kinds=None, since=None, until=None, limit: int = 50, cursor: str | None = None) -> RemotePage:
        raise NotSupported("list_remote_items")

    def update_metadata(self, external_id: str, patch: PublishMeta) -> bool:
        raise NotSupported("update_metadata")


def create_rutube_module(**deps: Any) -> RutubePartnerModule:
    return RutubePartnerModule(**deps)
