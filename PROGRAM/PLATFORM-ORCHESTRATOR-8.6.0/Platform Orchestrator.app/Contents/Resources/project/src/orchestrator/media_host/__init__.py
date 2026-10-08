"""Временный публичный медиахостинг (B2) для Instagram/Threads.

См. docs/STORAGE-OPTIONS.md, решение Q2 (04_DECISIONS).
Ключи только из .env (B2_KEY_ID, B2_APPLICATION_KEY, B2_BUCKET, B2_ENDPOINT).
"""

from .b2 import B2MediaHost, create_media_host

__all__ = ["B2MediaHost", "create_media_host"]
