#!/usr/bin/env python3
"""Удаление тестовых роликов ([orch-test]) через нативный YouTube module.

Безопасность:
  - по умолчанию dry-run;
  - удаляются только заголовки с test_publish.title_prefix;
  - токен разрешается через единый auth_tokens path (broker → account-scoped store);
  - штатный PlatformModule используется и для list, и для delete.

Использование (на сервере, из /opt/orchestrator):
    ./venv/bin/python scripts/yt_cleanup_test_videos.py
    ./venv/bin/python scripts/yt_cleanup_test_videos.py --yes
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.auth_tokens import get_access_token  # noqa: E402
from orchestrator.config import load_config  # noqa: E402
from orchestrator.platforms.youtube import create_youtube_module  # noqa: E402


def _load_env(path: str = ".env") -> None:
    p = Path(path)
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--yes", action="store_true", help="реально удалить (иначе dry-run)")
    ap.add_argument("--max", type=int, default=25)
    args = ap.parse_args(argv)

    _load_env()
    cfg = load_config(args.config)
    yt_cfg = cfg.platforms.get("youtube") if isinstance(cfg.platforms, dict) else None
    account_id = str(
        getattr(yt_cfg, "account_id", "")
        or getattr(yt_cfg, "integration_id", "")
        or ""
    ) if yt_cfg is not None else ""

    def token_provider() -> str:
        return get_access_token("youtube", account_id=account_id)

    mod = create_youtube_module(
        cfg=cfg,
        token_provider=token_provider,
        dry_run=False,
    )

    prefix = (cfg.test_publish.title_prefix or "[orch-test] ").strip()
    page = mod.list_remote_items(limit=max(1, min(int(args.max), 50)))
    candidates = [
        item for item in page.items
        if (item.title or "").startswith(prefix) and item.external_id
    ]
    if not candidates:
        print("тестовых роликов не найдено")
        return 0

    for item in candidates:
        action = "DELETE" if args.yes else "would delete"
        print(f"{action} {item.external_id} | {item.title}")
        if args.yes:
            mod.delete(str(item.external_id))

    if not args.yes:
        print(f"\nнайдено {len(candidates)}; повторите с --yes для удаления")
    else:
        print(f"\nудалено {len(candidates)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
