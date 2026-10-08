"""Provider API version/deprecation registry used by health and CI tooling."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class ApiVersionRecord:
    provider: str
    version: str
    released_at: date | None = None
    sunset_at: date | None = None
    source_url: str = ""

    def status(self, today: date | None = None) -> str:
        today = today or date.today()
        if self.sunset_at and today > self.sunset_at:
            return "SUNSET"
        if self.sunset_at and (self.sunset_at - today).days <= 30:
            return "SUNSET_SOON"
        return "ACTIVE"


# These are the versions/dates recorded in the 2026-10-01 architecture review.
# Provider-specific runtime code may override a version only when its documented
# endpoint requires it; CI should compare this registry with manifests.
REGISTRY: dict[str, ApiVersionRecord] = {
    "meta": ApiVersionRecord("meta", "v26.0", date(2026, 7, 29), None, "https://developers.facebook.com/docs/graph-api/"),
    "meta-legacy-v21": ApiVersionRecord("meta", "v21.0", None, date(2027, 1, 21), "https://developers.facebook.com/docs/graph-api/changelog/"),
    "threads": ApiVersionRecord("threads", "v1.0", None, None, "https://www.postman.com/meta/threads/overview"),
}


def get_record(provider: str) -> ApiVersionRecord | None:
    key = str(provider or "").strip().lower()
    return REGISTRY.get(key)


def validate_no_sunset(records: dict[str, ApiVersionRecord] | None = None, today: date | None = None) -> list[str]:
    errors: list[str] = []
    for key, rec in (records or REGISTRY).items():
        if rec.status(today) == "SUNSET":
            errors.append(f"{key}:{rec.version} is past sunset ({rec.sunset_at.isoformat() if rec.sunset_at else 'unknown'})")
    return errors
