Модуль YouTube (platforms.youtube) — v2.1.1
==========================================
ТЗ: docs/modules/MODULE_YOUTUBE.txt
Стандарт: 02_MODULE_STANDARD, 03_API_STANDARDS, A5/A6/A7

Файлы:
  manifest.yaml   — capabilities, limits, module_version 2.1.1, core_min 8.5.0
  api.py          — resumable (resume_dir), thumbnails, rejected check, clear_publish_at
  module.py       — PlatformModule + clear_schedule
  token_store.py  — tokens/youtube.json + auto-refresh
  __init__.py     — create_youtube_module, YouTubeTokenStore

Включение только после P5:
  engines.youtube: "module:youtube"

Токены: broker token_provider ИЛИ локальный store + YT_CLIENT_*.
Resume: resume_dir (сессии yt_upload_*.json, 600, удаляются после успеха).
Debug HTTP: ModuleHttpClient(debug_bodies=True, debug_dir=...).

Регресс 24.09: ошибка thumbnails.set не теряет videoId/URL.
