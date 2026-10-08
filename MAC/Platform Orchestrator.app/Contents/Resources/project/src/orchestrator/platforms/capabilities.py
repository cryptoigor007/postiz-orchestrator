"""Orthogonal provider capability contracts.

A provider module may implement any subset.  The core must never assume that
publishing, messaging, account identity and webhooks are the same operation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .base import AuthStatus, MediaSpec, PreparedMedia, PublishMeta, PublishResult, PublishStatus


@dataclass(frozen=True)
class ProviderHealth:
    state: str = "unknown"  # healthy|degraded|open|blocked|unknown
    reason: str = ""
    consecutive_failures: int = 0
    last_success_at: str | None = None
    last_failure_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class PublishingModule(Protocol):
    manifest: Any
    def auth_status(self) -> AuthStatus: ...
    def prepare(self, media: MediaSpec) -> PreparedMedia: ...
    def publish(self, media: PreparedMedia, meta: PublishMeta) -> PublishResult: ...
    def get_status(self, external_id: str) -> PublishStatus: ...


class MessagingModule(Protocol):
    manifest: Any
    def send_message(self, recipient: str, message: dict[str, Any]) -> dict[str, Any]: ...


class IdentityModule(Protocol):
    manifest: Any
    def auth_status(self) -> AuthStatus: ...


class WebhookModule(Protocol):
    manifest: Any
    def verify_webhook(self, headers: dict[str, str], body: bytes) -> bool: ...
    def handle_webhook(self, headers: dict[str, str], body: bytes) -> dict[str, Any]: ...


class MediaModule(Protocol):
    manifest: Any
    def upload_media(self, media: MediaSpec) -> dict[str, Any]: ...


class AnalyticsModule(Protocol):
    manifest: Any
    def get_metrics(self, external_id: str) -> dict[str, Any]: ...
