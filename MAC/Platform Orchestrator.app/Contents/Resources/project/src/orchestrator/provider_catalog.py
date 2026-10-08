"""Load/validate the canonical provider coverage registry."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .yaml_utils import DuplicateYAMLKeyError, load_unique_yaml

CATALOG = Path(__file__).resolve().parents[2] / "docs" / "provider-catalog.yaml"


@dataclass(frozen=True)
class ProviderEntry:
    id: str
    category: str
    implementation_state: str
    live_status: str
    publish_semantics: str = ""
    live_requirements: str = ""


def load_provider_catalog(path: str | Path | None = None) -> list[ProviderEntry]:
    p = Path(path or CATALOG)
    try:
        data: dict[str, Any] = load_unique_yaml(p) or {}
    except DuplicateYAMLKeyError as exc:
        raise ValueError(f"provider catalog duplicate key: {exc}") from exc
    entries = data.get("providers") or []
    if not isinstance(entries, list):
        raise ValueError("provider catalog: providers must be a list")
    out: list[ProviderEntry] = []
    seen: set[str] = set()
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("provider catalog: each provider must be a mapping")
        pid = str(item.get("id") or "").strip().lower()
        if not pid or pid in seen:
            raise ValueError(f"provider catalog: duplicate/empty provider id {pid!r}")
        seen.add(pid)
        out.append(
            ProviderEntry(
                pid,
                str(item.get("category") or ""),
                str(item.get("implementation_state") or ""),
                str(item.get("live_status") or "NOT_LIVE"),
                str(item.get("publish_semantics") or ""),
                str(item.get("live_requirements") or ""),
            )
        )
    return out
