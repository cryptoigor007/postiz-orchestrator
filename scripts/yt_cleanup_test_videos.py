#!/usr/bin/env python3
"""Удаление тестовых роликов ([orch-test]) с YouTube-канала через token broker + direct engine.

Безопасность:
  - по умолчанию dry-run (только показать найденное);
  - удаляются ТОЛЬКО заголовки, начинающиеся с test_publish.title_prefix (по умолчанию "[orch-test] ");
  - OAuth-токен берётся у token broker и при необходимости рефрешится (Postiz рефрешит лениво).

Использование (на сервере, из /opt/orchestrator):
    ./venv/bin/python scripts/yt_cleanup_test_videos.py            # dry-run
    ./venv/bin/python scripts/yt_cleanup_test_videos.py --yes      # удалить
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.config import load_config  # noqa: E402
from orchestrator.engines.direct_youtube import YouTubeEngine  # noqa: E402
from orchestrator.engines.token_broker_client import TokenBrokerClient  # noqa: E402


def _load_env(path: str = ".env") -> None:
    p = Path(path)
    if not p.is_file():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k, v)


def _fresh_token(broker_url: str, broker_secret: str) -> str:
    d = TokenBrokerClient(broker_url, broker_secret).get("youtube")
    body = urllib.parse.urlencode({
        "client_id": d.get("client_id", ""),
        "client_secret": d.get("client_secret", ""),
        "refresh_token": d.get("refresh_token", ""),
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=body)
    with urllib.request.urlopen(req, timeout=20) as r:
        fresh = json.load(r).get("access_token")
    if not fresh:
        raise RuntimeError("refresh не вернул access_token")
    return fresh


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--yes", action="store_true", help="реально удалить (иначе dry-run)")
    ap.add_argument("--max", type=int, default=25)
    args = ap.parse_args(argv)

    _load_env()
    cfg = load_config(args.config)
    prefix = (cfg.test_publish.title_prefix or "[orch-test] ").strip()
    token = _fresh_token(os.getenv("TOKEN_BROKER_URL", ""), os.getenv("TOKEN_BROKER_SECRET", ""))
    eng = YouTubeEngine(token_provider=lambda: token)

    candidates = [u for u in eng.list_uploads({"max_results": args.max})
                  if (u.get("title") or "").startswith(prefix)]
    if not candidates:
        print("тестовых роликов не найдено")
        return 0
    for u in candidates:
        print(f"{'DELETE' if args.yes else 'would delete'} {u.get('external_id')} | {u.get('title')}")
        if args.yes:
            eng.delete(str(u.get("external_id")))
    if not args.yes:
        print(f"\nнайдено {len(candidates)}; повторите с --yes для удаления")
    else:
        print(f"\nудалено {len(candidates)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
