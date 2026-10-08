# Platform Orchestrator — Complete Functional Reference

Generated from the audited source tree on 2026-10-01. This document describes what the current code actually exposes; historical roadmap documents are not treated as runtime truth.

## 0. Release/audit baseline

- Version: `8.6.0`
- Provider modules: **42**
- Provider manifests: **42**
- Pytest: **887 passed / 5 skipped**
- `gate_platform_zero.sh`: **126 passed**
- `gate_social_architecture.sh`: **PASS**
- Strict `DeprecationWarning -> error`: **887 passed / 5 skipped**
- AST parse + `compileall`: **PASS**

## 1. Runtime architecture

- `main.py`: CLI entrypoint and dependency composition.
- `runner.py`: long-running orchestration loop.
- `watcher.py`: discovers source media.
- `scheduler.py` / `slots.py`: schedules long videos, thematic shorts, standalone shorts.
- `publisher.py`: native module publish path, idempotency, safety, durable integration.
- `status_sync.py` / `reconciliation.py` / `consistency.py`: local↔remote state repair.
- `outbox.py` / `durable_jobs.py`: transactional events and restart-safe jobs.
- `media_transfer.py`: common media ingest, hashing, chunking, SSRF URL boundary.
- `provider_supervisor.py`: account/provider isolation, health, circuit state.
- `token_lifecycle.py` / `auth_tokens.py`: account-scoped credentials lifecycle.
- `webhook_ingress.py` / `webhook_processor.py`: verified event intake and replay/DLQ flow.
- `webapp_api.py`: HTTP control plane.
- `telegram_bot.py` / `telegram_transport.py`: bot command plane and long polling.
- `mcp_server.py`: MCP integration for external AI clients.

## 2. CLI options

| Option | Purpose |
|---|---|
| `--pidfile` | default=''; single-instance pidfile path |
| `--no-pidfile` | action=store_true; disable pidfile lock |
| `--config` | default='config.yaml' |
| `--db` | default='data/data.sqlite' |
| `--dry-run` | action=store_true |
| `--read-only` | action=store_true |
| `--watch-roots` |  |
| `--once` | action=store_true |
| `--scan` | action=store_true |
| `--schedule` | action=store_true |
| `--sync` | action=store_true |
| `--reconcile` | action=store_true |
| `--backup` | action=store_true |
| `--test-schedule` | action=store_true; Пробный пост: --test-platform P --test-entity TYPE:ID [--test-delay N] [--test-dry-run] |
| `--test-platform` | default='' |
| `--test-entity` | default=''; short:123 | long_video:45 |
| `--test-delay` | type=int; default=None |
| `--test-dry-run` | action=store_true |
| `--version` | action=store_true |
| `--daemon` | action=store_true; Run continuous loop |
| `--remote-scan` | action=store_true; Run remote inventory scan |
| `--claims` | action=store_true; Run YouTube claims checkpoint |
| `--b2-cleanup` | action=store_true; Run B2 TTL cleanup |
| `--health-port` | type=int; default=8080 |

## 3. Configuration keys

- `schedules`
- `schedules.long_video`
- `schedules.long_video.type`
- `schedules.long_video.source`
- `schedules.long_video.days`
- `schedules.long_video.time`
- `schedules.long_video.exception_days`
- `schedules.shorts_thematic`
- `schedules.shorts_thematic.type`
- `schedules.shorts_thematic.source`
- `schedules.shorts_thematic.default_time`
- `schedules.shorts_standalone`
- `schedules.shorts_standalone.type`
- `schedules.shorts_standalone.source`
- `schedules.shorts_standalone.days`
- `schedules.shorts_standalone.times`
- `schedules.shorts_standalone.exception_days`
- `platforms`
- `platforms.telegram`
- `platforms.telegram.post_mode`
- `platforms.telegram.send_via`
- `platforms.telegram.publish_chat_id`
- `platforms.telegram.link_preview_above`
- `platforms.telegram.video_variant`
- `platforms.telegram.audio_profile`
- `platforms.telegram.enabled`
- `platforms.telegram.daily_limit`
- `platforms.telegram.account_id`
- `platforms.telegram.channel_id`
- `platforms.youtube`
- `platforms.youtube.video_variant`
- `platforms.youtube.audio_profile`
- `platforms.youtube.enabled`
- `platforms.youtube.daily_limit`
- `platforms.youtube.account_id`
- `platforms.youtube.channel_id`
- `platforms.instagram`
- `platforms.instagram.video_variant`
- `platforms.instagram.audio_profile`
- `platforms.instagram.enabled`
- `platforms.instagram.daily_limit`
- `platforms.instagram.account_id`
- `platforms.instagram.channel_id`
- `platforms.instagram.graph_version`
- `platforms.tiktok`
- `platforms.tiktok.video_variant`
- `platforms.tiktok.audio_profile`
- `platforms.tiktok.enabled`
- `platforms.tiktok.daily_limit`
- `platforms.tiktok.account_id`
- `platforms.tiktok.channel_id`
- `platforms.facebook`
- `platforms.facebook.video_variant`
- `platforms.facebook.audio_profile`
- `platforms.facebook.enabled`
- `platforms.facebook.daily_limit`
- `platforms.facebook.account_id`
- `platforms.facebook.channel_id`
- `platforms.facebook.graph_version`
- `platforms.threads`
- `platforms.threads.video_variant`
- `platforms.threads.audio_profile`
- `platforms.threads.enabled`
- `platforms.threads.daily_limit`
- `platforms.threads.account_id`
- `platforms.threads.channel_id`
- `platforms.vk`
- `platforms.vk.enabled`
- `platforms.vk.daily_limit`
- `platforms.vk.min_interval_sec`
- `platforms.vk.group_id`
- `platforms.vk.account_id`
- `platforms.vk.modes`
- `platforms.vk.content_kind_default`
- `platforms.vk.video_variant`
- `platforms.x`
- `platforms.x.enabled`
- `platforms.x.daily_limit`
- `platforms.x.min_interval_sec`
- `platforms.x.account_id`
- `platforms.x.content_kind_default`
- `platforms.x.max_chars`
- `platforms.rutube`
- `platforms.rutube.enabled`
- `platforms.rutube.daily_limit`
- `platforms.rutube.account_id`
- `platforms.rutube.content_kind_default`
- `tail`
- `tail.soft_enter_days`
- `tail.series_end_question_ttl_days`
- `tail.series_end_question_cooldown_days`
- `tail.use_all_short_slots`
- `tail.pause_standalone_during_tail`
- `tail.ask_minutes_before`
- `tail.reminder_minutes_before`
- `tail.default_action`
- `limits`
- `limits.max_posts_per_distribute`
- `limits.module_create_per_hour`
- `limits.max_shorts_per_long_video`
- `limits.overflow_move_files`
- `link_update`
- `link_update.release_url_timeout_min`
- `link_update.missing_url_dialog_ttl_hours`
- `link_update.missing_url_default_action`
- `link_update.placeholder_text`
- `description_templates`
- `description_templates.x_promo`
- `description_templates.vk_promo`
- `description_templates.telegram_link`
- `description_templates.telegram_link_no_link`
- `description_templates.thematic_short`
- `description_templates.thematic_short_no_link`
- `description_templates.default`
- `safety`
- `safety.min_interval_minutes`
- `safety.conflict_window_minutes`
- `safety.jitter_seconds`
- `safety.warmup_days`
- `safety.warmup_daily_limit`
- `safety.warmup_after_pause_hours`
- `safety.on_serious_error`
- `safety.on_serious_error.action`
- `safety.on_serious_error.pause_hours`
- `safety.on_serious_error.notify`
- `safety.serious_errors`
- `safety.rate_limit_errors`
- `safety.auth_errors`
- `telegram`
- `telegram.allowed_chat_ids`
- `default_project`
- `projects`
- `projects.tochka`
- `projects.tochka.title`
- `projects.tochka.series_ids`
- `projects.tochka.folders`
- `projects.tochka.telegram_chat_ids`
- `projects.project2`
- `projects.project2.title`
- `projects.project2.series_ids`
- `projects.project2.folders`
- `projects.project2.telegram_chat_ids`
- `media`
- `media.symlink_mode`
- `media.local_prefix`
- `media.cache_dir`
- `media.telegram_max_mb`
- `backup`
- `backup.enabled`
- `backup.interval_hours`
- `backup.keep_days`
- `backup.method`
- `reconciliation_interval_hours`
- `claims`
- `claims.enabled`
- `claims.hours_before`
- `daily_ahead`
- `daily_ahead.enabled`
- `daily_ahead.hour`
- `daily_ahead.minute`
- `daily_ahead.days`
- `daily_ahead.dry_run`
- `engines`
- `engines.youtube`
- `engines.telegram`
- `engines.instagram`
- `engines.facebook`
- `engines.threads`
- `engines.tiktok`
- `engines.vk`
- `engines.x`
- `engines.rutube`
- `manual_uploads`
- `manual_uploads.enabled`
- `manual_uploads.platforms`
- `manual_uploads.lookback_days`
- `manual_uploads.page_size`
- `manual_uploads.schedule_scan`
- `manual_uploads.placement_default`
- `telegram_link_delay_min`
- `timezone`
- `watcher_interval_sec`
- `status_sync_interval_sec`
- `confirm_published_interval_sec`
- `file_stability_cycles`
- `watch_max_depth`
- `watch_max_age_days`
- `test_publish`
- `test_publish.enabled`
- `test_publish.default_delay_minutes`
- `test_publish.min_delay_minutes`
- `test_publish.max_delay_minutes`
- `test_publish.title_prefix`
- `test_publish.platforms`
- `test_publish.require_explicit_platforms`
- `test_publish.allow_prod_channel`
- `test_publish.prod_account_ids`
- `test_publish.test_account_ids`
- `test_publish.skip_tail_side_effects`
- `test_publish.skip_thematic_cascade`
- `test_publish.zero_jitter`

## 4. Environment variables

- `B2_APPLICATION_KEY`
- `B2_BUCKET`
- `B2_BUCKET_ID`
- `B2_ENDPOINT`
- `B2_KEY_ID`
- `BEEHIIV_ACCOUNT_ID`
- `BEEHIIV_PUBLICATION_ID`
- `BLUESKY_APP_PASSWORD`
- `BLUESKY_HANDLE`
- `BLUESKY_SERVICE`
- `BUILD`
- `CID`
- `CSEC`
- `DEVTO_API_KEY`
- `DEVTO_BASE_URL`
- `DISCORD_WEBHOOK_URL`
- `DRIBBBLE_ACCESS_TOKEN`
- `DRIBBBLE_API_BASE`
- `DRIBBBLE_TEAM_ID`
- `FACEBOOK_PAGE_ID`
- `FACEBOOK_PAGE_TOKEN`
- `FARCASTER_FID`
- `FARCASTER_SIGNER_UUID`
- `GOOGLE_BUSINESS_ACCOUNT_ID`
- `GOOGLE_BUSINESS_LOCATION_ID`
- `HASHNODE_API_TOKEN`
- `HASHNODE_PUBLICATION_ID`
- `INSTAGRAM_ACCESS_TOKEN`
- `INSTAGRAM_IG_USER_ID`
- `INSTAGRAM_USER_ID`
- `KICK_ACCESS_TOKEN`
- `KICK_API_BASE`
- `KICK_BROADCASTER_USER_ID`
- `KICK_CHANNEL_SLUG`
- `LEMMY_BASE_URL`
- `LEMMY_COMMUNITY_ID`
- `LEMMY_PASSWORD`
- `LEMMY_USERNAME`
- `LINE_API_URL`
- `LINE_CHANNEL_SECRET`
- `LINKEDIN_ACCESS_TOKEN`
- `LINKEDIN_API_BASE`
- `LINKEDIN_API_VERSION`
- `LINKEDIN_AUTHOR_URN`
- `LISTMONK_ACCOUNT_ID`
- `LISTMONK_API_TOKEN`
- `LISTMONK_API_USER`
- `LISTMONK_BASE_URL`
- `LISTMONK_LIST_IDS`
- `MASTODON_ACCESS_TOKEN`
- `MASTODON_BASE_URL`
- `MESSENGER_PAGE_ID`
- `META_APP_ID`
- `META_APP_SECRET`
- `META_GRAPH_BASE_URL`
- `META_GRAPH_VERSION`
- `META_VERIFY_TOKEN`
- `MEWE_API_BASE`
- `MEWE_API_TOKEN`
- `MEWE_APP_ID`
- `MEWE_GROUP_ID`
- `MOLTBOOK_API_BASE`
- `MOLTBOOK_API_KEY`
- `MOLTBOOK_SUBMOLT`
- `NEYNAR_API_BASE`
- `NEYNAR_API_KEY`
- `NOSTR_DEFAULT_KIND`
- `NOSTR_PRIVATE_KEY`
- `NOSTR_RELAY_URLS`
- `ORCH_BACKUP_MIRROR`
- `ORCH_CANARY_LIVE`
- `ORCH_CONSISTENCY_INTERVAL_MIN`
- `ORCH_CORS_ORIGIN`
- `ORCH_COVERS_DIR`
- `ORCH_DATA_DIR`
- `ORCH_GUARD_TTL_SEC`
- `ORCH_HEALTH_TOKEN`
- `ORCH_HTTP_BIND`
- `ORCH_HTTP_DEBUG_DIR`
- `ORCH_LEGACY_PATH_KEY`
- `ORCH_MAX_BODY_BYTES`
- `ORCH_PIDFILE`
- `ORCH_PUBLIC_BASE_URL`
- `ORCH_READ_ONLY`
- `ORCH_THREADS_CACHE`
- `ORCH_WEBAPP_INIT_MAX_AGE_SEC`
- `PINTEREST_ACCESS_TOKEN`
- `PINTEREST_API_BASE`
- `PINTEREST_BOARD_ID`
- `REDDIT_ACCESS_TOKEN`
- `REDDIT_API_BASE`
- `REDDIT_SUBREDDIT`
- `REDDIT_USER_AGENT`
- `RUN_ENV`
- `SLACK_API_URL`
- `SLACK_CHANNEL_ID`
- `SNAPCHAT_ACCESS_TOKEN`
- `SNAPCHAT_API_BASE`
- `SNAPCHAT_PROFILE_ID`
- `TELEGRAM_ACK_REACTION`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_MODE`
- `TELEGRAM_POLL_IDLE_SEC`
- `TELEGRAM_POLL_NO_ACK`
- `TELEGRAM_PUBLISH_CHAT_ID`
- `TG_INBOX_DIR`
- `TG_VOICE_STT`
- `TG_VOICE_STT_MODEL`
- `TG_VOICE_STT_PYTHON`
- `TG_VOICE_STT_TIMEOUT`
- `THREADS_ACCESS_TOKEN`
- `THREADS_API_VERSION`
- `THREADS_USER_ID`
- `TIKTOK_ACCESS_TOKEN`
- `TIKTOK_CLIENT_KEY`
- `TIKTOK_CLIENT_SECRET`
- `TIKTOK_CREATOR_INFO`
- `TIKTOK_INBOX_PATH`
- `TIKTOK_TOKENS_PATH`
- `TOKENS_DIR`
- `TOKEN_ALLOW_SHARED_ENV`
- `TOKEN_ALLOW_SHARED_FALLBACK`
- `TOKEN_BROKER_SECRET`
- `TOKEN_BROKER_STRICT`
- `TOKEN_BROKER_URL`
- `TUMBLR_API_BASE`
- `TUMBLR_BLOG`
- `TUMBLR_CONSUMER_KEY`
- `TUMBLR_CONSUMER_SECRET`
- `TUMBLR_OAUTH_TOKEN`
- `TUMBLR_OAUTH_TOKEN_SECRET`
- `TWITCH_ACCESS_TOKEN`
- `TWITCH_API_BASE`
- `TWITCH_BROADCASTER_ID`
- `TWITCH_CLIENT_ID`
- `URL`
- `VIBER_API_URL`
- `VIBER_AUTH_TOKEN`
- `VK_ACCESS_TOKEN`
- `VK_GROUP_ID`
- `WEBAPP_ACCESS_KEY`
- `WEBAPP_BROWSE_ROOT`
- `WEBAPP_DEV`
- `WEBAPP_PUBLIC_URL`
- `WEBAPP_RATE_LIMIT`
- `WECHAT_ACCESS_TOKEN`
- `WECHAT_API_BASE`
- `WECHAT_APP_ID`
- `WECHAT_APP_SECRET`
- `WHATSAPP_GRAPH_VERSION`
- `WHATSAPP_PHONE_NUMBER_ID`
- `WHATSAPP_VERIFY_TOKEN`
- `WHOP_API_KEY`
- `WHOP_EXPERIENCE_ID`
- `WHOP_EXTERNAL_ID_PREFIX`
- `WHOP_USERNAME`
- `WHOP_USER_ID`
- `WORDPRESS_APP_PASSWORD`
- `WORDPRESS_BASE_URL`
- `WORDPRESS_USERNAME`
- `X_ACCESS_TOKEN`
- `YT_CLIENT_ID`
- `YT_CLIENT_SECRET`
- `YT_TOKENS_PATH`

## 5. WebApp API routes

- `"trash_restore" if route == "trash/restore" else "trash_purge",`
- `f"n={n}" + (f" entities={gone}" if route == "trash/purge" else ""))`
- `if method == "GET" and route == "accounts/checklist":`
- `if method == "GET" and route == "backlog":`
- `if method == "GET" and route == "browse":`
- `if method == "GET" and route == "browse/search":`
- `if method == "GET" and route == "calendar":`
- `if method == "GET" and route == "failed":`
- `if method == "GET" and route == "job":`
- `if method == "GET" and route == "metrics":`
- `if method == "GET" and route == "ops":`
- `if method == "GET" and route == "platform_capabilities":`
- `if method == "GET" and route == "platforms":`
- `if method == "GET" and route == "projects":`
- `if method == "GET" and route == "queue":`
- `if method == "GET" and route == "roots":`
- `if method == "GET" and route == "schedule_settings":`
- `if method == "GET" and route == "status":`
- `if method == "GET" and route == "tail":`
- `if method == "GET" and route == "test/status":`
- `if method == "GET" and route == "trash":`
- `if method == "GET" and route == "version":`
- `if method == "GET" and route in ("cover/list", "cover/thumb"):`
- `if method == "GET" and route in ("inventory", "remote_inventory"):`
- `if method == "GET" and route.startswith("oauth/") and route.endswith("/start"):`
- `if method == "GET" and route.startswith("oauth/callback/"):`
- `if method == "POST" and route == "accounts/disconnect":`
- `if method == "POST" and route == "backlog/answer":`
- `if method == "POST" and route == "backup":`
- `if method == "POST" and route == "cover/frames":`
- `if method == "POST" and route == "cross_post":`
- `if method == "POST" and route == "distribute":`
- `if method == "POST" and route == "force_link":`
- `if method == "POST" and route == "groups":`
- `if method == "POST" and route == "inventory/scan":`
- `if method == "POST" and route == "job/cancel":`
- `if method == "POST" and route == "pause":`
- `if method == "POST" and route == "pause_platform":`
- `if method == "POST" and route == "queue/cleanup_orphans":`
- `if method == "POST" and route == "queue/detach":`
- `if method == "POST" and route == "queue/edit":`
- `if method == "POST" and route == "queue/remove":`
- `if method == "POST" and route == "queue/restore":`
- `if method == "POST" and route == "reconcile":`
- `if method == "POST" and route == "resume":`
- `if method == "POST" and route == "resume_platform":`
- `if method == "POST" and route == "roots":`
- `if method == "POST" and route == "scan":`
- `if method == "POST" and route == "schedule":`
- `if method == "POST" and route == "schedule_settings":`
- `if method == "POST" and route == "scheduling_mode":`
- `if method == "POST" and route == "series_end":`
- `if method == "POST" and route == "sync":`
- `if method == "POST" and route in ("cover/upload", "cover/fetch"):`
- `if method == "POST" and route in ("inventory/claim", "inventory/link", "inventory/ignore"):`
- `if method == "POST" and route in ("trash/restore", "trash/purge"):`
- `if route == "cover/thumb":`
- `if route == "cover/upload":`
- `if route == "manual/plan" and method == "GET":`
- `if route == "manual/scan" and method == "POST":`
- `if route == "manual/uploads" and method == "GET":`
- `if route == "test/schedule":`
- `if route == "trash/purge":`
- `if route == "trash/restore":`
- `if route in ("test/schedule", "test/status", "test/cancel"):`
- `if route.startswith("manual/uploads/") and method in ("GET", "POST"):`
- `key = "restored" if route == "trash/restore" else "purged"`

The main control-plane groups exposed by `webapp_api.py` are: version, metrics, status, OAuth start/callback, calendar, inventory/scan/claim/link/ignore, ops, queue/job management, projects/platforms/accounts, tail, failed, pause/resume, cross-post/distribute, series-end/force-link, roots/browse/search, cover management, manual-upload lifecycle, backlog, sync/reconcile/backup, test publish lifecycle, scheduling and platform pause.

## 6. Core public classes/functions

### `src/orchestrator/api_versions.py`
- **class `ApiVersionRecord`** — no class docstring
  - `status` — `def status(self, today: date | None=None) -> str:
    today = today or date.today()
    if self.sunset_at and today > self.sunset_at:
        return 'SUNSET'
    if self.sunset_at and (self.sunset_at - today).days <= 30:
        return 'SUNSET_SOON'
    return 'ACTIVE'` — no method docstring
- **function `get_record`** — `def get_record(provider: str) -> ApiVersionRecord | None:
    key = str(provider or '').strip().lower()
    return REGISTRY.get(key)` — no docstring
- **function `validate_no_sunset`** — `def validate_no_sunset(records: dict[str, ApiVersionRecord] | None=None, today: date | None=None) -> list[str]:
    errors: list[str] = []
    for key, rec in (records or REGISTRY).items():
        if rec.status(today) == 'SUNSET':
            errors.append(f"{key}:{rec.version} is past sunset ({(rec.sunset_at.isoformat() if rec.sunset_at else 'unknown')})")
    return errors` — no docstring
### `src/orchestrator/auth_tokens.py`
- **class `TokenResolutionError`** — Raised when a configured token broker cannot be used in strict mode.
- **function `get_access_token`** — `def get_access_token(platform: str, account_id: str='') -> str:
    """Resolve token: configured broker → account-scoped file → legacy shared file.

    When TOKEN_BROKER_URL is configured, a broker error is observable in strict mode
    (TOKEN_BROKER_STRICT=1); otherwise the documented local-file fallback remains
    available for single-host operation.
    """
    plat = (platform or '').strip().lower()
    aid = (account_id or '').strip()
    if not plat:
        return ''
    broker = _broker_client()
    if broker is not None:
        strict = os.getenv('TOKEN_BROKER_STRICT', '1').strip().lower() in {'1', 'true', 'yes', 'on'}
        try:
            data = broker.get(plat, aid or None)
            tok = str((data or {}).get('token') or (data or {}).get('access_token') or '')
            if tok:
                return tok
            if strict:
                raise TokenResolutionError(f"token broker returned no token for {plat}/{aid or '*'}")
        except Exception as exc:
            if strict:
                raise TokenResolutionError(f"token broker failed for {plat}/{aid or '*'}: {exc}") from exc
            logger.warning('token broker unavailable for %s: %s; using local token store', plat, type(exc).__name__)
    root = Path(os.getenv('TOKENS_DIR', 'tokens'))
    if aid:
        try:
            from .token_lifecycle import TokenLifecycleStore
            rec = TokenLifecycleStore(root).load(plat, aid)
            if rec is not None:
                if not rec.usable():
                    return ''
                if rec.access_token:
                    return rec.access_token
        except Exception:
            logger.debug('token lifecycle read failed', exc_info=True)
    candidates: list[Path] = []
    if aid:
        candidates.append(root / f'{plat}__{aid}.json')
        allow_shared = os.getenv('TOKEN_ALLOW_SHARED_FALLBACK', '0').strip().lower() in {'1', 'true', 'yes', 'on'}
        if allow_shared:
            candidates.append(root / f'{plat}.json')
    else:
        candidates.append(root / f'{plat}.json')
    for path in candidates:
        if not path.is_file():
            continue
        try:
            try:
                os.chmod(path, 384)
            except OSError:
                pass
            data: dict[str, Any] = json.loads(path.read_text(encoding='utf-8'))
            tok = str(data.get('access_token') or data.get('token') or '')
            if tok:
                return tok
        except Exception:
            logger.debug('auth_tokens read failed %s', path, exc_info=True)
    return ''` — Resolve token: configured broker → account-scoped file → legacy shared file. When TOKEN_BROKER_URL is configured, a broker error is observable in strict mode (TOKEN_BROKER_STRICT=1); otherwise the documented local-file fallback remains available for single-host operation.
- **function `token_provider_for`** — `def token_provider_for(platform_hint: str=''):
    """Return callable compatible with module registry token_provider(plat, account_id)."""

    def _provider(plat: str, account_id: str='') -> str:
        return get_access_token(plat or platform_hint, account_id=account_id)
    return _provider` — Return callable compatible with module registry token_provider(plat, account_id).
### `src/orchestrator/backlog.py`
- **class `BacklogManager`** — Unposted shorts of a finished series ("backlog"). When a series' slot (e.g. Tue/Fri 16:00) approaches and no new episode is ready, ask the user (ask_minutes_before) with actions: - distribute: schedule the backlog now (default if no answer by slot time) - wait: keep waiting for a new episode - skip: do not publish the backlog for now
  - `unposted_series_shorts` — `def unposted_series_shorts(self, platform: str) -> list[dict]:
    pcfg = self.cfg.platforms.get(platform)
    if pcfg is not None and getattr(pcfg, 'post_mode', 'media') == 'link':
        return []
    rows = self.db.fetchall("\n            SELECT s.id, s.parent_video_id, s.order_index, s.video_path, s.platform_paths,\n                   s.title_text, s.description_text, s.hashtags_text\n            FROM shorts s\n            WHERE s.parent_video_id IS NOT NULL\n              AND NOT EXISTS (\n                  SELECT 1 FROM entity_platform_status eps\n                  WHERE eps.entity_type='short' AND eps.entity_id=s.id\n                    AND eps.platform=? AND eps.status IN ('scheduled','published','skipped'))\n            ORDER BY s.parent_video_id, s.order_index, s.id\n            ", (platform,))
    sched = getattr(self, 'scheduler', None)
    if sched is None:
        return rows
    return [r for r in rows if sched._pick_short_path(r, platform)]` — no method docstring
  - `has_backlog` — `def has_backlog(self, platform: str) -> int:
    return len(self.unposted_series_shorts(platform))` — no method docstring
  - `awaiting` — `def awaiting(self, platform: str) -> bool:
    st = self._state(platform)
    return bool(st and st['pending_backlog_question'])` — no method docstring
  - `next_long_slot` — `def next_long_slot(self, platform: str, now: datetime | None=None) -> datetime | None:
    """P0.10: слот из effective-настроек платформы (override/группы/исключения)."""
    from . import sched_settings
    eff = sched_settings.effective(self.db, self.cfg, platform, 'long')
    days = eff.get('days') or ['tue', 'fri']
    t = eff.get('time') or '16:00'
    slots = next_long_video_dates(days, t, now or self.clock.now(), count=1, exception_days=eff.get('exception_days', []), tz_name=self.cfg.timezone)
    return slots[0] if slots else None` — P0.10: слот из effective-настроек платформы (override/группы/исключения).
  - `needs_question` — `def needs_question(self, platform: str, now: datetime | None=None) -> datetime | None:
    now = now or self.clock.now()
    slot = self.next_long_slot(platform, now)
    if not slot:
        return None
    ask_at = slot - timedelta(minutes=self.cfg.tail.ask_minutes_before)
    if not ask_at <= now < slot:
        return None
    if self.has_backlog(platform) == 0:
        return None
    if self.db.get_setting(f'backlog_slot_done_{platform}') == slot.isoformat():
        return None
    st = self._state(platform)
    if st and st['pending_backlog_question'] and (st['pending_backlog_at'] == slot.isoformat()):
        return None
    return slot` — no method docstring
  - `ask` — `def ask(self, platform: str, slot: datetime) -> None:
    now = self.clock.now().isoformat()
    self.db.execute('UPDATE platform_queue_state SET pending_backlog_question=1, pending_backlog_at=?, last_series_end_question_at=?, updated_at=? WHERE platform=?', (slot.isoformat(), now, now, platform))
    if self.notifier is not None:
        try:
            self.notifier.ask_backlog(platform, self.has_backlog(platform))
        except Exception:
            logger.exception('notifier.ask_backlog failed')` — no method docstring
  - `resolve` — `def resolve(self, platform: str, answer: str, slot: datetime | None=None) -> int:
    now = self.clock.now().isoformat()
    dec_slot = self._decision_slot(platform, slot)
    if dec_slot is not None:
        self.db.set_setting(f'backlog_slot_done_{platform}', dec_slot.isoformat())
    if answer == 'distribute':
        self.db.execute('UPDATE platform_queue_state SET pending_backlog_question=0, pending_backlog_at=NULL, series_tail_mode=1, updated_at=? WHERE platform=?', (now, platform))
        n = 0
        if self.scheduler is not None:
            n = self.scheduler.schedule_backlog(platform)
        if self.has_backlog(platform) == 0:
            self.db.execute('UPDATE platform_queue_state SET series_tail_mode=0, updated_at=? WHERE platform=?', (now, platform))
        self.db.log('system', None, platform, 'backlog_distribute', str(n))
        if self.notifier is not None:
            try:
                self.notifier.backlog_distributed(platform, n)
            except Exception:
                logger.exception('notifier.backlog_distributed failed')
        return n
    self.db.execute('UPDATE platform_queue_state SET pending_backlog_question=0, pending_backlog_at=NULL, series_tail_mode=0, last_series_end_question_at=?, updated_at=? WHERE platform=?', (now, now, platform))
    self.db.log('system', None, platform, f'backlog_{answer}', '')
    return 0` — no method docstring
  - `last_long_slot` — `def last_long_slot(self, platform: str, now: datetime | None=None) -> datetime | None:
    """Последний по времени слот серии (<= now) из effective-настроек платформы."""
    from . import sched_settings
    from .slots import DAY_MAP, get_tz, local_to_utc, parse_time
    now = now or self.clock.now()
    eff = sched_settings.effective(self.db, self.cfg, platform, 'long')
    days = {DAY_MAP[d.lower()[:3]] for d in eff.get('days') or ['tue', 'fri'] if d.lower()[:3] in DAY_MAP}
    exceptions = set(eff.get('exception_days') or [])
    t = eff.get('time') or '16:00'
    tz = get_tz(self.cfg.timezone)
    local_today = now.astimezone(tz).date()
    for i in range(0, 15):
        d = local_today - timedelta(days=i)
        if d.weekday() in days and d.isoformat() not in exceptions:
            dt = local_to_utc(d, parse_time(t), self.cfg.timezone)
            if dt <= now:
                return dt
    return None` — Последний по времени слот серии (<= now) из effective-настроек платформы.
  - `missed_default` — `def missed_default(self, platform: str, now: datetime | None=None) -> int:
    """Окно вопроса пропущено (оркестратор был недоступен) -> применяем дефолт."""
    now = now or self.clock.now()
    if self.awaiting(platform):
        return 0
    slot = self.last_long_slot(platform, now)
    if not slot:
        return 0
    if self.db.get_setting(f'backlog_slot_done_{platform}') == slot.isoformat():
        return 0
    if self.has_backlog(platform) == 0:
        return 0
    if now - slot > timedelta(hours=24):
        return 0
    if self.cfg.tail.default_action != 'distribute':
        self.db.set_setting(f'backlog_slot_done_{platform}', slot.isoformat())
        return 0
    logger.info('Backlog missed-window default for %s at %s', platform, slot)
    self.db.set_setting(f'backlog_slot_done_{platform}', slot.isoformat())
    return self.resolve(platform, 'distribute', slot)` — Окно вопроса пропущено (оркестратор был недоступен) -> применяем дефолт.
  - `should_remind` — `def should_remind(self, platform: str, now: datetime | None=None) -> datetime | None:
    now = now or self.clock.now()
    st = self._state(platform)
    if not (st and st['pending_backlog_question'] and st['pending_backlog_at']):
        return None
    raw = st['pending_backlog_at']
    try:
        slot = datetime.fromisoformat(raw)
    except Exception:
        return None
    if slot.tzinfo is None:
        slot = slot.replace(tzinfo=UTC)
    if not slot - timedelta(minutes=self.cfg.tail.reminder_minutes_before) <= now < slot:
        return None
    if self.db.get_setting(f'backlog_reminded_{platform}') == raw:
        return None
    return slot` — no method docstring
  - `mark_reminded` — `def mark_reminded(self, platform: str, slot: datetime) -> None:
    self.db.set_setting(f'backlog_reminded_{platform}', slot.isoformat())
    if self.notifier is not None:
        try:
            self.notifier.remind_backlog(platform, self.has_backlog(platform))
        except Exception:
            logger.exception('notifier.remind_backlog failed')` — no method docstring
  - `auto_default` — `def auto_default(self, platform: str, now: datetime | None=None) -> int:
    now = now or self.clock.now()
    st = self._state(platform)
    if not (st and st['pending_backlog_question'] and st['pending_backlog_at']):
        return 0
    try:
        slot = datetime.fromisoformat(st['pending_backlog_at'])
    except Exception:
        return 0
    if slot.tzinfo is None:
        slot = slot.replace(tzinfo=UTC)
    if now < slot:
        return 0
    action = self.cfg.tail.default_action
    answer = 'distribute' if action == 'distribute' else 'wait'
    logger.info('Backlog default action for %s: %s', platform, answer)
    return self.resolve(platform, answer, slot)` — no method docstring
### `src/orchestrator/backup.py`
- **function `run_backup`** — `def run_backup(db: Database, cfg: AppConfig, backup_dir: str | Path) -> Path | None:
    if not cfg.backup.enabled:
        return None
    backup_dir = Path(backup_dir)
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        if not os.access(backup_dir, os.W_OK):
            raise PermissionError(str(backup_dir))
    except OSError:
        alt = Path(db.path).resolve().parent / 'backups'
        try:
            alt.mkdir(parents=True, exist_ok=True)
            if not os.access(alt, os.W_OK):
                raise PermissionError(str(alt))
            logger.warning('Backup dir %s недоступен — использую %s', backup_dir, alt)
            backup_dir = alt
        except OSError:
            logger.warning('Backup пропущен: нет доступной папки для %s', db.path)
            return None
    ts = datetime.now(UTC).strftime('%Y%m%d_%H%M%S')
    dest = backup_dir.resolve() / f'data_{ts}.sqlite'
    try:
        dest_s = str(dest)
        if any((c in dest_s for c in ('\x00', '\n', '\r'))):
            raise ValueError(f'unsafe backup path: {dest_s!r}')
        with sqlite3.connect(db.path) as src:
            with sqlite3.connect(dest_s) as dst:
                src.backup(dst)
        logger.info('Backup created: %s', dest)
        mirror = os.getenv('ORCH_BACKUP_MIRROR', '').strip()
        if mirror:
            try:
                mdir = Path(mirror)
                mdir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest, mdir / dest.name)
                _cleanup(mdir, cfg.backup.keep_days)
                logger.info('Backup mirrored: %s', mdir / dest.name)
            except Exception:
                logger.exception('Backup mirror failed')
        _cleanup(backup_dir, cfg.backup.keep_days)
        try:
            with sqlite3.connect(db.path) as c:
                cur = c.execute("DELETE FROM publish_log WHERE created_at < datetime('now', '-90 day')")
                if cur.rowcount:
                    logger.info('publish_log pruned: %s rows', cur.rowcount)
        except Exception:
            logger.exception('publish_log prune failed')
        return dest
    except Exception as e:
        logger.error('Backup failed: %s', e)
        return None` — no docstring
- **function `verify_backup`** — `def verify_backup(path: str | Path) -> dict[str, str | bool]:
    """Verify a SQLite backup without mutating it."""
    p = Path(path)
    result: dict[str, str | bool] = {'path': str(p), 'exists': p.is_file(), 'ok': False}
    if not p.is_file():
        return result
    try:
        with sqlite3.connect(p) as con:
            check = str(con.execute('PRAGMA quick_check').fetchone()[0])
        result['quick_check'] = check
        result['ok'] = check.lower() == 'ok'
    except Exception as exc:
        result['quick_check'] = f'error:{exc}'
    return result` — Verify a SQLite backup without mutating it.
### `src/orchestrator/canary.py`
- **class `CanaryResult`** — no class docstring
- **class `ProviderContractCanary`** — Provider contract/canary harness with explicit non-publishing live mode.
  - `static` — `def static(self, module_id: str) -> CanaryResult:
    result = CanaryResult(module_id=module_id)
    manifest_path = Path(__file__).resolve().parent / 'platforms' / module_id / 'manifest.yaml'
    manifest = load_manifest(manifest_path)
    ModuleSDK.validate_manifest(manifest)
    result.static_ok = True
    result.notes.append(f'manifest={manifest.module_version}')
    result.notes.append(f"publish={bool(manifest.capabilities.get('publish', False))}")
    return result` — no method docstring
  - `dry` — `def dry(self, module_id: str) -> CanaryResult:
    result = self.static(module_id)
    try:
        module = self.registry.create(module_id, dry_run=True)
    except ModuleError as exc:
        if exc.code in {ModuleErrorCode.AUTH_REQUIRED, ModuleErrorCode.AUTH_EXPIRED, ModuleErrorCode.REVIEW_REQUIRED, ModuleErrorCode.DEPENDENCY_DOWN}:
            result.dry_ok = True
            result.state = 'dry_access_blocked'
            result.notes.append(f'constructor-access-blocked:{exc.code}')
            return result
        raise
    try:
        st = module.auth_status()
        if not isinstance(st, AuthStatus):
            raise TypeError(f'{module_id}: auth_status() must return AuthStatus')
    except ModuleError as exc:
        if exc.code not in {ModuleErrorCode.AUTH_REQUIRED, ModuleErrorCode.AUTH_EXPIRED, ModuleErrorCode.REVIEW_REQUIRED, ModuleErrorCode.DEPENDENCY_DOWN}:
            raise
        st = AuthStatus(False, account=module_id, details=str(exc))
    errors = getattr(module, 'validate_config', lambda cfg: [])({})
    if not isinstance(errors, list):
        raise TypeError(f'{module_id}: validate_config() must return list[str]')
    result.dry_ok = True
    result.state = 'dry_ready'
    if st.ok:
        result.notes.append('dry-auth-ok')
    else:
        result.notes.append(f'dry-auth-blocked:{st.details[:160]}')
    if errors:
        result.notes.append(f"config:{'; '.join((str(x) for x in errors))[:240]}")
    return result` — no method docstring
  - `dry_all` — `def dry_all(self) -> list[CanaryResult]:
    out: list[CanaryResult] = []
    for mid in self.registry.ids():
        try:
            out.append(self.dry(mid))
        except Exception as exc:
            out.append(CanaryResult(module_id=mid, state='error', notes=[f'{type(exc).__name__}: {exc}']))
    return out` — no method docstring
  - `live_read_only` — `def live_read_only(self, module_ids: list[str] | None=None) -> list[CanaryResult]:
    if os.getenv('ORCH_CANARY_LIVE', '').lower() not in {'1', 'true', 'yes'}:
        return [CanaryResult(module_id='__live__', state='disabled', notes=['set ORCH_CANARY_LIVE=1 to enable read-only live canary'])]
    ids = module_ids or self.registry.ids()
    out: list[CanaryResult] = []
    for mid in ids:
        result = self.static(mid)
        try:
            module = self.registry.create(mid, dry_run=False)
            auth = module.auth_status()
            if not isinstance(auth, AuthStatus):
                raise TypeError('auth_status did not return AuthStatus')
            result.live_ok = bool(auth.ok)
            result.state = 'live_auth_ok' if auth.ok else 'live_auth_blocked'
            result.notes.append(auth.details[:240])
            try:
                page = module.list_remote_items(limit=1)
                result.notes.append(f'inventory_items={len(page.items)}')
            except NotSupported:
                result.notes.append('inventory=not_supported')
        except Exception as exc:
            result.state = 'live_error'
            result.notes.append(f'{type(exc).__name__}: {exc}')
        out.append(result)
    return out` — no method docstring
  - `summary` — `def summary(self, results: list[CanaryResult]) -> dict[str, Any]:
    return {'generated_at': datetime.now(UTC).isoformat(), 'count': len(results), 'static_ok': sum((1 for r in results if r.static_ok)), 'dry_ok': sum((1 for r in results if r.dry_ok)), 'live_ok': sum((1 for r in results if r.live_ok)), 'states': {s: sum((1 for r in results if r.state == s)) for s in sorted({r.state for r in results})}, 'results': [asdict(r) for r in results]}` — no method docstring
### `src/orchestrator/claims.py`
- **class `ClaimsJobResult`** — no class docstring
- **function `run_claims_check`** — `def run_claims_check(db: Any, *, clock: Any, youtube_module: Any | None, hours_before: float=6.0, notifier: Any | None=None) -> ClaimsJobResult:
    """Check claims for scheduled YT rows within window; update claims_state."""
    res = ClaimsJobResult()
    if youtube_module is None:
        res.errors.append('youtube_module missing')
        return res
    now = clock.now()
    horizon = (now + timedelta(hours=hours_before)).isoformat()
    rows = db.fetchall("\n        SELECT entity_type, entity_id, platform, external_id, scheduled_for, claims_state\n        FROM entity_platform_status\n        WHERE platform='youtube'\n          AND status IN ('scheduled', 'scheduled_platform')\n          AND external_id IS NOT NULL AND external_id != ''\n          AND scheduled_for IS NOT NULL AND scheduled_for <= ?\n          AND (claims_state IS NULL OR claims_state IN ('', 'pending'))\n        ", (horizon,))
    for r in rows or []:
        res.checked += 1
        eid = r['external_id']
        try:
            cr = youtube_module.check_claims(eid)
        except Exception as e:
            res.errors.append(f'{eid}: {e}')
            continue
        supported = getattr(cr, 'supported', False)
        if not supported:
            res.skipped += 1
            db.execute("UPDATE entity_platform_status SET claims_state='unsupported', claims_checked_at=? WHERE entity_type=? AND entity_id=? AND platform=?", (now.isoformat(), r['entity_type'], r['entity_id'], r['platform']))
            continue
        has_claim = bool(getattr(cr, 'has_claim', False) or getattr(cr, 'claimed', False))
        if has_claim:
            res.claimed += 1
            db.execute("UPDATE entity_platform_status SET claims_state='claimed', claims_checked_at=? WHERE entity_type=? AND entity_id=? AND platform=?", (now.isoformat(), r['entity_type'], r['entity_id'], r['platform']))
            if notifier and hasattr(notifier, 'ask_claims'):
                try:
                    notifier.ask_claims(r['entity_type'], r['entity_id'], eid)
                except Exception:
                    logger.debug('claims notify failed', exc_info=True)
        else:
            res.clean += 1
            db.execute("UPDATE entity_platform_status SET claims_state='clean', claims_checked_at=? WHERE entity_type=? AND entity_id=? AND platform=?", (now.isoformat(), r['entity_type'], r['entity_id'], r['platform']))
    return res` — Check claims for scheduled YT rows within window; update claims_state.
- **function `a3_delete_and_next`** — `def a3_delete_and_next(db: Any, *, publisher: Any, entity_type: str, entity_id: int, platform: str, youtube_module: Any | None) -> bool:
    """A3: delete platform copy, mark claimed_skipped, queue next same type (publish_log)."""
    row = db.fetchone('SELECT external_id FROM entity_platform_status WHERE entity_type=? AND entity_id=? AND platform=?', (entity_type, entity_id, platform))
    if not row:
        return False
    eid = row.get('external_id')
    if eid and youtube_module is not None:
        try:
            youtube_module.delete(eid)
        except Exception:
            logger.warning('A3 delete failed %s', eid, exc_info=True)
    db.execute("UPDATE entity_platform_status SET status='claimed_skipped', claims_state='resolved_a3', external_id=NULL WHERE entity_type=? AND entity_id=? AND platform=?", (entity_type, entity_id, platform))
    try:
        db.log(entity_type, entity_id, platform, 'claims_a3_delete', str(eid or ''))
    except Exception:
        pass
    return True` — A3: delete platform copy, mark claimed_skipped, queue next same type (publish_log).
- **function `resolve_claim_a3`** — `def resolve_claim_a3(db: Any, entity_type: str, entity_id: int, platform: str='youtube') -> None:
    """A3: mark claimed_skipped and clear external ids so next item can take the slot."""
    row = db.fetchone('SELECT external_id FROM entity_platform_status WHERE entity_type=? AND entity_id=? AND platform=?', (entity_type, entity_id, platform))
    eid = row.get('external_id') if row else None
    db.execute("UPDATE entity_platform_status SET status='claimed_skipped', claims_state='resolved_a3', external_id=NULL, last_error='claims_a3' WHERE entity_type=? AND entity_id=? AND platform=?", (entity_type, entity_id, platform))
    db.log(entity_type, entity_id, platform, 'claims_a3_delete', str(eid or ''))` — A3: mark claimed_skipped and clear external ids so next item can take the slot.
### `src/orchestrator/clock.py`
- **class `Clock`** — no class docstring
  - `now` — `def now(self) -> datetime:
    """Return current UTC datetime."""
    ...` — Return current UTC datetime.
- **class `SystemClock`** — no class docstring
  - `now` — `def now(self) -> datetime:
    return datetime.now(UTC)` — no method docstring
- **class `FakeClock`** — no class docstring
  - `now` — `def now(self) -> datetime:
    return self._now` — no method docstring
  - `set` — `def set(self, dt: datetime) -> None:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    self._now = dt` — no method docstring
  - `advance` — `def advance(self, **kwargs) -> None:
    from datetime import timedelta
    self._now += timedelta(**kwargs)` — no method docstring
### `src/orchestrator/config.py`
- **class `PlatformCfg`** — no class docstring
- **class `ProjectCfg`** — Проект = ниша со своими каналами во всех сетях (см. docs/PLAN-PROJECTS.md).
- **class `TailCfg`** — no class docstring
- **class `LimitsCfg`** — no class docstring
- **class `LinkUpdateCfg`** — no class docstring
- **class `SafetyCfg`** — no class docstring
- **class `TelegramCfg`** — no class docstring
- **class `MediaCfg`** — no class docstring
- **class `ManualUploadsCfg`** — no class docstring
- **class `BackupCfg`** — no class docstring
- **class `OpsCfg`** — no class docstring
- **class `TestPublishCfg`** — Пробный (тестовый) пост: отдельный контур, не трогает боевые строки расписания.
- **class `DailyAheadCfg`** — A2: ежедневная ранняя загрузка (сегодня+завтра) через module:youtube.
- **class `ClaimsCfg`** — YouTube claims checkpoint before slot.
- **class `AppConfig`** — no class docstring
  - `parse_platforms` — `@field_validator('platforms', mode='before')
@classmethod
def parse_platforms(_cls, v: dict) -> dict:
    return {k: PlatformCfg(**val) if isinstance(val, dict) else val for k, val in v.items()}` — no method docstring
  - `project_of_series` — `def project_of_series(self, series_id: int | None) -> str:
    """Проект серии videomaker (пустая строка — не привязана ни к какому проекту)."""
    if series_id is None:
        return ''
    for name, prj in self.projects.items():
        if series_id in list(prj.series_ids or []):
            return name
    return ''` — Проект серии videomaker (пустая строка — не привязана ни к какому проекту).
  - `project_of_folder` — `def project_of_folder(self, folder: str | None) -> str:
    """Проект по папке (сама папка или вложенная в неё)."""
    f = _norm_folder(folder or '')
    if not f:
        return ''
    for name, prj in self.projects.items():
        for root in list(prj.folders or []):
            r = _norm_folder(root)
            if r and (f == r or f.startswith(r + '/')):
                return name
    return ''` — Проект по папке (сама папка или вложенная в неё).
  - `project_title` — `def project_title(self, project: str) -> str:
    prj = self.projects.get(project or '')
    title = (prj.title if prj else '') or ''
    return title or (project or 'Основной')` — no method docstring
  - `platforms_of_project` — `def platforms_of_project(self, project: str) -> list[str]:
    return [k for k, p in self.platforms.items() if (p.project or '') == (project or '')]` — no method docstring
  - `resolve_project` — `def resolve_project(self, *, series_id: int | None=None, series_folder: str | None=None, folder: str | None=None) -> str:
    """Проект сущности: серия → папка серии → своя папка (первое совпадение).

        Для шортса серии `series_folder` — папка фильма-родителя, `folder` — его собственная
        папка: так тематический шортс попадает в проект своей серии, а не папки шортсов.
        """
    return self.project_of_series(series_id) or self.project_of_folder(series_folder) or self.project_of_folder(folder) or self.default_project` — Проект сущности: серия → папка серии → своя папка (первое совпадение). Для шортса серии `series_folder` — папка фильма-родителя, `folder` — его собственная папка: так тематический шортс попадает в проект своей серии, а не папки шортсов.
  - `platform_matches_project` — `def platform_matches_project(self, platform: str, *, series_id: int | None=None, series_folder: str | None=None, folder: str | None=None) -> bool:
    """Публиковать ли сущность в эту платформу с учётом проекта.

        Платформа без проекта — как раньше, принимает всё. Платформа проекта берёт
        только сущности этого проекта (серия из `series_ids` или папка из `folders`).
        """
    pcfg = self.platforms.get(platform)
    if pcfg is None:
        return False
    want = pcfg.project or ''
    if not want:
        return True
    return self.resolve_project(series_id=series_id, series_folder=series_folder, folder=folder) == want` — Публиковать ли сущность в эту платформу с учётом проекта. Платформа без проекта — как раньше, принимает всё. Платформа проекта берёт только сущности этого проекта (серия из `series_ids` или папка из `folders`).
  - `engine_for` — `def engine_for(self, platform: str) -> str:
    """Publication engine for a platform (default: module path)."""
    eng = self.engines.get(platform, f'module:{platform}')
    e = str(eng).strip().lower()
    if e.startswith('module:'):
        return eng
    if e == '':
        return eng
    raise ValueError(f'unsupported engine for platform={platform!r}: {eng!r}; use module:<id>')` — Publication engine for a platform (default: module path).
- **class `ConfigurationError`** — Invalid configuration, including duplicate YAML keys.
- **function `load_config`** — `def load_config(path: str | Path) -> AppConfig:
    try:
        raw = load_unique_yaml(path) or {}
    except DuplicateYAMLKeyError as exc:
        raise ConfigurationError(str(exc)) from exc
    raw = migrate_config_dict(raw)
    cfg = AppConfig(**raw)
    allowed_prefixes = ('module:',)
    allowed_exact = {''}
    bad = []
    for plat, eng in (cfg.engines or {}).items():
        e = str(eng).strip().lower()
        if e in allowed_exact or any((e.startswith(p) for p in allowed_prefixes)):
            continue
        bad.append(f'{plat}={eng}')
    if bad:
        raise ValueError('unsupported engine (use module:<id>): ' + ', '.join(sorted(bad)))
    return cfg` — no docstring
### `src/orchestrator/config_migrations.py`
- **function `migrate_config_dict`** — `def migrate_config_dict(raw: dict[str, Any]) -> dict[str, Any]:
    """Upgrade persisted YAML config shapes without mutating caller input.

    v1 -> v2: account identity is canonical `account_id`; the legacy
    `integration_id` remains accepted by AppConfig for read compatibility,
    but is copied into account_id when account_id is absent.
    """
    data = deepcopy(dict(raw or {}))
    try:
        version = int(data.get('config_schema_version', 1))
    except (TypeError, ValueError) as exc:
        raise ValueError('config_schema_version must be an integer') from exc
    if version > CURRENT_CONFIG_SCHEMA_VERSION:
        raise ValueError(f'unsupported config_schema_version={version}; current={CURRENT_CONFIG_SCHEMA_VERSION}')
    if version < 2:
        platforms = data.get('platforms') or {}
        if isinstance(platforms, dict):
            for _, cfg in platforms.items():
                if isinstance(cfg, dict) and (not cfg.get('account_id')) and cfg.get('integration_id'):
                    cfg['account_id'] = cfg['integration_id']
        data['config_schema_version'] = 2
        version = 2
    data['config_schema_version'] = version
    return data` — Upgrade persisted YAML config shapes without mutating caller input. v1 -> v2: account identity is canonical `account_id`; the legacy `integration_id` remains accepted by AppConfig for read compatibility, but is copied into account_id when account_id is absent.
### `src/orchestrator/connection_control.py`
- **class `ConnectionChecklist`** — no class docstring
- **class `ConnectionControl`** — Unified provider connection onboarding/reconnect/disconnect control plane.
  - `checklist` — `def checklist(self, provider: str, account_id: str) -> ConnectionChecklist:
    provider = provider.strip().lower()
    mod = self.registry.create(provider) if self.registry and self.registry.has(provider) else None
    manifest = getattr(mod, 'manifest', None)
    auth = getattr(manifest, 'auth', {}) or {}
    method = str(auth.get('method') or 'planned')
    strategy = str(auth.get('strategy') or '')
    acc = self.accounts.get(account_id) if self.accounts else None
    rec = self.tokens.load(provider, account_id) if self.tokens and account_id else None
    token_present = bool(rec and rec.access_token)
    token_usable = bool(rec and rec.usable())
    enabled = bool(acc.enabled) if acc else False
    state = str(acc.connection_state if acc else 'NOT_CONFIGURED')
    blockers: list[str] = []
    if method in {'oauth', 'oauth2_authorization_code'} and (not strategy):
        blockers.append('missing_auth_strategy')
    if not token_present:
        blockers.append('token_missing')
    elif not token_usable:
        blockers.append('token_unusable')
    if acc is None:
        blockers.append('account_missing')
    elif not enabled:
        blockers.append('account_disabled')
    return ConnectionChecklist(provider, account_id, method, strategy, token_present, token_usable, enabled, state, not blockers, blockers)` — no method docstring
  - `disconnect` — `def disconnect(self, account_id: str, *, reason: str='manual_disconnect') -> bool:
    acc = self.accounts.get(account_id)
    if not acc:
        return False
    self.tokens.revoke(acc.platform, account_id, reason=reason)
    self.accounts.set_enabled(account_id, False)
    self.db.execute("UPDATE platform_accounts SET connection_state='DISCONNECTED', refresh_status='revoked', updated_at=? WHERE id=?", (__import__('time').time(), account_id))
    return True` — no method docstring
  - `mark_authorizing` — `def mark_authorizing(self, account_id: str) -> bool:
    return bool(self.db.execute("UPDATE platform_accounts SET connection_state='AUTHORIZING', updated_at=? WHERE id=?", (__import__('time').time(), account_id)))` — no method docstring
  - `mark_connected` — `def mark_connected(self, account_id: str, *, expires_at: float | None=None, scopes: str='') -> bool:
    return bool(self.db.execute("UPDATE platform_accounts SET connection_state='CONNECTED', enabled=1, expires_at=?, granted_scopes=?, updated_at=? WHERE id=?", (expires_at, scopes, __import__('time').time(), account_id)))` — no method docstring
  - `as_dict` — `@staticmethod
def as_dict(checklist: ConnectionChecklist) -> dict[str, Any]:
    return asdict(checklist)` — no method docstring
### `src/orchestrator/consistency.py`
- **class `ConsistencySweeper`** — no class docstring
  - `sweep` — `def sweep(self, platform: str, account_id: str='', *, limit: int=100) -> dict[str, int | str]:
    platform = str(platform or '').strip().lower()
    account_id = str(account_id or '')
    start = datetime.now(UTC).isoformat()
    run_id = self.db.execute('INSERT INTO consistency_runs(platform, account_id, started_at) VALUES (?, ?, ?)', (platform, account_id, start))
    scanned = repaired = conflicts = 0
    try:
        rows = self.db.fetchall("SELECT entity_type, entity_id, account_id, external_id, external_url, status FROM entity_platform_status WHERE platform=? AND account_id=? AND external_id IS NOT NULL AND external_id!='' ORDER BY entity_id LIMIT ?", (platform, account_id, max(1, int(limit))))
        scanned = len(rows)
        mod = None
        authoritative = False
        try:
            mod = self.module_factory(platform, account_id=account_id)
            authoritative = str(getattr(getattr(mod, 'manifest', None), 'status_authority', 'unknown') or 'unknown').lower() == 'authoritative'
        except Exception:
            mod = None
        if mod is not None and authoritative and hasattr(mod, 'get_status'):
            for row in rows:
                ext = str(row.get('external_id') or '').strip()
                if not ext:
                    continue
                try:
                    remote = mod.get_status(ext)
                except Exception:
                    continue
                remote_state = str(getattr(remote, 'state', 'unknown') or 'unknown').lower()
                if remote_state == 'unknown':
                    continue
                remote_url = str(getattr(remote, 'url', '') or '').strip()
                local_state = str(row.get('status') or '').lower()
                if remote_state != local_state or (remote_url and remote_url != str(row.get('external_url') or '')):
                    conflicts += 1
                    repaired += self.db.execute("UPDATE entity_platform_status SET status=?, external_url=COALESCE(NULLIF(?, ''), external_url), release_url=COALESCE(NULLIF(?, ''), release_url), last_status_sync_at=? WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?", (remote_state, remote_url, remote_url, datetime.now(UTC).isoformat(), row['entity_type'], row['entity_id'], platform, account_id))
        self.db.execute("UPDATE consistency_runs SET finished_at=?, scanned=?, repaired=?, conflicts=?, status='done' WHERE id=?", (datetime.now(UTC).isoformat(), scanned, repaired, conflicts, run_id))
        return {'run_id': run_id, 'scanned': scanned, 'repaired': repaired, 'conflicts': conflicts, 'status': 'done'}
    except Exception as exc:
        self.db.execute("UPDATE consistency_runs SET finished_at=?, scanned=?, repaired=?, conflicts=?, status='error', error=? WHERE id=?", (datetime.now(UTC).isoformat(), scanned, repaired, conflicts, str(exc)[:1000], run_id))
        raise` — no method docstring
### `src/orchestrator/daily_ahead.py`
- **class `AheadItem`** — no class docstring
- **class `AheadResult`** — no class docstring
- **function `plan_horizon`** — `def plan_horizon(today: date | None=None, days: int=2) -> list[date]:
    """Сегодня + (days-1) следующих дней."""
    base = today or datetime.now(UTC).date()
    return [base + timedelta(days=i) for i in range(max(1, days))]` — Сегодня + (days-1) следующих дней.
- **function `run_daily_ahead`** — `def run_daily_ahead(items: list[AheadItem], youtube_module: _YoutubeLike | None, *, dry_run: bool=True, make_meta: Callable[[AheadItem], Any] | None=None, make_media: Callable[[AheadItem], Any] | None=None) -> AheadResult:
    """Загрузить недостающие (без external_id). Идемпотентно по external_id."""
    from .platforms.base import PreparedMedia, PublishMeta
    result = AheadResult()
    if youtube_module is None:
        result.errors.append('youtube_module не передан — daily_ahead noop')
        return result
    for it in items:
        if it.external_id:
            result.skipped += 1
            continue
        meta = make_meta(it) if make_meta else PublishMeta(title=it.title)
        media = make_media(it) if make_media else PreparedMedia(path=it.path, kind='video')
        if dry_run:
            logger.info('daily_ahead dry-run would upload %s at %s', it.path, it.slot)
            result.uploaded += 1
            continue
        try:
            youtube_module.upload(media, meta, when=it.slot)
            result.uploaded += 1
        except Exception as e:
            result.errors.append(f'{it.path}: {e}')
    return result` — Загрузить недостающие (без external_id). Идемпотентно по external_id.
- **class `QuotaBuckets`** — YouTube two-bucket accounting (not cost_upload 1600).
  - `can_upload` — `def can_upload(self, cost: int=1) -> bool:
    return self.used_upload + cost <= self.upload_bucket` — no method docstring
  - `reserve_upload` — `def reserve_upload(self, cost: int=1) -> bool:
    if not self.can_upload(cost):
        return False
    self.used_upload += cost
    return True` — no method docstring
- **function `run_daily_ahead_with_quota`** — `def run_daily_ahead_with_quota(items: list[AheadItem], youtube_module: _YoutubeLike | None, quota: QuotaBuckets | None=None, *, dry_run: bool=True, posts_per_day: int | None=None) -> AheadResult:
    """Module-only daily_ahead with optional two-bucket quota reserve.

    posts_per_day is a safety cap (config), independent of upload_bucket 100.
    """
    result = AheadResult()
    if youtube_module is None:
        result.errors.append('youtube_module не передан — daily_ahead noop')
        return result
    q = quota or QuotaBuckets()
    uploaded_today = 0
    for it in items:
        if it.external_id:
            result.skipped += 1
            continue
        if posts_per_day is not None and uploaded_today >= posts_per_day:
            result.skipped += 1
            continue
        if not q.reserve_upload(1):
            result.errors.append(f'quota upload_bucket exhausted at {it.path}')
            break
        if dry_run:
            result.uploaded += 1
            uploaded_today += 1
            continue
        try:
            from .platforms.base import PreparedMedia, PublishMeta
            youtube_module.upload(PreparedMedia(path=it.path, kind='video'), PublishMeta(title=it.title), when=it.slot)
            result.uploaded += 1
            uploaded_today += 1
        except Exception as e:
            result.errors.append(f'{it.path}: {e}')
    return result` — Module-only daily_ahead with optional two-bucket quota reserve. posts_per_day is a safety cap (config), independent of upload_bucket 100.
### `src/orchestrator/db.py`
- **class `Database`** — no class docstring
  - `transaction` — `@contextmanager
def transaction(self) -> Generator[sqlite3.Connection, None, None]:
    """Run multiple related mutations in one SQLite transaction.

        Domain state and its outbox event can therefore commit or roll back
        together.  Callers must use the yielded connection for every statement
        that belongs to the transaction.
        """
    c = self._connect()
    try:
        c.execute('BEGIN IMMEDIATE')
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()` — Run multiple related mutations in one SQLite transaction. Domain state and its outbox event can therefore commit or roll back together. Callers must use the yielded connection for every statement that belongs to the transaction.
  - `conn` — `@contextmanager
def conn(self) -> Generator[sqlite3.Connection, None, None]:
    with self.transaction() as c:
        yield c` — no method docstring
  - `execute` — `def execute(self, sql: str, params: tuple | dict=()) -> int:
    with self.conn() as c:
        return int(c.execute(sql, params).rowcount)` — no method docstring
  - `executemany` — `def executemany(self, sql: str, seq: Iterable) -> None:
    with self.conn() as c:
        c.executemany(sql, seq)` — no method docstring
  - `fetchone` — `def fetchone(self, sql: str, params: tuple | dict=()) -> dict[str, Any] | None:
    with self.conn() as c:
        row = c.execute(sql, params).fetchone()
        return dict(row) if row else None` — no method docstring
  - `fetchall` — `def fetchall(self, sql: str, params: tuple | dict=()) -> list[dict[str, Any]]:
    with self.conn() as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]` — no method docstring
  - `log` — `def log(self, entity_type: str, entity_id: int | None, platform: str | None, action: str, details: str='') -> None:
    self.execute('INSERT INTO publish_log (entity_type, entity_id, platform, action, details, created_at) VALUES (?, ?, ?, ?, ?, ?)', (entity_type, entity_id, platform, action, details, _utc_now()))` — no method docstring
  - `get_setting` — `def get_setting(self, key: str, default: str | None=None) -> str | None:
    row = self.fetchone('SELECT value FROM system_state WHERE key=?', (key,))
    return row['value'] if row else default` — no method docstring
  - `set_setting` — `def set_setting(self, key: str, value: str) -> None:
    self.execute('INSERT INTO system_state (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at', (key, value, _utc_now()))` — no method docstring
  - `set_content_kind` — `def set_content_kind(self, entity_type: str, entity_id: int, platform: str, content_kind: str) -> None:
    """KIND-01: persist content_kind on EPS row."""
    kind = (content_kind or 'video_native').strip() or 'video_native'
    self.execute('UPDATE entity_platform_status SET content_kind=? WHERE entity_type=? AND entity_id=? AND platform=?', (kind, entity_type, entity_id, platform))` — KIND-01: persist content_kind on EPS row.
  - `upsert_upload` — `def upsert_upload(self, engine: str, platform: str, external_id: str, url: str | None=None, title: str | None=None, description: str | None=None, published_at: str | None=None, duration_sec: float | None=None, width: int | None=None, height: int | None=None, thumbnail_url: str | None=None, origin: str='manual', raw_json: str | None=None) -> dict[str, Any]:
    now = _utc_now()
    self.execute('\n            INSERT INTO platform_uploads\n                (engine, platform, platform_video_id, url, title, description, published_at,\n                 duration_sec, width, height, thumbnail_url, origin, raw_json,\n                 first_seen_at, last_seen_at)\n            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n            ON CONFLICT(engine, platform, platform_video_id) DO UPDATE SET\n                url=COALESCE(excluded.url, platform_uploads.url),\n                title=COALESCE(excluded.title, platform_uploads.title),\n                description=COALESCE(excluded.description, platform_uploads.description),\n                published_at=COALESCE(excluded.published_at, platform_uploads.published_at),\n                duration_sec=COALESCE(excluded.duration_sec, platform_uploads.duration_sec),\n                width=COALESCE(excluded.width, platform_uploads.width),\n                height=COALESCE(excluded.height, platform_uploads.height),\n                thumbnail_url=COALESCE(excluded.thumbnail_url, platform_uploads.thumbnail_url),\n                origin=excluded.origin,\n                raw_json=COALESCE(excluded.raw_json, platform_uploads.raw_json),\n                last_seen_at=excluded.last_seen_at\n            ', (engine, platform, external_id, url, title, description, published_at, duration_sec, width, height, thumbnail_url, origin, raw_json, now, now))
    return self.fetchone('SELECT * FROM platform_uploads WHERE engine=? AND platform=? AND platform_video_id=?', (engine, platform, external_id))` — no method docstring
  - `get_upload` — `def get_upload(self, upload_id: int) -> dict[str, Any] | None:
    return self.fetchone('SELECT * FROM platform_uploads WHERE id=?', (upload_id,))` — no method docstring
  - `list_uploads` — `def list_uploads(self, status: str | None=None, platform: str | None=None) -> list[dict[str, Any]]:
    sql = 'SELECT * FROM platform_uploads WHERE 1=1'
    params: list[Any] = []
    if status:
        sql += ' AND match_status=?'
        params.append(status)
    if platform:
        sql += ' AND platform=?'
        params.append(platform)
    sql += ' ORDER BY COALESCE(published_at, first_seen_at) DESC'
    return self.fetchall(sql, tuple(params))` — no method docstring
  - `set_upload_match` — `def set_upload_match(self, upload_id: int, entity_type: str | None, entity_id: int | None, confidence: float | None=None, status: str='confirmed') -> None:
    self.execute('UPDATE platform_uploads SET match_status=?, matched_entity_type=?, matched_entity_id=?, confidence=?, last_seen_at=? WHERE id=?', (status, entity_type, entity_id, confidence, _utc_now(), upload_id))` — no method docstring
  - `ensure_platform_states` — `def ensure_platform_states(self, platforms: list[str]) -> None:
    now = _utc_now()
    with self.conn() as c:
        for p in platforms:
            c.execute('INSERT OR IGNORE INTO platform_queue_state (platform, updated_at) VALUES (?, ?)', (p, now))
            c.execute('INSERT OR IGNORE INTO platform_safety_state (platform, updated_at) VALUES (?, ?)', (p, now))` — no method docstring
- **function `verify_eps_schema`** — `def verify_eps_schema(db: 'Database') -> None:
    """Fail closed if entity_platform_status is missing critical columns."""
    rows = db.fetchall('PRAGMA table_info(entity_platform_status)')
    names = {str(r['name'] if isinstance(r, dict) else r[1]) for r in rows or []}
    missing = [c for c in _CRITICAL_EPS_COLS if c not in names]
    if missing:
        raise RuntimeError(f'schema incomplete, missing EPS columns: {missing}')` — Fail closed if entity_platform_status is missing critical columns.
### `src/orchestrator/http_client.py`
- **function `mask_secrets`** — `def mask_secrets(text: str) -> str:
    """Заменить токены/секреты на *** (для логов и сообщений об ошибках)."""
    if not text:
        return text

    def _sub(m: re.Match[str]) -> str:
        g = m.groups()
        if g[0]:
            return f'{g[0]}***'
        if g[1]:
            return f'{g[1]}=***'
        if g[3]:
            return f'{g[3]}***'
        return '***'
    return _SECRET_RE.sub(_sub, text)` — Заменить токены/секреты на *** (для логов и сообщений об ошибках).
- **function `cleanup_debug_dir`** — `def cleanup_debug_dir(debug_dir: Path, *, retention_sec: float=_DEBUG_RETENTION_SEC) -> int:
    """Удалить файлы старше retention. Возвращает число удалённых."""
    if not debug_dir.is_dir():
        return 0
    cutoff = time.time() - retention_sec
    removed = 0
    try:
        for p in debug_dir.iterdir():
            if not p.is_file():
                continue
            try:
                if p.stat().st_mtime < cutoff:
                    p.unlink(missing_ok=True)
                    removed += 1
            except OSError:
                pass
    except OSError:
        pass
    return removed` — Удалить файлы старше retention. Возвращает число удалённых.
- **class `ModuleHttpClient`** — HTTP-клиент модулей: таймауты, backoff, Retry-After, маскирование. Инъектируемый: в тестах передаётся mock / httpx.MockTransport. A7: debug_bodies + debug_dir → запись тел (masked) ≤10 МБ, ретенция 7 дней.
  - `request` — `def request(self, method: str, url: str, *, headers: dict[str, str] | None=None, params: dict[str, Any] | None=None, json: Any=None, data: Any=None, content: Any=None, files: Any=None, idempotent: bool=True, upload: bool=False, idempotency_key: str | None=None, correlation_id: str | None=None) -> httpx.Response:
    """Выполнить запрос с ретраями только для безопасных/TRANSIENT случаев."""
    method_u = method.upper()
    self._validate_url(url)
    safe_retry = idempotent and method_u in ('GET', 'HEAD', 'PUT', 'DELETE', 'PATCH')
    if method_u == 'POST' and idempotency_key:
        safe_retry = True
    last_exc: Exception | None = None
    delays = [1.0, 2.0, 4.0, 8.0, 16.0]
    for attempt in range(self.max_retries):
        t0 = time.monotonic()
        try:
            self._rate_limit()
            req_headers = dict(headers or {})
            request_id = str(correlation_id or uuid.uuid4())
            req_headers.setdefault('X-Request-Id', request_id)
            req_headers.setdefault('X-Correlation-Id', request_id)
            if idempotency_key:
                req_headers.setdefault('Idempotency-Key', str(idempotency_key))
            with self._client(upload=upload) as client:
                request_kwargs: dict[str, Any] = {'headers': req_headers, 'params': params, 'json': json, 'files': files}
                if data is not None:
                    if isinstance(data, (bytes, bytearray, memoryview, str)):
                        request_kwargs['content'] = data
                    else:
                        request_kwargs['data'] = data
                elif content is not None:
                    request_kwargs['content'] = content
                resp = client.request(method_u, url, **request_kwargs)
            elapsed = time.monotonic() - t0
            self._log(method_u, url, resp.status_code, elapsed, resp)
            if resp.status_code == 429:
                if not safe_retry:
                    return resp
                sleep_for = _retry_after_seconds(resp)
                if sleep_for is None:
                    sleep_for = delays[min(attempt, len(delays) - 1)]
                    sleep_for += random.uniform(0, sleep_for * 0.25)
                last_exc = httpx.HTTPStatusError('rate limited', request=resp.request, response=resp)
                if attempt + 1 >= self.max_retries:
                    return resp
                time.sleep(sleep_for)
                continue
            if resp.status_code >= 500 and safe_retry:
                last_exc = httpx.HTTPStatusError(f'server {resp.status_code}', request=resp.request, response=resp)
                if attempt + 1 >= self.max_retries:
                    return resp
                sleep_for = delays[min(attempt, len(delays) - 1)]
                sleep_for += random.uniform(0, sleep_for * 0.25)
                time.sleep(sleep_for)
                continue
            return resp
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout, httpx.ReadTimeout) as e:
            last_exc = e
            if not safe_retry and method_u == 'POST':
                raise
            if attempt + 1 >= self.max_retries:
                raise
            sleep_for = delays[min(attempt, len(delays) - 1)]
            sleep_for += random.uniform(0, sleep_for * 0.25)
            logger.warning('http %s %s transient %s, retry in %.1fs (%s/%s)', method_u, mask_secrets(url), type(e).__name__, sleep_for, attempt + 1, self.max_retries)
            time.sleep(sleep_for)
    if last_exc is not None:
        raise last_exc
    raise RuntimeError('http retry exhausted')` — Выполнить запрос с ретраями только для безопасных/TRANSIENT случаев.
  - `get_json` — `def get_json(self, url: str, **kwargs: Any) -> Any:
    r = self.request('GET', url, **kwargs)
    r.raise_for_status()
    if not r.content:
        return {}
    return r.json()` — no method docstring
  - `request_json` — `def request_json(self, method: str, url: str, **kwargs: Any) -> Any:
    r = self.request(method, url, **kwargs)
    r.raise_for_status()
    if not r.content:
        return {}
    return r.json()` — no method docstring
### `src/orchestrator/http_server.py`
- **function `start_http_server`** — `def start_http_server(port: int, get_health: Callable[[], dict[str, Any]], webapp_handler: Callable[[str, str, dict, bytes], tuple[int, Any, str]] | None=None, webhook_handler: Callable[[str, str, dict, bytes], tuple[int, Any, str]] | None=None) -> ThreadingHTTPServer | None:
    if port <= 0:
        return None

    class Handler(BaseHTTPRequestHandler):

        def _send(self, code: int, payload: Any, ctype: str) -> None:
            if isinstance(payload, (dict, list)):
                body = json.dumps(payload, ensure_ascii=False).encode()
                ctype = 'application/json; charset=utf-8'
            elif isinstance(payload, bytes):
                body = payload
                ctype = ctype
            else:
                body = str(payload).encode()
                ctype = ctype or 'text/plain; charset=utf-8'
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            import os as _os
            cors = _os.getenv('ORCH_CORS_ORIGIN', '').strip()
            if cors:
                self.send_header('Access-Control-Allow-Origin', cors)
                self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Webapp-Key, X-Health-Token, Authorization')
                self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            if ctype.startswith('image/'):
                self.send_header('Cache-Control', 'public, max-age=604800, immutable')
            else:
                self.send_header('Cache-Control', 'no-store')
            if 'html' in (ctype or ''):
                nonce = getattr(_webapp_nonce, 'value', '') or ''
                src = "script-src 'self' https://telegram.org"
                sty = "style-src 'self'"
                if nonce:
                    src += f" 'nonce-{nonce}'"
                    sty += f" 'nonce-{nonce}'"
                self.send_header('Content-Security-Policy', f"default-src 'self'; {src}; {sty}; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'self'")
                self.send_header('Referrer-Policy', 'no-referrer')
            self.end_headers()
            self.wfile.write(body)

        def _headers_dict(self) -> dict[str, str]:
            return {k: v for k, v in self.headers.items()}

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            if path in ('/health', '/health/live', '/health/ready', '/ready', '/metrics', '/'):
                health = get_health()
                if path in ('/ready', '/health/ready'):
                    ready = bool(health.get('ready', health.get('db') == 'ok')) and (not bool(health.get('stopping')))
                    code = 200 if ready else 503
                    self._send(code, {'ready': ready, **health}, 'application/json')
                    return
                if path == '/health/live':
                    self._send(200, {'live': True, 'stopping': bool(health.get('stopping'))}, 'application/json')
                    return
                token = os.getenv('ORCH_HEALTH_TOKEN', '').strip()
                if token and path != '/health':
                    provided = self.headers.get('X-Health-Token') or self.headers.get('Authorization') or ''
                    if provided.startswith('Bearer '):
                        provided = provided[7:]
                    import hmac
                    if not hmac.compare_digest(provided, token):
                        self._send(401, {'error': 'unauthorized'}, 'application/json')
                        return
                self._send(200, get_health(), 'application/json')
                return
            if webhook_handler and path.startswith('/webhooks/'):
                code, payload, ctype = webhook_handler('GET', self.path, self._headers_dict(), b'')
                self._send(code, payload, ctype)
                return
            if webapp_handler and path.startswith('/webapp'):
                code, payload, ctype = webapp_handler('GET', self.path, self._headers_dict(), b'')
                self._send(code, payload, ctype)
                return
            if webapp_handler and path.startswith('/oauth/callback/'):
                forwarded = '/webapp/api' + path
                if self.path[len(path):]:
                    forwarded += self.path[len(path):]
                code, payload, ctype = webapp_handler('GET', forwarded, self._headers_dict(), b'')
                self._send(code, payload, ctype)
                return
            self._send(404, {'error': 'not found'}, 'application/json')

        def do_OPTIONS(self):
            self.send_response(204)
            import os as _os
            cors = _os.getenv('ORCH_CORS_ORIGIN', '').strip()
            if cors:
                self.send_header('Access-Control-Allow-Origin', cors)
                self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Webapp-Key, X-Health-Token, Authorization')
                self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.end_headers()

        def do_POST(self):
            parsed = urlparse(self.path)
            path = parsed.path
            try:
                max_body = int(os.getenv('ORCH_MAX_BODY_BYTES', str(50 * 1024 * 1024)))
            except ValueError:
                max_body = 50 * 1024 * 1024
            try:
                length = int(self.headers.get('Content-Length') or 0)
            except (TypeError, ValueError):
                self._send(400, {'error': 'bad content-length'}, 'application/json')
                return
            if length < 0:
                self._send(400, {'error': 'bad content-length'}, 'application/json')
                return
            if length > max_body:
                self._send(413, {'error': 'payload too large'}, 'application/json')
                return
            body = self.rfile.read(length) if length else b''
            if webhook_handler and path.startswith('/webhooks/'):
                code, payload, ctype = webhook_handler('POST', self.path, self._headers_dict(), body)
                self._send(code, payload, ctype)
                return
            if webapp_handler and path.startswith('/webapp'):
                code, payload, ctype = webapp_handler('POST', self.path, self._headers_dict(), body)
                self._send(code, payload, ctype)
                return
            self._send(404, {'error': 'not found'}, 'application/json')

        def log_message(self, fmt, *args):
            logger.debug('http: ' + fmt, *args)
    try:
        bind = os.getenv('ORCH_HTTP_BIND', '127.0.0.1').strip() or '127.0.0.1'
        server = ThreadingHTTPServer((bind, port), Handler)
    except OSError as e:
        logger.warning('HTTP server not started: %s', e)
        return None
    t = threading.Thread(target=server.serve_forever, name='http', daemon=True)
    t.start()
    logger.info('HTTP server on %s:%s (health + webapp)', bind, port)
    return server` — no docstring
### `src/orchestrator/jobs.py`
- **class `JobState`** — no class docstring
- **class `Job`** — Прогресс длительной операции с возможностью отмены.
  - `set_total` — `def set_total(self, total: int) -> None:
    self.state.total = max(0, int(total))` — no method docstring
  - `tick` — `def tick(self, n: int=1, message: str='') -> None:
    self.state.done += n
    if message:
        self.state.message = message` — no method docstring
  - `cancelled` — `@property
def cancelled(self) -> bool:
    return self._cancel.is_set()` — no method docstring
  - `cancel` — `def cancel(self) -> None:
    self._cancel.set()` — no method docstring
  - `finish` — `def finish(self, status: str='done', message: str='') -> None:
    if status == 'done' and self.cancelled:
        status = 'cancelled'
    if status == 'done':
        self.state.done = max(self.state.done, self.state.total)
    self.state.status = status
    if message:
        self.state.message = message
    self.state.finished_at = time.time()` — no method docstring
  - `snapshot` — `def snapshot(self) -> dict:
    s = self.state
    elapsed = (s.finished_at or time.time()) - s.started_at
    if s.total > 0:
        pct = min(100, int(100 * s.done / s.total))
    else:
        pct = 100 if s.status == 'done' else 0
    eta = None
    if s.status == 'running' and s.total > 0 and (s.done > 0):
        per = elapsed / s.done
        eta = max(0, int(per * (s.total - s.done)))
    return {'id': s.id, 'kind': s.kind, 'title': s.title, 'total': s.total, 'done': s.done, 'percent': pct, 'status': s.status, 'message': s.message, 'elapsed': int(elapsed), 'eta': eta}` — no method docstring
- **class `JobRegistry`** — Одна активная задача (панель однопользовательская).
  - `start` — `def start(self, kind: str, title: str='', total: int=0) -> Job:
    with self._lock:
        job = Job(kind, title, total)
        self.current = job
        return job` — no method docstring
  - `get` — `def get(self) -> Job | None:
    with self._lock:
        return self.current` — no method docstring
  - `snapshot` — `def snapshot(self) -> dict | None:
    job = self.get()
    if job is None:
        return None
    snap = job.snapshot()
    if snap['status'] != 'running' and time.time() - (job.state.finished_at or 0) > 60:
        return None
    return snap` — no method docstring
  - `cancel` — `def cancel(self) -> bool:
    job = self.get()
    if job is None or job.state.status != 'running':
        return False
    job.cancel()
    return True` — no method docstring
### `src/orchestrator/link_updater.py`
- **class `LinkUpdater`** — Update release_url / external_url on EPS; module-only (no platform client).
  - `check_missing_urls` — `def check_missing_urls(self) -> int:
    """Find published long videos without release_url past timeout → dialog or default."""
    timeout = self.cfg.link_update.release_url_timeout_min
    cutoff = (self.clock.now() - timedelta(minutes=timeout)).isoformat()
    rows = self.db.fetchall("\n            SELECT entity_id, platform, published_at FROM entity_platform_status\n            WHERE entity_type='long_video' AND status='published'\n              AND (release_url IS NULL OR release_url='')\n              AND (external_url IS NULL OR external_url='')\n              AND published_at IS NOT NULL AND published_at < ?\n            ", (cutoff,))
    acted = 0
    for r in rows:
        default = self.cfg.link_update.missing_url_default_action
        if default == 'post_without_link':
            self.db.execute("UPDATE entity_platform_status SET link_updated_at=? WHERE entity_type='long_video' AND entity_id=? AND platform=?", (self.clock.now().isoformat(), r['entity_id'], r['platform']))
            self.db.execute("UPDATE entity_platform_status SET status='published' WHERE entity_type='long_video' AND entity_id=? AND platform=? AND status='published'", (r['entity_id'], r['platform']))
            acted += 1
        elif default == 'refresh':
            self.db.execute("UPDATE entity_platform_status SET link_updated_at=? WHERE entity_type='long_video' AND entity_id=? AND platform=?", (self.clock.now().isoformat(), r['entity_id'], r['platform']))
            acted += 1
        else:
            self.tg.ask_missing_url(r['entity_id'], r['platform'])
            acted += 1
    return acted` — Find published long videos without release_url past timeout → dialog or default.
  - `force_update` — `def force_update(self, entity_id: int, platform: str, new_url: str, scheduler: Any=None, entity_type: str | None=None) -> bool:
    """Set release_url + external_url and drive refresh path."""
    if not (new_url.startswith('http://') or new_url.startswith('https://')):
        return False
    if entity_type:
        row = self.db.fetchone('SELECT entity_type, release_url, external_id, external_url FROM entity_platform_status WHERE entity_type=? AND entity_id=? AND platform=?', (entity_type, entity_id, platform))
    else:
        row = self.db.fetchone("SELECT entity_type, release_url, external_id, external_url FROM entity_platform_status WHERE entity_id=? AND platform=? ORDER BY   CASE WHEN release_url IS NULL OR release_url='' THEN 0 ELSE 1 END,   CASE entity_type WHEN 'long_video' THEN 0 ELSE 1 END LIMIT 1", (entity_id, platform))
    if not row:
        return False
    entity_type = row['entity_type'] or 'long_video'
    self.db.execute('UPDATE entity_platform_status SET release_url=?, external_url=?, link_updated_at=? WHERE entity_id=? AND platform=? AND entity_type=?', (new_url, new_url, self.clock.now().isoformat(), entity_id, platform, entity_type))
    self.db.log(entity_type, entity_id, platform, 'force_link_update', new_url)
    if scheduler is not None:
        if entity_type == 'long_video':
            try:
                self.refresh_thematic_after_url(entity_id, platform, scheduler)
            except Exception:
                logger.exception('force_update thematic refresh failed')
        try:
            if hasattr(scheduler, 'refresh_telegram_links'):
                scheduler.refresh_telegram_links()
        except Exception:
            logger.exception('force_update telegram refresh failed')
    return True` — Set release_url + external_url and drive refresh path.
  - `refresh_thematic_after_url` — `def refresh_thematic_after_url(self, parent_id: int, platform: str, scheduler: Any) -> int:
    """When release_url appears: reschedule thematic shorts with link template."""
    parent = self.db.fetchone("SELECT release_url, external_url FROM entity_platform_status WHERE entity_type='long_video' AND entity_id=? AND platform=? AND status='published'", (parent_id, platform))
    if not parent:
        return 0
    url = parent.get('release_url') or parent.get('external_url') or ''
    if not url:
        return 0
    template = self.cfg.description_templates.get('thematic_short', '{description}\n\n▶ Полное видео: {link}')
    rows = self.db.fetchall("\n            SELECT eps.entity_id, eps.external_id, eps.scheduled_for,\n                   s.video_path, s.title_text, s.description_text, s.hashtags_text\n            FROM entity_platform_status eps\n            JOIN shorts s ON s.id = eps.entity_id\n            WHERE eps.entity_type='short' AND eps.platform=?\n              AND s.parent_video_id=?\n              AND eps.status IN ('scheduled', 'updating')\n              AND eps.external_id IS NOT NULL AND eps.external_id != ''\n            ", (platform, parent_id))
    updated = 0
    for r in rows:
        desc = template.format(description=r['description_text'] or '', link=url)
        content = {'title': r['title_text'] or '', 'description': desc, 'hashtags': r['hashtags_text'] or ''}
        sched = None
        if r['scheduled_for']:
            try:
                sched = datetime.fromisoformat(str(r['scheduled_for']).replace('Z', '+00:00'))
            except Exception:
                sched = None
        try:
            old_id = r['external_id']
            self.db.execute("UPDATE entity_platform_status SET external_id=NULL, status='ready' WHERE entity_type='short' AND entity_id=? AND platform=?", (r['entity_id'], platform))
            pub = getattr(scheduler, 'publisher', None)
            if pub is None:
                continue
            try:
                post = pub.publish('short', r['entity_id'], platform, r['video_path'], content, sched)
            except Exception:
                post = None
                logger.exception('refresh thematic publish failed %s', r['entity_id'])
            if post:
                if old_id and hasattr(pub, '_try_module_delete'):
                    try:
                        pub._try_module_delete(platform, old_id)
                    except Exception:
                        logger.debug('old post delete skipped %s', old_id, exc_info=True)
                updated += 1
            elif old_id:
                self.db.execute("UPDATE entity_platform_status SET external_id=?, status='scheduled', last_error='refresh_failed' WHERE entity_type='short' AND entity_id=? AND platform=?", (old_id, r['entity_id'], platform))
        except Exception:
            logger.exception('refresh thematic short %s', r['entity_id'])
    return updated` — When release_url appears: reschedule thematic shorts with link template.
### `src/orchestrator/main.py`
- **function `build`** — `def build(args: argparse.Namespace) -> dict:
    cfg = load_config(args.config)
    db = Database(args.db)
    platforms = list(cfg.platforms.keys())
    db.ensure_platform_states(platforms)
    clock = SystemClock()
    platform = None
    tg_pub = create_telegram_publisher(cfg)
    if tg_pub is not None:
        logger.info('Telegram: публикация через Bot API, канал %s', getattr(cfg.platforms.get('telegram'), 'publish_chat_id', '?'))
    safety = SafetyChecker(db, cfg, clock)
    try:
        _guard_ttl = int(os.getenv('ORCH_GUARD_TTL_SEC', '') or 120)
    except ValueError:
        _guard_ttl = 120
    guard = ScheduleGuard(cfg, clock, ttl_sec=_guard_ttl, sources=[('eps', eps_source(db))])
    comps_guard = guard
    broker = None
    if os.getenv('TOKEN_BROKER_URL'):
        broker = TokenBrokerClient(os.environ['TOKEN_BROKER_URL'], os.getenv('TOKEN_BROKER_SECRET', ''))
    from .provider_supervisor import ProviderSupervisor
    from .provider_access import ProviderAccessStore
    from .outbox import Outbox, DurableJobStore
    from .consistency import ConsistencySweeper
    supervisor = ProviderSupervisor(db)
    provider_access = ProviderAccessStore(db)
    outbox = Outbox(db)
    from .media_transfer import MediaTransferManager
    media_transfer = MediaTransferManager(db)
    from .token_lifecycle import TokenLifecycleStore
    from .webhook_processor import WebhookEventProcessor
    from .scheduler_recovery import SchedulerRecovery
    token_lifecycle = TokenLifecycleStore(os.getenv('TOKENS_DIR', 'tokens'), db=db)
    webhook_processor = WebhookEventProcessor(db)
    scheduler_recovery = SchedulerRecovery(db, clock)
    durable_jobs = DurableJobStore(db)

    def _job_publish_completed(body):
        logger.info('durable event publish.completed: %s/%s/%s', body.get('platform'), body.get('entity_type'), body.get('entity_id'))
    job_handlers = {'publish.completed': _job_publish_completed}
    publisher = Publisher(db, cfg, safety, clock, dry_run=args.dry_run, guard=guard, broker=broker, supervisor=supervisor, outbox=outbox)
    scheduler = Scheduler(db, cfg, publisher, safety, clock, telegram=tg_pub)
    status_sync = StatusSync(db, clock, cfg)
    recon = ModuleReconciliation(db, cfg, clock)
    watcher = Watcher(db, cfg, clock, args.watch_roots or [], max_age_days=int(getattr(cfg, 'watch_max_age_days', 3650) or 0))
    tg = TelegramNotifier(cfg, db, clock)
    tail = TailManager(db, cfg, clock, tg)
    link_upd = LinkUpdater(db, cfg, clock, tg)
    manual = ManualUploadsService(db, cfg, clock)
    try:
        manual_sources = build_manual_sources(cfg, os.environ)
    except Exception:
        manual_sources = {}
    backlog = BacklogManager(db, cfg, clock, scheduler=scheduler, notifier=tg)
    try:
        from .platforms import default_registry
        module_registry = default_registry()
    except Exception:
        module_registry = None
        logger.warning('module registry unavailable', exc_info=True)
    try:
        from .media_host.b2 import create_media_host
        import os as _os
        media_host = create_media_host(dry_run=bool(args.dry_run), db=db, key_id=_os.getenv('B2_KEY_ID', ''), app_key=_os.getenv('B2_APPLICATION_KEY', ''), bucket_id=_os.getenv('B2_BUCKET_ID', ''), bucket_name=_os.getenv('B2_BUCKET', ''))
    except Exception:
        media_host = None
        logger.debug('media_host init skipped', exc_info=True)
    from .publish_recovery import PublishAttemptRecovery
    publish_recovery = PublishAttemptRecovery(db, module_registry, cfg=cfg, clock=clock) if module_registry is not None else None

    def _consistency_factory(platform: str, **deps):
        if module_registry is None:
            raise RuntimeError('module registry unavailable')
        from .auth_tokens import token_provider_for
        return module_registry.create(platform, cfg=cfg, dry_run=bool(args.dry_run), token_provider=token_provider_for(platform), account_id=str(deps.get('account_id') or ''), media_host=media_host)
    consistency = ConsistencySweeper(db, module_registry, cfg, module_factory=_consistency_factory) if module_registry is not None else None
    comps = {'cfg': cfg, 'db': db, 'jobs': JobRegistry(), 'guard': comps_guard, 'clock': clock, 'safety': safety, 'publisher': publisher, 'scheduler': scheduler, 'status_sync': status_sync, 'recon': recon, 'watcher': watcher, 'tg': tg, 'tail': tail, 'link_upd': link_upd, 'manual': manual, 'manual_sources': manual_sources, 'backlog': backlog, 'broker': broker, 'module_registry': module_registry, 'media_host': media_host, 'provider_supervisor': supervisor, 'provider_access': provider_access, 'outbox': outbox, 'durable_jobs': durable_jobs, 'media_transfer': media_transfer, 'token_lifecycle': token_lifecycle, 'webhook_processor': webhook_processor, 'scheduler_recovery': scheduler_recovery, 'job_handlers': job_handlers, 'publish_recovery': publish_recovery, 'consistency': consistency}
    if module_registry is not None and hasattr(publisher, '_module_registry'):
        publisher._module_registry = module_registry
    if media_host is not None and hasattr(publisher, 'media_host'):
        publisher.media_host = media_host
    if hasattr(recon, 'media_host'):
        recon.media_host = media_host
    setup_commands(tg, comps)
    db = comps['db']
    transport = TelegramTransport(on_message=tg.handle_update, load_seen=lambda: int(db.get_setting('tg_seen_update_id') or 0), save_seen=lambda v: db.set_setting('tg_seen_update_id', str(v)))
    tg.transport = transport
    comps['tg_transport'] = transport
    transport.recover_voices()
    return comps` — no docstring
- **function `main`** — `def main(argv: list[str] | None=None) -> int:
    parser = argparse.ArgumentParser(description=f'Content publish orchestrator v{__version__}')
    parser.add_argument('--pidfile', default='', help='single-instance pidfile path')
    parser.add_argument('--no-pidfile', action='store_true', help='disable pidfile lock')
    parser.add_argument('--config', default='config.yaml')
    parser.add_argument('--db', default='data/data.sqlite')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--read-only', action='store_true')
    parser.add_argument('--watch-roots', nargs='*', default=[])
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--scan', action='store_true')
    parser.add_argument('--schedule', action='store_true')
    parser.add_argument('--sync', action='store_true')
    parser.add_argument('--reconcile', action='store_true')
    parser.add_argument('--backup', action='store_true')
    parser.add_argument('--test-schedule', action='store_true', help='Пробный пост: --test-platform P --test-entity TYPE:ID [--test-delay N] [--test-dry-run]')
    parser.add_argument('--test-platform', default='')
    parser.add_argument('--test-entity', default='', help='short:123 | long_video:45')
    parser.add_argument('--test-delay', type=int, default=None)
    parser.add_argument('--test-dry-run', action='store_true')
    parser.add_argument('--version', action='store_true')
    parser.add_argument('--daemon', action='store_true', help='Run continuous loop')
    parser.add_argument('--remote-scan', action='store_true', help='Run remote inventory scan')
    parser.add_argument('--claims', action='store_true', help='Run YouTube claims checkpoint')
    parser.add_argument('--b2-cleanup', action='store_true', help='Run B2 TTL cleanup')
    parser.add_argument('--health-port', type=int, default=8080)
    args = parser.parse_args(argv)
    if args.version:
        print(__version__)
        return 0
    if args.read_only:
        os.environ['ORCH_READ_ONLY'] = '1'
        logger.info('Read-only mode (ORCH_READ_ONLY=1)')
    _ensure_single_instance(args)
    comps = build(args)
    cfg = comps['cfg']
    _tp = getattr(cfg, 'test_publish', None)
    if _tp is not None and getattr(_tp, 'enabled', False) and (not (getattr(_tp, 'prod_integration_ids', None) or [])):
        logging.getLogger(__name__).warning('test_publish.enabled=true, но prod_integration_ids пуст: тест разрешён только для test_integration_ids=%s (fail-closed). При переходе на боевые каналы — заполните prod ids.', list(getattr(_tp, 'test_integration_ids', []) or []))
    from .metrics import Metrics as _Metrics
    metrics = comps.get('metrics') or _Metrics(Path(args.db).resolve().parent / 'metrics.json')
    comps['metrics'] = metrics
    if args.daemon:
        from .runner import Runner
        comps['tg_transport'].start()
        try:
            Runner(comps, dry_run=args.dry_run, health_port=args.health_port).run_forever()
        finally:
            comps['tg_transport'].stop()
        return 0
    if args.scan or args.once:
        stats = comps['watcher'].scan()
        logger.info('Scan: %s', stats)
        parents = comps['db'].fetchall('SELECT DISTINCT parent_video_id FROM shorts WHERE parent_video_id IS NOT NULL')
        for p in parents:
            move_excess_shorts(comps['db'], cfg, comps['clock'], p['parent_video_id'])
    if args.schedule or args.once:
        _roots = [str(r) for r in comps['watcher'].effective_roots()]
        n = comps['scheduler'].schedule_long_videos(scope_roots=_roots)
        logger.info('Scheduled long: %s', n)
        n2 = comps['scheduler'].schedule_standalone_shorts(comps['tail'], scope_roots=_roots)
        logger.info('Scheduled standalone: %s', n2)
        pubs = comps['db'].fetchall("SELECT entity_id, platform FROM entity_platform_status WHERE entity_type='long_video' AND status IN ('published','scheduled')")
        for r in pubs:
            nt = comps['scheduler'].schedule_thematic_shorts(r['entity_id'], r['platform'], scope_roots=_roots)
            if nt:
                logger.info('Thematic %s/%s: %s', r['entity_id'], r['platform'], nt)
    if args.sync or args.once:
        n = comps['status_sync'].sync()
        logger.info('Status sync: %s', n)
        comps['link_upd'].check_missing_urls()
        for p in cfg.platforms:
            comps['tail'].check_soft_enter(p)
    if args.reconcile or args.once:
        r = comps['recon'].run()
        logger.info('Reconciliation: %s', r)
    if args.test_schedule:
        from .test_publish import TestPublishError, schedule_test_post
        if ':' not in args.test_entity or not args.test_platform:
            print('нужно: --test-platform P --test-entity TYPE:ID', file=sys.stderr)
            return 2
        etype, eid = args.test_entity.split(':', 1)
        try:
            res = schedule_test_post(comps, platform=args.test_platform, entity_type=etype.strip(), entity_id=int(eid), delay_minutes=args.test_delay, dry_run=args.test_dry_run)
        except TestPublishError as e:
            print(f'test-schedule: {e}', file=sys.stderr)
            return 1
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    if args.remote_scan:
        try:
            from .remote_scan.service import RemoteScanService
            from .platforms import default_registry
            svc = RemoteScanService(comps['db'], cfg, module_registry=default_registry(), media_host=comps.get('media_host'))
            out = []
            for plat, pcfg in cfg.platforms.items():
                if getattr(pcfg, 'enabled', False):
                    out.append(svc.scan_platform(plat))
            print(out)
        except Exception as e:
            logger.exception('remote-scan failed')
            print(f'remote-scan error: {e}', file=sys.stderr)
            return 1
        return 0
    if args.claims:
        try:
            from .claims import run_claims_check
            from .platforms import default_registry, resolve_engine
            from .auth_tokens import token_provider_for
            yt = None
            eng = str(cfg.engine_for('youtube') or '')
            try:
                resolved = resolve_engine(eng)
                reg = comps.get('module_registry') or default_registry()
                if resolved.kind == 'module' and resolved.module_id and reg.has(resolved.module_id):
                    yt = reg.create(resolved.module_id, cfg=cfg, dry_run=bool(args.dry_run), http=None, token_provider=token_provider_for('youtube'), media_host=comps.get('media_host'))
            except Exception:
                logger.debug('youtube module create for CLI claims failed', exc_info=True)
            res = run_claims_check(comps['db'], clock=comps.get('clock'), youtube_module=yt, notifier=comps.get('tg'))
            print(res)
        except Exception as e:
            logger.exception('claims failed')
            print(f'claims error: {e}', file=sys.stderr)
            return 1
        return 0
    if args.b2_cleanup:
        try:
            from .media_host.b2 import create_media_host
            host = create_media_host(dry_run=args.dry_run, db=comps['db'])
            n = host.cleanup_expired()
            print({'deleted': n})
        except Exception as e:
            logger.exception('b2-cleanup failed')
            print(f'b2-cleanup error: {e}', file=sys.stderr)
            return 1
        return 0
    if args.backup or args.once:
        bdir = Path(args.db).resolve().parent.parent / 'backups'
        try:
            path = run_backup(comps['db'], cfg, bdir)
        except Exception:
            logger.exception('backup failed (не критично, продолжаем)')
            path = None
        logger.info('Backup: %s', path)
    if not any([args.scan, args.schedule, args.sync, args.reconcile, args.backup, args.once]):
        logger.info('Orchestrator v%s ready (dry-run=%s)', __version__, args.dry_run)
    return 0` — no docstring
### `src/orchestrator/manual_sources.py`
- **function `build_manual_sources`** — `def build_manual_sources(cfg: Any, env: dict) -> dict[str, Any]:
    """Build manual-source objects from native provider modules only.

    Legacy legacy transport transports are intentionally not resolvable in the
    production runtime. Manual adoption is a metadata/storage operation; actual
    platform transport remains inside the native module registry.
    """
    broker = None
    if env.get('TOKEN_BROKER_URL'):
        broker = TokenBrokerClient(env['TOKEN_BROKER_URL'], env.get('TOKEN_BROKER_SECRET', ''))
    out: dict[str, Any] = {}
    for platform, pcfg in (cfg.platforms or {}).items():
        if not getattr(pcfg, 'enabled', True):
            continue
        try:
            engine = str(cfg.engine_for(platform) or '').strip().lower()
            if not engine.startswith('module:'):
                logger.warning('manual_sources: skipping non-module engine for %s', platform)
                continue
            module_id = engine.split(':', 1)[1].strip()
            from .platforms import default_registry
            reg = default_registry()
            if not reg.has(module_id):
                logger.error('manual_sources: module %r not registered (platform=%s)', module_id, platform)
                continue
            aid = str(getattr(pcfg, 'account_id', '') or getattr(pcfg, 'integration_id', '') or '')

            def _token_provider(p: str=platform, b: Any=broker, i: str=aid) -> str:
                if b is not None:
                    try:
                        value = str((b.get(p, i) or {}).get('token') or '')
                        if value:
                            return value
                    except Exception:
                        logger.debug('manual token broker lookup failed', exc_info=True)
                try:
                    from .auth_tokens import get_access_token
                    return get_access_token(p, account_id=i)
                except Exception:
                    return ''
            out[platform] = reg.create(module_id, token_provider=_token_provider, cfg=cfg, dry_run=False, http=None, account_id=aid)
        except Exception:
            logger.exception('manual_sources: failed to create module for %s', platform)
    return out` — Build manual-source objects from native provider modules only. Legacy legacy transport transports are intentionally not resolvable in the production runtime. Manual adoption is a metadata/storage operation; actual platform transport remains inside the native module registry.
### `src/orchestrator/manual_uploads.py`
- **function `normalize_title`** — `def normalize_title(value: str | None) -> str:
    if not value:
        return ''
    return ' '.join(_WORD.sub(' ', value.lower()).split())` — no docstring
- **function `title_similarity`** — `def title_similarity(a: str | None, b: str | None) -> float:
    ta = set(normalize_title(a).split())
    tb = set(normalize_title(b).split())
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0` — no docstring
- **function `match_score`** — `def match_score(upload: dict[str, Any], entity: dict[str, Any]) -> tuple[float, dict]:
    parts: list[tuple[float, float]] = []
    why: dict[str, float] = {}
    if upload.get('title') and entity.get('title'):
        s = title_similarity(upload['title'], entity['title'])
        parts.append((0.5, s))
        why['title'] = round(s, 3)
    ds = _date_score(upload.get('published_at'), entity.get('created_at'))
    if ds is not None:
        parts.append((0.3, ds))
        why['date'] = round(ds, 3)
    dus = _dur_score(upload.get('duration_sec'), entity.get('duration_sec'))
    if dus is not None:
        parts.append((0.2, dus))
        why['duration'] = round(dus, 3)
    if not parts:
        return (0.0, why)
    weight = sum((w for w, _ in parts))
    score = sum((w * s for w, s in parts)) / weight
    return (score, why)` — no docstring
- **class `ManualUploadsService`** — Scan -> match -> confirm/reject for manually uploaded videos.
  - `scan_all` — `def scan_all(self, sources: dict) -> dict:
    """Scan every source that supports listing; return per-platform stats."""
    page = getattr(self.cfg.manual_uploads, 'page_size', 50)
    allowed = set(getattr(self.cfg.manual_uploads, 'platforms', []) or [])
    stats: dict = {}
    for platform, src in (sources or {}).items():
        if allowed and platform not in allowed:
            continue
        caps = getattr(src, 'capabilities', lambda: {})()
        if not caps.get('list', False):
            stats[platform] = {'skipped': 'engine does not support listing uploads'}
            continue
        try:
            try:
                uploads = src.list_uploads({'max_results': page})
            except TypeError:
                uploads = src.list_uploads()
        except Exception as e:
            stats[platform] = {'error': str(e)}
            continue
        stats[platform] = self.scan(platform, uploads, engine=self.cfg.engine_for(platform))
    return stats` — Scan every source that supports listing; return per-platform stats.
  - `candidates` — `def candidates(self, upload_id: int) -> list[dict]:
    up = self.db.get_upload(upload_id)
    if not up:
        return []
    scored = []
    for e in self._entities(up['platform']):
        s, why = match_score(up, e)
        scored.append((s, e, why))
    scored.sort(key=lambda x: -x[0])
    res = []
    for s, e, why in scored[:5]:
        if s <= 0:
            continue
        res.append({'entity_type': e['_type'], 'entity_id': e['_id'], 'title': e['title'], 'score': round(s, 3), 'reasons': why})
    return res` — no method docstring
  - `scan` — `def scan(self, platform: str, uploads: list[dict], engine: str='direct') -> dict:
    known = self._known_ids(platform)
    lookback = getattr(self.cfg.manual_uploads, 'lookback_days', 0) or 0
    stats = {'found': 0, 'manual': 0, 'module': 0, 'suggested': 0}
    for u in uploads:
        ext = str(u.get('external_id') or '')
        if not ext:
            continue
        if lookback and (not _within_lookback(u.get('published_at'), lookback, self.clock.now())):
            continue
        origin = 'module' if ext in known else 'manual'
        row = self.db.upsert_upload(engine=engine, platform=platform, external_id=ext, url=u.get('url'), title=u.get('title'), description=u.get('description'), published_at=u.get('published_at'), duration_sec=u.get('duration_sec'), width=u.get('width'), height=u.get('height'), thumbnail_url=u.get('thumbnail_url'), origin=origin)
        stats['found'] += 1
        stats[origin] += 1
        if origin == 'manual' and row['match_status'] == 'unmatched':
            cands = self.candidates(row['id'])
            if cands:
                best = cands[0]
                self.db.set_upload_match(row['id'], best['entity_type'], best['entity_id'], best['score'], 'suggested')
                stats['suggested'] += 1
    return stats` — no method docstring
  - `confirm` — `def confirm(self, upload_id: int, entity_type: str, entity_id: int, confidence: float | None=None, apply_edits: bool=False, engine: Any=None) -> bool:
    row = self.db.get_upload(upload_id)
    if not row:
        return False
    if confidence is None:
        confidence = row.get('confidence')
    self.db.set_upload_match(upload_id, entity_type, entity_id, confidence, 'confirmed')
    now = self.clock.now().isoformat()
    ext_id = str(row.get('platform_video_id') or '').strip()
    ext_url = str(row.get('url') or '').strip() or None
    self.db.execute("\n            INSERT INTO entity_platform_status\n                (entity_type, entity_id, platform, status, published_at, release_url,\n                 external_id, external_url, source, publish_mode)\n            VALUES (?, ?, ?, 'published', ?, ?, ?, ?, 'manual', 'manual_confirmed')\n            ON CONFLICT(entity_type, entity_id, platform, account_id) DO UPDATE SET\n                status='published',\n                published_at=excluded.published_at,\n                release_url=COALESCE(excluded.release_url, entity_platform_status.release_url),\n                external_id=COALESCE(excluded.external_id, entity_platform_status.external_id),\n                external_url=COALESCE(excluded.external_url, entity_platform_status.external_url),\n                source=COALESCE(excluded.source, entity_platform_status.source),\n                publish_mode=COALESCE(excluded.publish_mode, entity_platform_status.publish_mode)\n            ", (entity_type, entity_id, row['platform'], now, ext_url, ext_id or None, ext_url))
    if apply_edits and engine is not None and (row.get('claim_status') == 'claimed'):
        self.db.execute('UPDATE platform_uploads SET edit_error=? WHERE id=?', ('blocked: claim', upload_id))
    elif apply_edits and engine is not None:
        try:
            ok = engine.update_metadata(str(row['platform_video_id']), {'description': row.get('description') or ''})
            if not ok:
                self.db.execute('UPDATE platform_uploads SET edit_error=? WHERE id=?', ('update_metadata failed', upload_id))
        except Exception as e:
            self.db.execute('UPDATE platform_uploads SET edit_error=? WHERE id=?', (str(e), upload_id))
    self.db.log(entity_type, entity_id, row['platform'], 'manual_confirmed', str(row['platform_video_id']))
    return True` — no method docstring
  - `reject` — `def reject(self, upload_id: int) -> bool:
    self.db.set_upload_match(upload_id, None, None, None, 'rejected')
    return True` — no method docstring
  - `ignore` — `def ignore(self, upload_id: int) -> bool:
    self.db.set_upload_match(upload_id, None, None, None, 'ignored')
    return True` — no method docstring
### `src/orchestrator/media.py`
- **class `MediaRef`** — no class docstring
- **function `maybe_compress`** — `def maybe_compress(path: str, platform: str, cfg: AppConfig) -> str:
    """Telegram (Bot API) принимает <=50 МБ — при необходимости сжимаем в кэш."""
    media_cfg = getattr(cfg, 'media', None)
    if not media_cfg or platform != 'telegram':
        return path
    limit_mb = int(getattr(media_cfg, 'telegram_max_mb', 0))
    if limit_mb <= 0:
        return path
    limit = limit_mb * 1024 * 1024
    try:
        size = _cached_size(path)
    except OSError:
        return path
    if size <= limit:
        return path
    ffmpeg = _ffmpeg()
    if not ffmpeg:
        logger.warning('ffmpeg не найден: файл %s больше лимита Telegram (%s МБ)', path, limit_mb)
        raise RuntimeError(f'telegram media exceeds {limit_mb}MB and ffmpeg unavailable: {path}')
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = 0
    key = hashlib.sha1(f'{path}:{size}:{mtime}'.encode()).hexdigest()[:16]
    cache_dir = Path(getattr(media_cfg, 'cache_dir', '/mnt/video/.orch_cache')) / 'telegram'
    cache_dir.mkdir(parents=True, exist_ok=True)
    dst = cache_dir / f'{key}.mp4'
    if dst.exists() and dst.stat().st_size <= limit:
        return str(dst)
    attempts = ((21, '10M'), (25, '5M'), (29, '2.5M'))
    for crf, maxrate in attempts:
        cmd = [ffmpeg, '-y', '-nostdin', '-loglevel', 'error', '-i', path, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', str(crf), '-maxrate', maxrate, '-bufsize', '8M', '-vf', "scale=w='if(gt(iw,ih),1920,-2)':h='if(gt(iw,ih),-2,1920)'", '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', str(dst)]
        try:
            subprocess.run(cmd, check=True, timeout=3600, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            logger.exception('ffmpeg сжатие не удалось: %s', path)
            continue
        if dst.exists() and dst.stat().st_size <= limit:
            logger.info('Сжат для Telegram: %s -> %s (%.1f МБ)', path, dst, dst.stat().st_size / 1048576)
            return str(dst)
    if dst.exists() and dst.stat().st_size <= limit:
        return str(dst)
    raise RuntimeError(f'telegram media still exceeds {limit_mb}MB after compress: {path}')` — Telegram (Bot API) принимает <=50 МБ — при необходимости сжимаем в кэш.
- **function `make_media`** — `def make_media(path: str, platform: str, cfg: AppConfig, client=None, broker=None) -> MediaRef:
    """MediaRef for module path: symlink via broker, or local path ref for upload.

    ``client`` is ignored (legacy signature); platform upload_media removed.
    """
    path = maybe_compress(path, platform, cfg)
    media_cfg = getattr(cfg, 'media', None)
    if media_cfg is not None and getattr(media_cfg, 'symlink_mode', False) and (broker is not None) and path.startswith(getattr(media_cfg, 'local_prefix', '/mnt/video/')):
        try:
            data = broker.symlink(path)
            if data and data.get('path'):
                return MediaRef(id=str(data.get('media_id') or 'local'), path=str(data['path']))
        except Exception:
            logger.warning('symlink media failed, fallback to local ref', exc_info=True)
    return MediaRef(id='', path=path)` — MediaRef for module path: symlink via broker, or local path ref for upload. ``client`` is ignored (legacy signature); platform upload_media removed.
- **function `prepublish_validate`** — `def prepublish_validate(path: str, platform: str, cfg: AppConfig, *, content_kind: str='video_native') -> list[str]:
    """Pre-publish checks (size/mime/kind). Returns list of human-readable problems (empty = ok)."""
    problems: list[str] = []
    p = Path(path) if path else None
    if content_kind in ('video_native', 'video_link') and p is not None and path:
        if not p.is_file():
            problems.append(f'media missing: {path}')
            return problems
        size_mb = p.stat().st_size / (1024 * 1024)
        media_cfg = getattr(cfg, 'media', None)
        if platform == 'telegram':
            limit = float(getattr(media_cfg, 'telegram_max_mb', 50) or 50)
            if size_mb > limit:
                problems.append(f'telegram size {size_mb:.1f}MB > {limit}MB — compress or use link-mode')
        if platform == 'x' and size_mb > 5 and (content_kind != 'promo_text'):
            problems.append(f'x image/video size {size_mb:.1f}MB may exceed free-tier media limit')
    if content_kind == 'promo_text' and platform in ('youtube',):
        problems.append('youtube does not accept promo_text content_kind as native upload')
    return problems` — Pre-publish checks (size/mime/kind). Returns list of human-readable problems (empty = ok).
### `src/orchestrator/media_transfer.py`
- **class `MediaArtifact`** — no class docstring
- **class `SSRFBlocked`** — no class docstring
- **class `MediaTransferManager`** — Shared media boundary: safe URL fetch, hashing, temp cleanup and chunks.
  - `validate_url` — `@classmethod
def validate_url(cls, url: str) -> None:
    p = urlparse(url)
    if p.scheme not in {'https', 'http'} or not p.hostname:
        raise SSRFBlocked('unsupported or malformed media URL')
    host = p.hostname.strip().lower()
    if host in {'localhost', 'localhost.localdomain'}:
        raise SSRFBlocked('localhost blocked')
    try:
        answers = socket.getaddrinfo(host, p.port or (443 if p.scheme == 'https' else 80), type=socket.SOCK_STREAM)
    except OSError as exc:
        raise SSRFBlocked(f'DNS resolution failed: {host}') from exc
    ips = {str(a[4][0]) for a in answers}
    if not ips or not all((cls._safe_ip(ip) for ip in ips)):
        raise SSRFBlocked(f'private/reserved media host blocked: {host}')` — no method docstring
  - `ingest_local` — `def ingest_local(self, path: str | Path, *, kind: str='video', mime_type: str='') -> MediaArtifact:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(str(p))
    h = hashlib.sha256()
    size = 0
    with p.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            h.update(chunk)
            size += len(chunk)
    artifact = MediaArtifact(uuid.uuid4().hex, str(p), h.hexdigest(), size, mime_type, kind)
    self._record(artifact)
    return artifact` — no method docstring
  - `fetch_url` — `def fetch_url(self, url: str, *, kind: str='video', mime_type: str='', filename: str | None=None) -> MediaArtifact:
    current = url
    for _hop in range(4):
        self.validate_url(current)
        req = urllib.request.Request(current, headers={'User-Agent': 'orchestrator-media/1.0'})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                status = getattr(resp, 'status', 200)
                if status in {301, 302, 303, 307, 308}:
                    target = resp.headers.get('Location')
                    if not target:
                        raise SSRFBlocked('redirect without Location')
                    current = target
                    continue
                out = self.temp_dir / (filename or f'{uuid.uuid4().hex}.bin')
                h = hashlib.sha256()
                size = 0
                with out.open('wb') as fh:
                    while True:
                        chunk = resp.read(1024 * 1024)
                        if not chunk:
                            break
                        size += len(chunk)
                        if size > self.max_download_bytes:
                            out.unlink(missing_ok=True)
                            raise ValueError('media download exceeds configured limit')
                        h.update(chunk)
                        fh.write(chunk)
                artifact = MediaArtifact(uuid.uuid4().hex, str(out), h.hexdigest(), size, mime_type or str(resp.headers.get_content_type() or ''), kind, current)
                self._record(artifact)
                return artifact
        except urllib.error.URLError as exc:
            raise RuntimeError(f'media fetch failed: {exc}') from exc
    raise SSRFBlocked('too many media redirects')` — no method docstring
  - `iter_chunks` — `@staticmethod
def iter_chunks(path: str | Path, *, chunk_size: int=8 * 1024 * 1024) -> Iterable[tuple[int, bytes]]:
    if chunk_size <= 0:
        raise ValueError('chunk_size must be positive')
    offset = 0
    with Path(path).open('rb') as fh:
        while True:
            data = fh.read(chunk_size)
            if not data:
                return
            yield (offset, data)
            offset += len(data)` — no method docstring
  - `cleanup_orphans` — `def cleanup_orphans(self, *, older_than_sec: int=86400, active_paths: set[str] | None=None) -> int:
    active_paths = active_paths or set()
    cutoff = datetime.now(UTC).timestamp() - int(older_than_sec)
    removed = 0
    for row in self.db.fetchall('SELECT id,path FROM media_artifacts WHERE deleted_at IS NULL') if self.db else []:
        path = str(row.get('path') or '')
        if not path or path in active_paths:
            continue
        try:
            if Path(path).exists() and Path(path).stat().st_mtime > cutoff:
                continue
            Path(path).unlink(missing_ok=True)
        except OSError:
            continue
        if self.db:
            self.db.execute('UPDATE media_artifacts SET deleted_at=? WHERE id=?', (datetime.now(UTC).isoformat(), row['id']))
        removed += 1
    return removed` — no method docstring
### `src/orchestrator/metrics.py`
- **class `Metrics`** — no class docstring
  - `incr` — `def incr(self, key: str, n: int=1) -> None:
    self.data[key] = int(self.data.get(key) or 0) + n` — no method docstring
  - `set` — `def set(self, key: str, value: Any) -> None:
    self.data[key] = value` — no method docstring
  - `tick_cycle` — `def tick_cycle(self) -> None:
    self.incr('cycles')
    self.data['last_cycle_at'] = time.time()
    self.flush()` — no method docstring
  - `flush` — `def flush(self) -> None:
    if not self.path:
        return
    try:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.data, ensure_ascii=False, indent=2)
        fd, tmp = tempfile.mkstemp(prefix=f'.{self.path.name}.', dir=str(self.path.parent))
        try:
            os.fchmod(fd, 384)
            with os.fdopen(fd, 'w', encoding='utf-8') as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self.path)
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    except Exception:
        logger.debug('metrics flush failed', exc_info=True)` — no method docstring
  - `snapshot` — `def snapshot(self) -> dict[str, Any]:
    return dict(self.data)` — no method docstring
- **function `sanitize_metrics`** — `def sanitize_metrics(data: dict) -> dict:
    """S19: strip secrets/tokens from metrics payload before exposure."""
    if not isinstance(data, dict):
        return {}
    banned = ('token', 'secret', 'password', 'api_key', 'authorization', 'cookie')
    out = {}
    for k, v in data.items():
        kl = str(k).lower()
        if any((b in kl for b in banned)):
            continue
        if isinstance(v, dict):
            out[k] = sanitize_metrics(v)
        else:
            out[k] = v
    return out` — S19: strip secrets/tokens from metrics payload before exposure.
### `src/orchestrator/ops_health.py`
- **class `OpsHealth`** — Operational readiness checks: disk, backups, config and token expiry.
  - `snapshot` — `def snapshot(self) -> dict[str, Any]:
    disk = self._disk()
    backups = self._backups()
    tokens = self._tokens()
    ready = bool(disk['ok'] and backups['ok'])
    return {'config_schema_version': int(getattr(self.cfg, 'config_schema_version', 1)), 'disk': disk, 'backups': backups, 'tokens': tokens, 'ready': ready}` — no method docstring
### `src/orchestrator/outbox.py`
- **class `Outbox`** — no class docstring
  - `enqueue_in_transaction` — `def enqueue_in_transaction(self, conn: Any, event_type: str, aggregate_type: str, aggregate_id: str, payload: dict[str, Any]) -> int:
    """Insert an outbox row using an existing transaction connection."""
    now = _now()
    cur = conn.execute('INSERT INTO outbox_events(event_type, aggregate_type, aggregate_id, payload_json, created_at) VALUES (?, ?, ?, ?, ?)', (event_type, aggregate_type, aggregate_id, json.dumps(payload, ensure_ascii=False, sort_keys=True), now))
    return int(cur.lastrowid or 0)` — Insert an outbox row using an existing transaction connection.
  - `enqueue` — `def enqueue(self, event_type: str, aggregate_type: str, aggregate_id: str, payload: dict[str, Any]) -> int:
    with self.db.transaction() as conn:
        return self.enqueue_in_transaction(conn, event_type, aggregate_type, aggregate_id, payload)` — no method docstring
  - `claim` — `def claim(self, limit: int=50, lease_sec: int=60) -> list[dict[str, Any]]:
    now = _now()
    until = (datetime.now(UTC) + timedelta(seconds=lease_sec)).isoformat()
    rows = self.db.fetchall('SELECT * FROM outbox_events WHERE published_at IS NULL AND (locked_until IS NULL OR locked_until < ?) ORDER BY id LIMIT ?', (now, max(1, int(limit))))
    claimed: list[dict[str, Any]] = []
    for row in rows:
        updated = self.db.execute('UPDATE outbox_events SET locked_until=?, attempts=attempts+1 WHERE id=? AND published_at IS NULL AND (locked_until IS NULL OR locked_until < ?)', (until, row['id'], now))
        if updated:
            claimed.append(dict(row))
    return claimed` — no method docstring
  - `mark_published` — `def mark_published(self, event_id: int) -> None:
    self.db.execute('UPDATE outbox_events SET published_at=?, locked_until=NULL, last_error=NULL WHERE id=?', (_now(), int(event_id)))` — no method docstring
  - `mark_failed` — `def mark_failed(self, event_id: int, error: str, *, max_attempts: int=12) -> None:
    row = self.db.fetchone('SELECT attempts FROM outbox_events WHERE id=?', (int(event_id),))
    attempts = int(row.get('attempts') or 0) if row else 0
    if attempts >= max(1, int(max_attempts)):
        self.db.execute('UPDATE outbox_events SET locked_until=NULL, last_error=? WHERE id=?', ('DEAD_LETTER: ' + str(error)[:900], int(event_id)))
    else:
        self.db.execute('UPDATE outbox_events SET locked_until=NULL, last_error=? WHERE id=?', (str(error)[:1000], int(event_id)))` — no method docstring
- **class `DurableJobStore`** — SQLite-backed restart-safe jobs with leases, retries and a durable DLQ.
  - `enqueue` — `def enqueue(self, kind: str, payload: dict[str, Any], *, provider: str='', account_id: str='', job_id: str | None=None, available_at: str | None=None, max_attempts: int=8) -> str:
    jid = job_id or secrets.token_urlsafe(16)
    now = _now()
    self.db.execute('INSERT INTO durable_jobs(id, kind, provider, account_id, payload_json, available_at, created_at, updated_at, max_attempts, next_retry_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL) ON CONFLICT(id) DO NOTHING', (jid, kind, provider, account_id, json.dumps(payload, ensure_ascii=False, sort_keys=True), available_at or now, now, now, max(1, int(max_attempts))))
    return jid` — no method docstring
  - `reap_expired` — `def reap_expired(self, *, now: str | None=None) -> dict[str, int]:
    now = now or _now()
    rows = self.db.fetchall("SELECT id, attempts, max_attempts FROM durable_jobs WHERE status='running' AND locked_until IS NOT NULL AND locked_until<?", (now,))
    requeued = dead = 0
    for row in rows:
        attempts = int(row.get('attempts') or 0)
        limit = max(1, int(row.get('max_attempts') or 8))
        if attempts >= limit:
            self.dead_letter(str(row['id']), 'worker lease expired; max attempts reached')
            dead += 1
        else:
            delay = min(3600, 2 ** min(attempts, 10))
            available = (datetime.now(UTC) + timedelta(seconds=delay)).isoformat()
            self.retry(str(row['id']), 'worker lease expired', available_at=available)
            requeued += 1
    return {'requeued': requeued, 'dead': dead}` — no method docstring
  - `claim` — `def claim(self, worker_id: str, *, limit: int=10, lease_sec: int=300) -> list[dict[str, Any]]:
    now = _now()
    self.reap_expired(now=now)
    until = (datetime.now(UTC) + timedelta(seconds=lease_sec)).isoformat()
    rows = self.db.fetchall("SELECT * FROM durable_jobs WHERE status='queued' AND available_at<=? AND (next_retry_at IS NULL OR next_retry_at<=?) AND (locked_until IS NULL OR locked_until<?) AND attempts < COALESCE(max_attempts,8) ORDER BY available_at, created_at LIMIT ?", (now, now, now, max(1, int(limit))))
    out: list[dict[str, Any]] = []
    for row in rows:
        n = self.db.execute("UPDATE durable_jobs SET status='running', locked_until=?, worker_id=?, attempts=attempts+1, updated_at=?, next_retry_at=NULL WHERE id=? AND status='queued' AND (locked_until IS NULL OR locked_until<?) AND attempts < COALESCE(max_attempts,8)", (until, worker_id, now, row['id'], now))
        if n:
            row = dict(row)
            row['attempts'] = int(row.get('attempts') or 0) + 1
            out.append(row)
    return out` — no method docstring
  - `heartbeat` — `def heartbeat(self, job_id: str, worker_id: str, *, lease_sec: int=300) -> bool:
    now = _now()
    until = (datetime.now(UTC) + timedelta(seconds=lease_sec)).isoformat()
    return bool(self.db.execute("UPDATE durable_jobs SET locked_until=?, updated_at=? WHERE id=? AND status='running' AND worker_id=?", (until, now, job_id, worker_id)))` — no method docstring
  - `complete` — `def complete(self, job_id: str) -> None:
    now = _now()
    self.db.execute("UPDATE durable_jobs SET status='done', locked_until=NULL, worker_id=NULL, finished_at=?, updated_at=? WHERE id=?", (now, now, job_id))` — no method docstring
  - `retry` — `def retry(self, job_id: str, error: str, *, available_at: str | None=None) -> None:
    now = _now()
    self.db.execute("UPDATE durable_jobs SET status='queued', locked_until=NULL, worker_id=NULL, available_at=?, next_retry_at=?, last_error=?, updated_at=? WHERE id=?", (available_at or now, available_at or now, str(error)[:1000], now, job_id))` — no method docstring
  - `fail_or_retry` — `def fail_or_retry(self, job_id: str, error: str) -> str:
    row = self.db.fetchone('SELECT attempts, max_attempts FROM durable_jobs WHERE id=?', (job_id,))
    attempts = int(row.get('attempts') or 0) if row else 0
    limit = max(1, int(row.get('max_attempts') or 8)) if row else 8
    if attempts >= limit:
        self.dead_letter(job_id, error)
        return 'dead'
    delay = min(3600, 2 ** min(attempts, 10))
    when = (datetime.now(UTC) + timedelta(seconds=delay)).isoformat()
    self.retry(job_id, error, available_at=when)
    return 'retry'` — no method docstring
  - `dead_letter` — `def dead_letter(self, job_id: str, error: str) -> None:
    now = _now()
    self.db.execute("UPDATE durable_jobs SET status='dead', locked_until=NULL, worker_id=NULL, last_error=?, finished_at=?, updated_at=? WHERE id=?", (str(error)[:1000], now, now, job_id))` — no method docstring
### `src/orchestrator/overflow.py`
- **function `move_excess_shorts`** — `def move_excess_shorts(db: Database, cfg: AppConfig, clock: Clock, parent_video_id: int) -> int:
    """Move shorts beyond max_shorts_per_long_video into shorts_overflow/ and mark skipped.

    P2.9: переполнение помечается 'skipped' на ВСЕХ платформах конфига (не только на
    включённых) — это консервативно и предотвращает публикацию лишних шортсов, если
    платформу включат позже; файлы при overflow_move_files=false НЕ переносятся.
    """
    max_n = cfg.limits.max_shorts_per_long_video
    shorts = db.fetchall('SELECT id, folder_path FROM shorts WHERE parent_video_id=? ORDER BY order_index, id', (parent_video_id,))
    if len(shorts) <= max_n:
        return 0
    excess = shorts[max_n:]
    MAX_OVERFLOW_BATCH = 200
    excess = excess[:MAX_OVERFLOW_BATCH]
    moved = 0
    for s in excess:
        src = Path(s['folder_path'])
        if not src.exists():
            continue
        move_files = bool(getattr(cfg.limits, 'overflow_move_files', False))
        if move_files:
            series = src.parent.parent if src.parent.name == 'shorts' else src.parent
            overflow = series / 'shorts_overflow' / src.name
            overflow.parent.mkdir(parents=True, exist_ok=True)
            if not overflow.exists():
                shutil.move(str(src), str(overflow))
        for platform in cfg.platforms:
            db.execute("\n                INSERT INTO entity_platform_status\n                    (entity_type, entity_id, platform, status, last_error)\n                VALUES ('short', ?, ?, 'skipped', 'overflow')\n                ON CONFLICT(entity_type, entity_id, platform, account_id) DO UPDATE SET\n                    status='skipped', last_error='overflow'\n                ", (s['id'], platform))
        db.log('short', s['id'], None, 'overflow_moved' if move_files else 'overflow_skipped', '')
        moved += 1
        if move_files:
            logger.info('Moved excess short %s -> %s', src, overflow)
        else:
            logger.info('Excess short skipped (files kept): %s', src)
    return moved` — Move shorts beyond max_shorts_per_long_video into shorts_overflow/ and mark skipped. P2.9: переполнение помечается 'skipped' на ВСЕХ платформах конфига (не только на включённых) — это консервативно и предотвращает публикацию лишних шортсов, если платформу включат позже; файлы при overflow_move_files=false НЕ переносятся.
### `src/orchestrator/pidfile.py`
- **function `acquire_pidfile`** — `def acquire_pidfile(path: str | Path, *, stale_sec: int=86400) -> None:
    """Acquire exclusive lock on pidfile. Raises SystemExit(1) if held."""
    global _lock_fh
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fh = open(p, 'a+', encoding='utf-8')
    try:
        import fcntl
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fh.seek(0)
        old = (fh.read() or '').strip()
        logger.error('another orchestrator instance holds pidfile %s (pid=%s); exit', p, old or '?')
        fh.close()
        raise SystemExit(1) from None
    except ImportError:
        logger.warning('fcntl unavailable — pidfile without flock')
    fh.seek(0)
    fh.truncate()
    fh.write(str(os.getpid()))
    fh.flush()
    _lock_fh = fh

    def _release() -> None:
        global _lock_fh
        try:
            if _lock_fh is not None:
                try:
                    import fcntl
                    fcntl.flock(_lock_fh.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
                _lock_fh.close()
                _lock_fh = None
        except Exception:
            pass
    atexit.register(_release)` — Acquire exclusive lock on pidfile. Raises SystemExit(1) if held.
- **function `pidfile_path_from_env`** — `def pidfile_path_from_env(default: str='data/orchestrator.pid') -> str:
    return os.getenv('ORCH_PIDFILE', default)` — no docstring
### `src/orchestrator/provider_access.py`
- **class `ProviderAccessSnapshot`** — no class docstring
  - `validate` — `def validate(self) -> None:
    if self.state not in STATES:
        raise ValueError(f'unknown provider access state: {self.state}')` — no method docstring
- **class `ProviderAccessStore`** — no class docstring
  - `upsert` — `def upsert(self, snapshot: ProviderAccessSnapshot) -> None:
    snapshot.validate()
    now = time.time()
    self.db.execute('INSERT INTO provider_access\n            (platform, account_id, state, credentials_ok, redirect_ok, account_ok,\n             token_ok, scopes_ok, business_verification_ok, app_review_ok, audit_ok,\n             webhook_ok, media_host_ok, smoke_test_ok, live_ok, details, updated_at)\n            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n            ON CONFLICT(platform, account_id) DO UPDATE SET\n              state=excluded.state, credentials_ok=excluded.credentials_ok,\n              redirect_ok=excluded.redirect_ok, account_ok=excluded.account_ok,\n              token_ok=excluded.token_ok, scopes_ok=excluded.scopes_ok,\n              business_verification_ok=excluded.business_verification_ok,\n              app_review_ok=excluded.app_review_ok, audit_ok=excluded.audit_ok,\n              webhook_ok=excluded.webhook_ok, media_host_ok=excluded.media_host_ok,\n              smoke_test_ok=excluded.smoke_test_ok, live_ok=excluded.live_ok,\n              details=excluded.details, updated_at=excluded.updated_at', (snapshot.provider.lower(), snapshot.account_id, snapshot.state, int(snapshot.credentials_ok), int(snapshot.redirect_ok), int(snapshot.account_ok), int(snapshot.token_ok), int(snapshot.scopes_ok), int(snapshot.business_verification_ok), int(snapshot.app_review_ok), int(snapshot.audit_ok), int(snapshot.webhook_ok), int(snapshot.media_host_ok), int(snapshot.smoke_test_ok), int(snapshot.live_ok), snapshot.details[:2000], now))` — no method docstring
  - `get` — `def get(self, provider: str, account_id: str='') -> ProviderAccessSnapshot | None:
    row = self.db.fetchone('SELECT * FROM provider_access WHERE platform=? AND account_id=?', (provider.lower(), account_id))
    if not row:
        return None
    return ProviderAccessSnapshot(provider=str(row.get('platform') or provider), account_id=str(row.get('account_id') or ''), credentials_ok=bool(row.get('credentials_ok')), redirect_ok=bool(row.get('redirect_ok')), account_ok=bool(row.get('account_ok')), token_ok=bool(row.get('token_ok')), scopes_ok=bool(row.get('scopes_ok')), business_verification_ok=bool(row.get('business_verification_ok')), app_review_ok=bool(row.get('app_review_ok')), audit_ok=bool(row.get('audit_ok')), webhook_ok=bool(row.get('webhook_ok')), media_host_ok=bool(row.get('media_host_ok')), smoke_test_ok=bool(row.get('smoke_test_ok')), live_ok=bool(row.get('live_ok')), state=str(row.get('state') or 'NOT_CONFIGURED'), details=str(row.get('details') or ''))` — no method docstring
  - `snapshot_all` — `def snapshot_all(self) -> dict[str, dict[str, Any]]:
    rows = self.db.fetchall('SELECT * FROM provider_access ORDER BY platform, account_id')
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        snap = self.get(str(row.get('platform') or ''), str(row.get('account_id') or ''))
        if snap is None:
            continue
        item = asdict(snap)
        out[f'{snap.provider}::{snap.account_id}'] = item
    return out` — no method docstring
### `src/orchestrator/provider_catalog.py`
- **class `ProviderEntry`** — no class docstring
- **function `load_provider_catalog`** — `def load_provider_catalog(path: str | Path | None=None) -> list[ProviderEntry]:
    p = Path(path or CATALOG)
    try:
        data: dict[str, Any] = load_unique_yaml(p) or {}
    except DuplicateYAMLKeyError as exc:
        raise ValueError(f'provider catalog duplicate key: {exc}') from exc
    entries = data.get('providers') or []
    if not isinstance(entries, list):
        raise ValueError('provider catalog: providers must be a list')
    out: list[ProviderEntry] = []
    seen: set[str] = set()
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError('provider catalog: each provider must be a mapping')
        pid = str(item.get('id') or '').strip().lower()
        if not pid or pid in seen:
            raise ValueError(f'provider catalog: duplicate/empty provider id {pid!r}')
        seen.add(pid)
        out.append(ProviderEntry(pid, str(item.get('category') or ''), str(item.get('implementation_state') or '')))
    return out` — no docstring
### `src/orchestrator/provider_supervisor.py`
- **class `Circuit`** — no class docstring
- **class `ProviderSupervisor`** — Provider/account isolation, circuit breaker, execution queues and probes.
  - `queue` — `@contextmanager
def queue(self, provider: str, account_id: str='', *, timeout: float | None=None) -> Iterator[bool]:
    """Serialize provider operations per account while keeping accounts isolated."""
    key = self._key(provider, account_id)
    with self._lock:
        lock = self._queue_locks.setdefault(key, threading.Lock())
    acquired = lock.acquire(timeout=timeout) if timeout is not None else lock.acquire()
    try:
        yield acquired
    finally:
        if acquired:
            lock.release()` — Serialize provider operations per account while keeping accounts isolated.
  - `run_probe` — `def run_probe(self, provider: str, account_id: str, probe: Callable[[], Any]) -> bool:
    """Run one safe auth/status probe; half-open only. No publish is performed here."""
    if not self.allow(provider, account_id):
        return False
    with self.queue(provider, account_id, timeout=0) as acquired:
        if not acquired:
            return False
        try:
            probe()
        except Exception as exc:
            self.record_failure(provider, account_id, str(exc))
            return False
        self.record_success(provider, account_id)
        return True` — Run one safe auth/status probe; half-open only. No publish is performed here.
  - `record_success` — `def record_success(self, provider: str, account_id: str='') -> None:
    with self._lock:
        c = self._load(provider, account_id)
        c.failures = 0
        c.opened_at = None
        c.half_open_until = None
        c.last_success_at = time.time()
        c.last_error = ''
        c.last_state = 'healthy'
        self._persist(provider, account_id, c, 'healthy')
        self._metric('provider_success', provider, account_id)` — no method docstring
  - `record_failure` — `def record_failure(self, provider: str, account_id: str='', error: str='') -> None:
    with self._lock:
        c = self._load(provider, account_id)
        now = time.time()
        c.failures += 1
        c.last_failure_at = now
        c.last_error = str(error)[:500]
        if c.half_open_until is not None or c.failures >= self.failure_threshold:
            c.opened_at = now
            c.half_open_until = None
        state = 'open' if c.opened_at is not None else 'degraded'
        prev = c.last_state
        c.last_state = state
        self._persist(provider, account_id, c, state)
        self._metric('provider_failure', provider, account_id)
        if state in {'open', 'degraded'} and state != prev:
            self._emit_alert(provider, account_id, state, c.last_error)` — no method docstring
  - `allow` — `def allow(self, provider: str, account_id: str='') -> bool:
    with self._lock:
        c = self._load(provider, account_id)
        if c.opened_at is None:
            return True
        now = time.time()
        if now - c.opened_at < self.cooldown_sec:
            return False
        if c.half_open_until is not None and c.half_open_until > now:
            return False
        c.half_open_until = now + self.probe_lease_sec
        self._persist(provider, account_id, c, 'half_open')
        return True` — no method docstring
  - `reset` — `def reset(self, provider: str, account_id: str='') -> None:
    with self._lock:
        c = self._load(provider, account_id)
        c.failures = 0
        c.opened_at = None
        c.half_open_until = None
        c.last_error = ''
        c.last_state = 'healthy'
        self._persist(provider, account_id, c, 'healthy')` — no method docstring
  - `state` — `def state(self, provider: str, account_id: str='') -> str:
    with self._lock:
        c = self._load(provider, account_id)
        if c.opened_at is not None:
            now = time.time()
            if now - c.opened_at < self.cooldown_sec:
                return 'open'
            if c.half_open_until is not None and c.half_open_until > now:
                return 'half_open'
            return 'degraded'
        if c.failures:
            return 'degraded'
        return 'healthy'` — no method docstring
  - `snapshot` — `def snapshot(self) -> dict[str, dict[str, Any]]:
    with self._lock:
        out: dict[str, dict[str, Any]] = {}
        if self.db is not None:
            try:
                rows = self.db.fetchall('SELECT * FROM provider_health')
                for row in rows:
                    self._load(str(row.get('platform') or ''), str(row.get('account_id') or ''))
            except Exception:
                pass
        for key, c in self._circuits.items():
            provider, _, account = key.partition('::')
            out[key] = {'provider': provider, 'account_id': account, 'state': self.state(provider, account), 'consecutive_failures': c.failures, 'last_success_at': c.last_success_at, 'last_failure_at': c.last_failure_at, 'last_error': c.last_error}
        return out` — no method docstring
### `src/orchestrator/publish_recovery.py`
- **class `RecoveryResult`** — no class docstring
- **class `PublishAttemptRecovery`** — Repair publish attempts after lost responses without inventing a remote ID.
  - `run` — `def run(self, *, limit: int=50) -> RecoveryResult:
    res = RecoveryResult()
    rows = self.db.fetchall("SELECT * FROM publish_attempts WHERE status IN ('started','unknown','processing') ORDER BY started_at LIMIT ?", (max(1, int(limit)),))
    for row in rows:
        res.checked += 1
        try:
            if self._repair_one(row):
                res.repaired += 1
            elif self._is_ambiguous(row):
                res.ambiguous += 1
        except Exception as exc:
            res.failed += 1
            res.errors.append(f"{row.get('id')}: {type(exc).__name__}: {exc}")
    return res` — no method docstring
### `src/orchestrator/publisher.py`
- **class `PublishOutcome`** — no class docstring
- **class `Publisher`** — Module-only publisher (platform transport removed in F3).
  - `publish` — `def publish(self, entity_type: str, entity_id: int, platform: str, media_path: str | None, content: dict[str, Any], scheduled_for: datetime | None=None, account_id: str | None=None) -> PublishOutcome | None:
    """Full publish pipeline with safety + idempotency (module path only)."""
    if scheduled_for and scheduled_for.tzinfo is None:
        scheduled_for = scheduled_for.replace(tzinfo=UTC)
    if scheduled_for and self.cfg.safety.jitter_seconds:
        from .slots import apply_jitter
        jittered = apply_jitter(scheduled_for, self.cfg.safety.jitter_seconds)
        if jittered > self.clock.now():
            scheduled_for = jittered
    plat_cfg_for_account = self.cfg.platforms.get(platform)
    if account_id is None:
        account_id = str(getattr(plat_cfg_for_account, 'account_id', '') or getattr(plat_cfg_for_account, 'integration_id', '') or '') if plat_cfg_for_account else ''
    else:
        account_id = str(account_id or '')
    existing = self._already_exists(entity_type, entity_id, platform, account_id)
    if existing == '__publishing__':
        logger.info('Publish in progress %s/%s %s', entity_type, entity_id, platform)
        return None
    if existing:
        logger.info('Already exists %s/%s %s -> %s', entity_type, entity_id, platform, existing)
        return PublishOutcome(id=str(existing), platform=platform, status='scheduled')
    if not self.dry_run:
        if not self._reserve_publish(entity_type, entity_id, platform, account_id):
            existing = self._already_exists(entity_type, entity_id, platform, account_id)
            if existing and existing != '__publishing__':
                return PublishOutcome(id=str(existing), platform=platform, status='scheduled')
            logger.info('Could not reserve %s/%s %s (race)', entity_type, entity_id, platform)
            return None
    plat_cfg = self.cfg.platforms.get(platform)
    if self.supervisor is not None:
        try:
            if not self.supervisor.allow(platform, account_id):
                self.db.log(entity_type, entity_id, platform, 'provider_circuit_open', 'provider failure isolation')
                self._release_reserve(entity_type, entity_id, platform, account_id)
                return None
        except Exception:
            logger.debug('provider supervisor allow check failed', exc_info=True)
    if not plat_cfg or not plat_cfg.enabled:
        logger.warning('Platform %s disabled', platform)
        self._release_reserve(entity_type, entity_id, platform, account_id)
        return None
    if scheduled_for:
        from . import sched_settings
        limit = sched_settings.effective_daily_limit(self.db, self.cfg, platform)
        ok, reason = self.safety.can_schedule(platform, scheduled_for, limit)
        if not ok:
            self.db.log(entity_type, entity_id, platform, 'safety_block', reason)
            logger.info('Safety block %s/%s %s: %s', entity_type, entity_id, platform, reason)
            self._release_reserve(entity_type, entity_id, platform, account_id)
            return None
    if self.guard is not None and scheduled_for is not None:
        reason = self.guard.conflict(platform, scheduled_for)
        if reason:
            self.db.log(entity_type, entity_id, platform, 'safety_block', reason)
            logger.info('Schedule conflict %s/%s %s: %s', entity_type, entity_id, platform, reason)
            self._release_reserve(entity_type, entity_id, platform, account_id)
            return None
    if self.dry_run or getattr(self.cfg, 'read_only', False) or bool(os.getenv('ORCH_READ_ONLY')):
        logger.info('[READ-ONLY/DRY-RUN] skip publish %s/%s to %s at %s', entity_type, entity_id, platform, scheduled_for)
        self.db.log(entity_type, entity_id, platform, 'dry_run', str(scheduled_for))
        self._release_reserve(entity_type, entity_id, platform, account_id)
        return None
    hourly = getattr(self.cfg.limits, 'module_create_per_hour', 0) or getattr(self.cfg.limits, 'legacy_create_per_hour', 0) or 0
    if hourly and str((content or {}).get('priority') or '') == 'link':
        hourly = 0
    if hourly:
        cutoff = (self.clock.now() - timedelta(hours=1)).isoformat()
        row = self.db.fetchone("SELECT COUNT(*) AS c FROM publish_log WHERE action='created' AND created_at >= ?", (cutoff,))
        if row and row['c'] >= hourly:
            self.db.log(entity_type, entity_id, platform, 'safety_block', 'hourly_create_limit')
            logger.info('Hourly create limit reached (%s)', hourly)
            self._release_reserve(entity_type, entity_id, platform, account_id)
            return None
    content_kind = str((content or {}).get('content_kind') or getattr(plat_cfg, 'content_kind_default', '') or 'video_native').strip() or 'video_native'
    if media_path:
        try:
            from pathlib import Path as _P
            from .media import prepublish_validate, maybe_compress
            if _P(media_path).is_file():
                if platform == 'telegram' and content_kind.startswith('video'):
                    try:
                        media_path = maybe_compress(media_path, platform, self.cfg) or media_path
                    except Exception:
                        logger.debug('maybe_compress failed', exc_info=True)
                problems = prepublish_validate(media_path or '', platform, self.cfg, content_kind=content_kind)
                if problems:
                    msg = '; '.join(problems)[:500]
                    self.db.log(entity_type, entity_id, platform, 'prepublish_block', msg)
                    logger.info('prepublish block %s/%s %s: %s', entity_type, entity_id, platform, msg)
                    self._release_reserve(entity_type, entity_id, platform, account_id)
                    return None
            else:
                problems = prepublish_validate('', platform, self.cfg, content_kind=content_kind)
                problems = [x for x in problems if 'missing' not in x.lower()]
                if problems:
                    msg = '; '.join(problems)[:500]
                    self.db.log(entity_type, entity_id, platform, 'prepublish_block', msg)
                    self._release_reserve(entity_type, entity_id, platform, account_id)
                    return None
        except Exception:
            logger.debug('prepublish_validate skipped', exc_info=True)
    if content is not None:
        content = dict(content)
        content.setdefault('content_kind', content_kind)
    if content_kind.startswith('promo') or content_kind == 'image_carousel':
        from pathlib import Path as _P
        cover = str((content or {}).get('cover') or (content or {}).get('cover_path') or '').strip()
        if (not media_path or not _P(media_path).is_file()) and cover and _P(cover).is_file():
            media_path = cover
            if content is not None:
                content['media_kind'] = 'image'
        elif not media_path:
            media_path = None
    if media_path and plat_cfg is not None and (str(getattr(plat_cfg, 'post_mode', 'media') or 'media').lower() == 'link'):
        logger.warning('link-mode %s: skip file %s, publish link only', platform, media_path)
        try:
            self.db.log(entity_type, entity_id, platform, 'link_mode_media_skipped', str(media_path))
        except Exception:
            logger.debug('link-mode log failed', exc_info=True)
        media_path = None
    revision_hash = self._ensure_content_revision(entity_type, entity_id, content or {}, media_path)
    target_id = self._ensure_distribution_target(entity_type, entity_id, platform, account_id, revision_hash, scheduled_for)
    attempt_key, previous_attempt = self._begin_publish_attempt(entity_type, entity_id, platform, account_id, media_path, content or {})
    self.db.execute('UPDATE publish_attempts SET revision_hash=? WHERE platform=? AND account_id=? AND idempotency_key=?', (revision_hash, platform, account_id, attempt_key))
    if previous_attempt and previous_attempt.get('remote_object_id'):
        remote_id = str(previous_attempt.get('remote_object_id'))
        return PublishOutcome(id=remote_id, platform=platform, status=str(previous_attempt.get('status') or 'published'))
    try:
        if self.supervisor is not None and (not self.supervisor.allow(platform, account_id)):
            msg = 'provider circuit open'
            self.db.execute("UPDATE entity_platform_status SET status='ready', last_error=?, lease_until=NULL, next_retry_at=? WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?", (msg, self.clock.now().isoformat(), entity_type, entity_id, platform, account_id))
            self._finish_publish_attempt(attempt_key, platform, account_id, 'deferred', error_code='CIRCUIT_OPEN', error_message=msg)
            return None
        if self.supervisor is not None:
            with self.supervisor.queue(platform, account_id, timeout=0) as queue_acquired:
                if not queue_acquired:
                    self._finish_publish_attempt(attempt_key, platform, account_id, 'deferred', error_code='QUEUE_BUSY', error_message='provider account queue busy')
                    self._release_reserve(entity_type, entity_id, platform, account_id)
                    return None
                mod_post = self._try_module_publish(entity_type, entity_id, platform, media_path, content or {}, scheduled_for, account_id)
        else:
            mod_post = self._try_module_publish(entity_type, entity_id, platform, media_path, content or {}, scheduled_for, account_id)
        if mod_post is not None:
            result_status = str(getattr(mod_post, 'status', '') or getattr(mod_post, 'state', '') or 'published')
            self._finish_publish_attempt(attempt_key, platform, account_id, result_status, mod_post.id)
            self.db.execute('UPDATE distribution_targets SET status=?, updated_at=? WHERE id=?', ('published' if result_status not in {'processing', 'uploaded', 'scheduled'} else result_status, self.clock.now().isoformat(), target_id))
            if self.supervisor is not None:
                try:
                    self.supervisor.record_success(platform, account_id)
                except Exception:
                    logger.debug('provider supervisor success update failed', exc_info=True)
            return mod_post
    except Exception as e:
        err = f'{type(e).__name__}: {e}'[:500]
        retryable = bool(getattr(e, 'retryable', False))
        next_status = 'ready' if retryable else 'error'
        logger.exception('module publish failed %s %s %s retryable=%s', platform, entity_type, entity_id, retryable)
        self._finish_publish_attempt(attempt_key, platform, account_id, 'error', error_code=str(getattr(e, 'code', 'FATAL')), error_message=err)
        self.db.execute('UPDATE distribution_targets SET status=?, updated_at=? WHERE id=?', ('failed', self.clock.now().isoformat(), target_id))
        if self.supervisor is not None:
            try:
                code = str(getattr(e, 'code', 'FATAL'))
                infrastructure_failure = retryable or code in {'AUTH_EXPIRED', 'AUTH_REQUIRED', 'RATE_LIMIT', 'TRANSIENT', 'DEPENDENCY_DOWN', 'API_DEPRECATED', 'WEBHOOK_BROKEN'}
                if infrastructure_failure:
                    self.supervisor.record_failure(platform, account_id, err)
            except Exception:
                logger.debug('provider supervisor failure update failed', exc_info=True)
        try:
            self.db.execute('UPDATE entity_platform_status SET status=?, last_error=?, lease_until=NULL, next_retry_at=? WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?', (next_status, err, self.clock.now().isoformat() if retryable else None, entity_type, entity_id, platform, account_id))
            self.db.log(entity_type, entity_id, platform, 'publish_error', err)
        except Exception:
            self._release_reserve(entity_type, entity_id, platform, account_id)
        raise
    self._release_reserve(entity_type, entity_id, platform, account_id)
    raise RuntimeError(f'publisher: no module path for platform={platform!r} — configure engines.<platform>=module:<id>')` — Full publish pipeline with safety + idempotency (module path only).
  - `cancel_or_delete` — `def cancel_or_delete(self, platform: str, external_id: str) -> bool:
    """Best-effort remote cancel via platform module; always clears local lease."""
    external_id = str(external_id or '').strip()
    if not external_id:
        return False
    try:
        from .platforms import default_registry, resolve_engine
        eng = str(self.cfg.engine_for(platform) or '').strip()
        resolved = resolve_engine(eng)
        if resolved.kind != 'module' or not resolved.module_id:
            return False
        reg = self._module_registry or default_registry()
        if not reg.has(resolved.module_id):
            return False
        try:
            mod = reg.create(resolved.module_id, dry_run=self.dry_run)
        except Exception:
            return False
        if hasattr(mod, 'delete'):
            try:
                mod.delete(external_id)
                return True
            except Exception:
                logger.warning('cancel_or_delete module.delete failed %s/%s', platform, external_id, exc_info=True)
        return False
    except Exception:
        logger.warning('cancel_or_delete failed %s/%s', platform, external_id, exc_info=True)
        return False` — Best-effort remote cancel via platform module; always clears local lease.
### `src/orchestrator/reconciliation.py`
- **class `ReconResult`** — no class docstring
- **class `ModuleReconciliation`** — EPS external_id → module.get_status; missing streak; remote orphans → review.
  - `run` — `def run(self) -> ReconResult:
    res = ReconResult()
    rows = self.db.fetchall("\n            SELECT entity_type, entity_id, platform, account_id, external_id, status, last_error, scheduled_for\n            FROM entity_platform_status\n            WHERE status IN (\n                'scheduled', 'scheduled_platform', 'publishing', 'uploaded_inbox',\n                'waiting_manual_publish', 'published'\n            )\n            ")
    for r in rows or []:
        res.checked += 1
        ext = (r.get('external_id') or '').strip()
        platform = r.get('platform') or ''
        if not ext:
            sched = r.get('scheduled_for')
            if sched and r.get('status') in ('scheduled', 'publishing'):
                try:
                    from datetime import datetime, timezone
                    st = datetime.fromisoformat(str(sched).replace('Z', '+00:00'))
                    if st.tzinfo is None:
                        st = st.replace(tzinfo=timezone.utc)
                    if self.clock.now() > st:
                        self.db.execute("UPDATE entity_platform_status SET status='error', last_error='past_due_no_external_id' WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?", (r['entity_type'], r['entity_id'], platform, r.get('account_id') or ''))
                        res.updated += 1
                except Exception:
                    pass
            continue
        st = self._module_status(platform, ext, str(r.get('account_id') or ''))
        if st is None:
            prev = r.get('last_error') or ''
            streak = 0
            if prev.startswith('missing_on_platform:'):
                try:
                    streak = int(prev.split(':')[1])
                except Exception:
                    streak = 1
            streak += 1
            res.missing += 1
            if streak >= self.missing_threshold:
                self.db.execute("UPDATE entity_platform_status SET status='error', last_error=? WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?", (f'missing_on_platform:{streak}', r['entity_type'], r['entity_id'], platform, r.get('account_id') or ''))
                res.updated += 1
            else:
                self.db.execute('UPDATE entity_platform_status SET last_error=? WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?', (f'missing_on_platform:{streak}', r['entity_type'], r['entity_id'], platform, r.get('account_id') or ''))
            continue
        state = getattr(st, 'state', None) or getattr(st, 'status', None) or ''
        if state == 'published' and r['status'] != 'published':
            self.db.execute("UPDATE entity_platform_status SET status='published', external_url=COALESCE(?, external_url), last_error=NULL WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?", (getattr(st, 'url', None), r['entity_type'], r['entity_id'], platform, r.get('account_id') or ''))
            res.updated += 1
    try:
        orphans = self.db.fetchall('\n                SELECT ru.id, ru.platform, ru.external_id FROM remote_uploads ru\n                LEFT JOIN remote_upload_matches m ON m.remote_upload_id = ru.id\n                WHERE m.id IS NULL\n                LIMIT 50\n                ')
        res.orphans = len(orphans or [])
    except Exception:
        pass
    return res` — no method docstring
### `src/orchestrator/reload.py`
- **function `reload_config`** — `def reload_config(path: str | Path, current: AppConfig) -> tuple[AppConfig | None, str]:
    """Load and validate new config. On failure return (None, error) — caller keeps current."""
    path = Path(path)
    backup = path.with_suffix(path.suffix + '.bak')
    try:
        new_cfg = load_config(path)
    except Exception as e:
        logger.error('Config validation failed: %s', e)
        return (None, str(e))
    try:
        if path.exists():
            shutil.copy2(path, backup)
    except Exception:
        pass
    logger.info('Config reloaded from %s', path)
    return (new_cfg, 'ok')` — Load and validate new config. On failure return (None, error) — caller keeps current.
- **function `apply_config_to_comps`** — `def apply_config_to_comps(comps: dict[str, Any], new_cfg: AppConfig) -> list[str]:
    """Push new_cfg into live components that hold a cfg reference (L38).

    Returns list of component keys updated. Some services (http server bind, etc.)
    still require process restart — those are listed in the log message.
    """
    updated: list[str] = []
    comps['cfg'] = new_cfg
    updated.append('cfg')
    for key, obj in list(comps.items()):
        if key == 'cfg':
            continue
        if obj is not None and hasattr(obj, 'cfg'):
            try:
                obj.cfg = new_cfg
                updated.append(key)
            except Exception:
                logger.exception('failed to update cfg on %s', key)
    logger.info('Config applied to comps=%s; restart required for HTTP bind/TLS/broker env', updated)
    return updated` — Push new_cfg into live components that hold a cfg reference (L38). Returns list of component keys updated. Some services (http server bind, etc.) still require process restart — those are listed in the log message.
### `src/orchestrator/runner.py`
- **class `Runner`** — Long-running loop: watcher → schedule → sync → reconcile → backup by intervals.
  - `stop` — `def stop(self, *_args) -> None:
    logger.info('Shutdown requested')
    self._stop = True` — no method docstring
  - `run_forever` — `def run_forever(self) -> None:
    signal.signal(signal.SIGINT, self.stop)
    signal.signal(signal.SIGTERM, self.stop)
    last_watch = last_sync = last_recon = last_backup = last_test_cleanup = time.monotonic()
    last_remote_scan = last_claims = last_b2 = last_ig_finalize = time.monotonic()
    last_daily_ahead_date: str | None = None
    last_provider_health = time.monotonic()
    last_outbox = time.monotonic()
    last_jobs = time.monotonic()
    last_recovery = time.monotonic()
    last_media_cleanup = time.monotonic()
    last_webhooks = time.monotonic()
    worker_id = f'runner-{os.getpid()}'
    last_consistency = time.monotonic()
    w_int = self.cfg.watcher_interval_sec
    s_int = self.cfg.status_sync_interval_sec
    r_int = self.cfg.reconciliation_interval_hours * 3600
    b_int = self.cfg.backup.interval_hours * 3600
    m_int = 86400 if self.cfg.manual_uploads.schedule_scan == 'daily' else 0
    last_manual = time.monotonic()
    logger.info('Runner started (watch=%ss sync=%ss recon=%sh backup=%sh dry_run=%s)', w_int, s_int, self.cfg.reconciliation_interval_hours, self.cfg.backup.interval_hours, self.dry_run)
    while not self._stop:
        now = time.monotonic()
        try:
            if now - last_watch >= w_int:
                self._cycle_watch()
                last_watch = now
            if now - last_sync >= s_int:
                self._cycle_sync()
                last_sync = now
            if now - last_recon >= r_int:
                self._cycle_recon()
                last_recon = now
            if now - last_backup >= b_int:
                self._cycle_backup()
                last_backup = now
            if m_int and now - last_manual >= m_int:
                self._cycle_manual()
                last_manual = now
            if now - last_test_cleanup >= 3600:
                self._cycle_test_cleanup()
                last_test_cleanup = now
            if now - last_remote_scan >= 3600:
                self._cycle_remote_scan()
                last_remote_scan = now
            if now - last_claims >= 1800:
                self._cycle_claims()
                last_claims = now
            if now - last_b2 >= 3600:
                self._cycle_b2_cleanup()
                last_b2 = now
            if now - last_ig_finalize >= 120:
                self._cycle_ig_finalize()
                self._cycle_local_schedule_due()
                last_ig_finalize = now
            if now - last_provider_health >= 30:
                self._cycle_provider_health()
                self._cycle_provider_access()
                last_provider_health = now
            if now - last_outbox >= 15:
                self._cycle_outbox()
                last_outbox = now
            if now - last_jobs >= 5:
                self._cycle_durable_jobs(worker_id)
                last_jobs = now
            if now - last_recovery >= 60:
                self._cycle_publish_recovery()
                last_recovery = now
            if now - last_media_cleanup >= 3600:
                self._cycle_media_cleanup()
                last_media_cleanup = now
            if now - last_webhooks >= 10:
                self._cycle_webhooks()
                last_webhooks = now
            consistency_min = max(5, int(os.getenv('ORCH_CONSISTENCY_INTERVAL_MIN', '60') or 60))
            if now - last_consistency >= consistency_min * 60:
                self._cycle_consistency()
                last_consistency = now
            da = getattr(self.cfg, 'daily_ahead', None)
            if da is not None and getattr(da, 'enabled', False):
                last_daily_ahead_date = self._maybe_daily_ahead(last_daily_ahead_date)
        except Exception as e:
            self.metrics.incr('errors')
            self.metrics.set('last_error', str(e))
            self.metrics.flush()
            self._cycle_fail_streak += 1
            delay = min(300, 2 ** min(self._cycle_fail_streak, 8))
            logger.exception('Cycle error (streak=%s, backoff=%ss)', self._cycle_fail_streak, delay)
            if self._cycle_fail_streak in (3, 10, 30):
                self._alert_cycle_fail(str(e))
            time.sleep(delay)
            continue
        else:
            self._cycle_fail_streak = 0
        time.sleep(1)
    logger.info('Runner stopped')` — no method docstring
### `src/orchestrator/safety.py`
- **class `SafetyChecker`** — no class docstring
  - `is_platform_paused` — `def is_platform_paused(self, platform: str) -> bool:
    row = self.db.fetchone('SELECT is_paused, paused_at FROM platform_safety_state WHERE platform = ?', (platform,))
    if not row or not row['is_paused']:
        return False
    pause_hours = int(self.safety.on_serious_error.get('pause_hours') or 0)
    if pause_hours > 0 and row['paused_at']:
        paused_at = _parse_dt(row['paused_at'])
        if paused_at and self.clock.now() >= paused_at + timedelta(hours=pause_hours):
            self.resume_platform(platform)
            return False
    return True` — no method docstring
  - `pause_platform` — `def pause_platform(self, platform: str, reason: str) -> None:
    now = self.clock.now().isoformat()
    self.db.execute('INSERT INTO platform_safety_state (platform, is_paused, paused_at, pause_reason, updated_at) VALUES (?, 1, ?, ?, ?) ON CONFLICT(platform) DO UPDATE SET is_paused=1, paused_at=excluded.paused_at, pause_reason=excluded.pause_reason, updated_at=excluded.updated_at', (platform, now, reason, now))
    self.db.log('system', None, platform, 'pause', reason)` — no method docstring
  - `resume_platform` — `def resume_platform(self, platform: str) -> None:
    now_dt = self.clock.now()
    now = now_dt.isoformat()
    self.db.execute('INSERT INTO platform_safety_state (platform, is_paused, updated_at) VALUES (?, 0, ?) ON CONFLICT(platform) DO NOTHING', (platform, now))
    row = self.db.fetchone('SELECT paused_at FROM platform_safety_state WHERE platform=?', (platform,))
    restart_warmup = False
    if row and row['paused_at']:
        paused_at = _parse_dt(row['paused_at'])
        hours = self.safety.warmup_after_pause_hours
        if paused_at and (now_dt - paused_at).total_seconds() >= hours * 3600:
            restart_warmup = True
    self.db.execute('UPDATE platform_safety_state SET is_paused=0, paused_at=NULL, pause_reason=NULL, updated_at=? WHERE platform=?', (now, platform))
    if restart_warmup:
        self.start_warmup(platform)
        self.db.log('system', None, platform, 'resume_warmup', '')
    else:
        self.db.log('system', None, platform, 'resume', '')` — no method docstring
  - `can_schedule` — `def can_schedule(self, platform: str, scheduled_for: datetime, platform_daily_limit: int) -> tuple[bool, str]:
    """Check limits and min_interval for a proposed schedule time."""
    if self.is_platform_paused(platform):
        return (False, 'platform_paused')
    try:
        from . import sched_settings as _ss
        from .slots import get_tz
        block = _ss.platform_block(self.db, platform)
        groups = _ss.load_groups(self.db)
        g = _ss.group_for(platform, groups)
        if g:
            settings = _ss.load_schedule_settings(self.db)
            gblock = settings.get(f"group:{g['name']}") or {}
            if isinstance(gblock, dict):
                block = {**block, **gblock}
        try:
            eff = _ss.effective(self.db, self.cfg, platform, 'long')
            for d in eff.get('exception_days') or []:
                block.setdefault('exception_days', [])
                if d not in block['exception_days']:
                    block['exception_days'] = list(block.get('exception_days') or []) + [d]
        except Exception:
            logger.debug('pause-state parse failed', exc_info=True)
        exc = {str(d) for d in (block or {}).get('exception_days') or []}
        if exc:
            day = scheduled_for.astimezone(get_tz(self.cfg.timezone)).strftime('%Y-%m-%d')
            if day in exc:
                return (False, 'exception_day')
    except Exception:
        logger.warning('exception_days: не смог проверить исключённые дни, защита пропущена', exc_info=True)
    if scheduled_for.tzinfo is None:
        scheduled_for = scheduled_for.replace(tzinfo=UTC)
    target_date, _, _ = self._local_day_bounds(scheduled_for)
    count = self._count_posts_on_date(platform, target_date)
    safety_row = self.db.fetchone('SELECT warmup_until FROM platform_safety_state WHERE platform = ?', (platform,))
    warmup_until = _parse_dt(safety_row['warmup_until']) if safety_row else None
    now = self.clock.now()
    limit = platform_daily_limit
    if warmup_until and now < warmup_until:
        limit = min(limit, self.safety.warmup_daily_limit)
    if count >= limit:
        return (False, f'daily_limit_reached ({count}/{limit})')
    win = self.safety.min_interval_minutes
    lo = (scheduled_for - timedelta(minutes=win)).isoformat()
    hi = (scheduled_for + timedelta(minutes=win)).isoformat()
    near = self.db.fetchone("\n            SELECT scheduled_for AS sched_at\n            FROM entity_platform_status\n            WHERE platform = ? AND scheduled_for IS NOT NULL\n              AND status IN ('scheduled', 'updating', 'published',\n                             'scheduled_platform', 'uploaded_inbox', 'waiting_manual_publish')\n              AND scheduled_for > ?\n              AND scheduled_for < ?\n            LIMIT 1\n            ", (platform, lo, hi))
    if near:
        return (False, f"min_interval_conflict ({near['sched_at']})")
    return (True, 'ok')` — Check limits and min_interval for a proposed schedule time.
  - `record_post` — `def record_post(self, platform: str, scheduled_for: datetime) -> None:
    """Update last_post_at and posts_today (reset when calendar day changes in cfg.timezone)."""
    now = self.clock.now().isoformat()
    if scheduled_for.tzinfo is None:
        scheduled_for = scheduled_for.replace(tzinfo=UTC)
    date_str, _, _ = self._local_day_bounds(scheduled_for)
    row = self.db.fetchone('SELECT posts_today, posts_today_date FROM platform_safety_state WHERE platform=?', (platform,))
    if row is None:
        self.db.execute('\n                INSERT INTO platform_safety_state\n                    (platform, last_post_at, posts_today, posts_today_date, updated_at)\n                VALUES (?, ?, 1, ?, ?)\n                ', (platform, scheduled_for.isoformat(), date_str, now))
        return
    prev_date = row['posts_today_date']
    if prev_date != date_str:
        new_count = 1
    else:
        new_count = int(row['posts_today'] or 0) + 1
    self.db.execute('\n            UPDATE platform_safety_state\n            SET last_post_at = ?, posts_today = ?, posts_today_date = ?, updated_at = ?\n            WHERE platform = ?\n            ', (scheduled_for.isoformat(), new_count, date_str, now, platform))` — Update last_post_at and posts_today (reset when calendar day changes in cfg.timezone).
  - `start_warmup` — `def start_warmup(self, platform: str) -> None:
    until = self.clock.now() + timedelta(days=self.safety.warmup_days)
    now = self.clock.now().isoformat()
    self.db.execute('INSERT INTO platform_safety_state (platform, warmup_until, updated_at) VALUES (?, ?, ?) ON CONFLICT(platform) DO UPDATE SET warmup_until=excluded.warmup_until, updated_at=excluded.updated_at', (platform, until.isoformat(), now))` — no method docstring
  - `handle_error` — `def handle_error(self, platform: str, error: str) -> None:
    """Classify and react to auth / serious errors."""
    now = self.clock.now().isoformat()
    self.db.execute('UPDATE platform_safety_state SET last_error=?, last_error_at=?, updated_at=? WHERE platform=?', (error, now, now, platform))
    err_l = error.lower()
    if any((a.lower() in err_l for a in getattr(self.safety, 'auth_errors', []))):
        self.pause_platform(platform, f'auth: {error}')
        return
    if any((r.lower() in err_l for r in getattr(self.safety, 'rate_limit_errors', []))):
        return
    if any((s.lower() in err_l for s in self.safety.serious_errors)):
        action = self.safety.on_serious_error.get('action', 'pause_platform')
        if action == 'pause_platform':
            self.pause_platform(platform, f'serious: {error}')
        return` — Classify and react to auth / serious errors.
### `src/orchestrator/sched_settings.py`
- **function `load_groups`** — `def load_groups(db: Database) -> list[dict[str, Any]]:
    data = _load_json(db, GROUPS_KEY, [])
    out: list[dict[str, Any]] = []
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            name = str(item.get('name') or '').strip()
            platforms = [str(p).strip() for p in item.get('platforms') or []]
            platforms = [p for p in platforms if p]
            if name and platforms:
                out.append({'name': name, 'platforms': platforms})
    return out` — no docstring
- **function `save_groups`** — `def save_groups(db: Database, groups: list[dict[str, Any]]) -> None:
    db.set_setting(GROUPS_KEY, json.dumps(groups, ensure_ascii=False))` — no docstring
- **function `load_schedule_settings`** — `def load_schedule_settings(db: Database) -> dict[str, Any]:
    data = _load_json(db, SCHEDULE_SETTINGS_KEY, {})
    return data if isinstance(data, dict) else {}` — no docstring
- **function `save_schedule_settings`** — `def save_schedule_settings(db: Database, settings: dict[str, Any]) -> None:
    db.set_setting(SCHEDULE_SETTINGS_KEY, json.dumps(settings, ensure_ascii=False))` — no docstring
- **function `group_for`** — `def group_for(platform: str, groups: list[dict[str, Any]]) -> dict[str, Any] | None:
    for g in groups:
        if platform in g.get('platforms', []):
            return g
    return None` — no docstring
- **function `effective`** — `def effective(db: Database, cfg: AppConfig, platform: str, kind: str) -> dict[str, Any]:
    """Итоговые настройки слота для платформы и типа контента.

    Порядок: override группы (если платформа в группе с настройками) → override платформы
    → конфиг → дефолты. Ключи результата нормализованы по типу:
    long: days/time; thematic: time; standalone: days/times.
    """
    if kind not in KIND_TO_CFG:
        raise ValueError(f'unknown kind: {kind}')
    base = dict(cfg.schedules.get(KIND_TO_CFG[kind], {}) or {})
    over = _override_for(db, platform, kind) or {}
    if kind == 'thematic':
        return {'time': str(over.get('time') or base.get('default_time') or '20:30')}
    if kind == 'long':
        days = over.get('days') or base.get('days') or ['tue', 'fri']
        time_str = over.get('time') or base.get('time') or '16:00'
        return {'days': [str(d) for d in days], 'time': str(time_str), 'exception_days': list(base.get('exception_days', []))}
    days = over.get('days') if over.get('days') is not None else base.get('days', [])
    times = over.get('times') or base.get('times') or []
    return {'days': [str(d) for d in days or []], 'times': [str(t) for t in times], 'exception_days': list(base.get('exception_days', []))}` — Итоговые настройки слота для платформы и типа контента. Порядок: override группы (если платформа в группе с настройками) → override платформы → конфиг → дефолты. Ключи результата нормализованы по типу: long: days/time; thematic: time; standalone: days/times.
- **function `effective_daily_limit`** — `def effective_daily_limit(db: Database, cfg: AppConfig, platform: str) -> int:
    settings = load_schedule_settings(db)
    block = settings.get(platform)
    if isinstance(block, dict):
        val = block.get('daily_limit')
        if isinstance(val, int) and 0 <= val <= 50:
            return val
    pcfg = cfg.platforms.get(platform)
    return int(getattr(pcfg, 'daily_limit', 0) or 0)` — no docstring
- **function `validate_time`** — `def validate_time(value: Any) -> bool:
    return bool(TIME_RE.match(str(value or '')))` — no docstring
- **function `validate_schedule_settings`** — `def validate_schedule_settings(settings: Any) -> tuple[bool, str]:
    if not isinstance(settings, dict):
        return (False, 'schedule_settings must be an object')
    for key, block in settings.items():
        if not isinstance(block, dict):
            return (False, f'{key}: must be an object')
        for kind in ('long', 'thematic', 'standalone'):
            part = block.get(kind)
            if part is None:
                continue
            if not isinstance(part, dict):
                return (False, f'{key}.{kind}: must be an object')
            if kind == 'long':
                if 'days' in part and (not isinstance(part['days'], list) or any((str(d).lower()[:3] not in DAYS for d in part['days']))):
                    return (False, f'{key}.long.days: invalid')
                if 'time' in part and (not validate_time(part['time'])):
                    return (False, f'{key}.long.time: invalid')
            elif kind == 'thematic':
                if 'time' in part and (not validate_time(part['time'])):
                    return (False, f'{key}.thematic.time: invalid')
            else:
                if 'days' in part and (not isinstance(part['days'], list) or any((str(d).lower()[:3] not in DAYS for d in part['days']))):
                    return (False, f'{key}.standalone.days: invalid')
                if 'times' in part and (not isinstance(part['times'], list) or any((not validate_time(t) for t in part['times']))):
                    return (False, f'{key}.standalone.times: invalid')
        if 'daily_limit' in block:
            val = block['daily_limit']
            if not isinstance(val, int) or not 0 <= val <= 50:
                return (False, f'{key}.daily_limit: invalid')
    return (True, '')` — no docstring
- **function `validate_groups`** — `def validate_groups(groups: Any, known_platforms: list[str]) -> tuple[bool, str]:
    if not isinstance(groups, list):
        return (False, 'groups must be a list')
    seen = set()
    for g in groups:
        if not isinstance(g, dict):
            return (False, 'group must be an object')
        name = str(g.get('name') or '').strip()
        if not name:
            return (False, 'group.name is required')
        if name in seen:
            return (False, f'duplicate group name: {name}')
        seen.add(name)
        plats = g.get('platforms')
        if not isinstance(plats, list) or not plats:
            return (False, f'group {name}: platforms required')
        for p in plats:
            if p not in known_platforms:
                return (False, f'group {name}: unknown platform {p}')
    return (True, '')` — no docstring
- **function `scheduling_mode`** — `def scheduling_mode(db: Database) -> str:
    """auto — раскладывать без подтверждения; manual — ждать кнопку/дату в панели."""
    raw = db.get_setting(SCHEDULING_MODE_KEY)
    return 'auto' if str(raw or '').strip().lower() == 'auto' else 'manual'` — auto — раскладывать без подтверждения; manual — ждать кнопку/дату в панели.
- **function `set_scheduling_mode`** — `def set_scheduling_mode(db: Database, mode: str) -> None:
    db.set_setting(SCHEDULING_MODE_KEY, 'auto' if mode == 'auto' else 'manual')` — no docstring
- **function `shorts_start_date`** — `def shorts_start_date(db: Database) -> str:
    raw = db.get_setting(SHORTS_START_KEY)
    return str(raw or '').strip()` — no docstring
- **function `set_shorts_start_date`** — `def set_shorts_start_date(db: Database, value: str) -> None:
    db.set_setting(SHORTS_START_KEY, str(value or '').strip())` — no docstring
- **function `all_times`** — `def all_times(db: Database, cfg: AppConfig, platform: str) -> list[str]:
    """Все разрешённые времена слотов платформы (HH:MM) из эффективных настроек."""
    out: list[str] = []
    long_eff = effective(db, cfg, platform, 'long')
    if long_eff.get('time'):
        out.append(str(long_eff['time']))
    th = effective(db, cfg, platform, 'thematic')
    if th.get('time'):
        out.append(str(th['time']))
    sa = effective(db, cfg, platform, 'standalone')
    for t in sa.get('times') or []:
        out.append(str(t))
    seen: list[str] = []
    for t in out:
        if t not in seen:
            seen.append(t)
    return seen` — Все разрешённые времена слотов платформы (HH:MM) из эффективных настроек.
- **function `platform_block`** — `def platform_block(db: Database, platform: str) -> dict[str, Any]:
    """Return schedule settings override block for platform (empty if none)."""
    settings = load_schedule_settings(db)
    block = settings.get(platform) or settings.get(f'platform:{platform}') or {}
    return block if isinstance(block, dict) else {}` — Return schedule settings override block for platform (empty if none).
### `src/orchestrator/schedule_guard.py`
- **function `eps_source`** — `def eps_source(db: Any) -> Callable[[str], list[datetime]]:
    """Busy times from EPS (scheduled / scheduled_platform) — primary C8 source."""

    def fn(platform: str) -> list[datetime]:
        out: list[datetime] = []
        try:
            rows = db.fetchall("\n                SELECT scheduled_for AS scheduled_for\n                FROM entity_platform_status\n                WHERE platform=? AND status IN (\n                    'scheduled', 'scheduled_platform', 'publishing', 'updating',\n                    'uploaded_inbox', 'waiting_manual_publish'\n                )\n                AND scheduled_for IS NOT NULL\n                ", (platform,))
        except Exception:
            return out
        for r in rows or []:
            dt = _parse(r.get('scheduled_for'))
            if dt:
                out.append(dt)
        return out
    return fn` — Busy times from EPS (scheduled / scheduled_platform) — primary C8 source.
- **class `ScheduleGuard`** — Check slot does not conflict with EPS (+ optional external sources).
  - `invalidate` — `def invalidate(self) -> None:
    self._cache.clear()` — no method docstring
  - `busy` — `def busy(self, platform: str) -> list[datetime]:
    out: list[datetime] = []
    for name, fn in self.sources:
        out.extend(self._times(name, fn, platform))
    return out` — no method docstring
  - `conflict` — `def conflict(self, platform: str, when: datetime) -> str | None:
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    minutes = getattr(self.cfg.safety, 'conflict_window_minutes', 0) or self.cfg.safety.min_interval_minutes
    window = timedelta(minutes=minutes)
    for t in self.busy(platform):
        if abs((t - when).total_seconds()) < window.total_seconds():
            return f'schedule_conflict:{t.isoformat()}'
    return None` — no method docstring
### `src/orchestrator/scheduler.py`
- **class `Scheduler`** — no class docstring
  - `schedule_long_videos` — `def schedule_long_videos(self, start_date: str | None=None, scope_roots: list | None=None) -> int:
    """Place ready long videos into future slots (per platform, effective settings)."""
    now = self.clock.now()
    ref = max(self._start_ref(start_date) or now, now)
    videos = self.db.fetchall('SELECT id, folder_path, wide_path, vertical_path, platform_paths, title_text, description_text, hashtags_text, cover_path FROM long_videos ORDER BY created_at')
    count = 0
    for platform, pcfg in self.cfg.platforms.items():
        if not pcfg.enabled:
            continue
        if getattr(pcfg, 'post_mode', 'media') == 'link':
            continue
        if self._backlog_active(platform):
            continue
        pq = self.db.fetchone('SELECT pending_series_end_question, COALESCE(pending_backlog_question,0) AS pending_backlog_question FROM platform_queue_state WHERE platform=?', (platform,))
        if pq and (pq['pending_series_end_question'] or pq['pending_backlog_question']):
            continue
        eff = sched_settings.effective(self.db, self.cfg, platform, 'long')
        future_slots = next_long_video_dates(eff.get('days') or ['tue', 'fri'], eff.get('time') or '16:00', ref, count=20, exception_days=eff.get('exception_days', []), tz_name=self.cfg.timezone)
        if not future_slots:
            continue
        limit = sched_settings.effective_daily_limit(self.db, self.cfg, platform)
        if self.job is not None:
            self.job.set_total(self.job.state.total + len(videos))
        for video in videos:
            if self.job is not None and self.job.cancelled:
                break
            if not self._in_scope(video.get('folder_path'), scope_roots):
                continue
            if not self._platform_ok(platform, etype='long_video', eid=video['id']):
                continue
            exists = self.db.fetchone("SELECT 1 FROM entity_platform_status WHERE entity_type='long_video' AND entity_id=? AND platform=? AND status IN ('scheduled','published','skipped')", (video['id'], platform))
            if exists:
                continue
            path = self._pick_path(video, platform, pcfg)
            if not path:
                continue
            if self._in_publish_cooldown('long_video', video['id'], platform):
                continue
            for slot in future_slots:
                if slot <= now:
                    continue
                if self._guard_busy(platform, slot):
                    continue
                ok, _ = self.safety.can_schedule(platform, self._slot_for_safety(slot), limit)
                if ok:
                    content = {'title': video['title_text'] or '', 'description': video['description_text'] or '', 'hashtags': video['hashtags_text'] or '', 'cover': video.get('cover_path') or ''}
                    post = self._safe_publish('long_video', video['id'], platform, path, content, slot)
                    if post:
                        count += 1
                        if self.job is not None:
                            self.job.tick(1, f"Фильм #{video['id']} → {platform}")
                    else:
                        self._mark_publish_failed('long_video', video['id'], platform)
                    break
    return count` — Place ready long videos into future slots (per platform, effective settings).
  - `schedule_thematic_shorts` — `def schedule_thematic_shorts(self, parent_id: int, platform: str, scope_roots: list | None=None) -> int:
    """Schedule thematic shorts for a published long video that has release_url."""
    if not self._platform_ok(platform, etype='long_video', eid=parent_id):
        return 0
    parent = self.db.fetchone("SELECT * FROM entity_platform_status WHERE entity_type='long_video' AND entity_id=? AND platform=? AND status='published' AND release_url IS NOT NULL", (parent_id, platform))
    if not parent:
        parent = self.db.fetchone("SELECT * FROM entity_platform_status WHERE entity_type='long_video' AND entity_id=? AND platform=? AND status IN ('published','scheduled')", (parent_id, platform))
        if not parent:
            return 0
    if scope_roots:
        film = self.db.fetchone('SELECT folder_path FROM long_videos WHERE id=?', (parent_id,))
        if film is None or not self._in_scope(film.get('folder_path'), scope_roots):
            return 0
    release_url = parent.get('release_url')
    template_key = 'thematic_short' if release_url else 'thematic_short_no_link'
    template = self.cfg.description_templates.get(template_key, '{description}')
    shorts = self.db.fetchall("\n            SELECT s.* FROM shorts s\n            WHERE s.parent_video_id = ?\n              AND NOT EXISTS (\n                  SELECT 1 FROM entity_platform_status eps\n                  WHERE eps.entity_type='short' AND eps.entity_id=s.id\n                    AND eps.platform=? AND eps.status IN ('scheduled','published','skipped')\n              )\n            ORDER BY s.order_index, s.id\n            LIMIT ?\n            ", (parent_id, platform, self.cfg.limits.max_shorts_per_long_video))
    if not shorts:
        return 0
    long_sched = parent.get('scheduled_for') or parent.get('published_at')
    long_dt = datetime.fromisoformat(long_sched) if long_sched else self.clock.now()
    if long_dt.tzinfo is None:
        long_dt = long_dt.replace(tzinfo=UTC)
    next_long = self.db.fetchone("\n            SELECT scheduled_for AS scheduled_for\n            FROM entity_platform_status\n            WHERE entity_type='long_video' AND platform=? AND entity_id != ?\n              AND status IN ('scheduled','published','scheduled_platform')\n              AND scheduled_for > ?\n            ORDER BY scheduled_for LIMIT 1\n            ", (platform, parent_id, long_dt.isoformat()))
    next_dt = None
    if next_long and next_long.get('scheduled_for'):
        next_dt = datetime.fromisoformat(next_long['scheduled_for'])
        if next_dt.tzinfo is None:
            next_dt = next_dt.replace(tzinfo=UTC)
    eff = sched_settings.effective(self.db, self.cfg, platform, 'thematic')
    default_time = eff.get('time') or '20:30'
    slots = thematic_slot_days(long_dt, next_dt, default_time, tz_name=self.cfg.timezone)
    floor_raw = sched_settings.shorts_start_date(self.db)
    if floor_raw and slots:
        try:
            from datetime import date as _date
            from .slots import get_tz
            y, m, d = (int(x) for x in floor_raw.split('-'))
            floor = _date(y, m, d)
            tz = get_tz(self.cfg.timezone)
            slots = [sl for sl in slots if sl.astimezone(tz).date() >= floor]
        except Exception:
            logger.warning('bad shorts_start_date: %s', floor_raw)
    if not slots:
        return 0
    short_ids = [s['id'] for s in shorts]

    def _utc_minute_key(val) -> str:
        if val is None:
            return ''
        if isinstance(val, datetime):
            dt = val
        else:
            try:
                dt = datetime.fromisoformat(str(val))
            except Exception:
                return str(val)[:16]
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC).strftime('%Y-%m-%dT%H:%M')
    taken = set()
    for r in self.db.fetchall("SELECT scheduled_for AS scheduled_for FROM entity_platform_status WHERE platform=? AND scheduled_for IS NOT NULL AND status IN ('scheduled','updating','published','scheduled_platform',               'uploaded_inbox','waiting_manual_publish')", (platform,)):
        ts = r['scheduled_for']
        if ts:
            taken.add(_utc_minute_key(ts))
    now = self.clock.now()
    free_slots = [sl for sl in slots if sl > now and _utc_minute_key(sl) not in taken]
    free_slots = [sl for sl in free_slots if not self._guard_busy(platform, sl)]
    assignments = list(zip(short_ids, free_slots, strict=False))
    pcfg = self.cfg.platforms[platform]
    if getattr(pcfg, 'post_mode', 'media') == 'link':
        return 0
    if self.job is not None:
        self.job.set_total(max(self.job.state.total, len(assignments)))
    count = 0
    for sid, sched in assignments:
        if self.job is not None and self.job.cancelled:
            break
        if self._in_publish_cooldown('short', sid, platform):
            continue
        short = next((s for s in shorts if s['id'] == sid))
        desc = template.format(description=short['description_text'] or '', link=release_url or self.cfg.link_update.placeholder_text)
        content = {'title': short['title_text'] or '', 'description': desc, 'hashtags': short['hashtags_text'] or '', 'cover': short.get('cover_path') or ''}
        path = self._pick_short_path(short, platform)
        if not path:
            continue
        post = self._safe_publish('short', sid, platform, path, content, sched)
        if post:
            count += 1
        else:
            self._mark_publish_failed('short', sid, platform)
    return count` — Schedule thematic shorts for a published long video that has release_url.
  - `schedule_backlog` — `def schedule_backlog(self, platform: str, start_date: str | None=None) -> int:
    """Публикует остаток (неопубликованные шортсы серий) по свободным слотам."""
    pcfg = self.cfg.platforms.get(platform)
    if not pcfg or not pcfg.enabled:
        return 0
    if getattr(pcfg, 'post_mode', 'media') == 'link':
        return 0
    shorts = self.db.fetchall("\n            SELECT s.id, s.video_path, s.platform_paths, s.parent_video_id, s.folder_path,\n                   s.cover_path, s.title_text, s.description_text, s.hashtags_text\n            FROM shorts s\n            WHERE s.parent_video_id IS NOT NULL AND s.video_path IS NOT NULL\n              AND NOT EXISTS (\n                  SELECT 1 FROM entity_platform_status eps\n                  WHERE eps.entity_type='short' AND eps.entity_id=s.id\n                    AND eps.platform=? AND eps.status IN ('scheduled','published','skipped'))\n            ORDER BY s.parent_video_id, s.order_index, s.id\n            ", (platform,))
    if not shorts:
        return 0
    slots = self._backlog_slots(platform, start_date=start_date)
    count = 0
    for s in shorts:
        if not self._platform_ok(platform, etype='short', eid=s['id']):
            continue
        path = self._pick_short_path(s, platform)
        if not path:
            continue
        if self._in_publish_cooldown('short', s['id'], platform):
            continue
        for slot in slots:
            if self._guard_busy(platform, slot):
                continue
            ok, _ = self.safety.can_schedule(platform, self._slot_for_safety(slot), sched_settings.effective_daily_limit(self.db, self.cfg, platform))
            if not ok:
                continue
            content = {'title': s['title_text'] or '', 'description': s['description_text'] or '', 'hashtags': s['hashtags_text'] or '', 'cover': s.get('cover_path') or ''}
            post = self._safe_publish('short', s['id'], platform, path, content, slot)
            if post:
                count += 1
                break
            self._mark_publish_failed('short', s['id'], platform)
            break
    return count` — Публикует остаток (неопубликованные шортсы серий) по свободным слотам.
  - `send_due_telegram_posts` — `def send_due_telegram_posts(self) -> int:
    """Telegram (send_via=bot): отправить посты, у которых пришло время.

        Время = выход на YouTube + telegram_link_delay_min (лежит в
        scheduled_for). Пока ссылки нет — ждём release_url_timeout_min
        и потом отправляем без ссылки.
        """
    tg = self._bot_telegram()
    if tg is None:
        return 0
    now = self.clock.now()
    wait_min = int(getattr(self.cfg.link_update, 'release_url_timeout_min', 90) or 90)
    rows = self.db.fetchall("\n            SELECT entity_type, entity_id,\n                   scheduled_for AS scheduled_for\n            FROM entity_platform_status\n            WHERE platform='telegram' AND status='scheduled'\n              AND (external_id IS NULL\n                   OR external_id='')\n              AND scheduled_for IS NOT NULL\n              AND scheduled_for <= ?\n            ORDER BY scheduled_for\n            ", (now.isoformat(),))
    count = 0
    for r in rows:
        etype, eid = (r['entity_type'], r['entity_id'])
        try:
            when = datetime.fromisoformat(str(r['scheduled_for']))
            if when.tzinfo is None:
                when = when.replace(tzinfo=UTC)
        except Exception:
            logger.debug('telegram bot: плохое время у %s/%s', etype, eid, exc_info=True)
            when = now
        if self._in_publish_cooldown(etype, eid, 'telegram'):
            continue
        yt = self.db.fetchone("SELECT release_url FROM entity_platform_status WHERE entity_type=? AND entity_id=? AND platform='youtube' AND status='published' AND release_url IS NOT NULL", (etype, eid))
        url = str(yt['release_url']) if yt and yt['release_url'] else None
        if not url and now - when < timedelta(minutes=wait_min):
            continue
        text = self._telegram_post_html(etype, eid, url)
        if not text:
            continue
        buttons = [{'text': '▶️ Смотреть на YouTube', 'url': url}] if url else None
        try:
            pid = tg.send_post(text, buttons=buttons, preview_url=url)
        except Exception:
            logger.exception('telegram bot: отправка не удалась %s/%s', etype, eid)
            self._mark_publish_failed(etype, eid, 'telegram')
            continue
        self.db.execute("UPDATE entity_platform_status SET status='published', external_id=?, published_at=?, link_updated_at=COALESCE(link_updated_at, ?), last_error=NULL WHERE entity_type=? AND entity_id=? AND platform='telegram' AND (external_id IS NULL OR external_id='')", (pid, now.isoformat(), now.isoformat(), etype, eid))
        self.db.log(etype, eid, 'telegram', 'bot_sent', pid)
        logger.info('telegram bot: отправлен %s/%s -> %s', etype, eid, pid)
        count += 1
    return count` — Telegram (send_via=bot): отправить посты, у которых пришло время. Время = выход на YouTube + telegram_link_delay_min (лежит в scheduled_for). Пока ссылки нет — ждём release_url_timeout_min и потом отправляем без ссылки.
  - `schedule_telegram_links` — `def schedule_telegram_links(self) -> int:
    """Telegram (post_mode=link): посты-ссылки в плане заранее, с плейсхолдером до премьеры."""
    tcfg = self.cfg.platforms.get('telegram')
    if not tcfg or not tcfg.enabled or getattr(tcfg, 'post_mode', 'media') != 'link':
        return 0
    delay = int(getattr(self.cfg, 'telegram_link_delay_min', 15) or 0)
    limit = sched_settings.effective_daily_limit(self.db, self.cfg, 'telegram')
    count = 0
    from datetime import datetime as _dt2
    for r in self.db.fetchall("\n            SELECT t.entity_type, t.entity_id, t.scheduled_for AS scheduled_for,\n                   COALESCE(y.scheduled_for, y.published_at) AS yt_when\n            FROM entity_platform_status t\n            JOIN entity_platform_status y\n              ON y.entity_type=t.entity_type AND y.entity_id=t.entity_id\n             AND y.platform='youtube'\n            WHERE t.platform='telegram' AND t.status='ready'\n              AND t.last_error='waiting_for_youtube'\n              AND COALESCE(y.scheduled_for, y.published_at) IS NOT NULL\n            "):
        try:
            base = _dt2.fromisoformat(str(r['yt_when']))
        except Exception:
            continue
        new_when = (base + timedelta(minutes=delay)).isoformat()
        if str(r['scheduled_for'] or '') != new_when:
            self.db.execute("UPDATE entity_platform_status SET scheduled_for=? WHERE entity_type=? AND entity_id=? AND platform='telegram'", (new_when, r['entity_type'], r['entity_id']))
    rows = self.db.fetchall("\n            SELECT eps.entity_type, eps.entity_id, eps.status, eps.release_url,\n                   COALESCE(eps.scheduled_for, eps.published_at) AS when_at\n            FROM entity_platform_status eps\n            WHERE eps.platform='youtube' AND eps.status IN ('scheduled','published')\n              AND COALESCE(eps.scheduled_for, eps.published_at) IS NOT NULL\n            ORDER BY when_at\n            ")
    for r in rows:
        etype, eid = (r['entity_type'], r['entity_id'])
        if not self._platform_ok('telegram', etype=etype, eid=eid):
            continue
        exists = self.db.fetchone("SELECT 1 FROM entity_platform_status WHERE entity_type=? AND entity_id=? AND platform='telegram'", (etype, eid))
        if exists:
            continue
        url = r['release_url'] if r['status'] == 'published' else None
        try:
            from datetime import datetime as _dt
            yt_time = _dt.fromisoformat(str(r['when_at']))
        except Exception:
            continue
        when = yt_time + timedelta(minutes=delay)
        if when <= self.clock.now():
            when = self.clock.now() + timedelta(minutes=1)
        if url:
            text = self._link_text(etype, eid, url)
            if not text:
                continue
            if self._in_publish_cooldown(etype, eid, 'telegram'):
                continue
            for _ in range(8):
                if not self._guard_busy('telegram', when):
                    break
                when = when + timedelta(minutes=15)
            else:
                logger.info('telegram link (%s/%s): ближайшие слоты заняты', etype, eid)
                continue
            ok, reason = self.safety.can_schedule('telegram', self._slot_for_safety(when), limit)
            if not ok:
                logger.info('telegram link skip (%s/%s): %s', etype, eid, reason)
                self._mark_publish_failed(etype, eid, 'telegram')
                continue
            content = {'title': '', 'description': text, 'hashtags': '', 'priority': 'link'}
            post = self._safe_publish(etype, eid, 'telegram', None, content, when)
            if post:
                count += 1
                self.db.execute("UPDATE entity_platform_status SET link_updated_at=? WHERE entity_type=? AND entity_id=? AND platform='telegram'", (self.clock.now().isoformat(), etype, eid))
        else:
            self.db.execute("INSERT OR IGNORE INTO entity_platform_status (entity_type, entity_id, platform, status, scheduled_for, last_error) VALUES (?, ?, 'telegram', 'ready', ?, 'waiting_for_youtube')", (etype, eid, when.isoformat()))
            count += 1
    return count` — Telegram (post_mode=link): посты-ссылки в плане заранее, с плейсхолдером до премьеры.
  - `refresh_telegram_links` — `def refresh_telegram_links(self) -> int:
    """После выхода видео обновляем Telegram-пост реальной ссылкой (пересоздаём)."""
    tcfg = self.cfg.platforms.get('telegram')
    if not tcfg or not tcfg.enabled or getattr(tcfg, 'post_mode', 'media') != 'link':
        return 0
    rows = self.db.fetchall("\n            SELECT t.entity_type, t.entity_id,\n                   t.external_id AS external_id,\n                   t.scheduled_for AS scheduled_for\n            FROM entity_platform_status t\n            WHERE t.platform='telegram' AND t.status IN ('scheduled','updating','ready')\n              AND t.link_updated_at IS NULL\n              AND EXISTS (\n                SELECT 1 FROM entity_platform_status y\n                WHERE y.entity_type=t.entity_type AND y.entity_id=t.entity_id\n                  AND y.platform='youtube' AND y.status='published'\n                  AND y.release_url IS NOT NULL\n              )\n            ")
    count = 0
    for r in rows:
        etype, eid = (r['entity_type'], r['entity_id'])
        yt = self.db.fetchone("SELECT release_url FROM entity_platform_status WHERE entity_type=? AND entity_id=? AND platform='youtube' AND status='published' AND release_url IS NOT NULL", (etype, eid))
        if not yt or not yt['release_url']:
            continue
        if self._bot_telegram() is not None:
            self.db.execute("UPDATE entity_platform_status SET link_updated_at=?, status='scheduled', last_error=NULL WHERE entity_type=? AND entity_id=? AND platform='telegram'", (self.clock.now().isoformat(), etype, eid))
            count += 1
            continue
        text = self._link_text(etype, eid, yt['release_url'])
        if not text:
            continue
        when = None
        if r['scheduled_for']:
            try:
                from datetime import datetime as _dt
                when = _dt.fromisoformat(str(r['scheduled_for']))
            except Exception:
                when = None
        if when is None or when <= self.clock.now():
            when = self.clock.now() + timedelta(minutes=1)
        old_id = r['external_id']
        content = {'title': '', 'description': text, 'hashtags': ''}
        taken = self.db.execute("UPDATE entity_platform_status SET status='updating', external_id=NULL WHERE entity_type=? AND entity_id=? AND platform='telegram' AND external_id IS ?", (etype, eid, old_id))
        if not taken:
            logger.info('telegram refresh: строку уже обновляет другой цикл %s/%s', etype, eid)
            continue
        post = None
        try:
            post = self._safe_publish(etype, eid, 'telegram', None, content, when)
        except Exception:
            logger.exception('telegram refresh create failed %s/%s', etype, eid)
            post = None
        if post:
            if old_id:
                logger.info('telegram refresh: legacy id %s superseded by new post', old_id)
            self.db.execute("UPDATE entity_platform_status SET link_updated_at=? WHERE entity_type=? AND entity_id=? AND platform='telegram'", (self.clock.now().isoformat(), etype, eid))
            count += 1
        elif old_id:
            self.db.execute("UPDATE entity_platform_status SET status='scheduled', external_id=?, last_error='refresh_failed' WHERE entity_type=? AND entity_id=? AND platform='telegram'", (old_id, etype, eid))
    count += self._promote_waiting_without_url()
    count += self._enqueue_promo_for_long()
    return count` — После выхода видео обновляем Telegram-пост реальной ссылкой (пересоздаём).
  - `schedule_standalone_shorts` — `def schedule_standalone_shorts(self, tail_manager=None, start_date: str | None=None, scope_roots: list | None=None) -> int:
    """Schedule ShortsMaker standalone shorts on free (non-thematic) days."""
    from datetime import timedelta
    from .slots import DAY_MAP, get_tz, local_to_utc, parse_time
    now = self.clock.now()
    tz = get_tz(self.cfg.timezone)
    local_today = now.astimezone(tz).date()
    if start_date:
        try:
            from datetime import date as _date
            y, m, d = (int(x) for x in str(start_date).split('-'))
            local_today = _date(y, m, d)
        except Exception:
            pass
    count = 0
    for platform, pcfg in self.cfg.platforms.items():
        if not pcfg.enabled:
            continue
        if getattr(pcfg, 'post_mode', 'media') == 'link':
            continue
        if tail_manager and tail_manager.should_pause_standalone(platform):
            continue
        ready = self.db.fetchall("\n                SELECT s.id, s.video_path, s.folder_path, s.platform_paths, s.title_text,\n                       s.description_text, s.hashtags_text, s.cover_path\n                FROM shorts s\n                WHERE s.source = 'shortsmaker'\n                  AND s.parent_video_id IS NULL\n                  AND NOT EXISTS (\n                      SELECT 1 FROM entity_platform_status eps\n                      WHERE eps.entity_type='short' AND eps.entity_id=s.id\n                        AND eps.platform=?\n                        AND eps.status IN ('scheduled','published','skipped')\n                  )\n                ORDER BY s.order_index, s.id\n                LIMIT ?\n                ", (platform, self.cfg.limits.max_posts_per_distribute))
        if not ready:
            continue
        eff = sched_settings.effective(self.db, self.cfg, platform, 'standalone')
        days = eff.get('days') or ['mon', 'wed', 'thu', 'sat', 'sun']
        times = eff.get('times') or ['12:00', '18:00']
        limit = sched_settings.effective_daily_limit(self.db, self.cfg, platform)
        exceptions = set(eff.get('exception_days') or [])
        weekday_set = {DAY_MAP[d.lower()[:3]] for d in days}
        if self.job is not None:
            self.job.set_total(self.job.state.total + len(ready))
        for short in ready:
            if self.job is not None and self.job.cancelled:
                break
            if not self._in_scope(short.get('folder_path'), scope_roots):
                continue
            if not self._platform_ok(platform, folder=short.get('folder_path')):
                continue
            if self._in_publish_cooldown('short', short['id'], platform):
                continue
            cur = local_today
            placed = False
            failed = False
            for _ in range(28):
                if cur.weekday() in weekday_set and cur.isoformat() not in exceptions:
                    for ts in times:
                        t = parse_time(ts)
                        candidate = local_to_utc(cur, t, self.cfg.timezone)
                        if candidate <= now:
                            continue
                        if self._guard_busy(platform, candidate):
                            continue
                        ok, _ = self.safety.can_schedule(platform, self._slot_for_safety(candidate), limit)
                        if ok:
                            content = {'title': short['title_text'] or '', 'description': short['description_text'] or '', 'hashtags': short['hashtags_text'] or '', 'cover': short.get('cover_path') or ''}
                            post = self._safe_publish('short', short['id'], platform, self._pick_short_path(short, platform), content, candidate)
                            if post:
                                count += 1
                                placed = True
                                if self.job is not None:
                                    self.job.tick(1, f"Обычный шортс #{short['id']}")
                            else:
                                failed = True
                                self._mark_publish_failed('short', short['id'], platform)
                            break
                    if placed or failed:
                        break
                cur += timedelta(days=1)
    return count` — Schedule ShortsMaker standalone shorts on free (non-thematic) days.
### `src/orchestrator/scheduler_recovery.py`
- **class `SchedulerRecovery`** — Restart/DST safe scheduling primitives over account-aware EPS.
  - `recover_stale_leases` — `def recover_stale_leases(self, *, lease_grace_sec: int=60) -> int:
    now = self.clock.now()
    cutoff = (now - timedelta(seconds=max(0, int(lease_grace_sec)))).isoformat()
    return self.db.execute("UPDATE entity_platform_status SET status='ready', lease_until=NULL, last_error='recovered_stale_publish_lease', next_retry_at=? WHERE status='publishing' AND lease_until IS NOT NULL AND lease_until<?", (now.isoformat(), cutoff))` — no method docstring
  - `claim_due_local` — `def claim_due_local(self, limit: int=50) -> list[dict[str, Any]]:
    now = self.clock.now().isoformat()
    rows = self.db.fetchall("SELECT entity_type,entity_id,platform,account_id,external_id,publish_mode,status,scheduled_for FROM entity_platform_status WHERE status IN ('scheduled','ready') AND scheduled_for IS NOT NULL AND scheduled_for<=? AND (publish_mode='local_schedule' OR external_id LIKE 'local-%') ORDER BY scheduled_for LIMIT ?", (now, max(1, int(limit))))
    claimed = []
    lease = (self.clock.now() + timedelta(minutes=5)).isoformat()
    for row in rows:
        ok = self.db.execute("UPDATE entity_platform_status SET status='publishing', external_id=NULL, lease_until=?, attempt=COALESCE(attempt,0)+1 WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=? AND status IN ('scheduled','ready')", (lease, row['entity_type'], row['entity_id'], row['platform'], row.get('account_id') or ''))
        if ok:
            r = dict(row)
            r['account_id'] = str(row.get('account_id') or '')
            claimed.append(r)
    return claimed` — no method docstring
### `src/orchestrator/slots.py`
- **function `parse_time`** — `def parse_time(s: str) -> time:
    h, m = map(int, s.split(':'))
    return time(h, m)` — no docstring
- **function `get_tz`** — `def get_tz(name: str='Europe/Moscow') -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo('UTC')` — no docstring
- **function `local_to_utc`** — `def local_to_utc(d: date, t: time, tz_name: str) -> datetime:
    """Interpret wall-clock date+time in tz_name, return UTC datetime."""
    tz = get_tz(tz_name)
    local = datetime.combine(d, t, tzinfo=tz)
    return local.astimezone(UTC)` — Interpret wall-clock date+time in tz_name, return UTC datetime.
- **function `daterange_dates`** — `def daterange_dates(start: date, end: date) -> Iterator[date]:
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)` — no docstring
- **function `thematic_slot_days`** — `def thematic_slot_days(long_video_date: datetime, next_long_date: datetime | None, default_time: str='20:30', tz_name: str='Europe/Moscow', horizon_days: int=7) -> list[datetime]:
    """
    All days from long_video_date (inclusive) to the day before next_long_date.
    Times are wall-clock in tz_name, returned as UTC.
    If next_long_date is None, use horizon_days (default 7) from long date.
    """
    if long_video_date.tzinfo is None:
        long_video_date = long_video_date.replace(tzinfo=UTC)
    tz = get_tz(tz_name)
    local_long = long_video_date.astimezone(tz)
    t = parse_time(default_time)
    if next_long_date is None:
        end_day = local_long.date() + timedelta(days=max(0, horizon_days - 1))
        return [local_to_utc(d, t, tz_name) for d in daterange_dates(local_long.date(), end_day)]
    if next_long_date.tzinfo is None:
        next_long_date = next_long_date.replace(tzinfo=UTC)
    local_next = next_long_date.astimezone(tz)
    end_day = local_next.date() - timedelta(days=1)
    if end_day < local_long.date():
        end_day = local_long.date()
    return [local_to_utc(d, t, tz_name) for d in daterange_dates(local_long.date(), end_day)]` — All days from long_video_date (inclusive) to the day before next_long_date. Times are wall-clock in tz_name, returned as UTC. If next_long_date is None, use horizon_days (default 7) from long date.
- **function `next_long_video_dates`** — `def next_long_video_dates(days: list[str], time_str: str, from_dt: datetime, count: int=10, exception_days: list[str] | None=None, tz_name: str='Europe/Moscow') -> list[datetime]:
    """Future long-video times: wall-clock in tz_name, returned UTC."""
    exception_days = set(exception_days or [])
    weekday_set = {DAY_MAP[d.lower()[:3]] for d in days}
    t = parse_time(time_str)
    tz = get_tz(tz_name)
    if from_dt.tzinfo is None:
        from_dt = from_dt.replace(tzinfo=UTC)
    local_from = from_dt.astimezone(tz)
    result: list[datetime] = []
    cur = local_from.date()
    guard = 0
    while len(result) < count and guard < 400:
        guard += 1
        if cur.weekday() in weekday_set and cur.isoformat() not in exception_days:
            dt_utc = local_to_utc(cur, t, tz_name)
            if dt_utc > from_dt:
                result.append(dt_utc)
        cur += timedelta(days=1)
    return result` — Future long-video times: wall-clock in tz_name, returned UTC.
- **function `apply_jitter`** — `def apply_jitter(dt: datetime, jitter_seconds: int) -> datetime:
    if jitter_seconds <= 0:
        return dt
    h = int(hashlib.md5(dt.isoformat().encode()).hexdigest()[:8], 16)
    offset = h % (2 * jitter_seconds + 1) - jitter_seconds
    return dt + timedelta(seconds=offset)` — no docstring
### `src/orchestrator/status_sync.py`
- **function `is_thumbnail_only_error`** — `def is_thumbnail_only_error(x: Any) -> bool:
    return False` — no docstring
- **function `short_reason`** — `def short_reason(msg: Any, limit: int=300) -> str:
    return (str(msg) if msg else '')[:limit]` — no docstring
- **class `StatusSync`** — Module-only status pull for EPS rows with external_id. No platform client or legacy EPS field is required. Uses module.get_status only.
  - `sync` — `def sync(self, fresh_only: bool=False) -> int:
    """Pull status via module.get_status for rows with external_id.

        If fresh_only — only posts scheduled within confirm_published_interval
        window around now (uses scheduled_for, falls back to legacy column if present).
        """
    sql = "\n            SELECT entity_type, entity_id, platform, account_id, status,\n                   release_url, last_error,\n                   external_id, external_url, scheduled_for, source\n            FROM entity_platform_status\n            WHERE (\n                external_id IS NOT NULL AND external_id != ''\n              )\n              AND (\n                status IN ('scheduled', 'updating', 'error', 'publishing',\n                           'scheduled_platform', 'uploaded_inbox', 'waiting_manual_publish')\n                OR (status='published' AND (release_url IS NULL OR release_url=''\n                    OR external_url IS NULL OR external_url=''))\n              )\n        "
    rows = self.db.fetchall(sql)
    if fresh_only:
        window = self.cfg.confirm_published_interval_sec
        now = self.clock.now()
        filtered = []
        for r in rows:
            sched = r.get('scheduled_for')
            if not sched:
                filtered.append(r)
                continue
            try:
                st = datetime.fromisoformat(str(sched).replace('Z', '+00:00'))
                if st.tzinfo is None:
                    st = st.replace(tzinfo=UTC)
                if abs((st - now).total_seconds()) <= window * 3:
                    filtered.append(r)
            except Exception:
                filtered.append(r)
        rows = filtered
    updated = 0
    for row in rows:
        try:
            post = self._fetch_status(row)
        except Exception:
            logger.warning('get_status failed for %s/%s/%s (skip)', row.get('platform'), row.get('entity_type'), row.get('entity_id'), exc_info=True)
            continue
        if not post:
            prev = row.get('last_error') or ''
            streak = 0
            if prev.startswith('missing_on_platform:'):
                try:
                    streak = int(prev.split(':')[1])
                except Exception:
                    streak = 1
            streak += 1
            threshold = int(getattr(self.cfg, 'missing_error_after', None) or getattr(self.cfg, 'missing_error_after', None) or DEFAULT_MISSING_THRESHOLD)
            if streak >= threshold:
                self.db.execute("UPDATE entity_platform_status SET status='error', last_error=? WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?", (f'missing_on_platform:{streak}', row['entity_type'], row['entity_id'], row['platform'], row.get('account_id') or ''))
            else:
                self.db.execute('UPDATE entity_platform_status SET last_error=? WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?', (f'missing_on_platform:{streak}', row['entity_type'], row['entity_id'], row['platform'], row.get('account_id') or ''))
                logger.warning('get_status miss %s/%s/%s streak=%s/%s', row['entity_type'], row['entity_id'], row['platform'], streak, threshold)
            updated += 1
            continue
        st = self._normalize_status(getattr(post, 'status', None))
        if st == 'error':
            prev_err = str(row.get('last_error') or '')
            if row['status'] == 'published' and prev_err.startswith(THUMBNAIL_WARN_PREFIX):
                continue
            reason = short_reason(getattr(post, 'error', None), ERROR_REASON_LIMIT)
            if is_thumbnail_only_error(reason):
                now = self.clock.now().isoformat()
                warn = short_reason(f'{THUMBNAIL_WARN_PREFIX}: {reason}', ERROR_REASON_LIMIT)
                self.db.execute("\n                        UPDATE entity_platform_status\n                        SET status='published', published_at=?,\n                            release_url=COALESCE(?, release_url),\n                            last_error=?\n                        WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?\n                        ", (now, post.release_url, warn, row['entity_type'], row['entity_id'], row['platform'], row.get('account_id') or ''))
                self.db.log(row['entity_type'], row['entity_id'], row['platform'], 'published_without_cover', short_reason(reason))
                logger.warning('platform %s/%s %s — published without cover: %s', row['entity_type'], row['entity_id'], row['platform'], reason)
                updated += 1
                continue
            msg = short_reason(f'Ошибка площадки: {reason}', ERROR_REASON_LIMIT) if reason else 'platform_error'
            if row['status'] != 'error' or msg != prev_err:
                self.db.execute("UPDATE entity_platform_status SET status='error', last_error=? WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?", (msg, row['entity_type'], row['entity_id'], row['platform'], row.get('account_id') or ''))
                updated += 1
            if post.release_url and (not row.get('release_url')):
                self.db.execute("UPDATE entity_platform_status SET release_url=? WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=? AND (release_url IS NULL OR release_url='')", (post.release_url, row['entity_type'], row['entity_id'], row['platform'], row.get('account_id') or ''))
                updated += 1
            continue
        if st == 'published' and row['status'] != 'published':
            now = self.clock.now().isoformat()
            self.db.execute("\n                    UPDATE entity_platform_status\n                    SET status='published', published_at=?,\n                        release_url=COALESCE(?, release_url),\n                        external_url=COALESCE(?, external_url),\n                        last_error=NULL\n                    WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?\n                    ", (now, post.release_url, post.release_url, row['entity_type'], row['entity_id'], row['platform'], row.get('account_id') or ''))
            updated += 1
        elif st == 'published' and post.release_url and (not row.get('release_url')):
            self.db.execute("UPDATE entity_platform_status SET release_url=?, external_url=COALESCE(external_url, ?) WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=? AND (release_url IS NULL OR release_url='')", (post.release_url, post.release_url, row['entity_type'], row['entity_id'], row['platform'], row.get('account_id') or ''))
            updated += 1
        else:
            prev_err = row.get('last_error') or ''
            if prev_err.startswith('missing_on_platform:') or (row['status'] == 'error' and prev_err == 'reconciliation_missing'):
                new_status = row['status']
                if new_status == 'error':
                    new_status = st if st in ('scheduled', 'updating') else 'scheduled'
                self.db.execute('UPDATE entity_platform_status SET status=?, last_error=NULL WHERE entity_type=? AND entity_id=? AND platform=? AND account_id=?', (new_status, row['entity_type'], row['entity_id'], row['platform'], row.get('account_id') or ''))
                updated += 1
                logger.info('Recovered %s/%s/%s from %s -> %s', row['entity_type'], row['entity_id'], row['platform'], prev_err, new_status)
    return updated` — Pull status via module.get_status for rows with external_id. If fresh_only — only posts scheduled within confirm_published_interval window around now (uses scheduled_for, falls back to legacy column if present).
### `src/orchestrator/tail.py`
- **class `TailManager`** — no class docstring
  - `is_tail` — `def is_tail(self, platform: str) -> bool:
    row = self.db.fetchone('SELECT series_tail_mode FROM platform_queue_state WHERE platform=?', (platform,))
    return bool(row and row['series_tail_mode'])` — no method docstring
  - `on_new_long_video` — `def on_new_long_video(self, platform: str, video_id: int, at: str | None=None, *, reset_tail: bool | None=None) -> None:
    """Record new long video time (L17: entity time, not now).

        Tail reset policy (L20 / §2): reset series_tail_mode only when the long is
        already published or scheduled within soft_enter_days of now. Far-future
        scheduled longs update active/last timestamps but do not clear tail.
        """
    now = self.clock.now()
    now_s = now.isoformat()
    at_s = at or now_s
    do_reset = reset_tail
    if do_reset is None:
        do_reset = True
        try:
            at_dt = datetime.fromisoformat(at_s)
            if at_dt.tzinfo is None:
                at_dt = at_dt.replace(tzinfo=UTC)
            horizon = timedelta(days=int(self.cfg.tail.soft_enter_days or 0))
            if at_dt > now + horizon:
                do_reset = False
        except Exception:
            do_reset = True
    if do_reset:
        self.db.execute('\n                UPDATE platform_queue_state\n                SET series_tail_mode=0,\n                    active_long_video_id=?,\n                    last_long_video_at=?,\n                    pending_series_end_question=0,\n                    pending_series_end_at=NULL,\n                    updated_at=?\n                WHERE platform=?\n                ', (video_id, at_s, now_s, platform))
        logger.info('Tail reset on %s due to long video %s at %s', platform, video_id, at_s)
    else:
        self.db.execute('\n                UPDATE platform_queue_state\n                SET active_long_video_id=?,\n                    last_long_video_at=?,\n                    updated_at=?\n                WHERE platform=?\n                ', (video_id, at_s, now_s, platform))
        logger.info('Long %s on %s recorded at %s (tail kept — schedule beyond soft_enter)', video_id, platform, at_s)` — Record new long video time (L17: entity time, not now). Tail reset policy (L20 / §2): reset series_tail_mode only when the long is already published or scheduled within soft_enter_days of now. Far-future scheduled longs update active/last timestamps but do not clear tail.
  - `sync_new_long` — `def sync_new_long(self, platform: str) -> bool:
    """Отмечает последний запланированный/вышедший фильм.

        Без этого `check_soft_enter` никогда не срабатывал (last_long_video_at пустой).
        Возвращает True, если состояние обновилось.
        """
    row = self.db.fetchone("SELECT entity_id, COALESCE(published_at, scheduled_for) AS at FROM entity_platform_status WHERE entity_type='long_video' AND platform=?   AND status IN ('scheduled','published','updating') ORDER BY COALESCE(published_at, scheduled_for) DESC LIMIT 1", (platform,))
    if not row or not row['at']:
        return False
    cur = self.db.fetchone('SELECT active_long_video_id, last_long_video_at FROM platform_queue_state WHERE platform=?', (platform,))
    if cur and cur['active_long_video_id'] == row['entity_id'] and cur['last_long_video_at']:
        return False
    self.on_new_long_video(platform, row['entity_id'], at=row['at'])
    return True` — Отмечает последний запланированный/вышедший фильм. Без этого `check_soft_enter` никогда не срабатывал (last_long_video_at пустой). Возвращает True, если состояние обновилось.
  - `check_soft_enter` — `def check_soft_enter(self, platform: str) -> None:
    """If no new long video for soft_enter_days → ask user."""
    row = self.db.fetchone('SELECT last_long_video_at, series_tail_mode, pending_series_end_question, last_series_end_question_at FROM platform_queue_state WHERE platform=?', (platform,))
    if not row or row['series_tail_mode']:
        return
    last = row['last_long_video_at']
    if not last:
        return
    last_dt = datetime.fromisoformat(last)
    if last_dt.tzinfo is None:
        last_dt = last_dt.replace(tzinfo=UTC)
    days = (self.clock.now() - last_dt).days
    if days < self.cfg.tail.soft_enter_days:
        return
    if row['last_series_end_question_at']:
        prev = datetime.fromisoformat(row['last_series_end_question_at'])
        if prev.tzinfo is None:
            prev = prev.replace(tzinfo=UTC)
        if (self.clock.now() - prev).days < self.cfg.tail.series_end_question_cooldown_days:
            return
    now = self.clock.now().isoformat()
    self.db.execute('UPDATE platform_queue_state SET pending_series_end_question=1, pending_series_end_at=?, last_series_end_question_at=?, updated_at=? WHERE platform=?', (now, now, now, platform))
    self.tg.ask_series_end(platform)` — If no new long video for soft_enter_days → ask user.
  - `should_pause_standalone` — `def should_pause_standalone(self, platform: str) -> bool:
    return self.is_tail(platform) and self.cfg.tail.pause_standalone_during_tail` — no method docstring
  - `use_all_short_slots` — `def use_all_short_slots(self, platform: str) -> bool:
    return self.is_tail(platform) and self.cfg.tail.use_all_short_slots` — no method docstring
  - `expire_pending_questions` — `def expire_pending_questions(self) -> int:
    """Clear pending series_end questions past TTL (L19).

        Respects tail.default_action: if distribute → enter series_tail_mode;
        otherwise just clear the pending flag (wait / manual).
        """
    ttl = self.cfg.tail.series_end_question_ttl_days
    rows = self.db.fetchall('SELECT platform, pending_series_end_at FROM platform_queue_state WHERE pending_series_end_question=1 AND pending_series_end_at IS NOT NULL')
    n = 0
    now = self.clock.now()
    action = (self.cfg.tail.default_action or 'wait').lower()
    for r in rows:
        try:
            at = datetime.fromisoformat(r['pending_series_end_at'])
            if at.tzinfo is None:
                at = at.replace(tzinfo=UTC)
        except Exception:
            continue
        if (now - at).days >= ttl:
            if action == 'distribute':
                self.db.execute('UPDATE platform_queue_state SET pending_series_end_question=0, pending_series_end_at=NULL, series_tail_mode=1, updated_at=? WHERE platform=?', (now.isoformat(), r['platform']))
                logger.info('Expired series_end on %s → tail mode (default_action=distribute)', r['platform'])
            else:
                self.db.execute('UPDATE platform_queue_state SET pending_series_end_question=0, pending_series_end_at=NULL, updated_at=? WHERE platform=?', (now.isoformat(), r['platform']))
                logger.info('Expired series_end on %s → cleared (default_action=%s)', r['platform'], action)
            n += 1
    return n` — Clear pending series_end questions past TTL (L19). Respects tail.default_action: if distribute → enter series_tail_mode; otherwise just clear the pending flag (wait / manual).
### `src/orchestrator/telegram_bot.py`
- **class `TelegramNotifier`** — Abstract notifier + command router. Real transport plugged later.
  - `is_allowed` — `def is_allowed(self, chat_id: int) -> bool:
    allowed = self.cfg.telegram.allowed_chat_ids
    if not allowed:
        if self._owner_chat_id is None:
            self._owner_chat_id = chat_id
            return True
        return chat_id == self._owner_chat_id
    return chat_id in allowed` — no method docstring
  - `send` — `def send(self, chat_id: int, text: str, reply_markup: dict | None=None) -> None:
    if not self.is_allowed(chat_id):
        logger.warning('Blocked message to unauthorized chat %s', chat_id)
        return
    if self.transport:
        self.transport.send_message(chat_id, text, reply_markup)
    else:
        logger.info('[TG -> %s] %s', chat_id, (text or '')[:200])` — no method docstring
  - `broadcast` — `def broadcast(self, text: str) -> None:
    targets = self.cfg.telegram.allowed_chat_ids or ([self._owner_chat_id] if self._owner_chat_id else [])
    for cid in targets:
        if cid:
            self.send(cid, text)` — no method docstring
  - `register` — `def register(self, command: str, handler: Callable) -> None:
    self._handlers[command.lstrip('/')] = handler` — no method docstring
  - `handle_update` — `def handle_update(self, chat_id: int, text: str) -> str | None:
    if not self.is_allowed(chat_id):
        return 'Access denied'
    text = (text or '').strip()
    if chat_id in self._pending_dialogs:
        return self._resolve_dialog(chat_id, text)
    if not text.startswith('/'):
        return '🤖 Автоответ: сообщение дошло до бота. Когда я его прочитаю и отвечу, на нём появится 👍. Команды: /help'
    parts = text.split(maxsplit=1)
    cmd = parts[0].lstrip('/').split('@')[0]
    arg = parts[1] if len(parts) > 1 else ''
    handler = self._handlers.get(cmd)
    if not handler:
        return f'Неизвестная команда: /{cmd}. Список: /help'
    return handler(chat_id, arg)` — no method docstring
  - `ask_series_end` — `def ask_series_end(self, platform: str) -> None:
    """P0.11: спросить про soft-end и зарегистрировать диалог (иначе ответ не резолвится)."""
    from datetime import timedelta
    ttl_days = int(getattr(self.cfg.tail, 'series_end_question_ttl_days', 3) or 3)
    expires = (self.clock.now() + timedelta(days=ttl_days)).timestamp()
    targets = list(self.cfg.telegram.allowed_chat_ids or [])
    if not targets and self._owner_chat_id:
        targets = [self._owner_chat_id]
    for cid in targets:
        if cid:
            self._pending_dialogs[cid] = {'type': 'series_end', 'platform': platform, 'expires': expires}
    self.broadcast(f'Series soft-end on {platform}. Enter tail mode? Reply: yes / no')` — P0.11: спросить про soft-end и зарегистрировать диалог (иначе ответ не резолвится).
  - `ask_missing_url` — `def ask_missing_url(self, entity_id: int, platform: str, chat_id: int | None=None) -> None:
    dialog = {'type': 'missing_url', 'entity_id': entity_id, 'platform': platform, 'expires': self.clock.now().timestamp() + self.cfg.link_update.missing_url_dialog_ttl_hours * 3600}
    targets = [chat_id] if chat_id else self.cfg.telegram.allowed_chat_ids or ([self._owner_chat_id] if self._owner_chat_id else [])
    for cid in targets:
        if cid:
            self._pending_dialogs[cid] = dialog
            self.send(cid, f"No release_url for long_video #{entity_id} on {platform}.\nSend URL or 'skip' (default: {self.cfg.link_update.missing_url_default_action})")` — no method docstring
  - `broadcast_markup` — `def broadcast_markup(self, text: str, reply_markup: dict) -> None:
    """P0.12/N1: рассылка с inline-кнопками всем allowed чатам (метод класса)."""
    targets = list(self.cfg.telegram.allowed_chat_ids or [])
    if not targets and self._owner_chat_id:
        targets = [self._owner_chat_id]
    for cid in targets:
        if cid:
            self.send(cid, text, reply_markup)` — P0.12/N1: рассылка с inline-кнопками всем allowed чатам (метод класса).
  - `ask_backlog` — `def ask_backlog(self, platform: str, count: int) -> None:
    text = f'Серия закончилась? Не опубликовано шортсов: {count} ({platform}).\nЕсли не ответить до слота — распределю остаток автоматически.'
    self.broadcast_markup(text, self._backlog_markup(platform))` — no method docstring
  - `remind_backlog` — `def remind_backlog(self, platform: str, count: int) -> None:
    text = f'⚠️ ВАЖНО: серия закончилась, остаток {count} шортсов ({platform}) не распределён. Отвечай!'
    self.broadcast_markup(text, self._backlog_markup(platform))` — no method docstring
  - `backlog_distributed` — `def backlog_distributed(self, platform: str, n: int) -> None:
    self.broadcast(f'Остаток распределён ({platform}): {n} шортсов поставлено в план.')` — no method docstring
  - `ask_claims` — `def ask_claims(self, entity_type: str, entity_id: int, external_id: str) -> None:
    """Notify about possible Content ID claim; A3 buttons."""
    text = f'⚠️ Возможный claim на YouTube\n{entity_type}#{entity_id} id={external_id}\nA3: удалить копию на платформе и взять следующее видео?'
    markup = {'inline_keyboard': [[{'text': 'A3: удалить + next', 'callback_data': f'claims_a3 {entity_type} {entity_id} youtube'}, {'text': 'Оставить', 'callback_data': f'claims_keep {entity_type} {entity_id}'}]]}
    self.broadcast_markup(text, markup)` — Notify about possible Content ID claim; A3 buttons.
- **function `setup_commands`** — `def setup_commands(bot: TelegramNotifier, components: dict) -> None:
    db: Database = components['db']
    cfg: AppConfig = components['cfg']
    safety = components['safety']
    scheduler = components['scheduler']
    clock: Clock = components['clock']

    def cmd_status(chat_id: int, arg: str) -> str:
        rows = db.fetchall('SELECT platform, status, COUNT(*) AS cnt FROM entity_platform_status GROUP BY platform, status')
        if not rows:
            return 'No entities'
        lines = [f"{r['platform']} {r['status']}: {r['cnt']}" for r in rows]
        return 'Status:\n' + '\n'.join(lines)

    def cmd_pause(chat_id: int, arg: str) -> str:
        for p in cfg.platforms:
            safety.pause_platform(p, 'manual')
        return 'All platforms paused'

    def cmd_resume(chat_id: int, arg: str) -> str:
        for p in cfg.platforms:
            safety.resume_platform(p)
        return 'All platforms resumed'

    def cmd_resume_platform(chat_id: int, arg: str) -> str:
        p = arg.strip().lower()
        if p not in cfg.platforms:
            return f'Unknown platform: {p}'
        safety.resume_platform(p)
        return f'Resumed {p}'
    WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

    def _upcoming_rows(limit: int=30) -> list[dict]:
        return db.fetchall("\n            SELECT eps.entity_type, eps.entity_id, eps.platform, eps.status,\n                   eps.scheduled_for AS scheduled_for,\n                   COALESCE(lv.title_text, lv.title, sh.title_text) AS title\n            FROM entity_platform_status eps\n            LEFT JOIN long_videos lv\n                   ON eps.entity_type='long_video' AND lv.id = eps.entity_id\n            LEFT JOIN shorts sh\n                   ON eps.entity_type='short' AND sh.id = eps.entity_id\n            WHERE eps.status IN ('ready', 'scheduled')\n              AND eps.scheduled_for IS NOT NULL\n            ORDER BY eps.scheduled_for LIMIT ?\n            ", (limit,))
    PLATFORM_ICONS = {'youtube': '▶️', 'telegram': '✈️', 'instagram': '📸', 'tiktok': '🎵', 'facebook': '📘', 'vk': '🅥'}
    MONTHS_GEN = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']

    def _item_lines(limit: int=30, max_groups: int=30) -> str:
        """Строки очереди: дни разделены, у платформ цветовые маркеры (HTML-разметка)."""
        import html as _html
        rows = _upcoming_rows(limit)
        grouped: dict[tuple, dict] = {}
        for r in rows:
            dt = None
            try:
                from datetime import UTC, datetime
                from zoneinfo import ZoneInfo
                dt = datetime.fromisoformat(str(r['scheduled_for']).replace('Z', '+00:00'))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                dt = dt.astimezone(ZoneInfo(cfg.timezone))
            except Exception:
                dt = None
            day = f'{WEEKDAYS[dt.weekday()]}, {dt.day} {MONTHS_GEN[dt.month - 1]}' if dt else '—'
            hhmm = dt.strftime('%H:%M') if dt else str(r['scheduled_for'] or '')[:16]
            key = (r['entity_type'], r['entity_id'], day, hhmm)
            kind = 'Фильм' if r['entity_type'] == 'long_video' else 'Шортс'
            title = (r.get('title') or '').strip() or f"#{r['entity_id']}"
            g = grouped.setdefault(key, {'day': day, 'time': hhmm, 'label': f'{kind}: {title}', 'plats': []})
            g['plats'].append(r['platform'])
        lines: list[str] = []
        last_day = None
        shown = 0
        for g in grouped.values():
            if shown >= max_groups:
                break
            if g['day'] != last_day:
                if last_day is not None:
                    lines.append('')
                lines.append(f"📅 <b>{g['day']}</b>")
                last_day = g['day']
            marks = ' '.join((f"{PLATFORM_ICONS.get(p, '▪️')}" for p in dict.fromkeys(g['plats'])))
            lines.append(f"{marks} <code>{g['time']}</code> · {_html.escape(g['label'])}")
            shown += 1
        return '\n'.join(lines)

    def cmd_queue(chat_id: int, arg: str) -> str:
        body = _item_lines(limit=30, max_groups=17)
        if not body:
            return 'Очередь пуста.'
        return HTML_PREFIX + 'Очередь публикаций:\n\n' + body

    def cmd_failed(chat_id: int, arg: str) -> str:
        rows = db.fetchall("\n            SELECT eps.entity_type, eps.entity_id, eps.platform, eps.last_error,\n                   COALESCE(lv.title_text, lv.title, sh.title_text) AS title\n            FROM entity_platform_status eps\n            LEFT JOIN long_videos lv\n                   ON eps.entity_type='long_video' AND lv.id = eps.entity_id\n            LEFT JOIN shorts sh\n                   ON eps.entity_type='short' AND sh.id = eps.entity_id\n            WHERE eps.status IN ('failed','error') LIMIT 20\n            ")
        if not rows:
            return 'Ошибок нет.'
        out = ['Ошибки публикаций:']
        for r in rows:
            kind = 'Фильм' if r['entity_type'] == 'long_video' else 'Шортс'
            title = (r.get('title') or '').strip() or f"#{r['entity_id']}"
            out.append(f"{kind}: {title} · {r['platform']} · {r['last_error'] or '—'}")
        return '\n'.join(out)

    def cmd_tail(chat_id: int, arg: str) -> str:
        rows = db.fetchall('SELECT platform, series_tail_mode FROM platform_queue_state')
        return '\n'.join((f"{r['platform']}: tail={('ON' if r['series_tail_mode'] else 'OFF')}" for r in rows))

    def cmd_platforms(chat_id: int, arg: str) -> str:
        lines = []
        for name, p in cfg.platforms.items():
            st = db.fetchone('SELECT is_paused, pause_reason FROM platform_safety_state WHERE platform=?', (name,))
            paused = 'PAUSED' if st and st['is_paused'] else 'ok'
            lines.append(f'{name}: enabled={p.enabled} limit={p.daily_limit} {paused}')
        return '\n'.join(lines)

    def cmd_distribute(chat_id: int, arg: str) -> str:
        _w = components.get('watcher')
        _roots = [str(r) for r in _w.effective_roots()] if _w is not None else []
        n = scheduler.schedule_long_videos(scope_roots=_roots)
        return f'Distributed long videos: {n}'

    def cmd_calendar(chat_id: int, arg: str) -> str:
        body = _item_lines(limit=60, max_groups=30)
        if not body:
            return 'Календарь пуст.'
        return HTML_PREFIX + 'Ближайшие публикации:\n\n' + body

    def cmd_series_end(chat_id: int, arg: str) -> str:
        p = arg.strip().lower() or 'youtube'
        bot._pending_dialogs[chat_id] = {'type': 'series_end', 'platform': p, 'expires': clock.now().timestamp() + 86400}
        return f'Enter tail mode for {p}? yes / no'

    def cmd_force_link_update(chat_id: int, arg: str) -> str:
        parts = arg.split()
        if len(parts) < 3:
            return 'Usage: /force_link_update <entity_id> <platform> <url> [short|long_video]'
        eid, platform, url = (int(parts[0]), parts[1], parts[2])
        etype = parts[3] if len(parts) > 3 else None
        link_upd = components.get('link_upd')
        if not link_upd:
            return 'LinkUpdater not available'
        ok = link_upd.force_update(eid, platform, url, scheduler=components.get('scheduler'), entity_type=etype)
        return 'OK' if ok else 'Failed'

    def cmd_reload_config(chat_id: int, arg: str) -> str:
        from .reload import apply_config_to_comps, reload_config
        path = arg.strip() or 'config.yaml'
        new_cfg, msg = reload_config(path, cfg)
        if new_cfg is None:
            return f'Reload failed (kept old): {msg}'
        updated = apply_config_to_comps(components, new_cfg)
        return f"Config reloaded → {', '.join(updated)}; restart if bind/TLS changed"

    def cmd_next_video(chat_id: int, arg: str) -> str:
        platform = arg.strip() or None
        sql = "SELECT entity_id, platform, scheduled_for AS scheduled_for FROM entity_platform_status WHERE entity_type='long_video' AND status='scheduled' "
        params: tuple = ()
        if platform:
            sql += 'AND platform=? '
            params = (platform,)
        sql += 'ORDER BY scheduled_for LIMIT 5'
        rows = db.fetchall(sql, params)
        if not rows:
            return 'No scheduled long videos'
        return '\n'.join((f"#{r['entity_id']} {r['platform']} {r['scheduled_for']}" for r in rows))

    def cmd_next_short(chat_id: int, arg: str) -> str:
        platform = arg.strip() or None
        sql = "SELECT entity_id, platform, scheduled_for AS scheduled_for FROM entity_platform_status WHERE entity_type='short' AND status='scheduled' "
        params: tuple = ()
        if platform:
            sql += 'AND platform=? '
            params = (platform,)
        sql += 'ORDER BY scheduled_for LIMIT 5'
        rows = db.fetchall(sql, params)
        if not rows:
            return 'No scheduled shorts'
        return '\n'.join((f"#{r['entity_id']} {r['platform']} {r['scheduled_for']}" for r in rows))

    def broadcast_markup(self, text: str, reply_markup: dict) -> None:
        targets = self.cfg.telegram.allowed_chat_ids or ([self._owner_chat_id] if self._owner_chat_id else [])
        for cid in targets:
            if not cid:
                continue
            if not self.is_allowed(cid):
                continue
            if self.transport:
                self.transport.send_message(cid, text, reply_markup)
            else:
                logger.info('[TG-markup -> %s] %s', cid, text[:200])

    def cmd_app(chat_id: int, arg: str) -> str:
        import os
        url = os.getenv('WEBAPP_PUBLIC_URL', '').rstrip('/')
        if not url:
            return 'Задайте WEBAPP_PUBLIC_URL (например https://host/webapp/)'
        return f'Откройте панель:\n{url}/\n\n(В BotFather: Menu Button → Web App → этот URL)'

    def cmd_backlog_distribute(chat_id: int, arg: str) -> str:
        m = components.get('backlog')
        if not m:
            return 'Менеджер остатка недоступен'
        p = (arg or '').strip() or next(iter(cfg.platforms), '')
        n = m.resolve(p, 'distribute')
        return f'Остаток распределён ({p}): {n}'

    def cmd_backlog_wait(chat_id: int, arg: str) -> str:
        m = components.get('backlog')
        p = (arg or '').strip() or next(iter(cfg.platforms), '')
        if m:
            m.resolve(p, 'wait')
        return f'Ждём новую серию ({p}).'

    def cmd_backlog_skip(chat_id: int, arg: str) -> str:
        m = components.get('backlog')
        p = (arg or '').strip() or next(iter(cfg.platforms), '')
        if m:
            m.resolve(p, 'skip')
        return f'Остаток не публикуем ({p}).'

    def cmd_claims_a3(chat_id: int, arg: str) -> str:
        parts = (arg or '').split()
        if len(parts) < 2:
            return 'usage: claims_a3 TYPE ID [platform]'
        et, eid = (parts[0], parts[1])
        plat = parts[2] if len(parts) > 2 else 'youtube'
        try:
            eid_i = int(eid)
        except ValueError:
            return 'bad entity_id'
        from .claims import resolve_claim_a3
        try:
            resolve_claim_a3(db, et, eid_i, plat)
        except Exception as e:
            return f'claims A3 failed: {e}'
        return f'A3 applied for {et}#{eid} on {plat}'

    def cmd_claims_keep(chat_id: int, arg: str) -> str:
        parts = (arg or '').split()
        if len(parts) < 2:
            return 'usage: claims_keep TYPE ID'
        et, eid = (parts[0], parts[1])
        try:
            eid_i = int(eid)
        except ValueError:
            return 'bad entity_id'
        db.execute("UPDATE entity_platform_status SET claims_state='kept' WHERE entity_type=? AND entity_id=? AND platform='youtube'", (et, eid_i))
        return f'claim kept for {et}#{eid}'

    def cmd_help(chat_id: int, arg: str) -> str:
        return 'Команды:\n/app — открыть панель\n/status — статус и счётчики\n/queue — очередь публикаций\n/calendar — календарь\n/failed — ошибки публикаций\n/platforms — платформы и лимиты\n/pause, /resume — пауза / возобновить всё\n/distribute — разложить по слотам\n/tail — остаток шортсов серии\n/claims_a3 TYPE ID — A3 delete+next (claim)\n/claims_keep TYPE ID — оставить при claim'
    bot.register('claims_a3', cmd_claims_a3)
    bot.register('claims_keep', cmd_claims_keep)
    bot.register('help', cmd_help)
    bot.register('backlog_distribute', cmd_backlog_distribute)
    bot.register('backlog_wait', cmd_backlog_wait)
    bot.register('backlog_skip', cmd_backlog_skip)
    bot.register('app', cmd_app)
    bot.register('status', cmd_status)
    bot.register('pause', cmd_pause)
    bot.register('resume', cmd_resume)
    bot.register('resume_platform', cmd_resume_platform)
    bot.register('queue', cmd_queue)
    bot.register('failed', cmd_failed)
    bot.register('tail', cmd_tail)
    bot.register('platforms', cmd_platforms)
    bot.register('distribute', cmd_distribute)
    bot.register('calendar', cmd_calendar)
    bot.register('series_end', cmd_series_end)
    bot.register('force_link_update', cmd_force_link_update)
    bot.register('reload_config', cmd_reload_config)
    bot.register('next_video', cmd_next_video)
    bot.register('next_short', cmd_next_short)` — no docstring
### `src/orchestrator/telegram_publish.py`
- **function `is_bot_post_id`** — `def is_bot_post_id(post_id: Any) -> bool:
    """Наш ли это пост (отправлен ботом), а не внешний/legacy."""
    return str(post_id or '').startswith(BOT_ID_PREFIX)` — Наш ли это пост (отправлен ботом), а не внешний/legacy.
- **function `message_id_of`** — `def message_id_of(post_id: Any) -> int | None:
    s = str(post_id or '')
    if not s.startswith(BOT_ID_PREFIX):
        return None
    try:
        return int(s[len(BOT_ID_PREFIX):])
    except ValueError:
        return None` — no docstring
- **class `TelegramPublisher`** — Минимальный клиент Bot API: sendMessage / deleteMessage / editMessageText.
  - `enabled` — `@property
def enabled(self) -> bool:
    return bool(self.token) and bool(self.chat_id)` — no method docstring
  - `send_photo` — `def send_photo(self, path: str | pathlib.Path, caption: str='') -> str:
    """Показать владельцу картинку (скриншот «до/после») — он хочет видеть, а не читать описание.

        Возвращает `tg:<message_id>`, как и `send_post`.
        """
    if not self.enabled:
        raise RuntimeError('Telegram Bot API не настроен: нет токена или chat_id')
    file = pathlib.Path(path)
    if not file.is_file():
        raise RuntimeError(f'нет файла для отправки: {file}')
    url = f'{API_BASE}/bot{self.token}/sendPhoto'
    data: dict[str, Any] = {'chat_id': str(self.chat_id)}
    text = (caption or '').strip()
    if text:
        data['caption'] = text[:1024]
        data['parse_mode'] = 'HTML'
    suffix = file.suffix.lower().lstrip('.') or 'png'
    mime = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'webp': 'image/webp'}.get(suffix, 'image/png')
    with file.open('rb') as fh, httpx.Client(timeout=self.timeout, transport=self._transport) as client:
        resp = client.post(url, data=data, files={'photo': (file.name, fh, mime)})
    try:
        res = self._parse('sendPhoto', resp)
    except RuntimeError as e:
        if 'parse entities' not in str(e):
            raise
        logger.warning('подпись к картинке не разобралась, шлю простым текстом: %s', e)
        data.pop('parse_mode', None)
        with file.open('rb') as fh, httpx.Client(timeout=self.timeout, transport=self._transport) as client:
            resp = client.post(url, data=data, files={'photo': (file.name, fh, mime)})
        res = self._parse('sendPhoto', resp)
    mid = res.get('message_id')
    if mid is None:
        raise RuntimeError('telegram sendPhoto: нет message_id в ответе')
    return f'{BOT_ID_PREFIX}{mid}'` — Показать владельцу картинку (скриншот «до/после») — он хочет видеть, а не читать описание. Возвращает `tg:<message_id>`, как и `send_post`.
  - `send_post` — `def send_post(self, text: str, *, buttons: list[dict[str, str]] | None=None, preview_url: str | None=None) -> str:
    """Отправить пост. Возвращает id в нашем формате (`tg:<message_id>`)."""
    body = (text or '').strip()
    if len(body) > MAX_TEXT:
        body = body[:MAX_TEXT - 1].rstrip() + '…'
    preview: dict[str, Any] = {'show_above_text': self.show_above, 'prefer_large_media': self.prefer_large}
    if preview_url:
        preview['url'] = preview_url
    payload: dict[str, Any] = {'chat_id': self.chat_id, 'text': body, 'parse_mode': 'HTML', 'link_preview_options': preview}
    if buttons:
        payload['reply_markup'] = {'inline_keyboard': [buttons]}
    try:
        res = self._call('sendMessage', payload)
    except RuntimeError as e:
        if 'parse entities' not in str(e):
            raise
        logger.warning('telegram HTML не разобрался, отправляю простым текстом: %s', e)
        payload.pop('parse_mode', None)
        res = self._call('sendMessage', payload)
    mid = res.get('message_id')
    if mid is None:
        raise RuntimeError('telegram sendMessage: нет message_id в ответе')
    return f'{BOT_ID_PREFIX}{mid}'` — Отправить пост. Возвращает id в нашем формате (`tg:<message_id>`).
  - `send_chat_action` — `def send_chat_action(self, action: str='typing') -> bool:
    """Показать владельцу, что бот работает: «печатает…» в шапке чата.

        У ботов нет «прочитано», зато есть sendChatAction — индикатор держится ~5 секунд,
        поэтому для долгой работы его повторяют (см. tools/tg_say.py --typing-for).
        """
    try:
        self._call('sendChatAction', {'chat_id': self.chat_id, 'action': action})
        return True
    except Exception:
        logger.warning('telegram sendChatAction не сработал', exc_info=True)
        return False` — Показать владельцу, что бот работает: «печатает…» в шапке чата. У ботов нет «прочитано», зато есть sendChatAction — индикатор держится ~5 секунд, поэтому для долгой работы его повторяют (см. tools/tg_say.py --typing-for).
  - `delete_post` — `def delete_post(self, post_id: str) -> None:
    mid = message_id_of(post_id)
    if mid is None:
        return
    try:
        self._call('deleteMessage', {'chat_id': self.chat_id, 'message_id': mid})
    except RuntimeError as e:
        logger.warning('telegram deleteMessage %s: %s', mid, e)` — no method docstring
- **function `create_telegram_publisher`** — `def create_telegram_publisher(cfg: Any) -> TelegramPublisher | None:
    """Собрать издателя, если send_via=bot (иначе None — module/engine path).

    Токен берём из окружения (`TELEGRAM_BOT_TOKEN`), как и остальной код бота.
    """
    import os
    tcfg = getattr(cfg, 'platforms', {}).get('telegram')
    if not tcfg or not getattr(tcfg, 'enabled', True):
        return None
    if str(getattr(tcfg, 'send_via', 'bot') or 'bot').lower() != 'bot':
        return None
    token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    chat_id = getattr(tcfg, 'publish_chat_id', '') or ''
    if not token or not chat_id:
        logger.warning('telegram.send_via=bot, но нет TELEGRAM_BOT_TOKEN или platforms.telegram.publish_chat_id — bot path disabled')
        return None
    return TelegramPublisher(token, chat_id, show_above=bool(getattr(tcfg, 'link_preview_above', True)))` — Собрать издателя, если send_via=bot (иначе None — module/engine path). Токен берём из окружения (`TELEGRAM_BOT_TOKEN`), как и остальной код бота.
### `src/orchestrator/telegram_transport.py`
- **function `split_text`** — `def split_text(text: str, limit: int=3800) -> list[str]:
    """Разбивает длинный текст по строкам на части (лимит Telegram 4096)."""
    text = text or ''
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    cur = ''
    for line in text.splitlines():
        while len(line) > limit:
            if cur:
                parts.append(cur)
                cur = ''
            parts.append(line[:limit])
            line = line[limit:]
        if len(cur) + len(line) + 1 > limit:
            parts.append(cur)
            cur = line
        else:
            cur = cur + '\n' + line if cur else line
    if cur:
        parts.append(cur)
    return parts` — Разбивает длинный текст по строкам на части (лимит Telegram 4096).
- **class `TelegramTransport`** — Long-poll + optional webhook-style local push. Heavy handlers run on worker queue.
  - `enabled` — `@property
def enabled(self) -> bool:
    return bool(self.token) and self.mode != 'off'` — no method docstring
  - `set_reaction` — `def set_reaction(self, chat_id: int, message_id: int | None, emoji: str) -> bool:
    """Поставить реакцию на сообщение.

        У ботов в Telegram нет «прочитано» — галочка у владельца означает только доставку.
        Реакция на его сообщение и есть честный признак, что бот его получил/разобрал.
        """
    if not self.token or not message_id:
        return False
    try:
        r = httpx.post(f'{self._base}/setMessageReaction', json={'chat_id': chat_id, 'message_id': int(message_id), 'reaction': [{'type': 'emoji', 'emoji': emoji}]}, timeout=15)
        try:
            ok = bool(r.json().get('ok'))
        except Exception:
            ok = False
        if not ok:
            logger.info('setMessageReaction not ok: %s %s', r.status_code, r.text[:160])
        return ok
    except Exception:
        logger.warning('setMessageReaction failed', exc_info=True)
        return False` — Поставить реакцию на сообщение. У ботов в Telegram нет «прочитано» — галочка у владельца означает только доставку. Реакция на его сообщение и есть честный признак, что бот его получил/разобрал.
  - `send_message` — `def send_message(self, chat_id: int, text: str, reply_markup: dict | None=None) -> None:
    if not self.token:
        logger.info('[TG-mock -> %s] %s', chat_id, (text or '')[:200])
        return
    parse_mode = None
    if text and text.startswith(HTML_PREFIX):
        parse_mode = 'HTML'
        text = text[len(HTML_PREFIX):]
    chunks = split_text(text or '')
    for i, chunk in enumerate(chunks):
        payload: dict = {'chat_id': chat_id, 'text': chunk}
        if parse_mode:
            payload['parse_mode'] = parse_mode
        if reply_markup and i == len(chunks) - 1:
            payload['reply_markup'] = reply_markup
        try:
            r = httpx.post(f'{self._base}/sendMessage', json=payload, timeout=30)
            ok = False
            try:
                ok = bool(r.json().get('ok'))
            except Exception:
                ok = False
            if r.status_code == 429 and i == len(chunks) - 1:
                try:
                    wait = float(r.json().get('parameters', {}).get('retry_after') or 3)
                except Exception:
                    wait = 3
                import time as _t
                _t.sleep(max(1.0, min(60.0, wait)))
                r2 = httpx.post(f'{self._base}/sendMessage', json=payload, timeout=30)
                try:
                    ok = bool(r2.json().get('ok'))
                except Exception:
                    ok = False
            if not ok:
                logger.warning('sendMessage not ok: status=%s body=%s', r.status_code, r.text[:200])
        except Exception:
            logger.exception('sendMessage failed')` — no method docstring
  - `start` — `def start(self) -> None:
    if not self.enabled or self._poll_thread:
        return
    self._stop = False
    self._worker_thread = threading.Thread(target=self._worker, name='tg-worker', daemon=True)
    self._worker_thread.start()
    self._poll_thread = threading.Thread(target=self._loop, name='tg-poll', daemon=True)
    self._poll_thread.start()
    logger.info('Telegram transport started (mode=%s)', self.mode)` — no method docstring
  - `stop` — `def stop(self) -> None:
    self._stop = True
    self._q.put(None)
    for th in (self._poll_thread, self._worker_thread):
        if th:
            th.join(timeout=5)
    self._poll_thread = None
    self._worker_thread = None` — no method docstring
  - `push_update` — `def push_update(self, chat_id: int, text: str) -> None:
    """For tests / webhook adapter."""
    self._q.put((chat_id, text))` — For tests / webhook adapter.
  - `recover_voices` — `def recover_voices(self, directory: str | None=None) -> int:
    """Расшифровать голосовые, оставшиеся без текста (например, после перезапуска службы)."""
    if not voice_stt.enabled() or not voice_stt.available():
        return 0
    started = 0
    for rec in tg_inbox.read_messages(directory):
        path = rec.get('voice_file')
        text = str(rec.get('text') or '')
        if path and 'не расшифрован' in text and (not rec.get('voice_text')):
            self._transcribe_later(rec.get('message_id'), path)
            started += 1
    if started:
        logger.info('voice stt recovery started for %d message(s)', started)
    return started` — Расшифровать голосовые, оставшиеся без текста (например, после перезапуска службы).
### `src/orchestrator/test_publish.py`
- **class `TestPublishError`** — Ошибка тестового поста (валидация/лимиты) — с кодом ответа для API.
- **function `schedule_test_post`** — `def schedule_test_post(comps: dict[str, Any], *, platform: str, entity_type: str, entity_id: int, delay_minutes: int | None=None, scheduled_for: str | None=None, dry_run: bool=False) -> dict[str, Any]:
    """Создать пробный пост в platform через ~N минут, не трогая боевую очередь."""
    cfg = comps['cfg']
    db = comps['db']
    clock = comps['clock']
    tcfg = cfg.test_publish
    if not tcfg.enabled:
        raise TestPublishError('test_publish disabled', 403)
    pcfg = cfg.platforms.get(platform)
    if not pcfg or not getattr(pcfg, 'enabled', False):
        raise TestPublishError(f'platform {platform} is not enabled', 400)
    if tcfg.require_explicit_platforms and platform not in (tcfg.platforms or []):
        raise TestPublishError(f'platform {platform} not in test allowlist', 403)
    iid = getattr(pcfg, 'account_id', '') or getattr(pcfg, 'integration_id', '') or ''
    if not tcfg.allow_prod_channel:
        prod_ids = list(getattr(tcfg, 'prod_account_ids', None) or getattr(tcfg, 'prod_integration_ids', None) or [])
        if iid and iid in prod_ids:
            raise TestPublishError('prod channel is not allowed for test posts', 403)
        test_ids = list(getattr(tcfg, 'test_account_ids', None) or getattr(tcfg, 'test_integration_ids', None) or [])
        if not test_ids:
            raise TestPublishError('test_account_ids not configured (fail-closed)', 403)
        if iid not in test_ids:
            raise TestPublishError(f"integration {iid or '<empty>'} not in test allowlist", 403)
    now = clock.now()
    if scheduled_for:
        try:
            when = datetime.fromisoformat(str(scheduled_for).replace('Z', '+00:00'))
        except Exception as e:
            raise TestPublishError(f'bad scheduled_for: {e}', 400) from e
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        if when <= now:
            raise TestPublishError('scheduled_for must be in the future', 400)
    else:
        delay = int(delay_minutes if delay_minutes is not None else tcfg.default_delay_minutes)
        if delay < int(tcfg.min_delay_minutes) or delay > int(tcfg.max_delay_minutes):
            raise TestPublishError(f'delay_minutes must be within [{tcfg.min_delay_minutes}, {tcfg.max_delay_minutes}]', 400)
        when = now + timedelta(minutes=delay)
    row = _resolve_entity(db, entity_type, entity_id)
    title = f"{tcfg.title_prefix}{row.get('title_text') or row.get('title') or entity_id}"
    desc = (row.get('description_text') or '').strip()
    media = None
    if getattr(pcfg, 'post_mode', 'media') == 'link':
        url = _youtube_url(db, entity_type, entity_id)
        if not url:
            raise TestPublishError('link-режим: нет YouTube-ссылки у сущности (сначала опубликуйте видео)', 400)
        desc = f'{title}\n\n▶ Полное видео: {url}'
    else:
        media = _pick_media(row, platform, pcfg)
        if not media:
            raise TestPublishError('no media for entity/platform', 400)
        if platform == 'telegram':
            import os as _os
            try:
                size_mb = _os.path.getsize(media) / (1024 * 1024)
            except OSError:
                size_mb = 0
            if size_mb > 45:
                raise TestPublishError(f'telegram: файл {size_mb:.0f} МБ > 45 МБ (лимит Bot API) — укажите ссылку (post_mode=link) или меньшее видео', 400)
        desc = f'{title}\n\n{desc}'.strip() if desc else title
    content: dict[str, Any] = {'title': title, 'description': desc, 'hashtags': row.get('hashtags_text') or '', 'cover': row.get('cover_path') or '', 'integration_id': iid}
    safety = comps.get('safety')
    if safety is not None:
        if getattr(tcfg, 'ignore_limits', True):
            try:
                if safety.is_platform_paused(platform):
                    raise TestPublishError('safety: platform_paused', 409)
            except AttributeError:
                pass
        else:
            ok, reason = safety.can_schedule(platform, when, pcfg.daily_limit)
            if not ok:
                raise TestPublishError(f'safety: {reason}', 409)
    if dry_run:
        db.log(entity_type, entity_id, platform, 'test_dry_run', f'would schedule {when.isoformat()}')
        return {'ok': True, 'dry_run': True, 'platform': platform, 'entity_type': entity_type, 'entity_id': entity_id, 'scheduled_for': when.isoformat(), 'media': media}
    external_id = _module_publish_test(comps, platform=platform, media=media, content=content, scheduled_for=when)
    db.log(entity_type, entity_id, platform, 'test_scheduled', f'{external_id} @ {when.isoformat()}')
    _metric(comps, 'test_scheduled')
    logger.info('test post scheduled: %s/%s %s -> %s @ %s', entity_type, entity_id, platform, external_id, when.isoformat())
    return {'ok': True, 'dry_run': False, 'platform': platform, 'entity_type': entity_type, 'entity_id': entity_id, 'external_id': external_id, 'scheduled_for': when.isoformat()}` — Создать пробный пост в platform через ~N минут, не трогая боевую очередь.
- **function `cleanup_expired_test_posts`** — `def cleanup_expired_test_posts(comps: dict[str, Any]) -> int:
    """Remove expired test posts via module.delete when available; always log cancel."""
    db = comps['db']
    tcfg = comps['cfg'].test_publish
    ttl = int(getattr(tcfg, 'cleanup_after_hours', 0) or 0)
    if ttl <= 0:
        return 0
    from datetime import UTC as _UTC
    active: dict[str, tuple[str, str]] = {}
    for r in db.fetchall("SELECT details, created_at, platform FROM publish_log WHERE action='test_scheduled'"):
        pid = (r['details'] or '').strip().split(' ', 1)[0]
        if pid:
            active[pid] = (r['created_at'] or '', r.get('platform') or '')
    for r in db.fetchall("SELECT details FROM publish_log WHERE action IN ('test_cancelled', 'test_auto_cancelled')"):
        active.pop((r['details'] or '').strip(), None)
    now = comps['clock'].now()
    n = 0
    for pid, (created, platform) in active.items():
        try:
            ts = datetime.fromisoformat(created)
        except Exception:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=_UTC)
        if (now - ts).total_seconds() < ttl * 3600:
            continue
        _module_delete(comps, pid, platform)
        db.log('system', None, platform or '', 'test_auto_cancelled', pid)
        n += 1
    if n:
        logger.info('Test auto-cleanup: removed %s expired test post(s)', n)
    return n` — Remove expired test posts via module.delete when available; always log cancel.
- **function `test_recent`** — `def test_recent(db, limit: int=10) -> list[dict]:
    """Последние пробные посты из publish_log (кроме dry-run)."""
    rows = db.fetchall("SELECT entity_type, entity_id, platform, details, created_at FROM publish_log WHERE action='test_scheduled' ORDER BY id DESC LIMIT ?", (limit,))
    return [dict(r) for r in rows]` — Последние пробные посты из publish_log (кроме dry-run).
- **function `cancel_test_post`** — `def cancel_test_post(comps: dict[str, Any], external_id: str | None=None, *, legacy_post_id: str | None=None) -> dict[str, Any]:
    """Delete test post via module (legacy alias: legacy_post_id → external_id)."""
    db = comps['db']
    pid = (external_id or legacy_post_id or '').strip()
    if not pid:
        raise TestPublishError('external_id required', 400)
    marked = False
    platform = ''
    for r in db.fetchall("SELECT details, platform FROM publish_log WHERE action='test_scheduled'"):
        token = (r['details'] or '').strip().split(' ', 1)[0]
        if token and token == pid:
            marked = True
            platform = r.get('platform') or ''
            break
    if not marked:
        raise TestPublishError('post is not a test post', 404)
    _module_delete(comps, pid, platform)
    db.log('system', None, platform or '', 'test_cancelled', pid)
    _metric(comps, 'test_cancelled')
    return {'ok': True, 'deleted': pid, 'external_id': pid}` — Delete test post via module (legacy alias: legacy_post_id → external_id).
### `src/orchestrator/tg_inbox.py`
- **function `inbox_dir`** — `def inbox_dir(directory: str | Path | None=None) -> Path:
    if directory is not None:
        return Path(directory)
    env = os.getenv('TG_INBOX_DIR', '').strip()
    return Path(env) if env else Path('data') / 'tg_inbox'` — no docstring
- **function `inbox_file`** — `def inbox_file(directory: str | Path | None=None) -> Path:
    return inbox_dir(directory) / 'inbox.jsonl'` — no docstring
- **function `seen_file`** — `def seen_file(directory: str | Path | None=None) -> Path:
    """Файл со списком обработанных номеров сообщений (не «максимум»!).

    Раньше здесь лежало одно число — максимальный обработанный номер, и любое
    сообщение с меньшим номером считалось прочитанным. Из-за этого случайный
    большой номер (например, тестовый) «съедал» реальные сообщения владельца.
    """
    return inbox_dir(directory) / 'seen_ids.json'` — Файл со списком обработанных номеров сообщений (не «максимум»!). Раньше здесь лежало одно число — максимальный обработанный номер, и любое сообщение с меньшим номером считалось прочитанным. Из-за этого случайный большой номер (например, тестовый) «съедал» реальные сообщения владельца.
- **function `append_message`** — `def append_message(chat_id: int | None, message_id: int | None, text: str, *, directory: str | Path | None=None, ts: float | None=None, kind: str='message', extra: dict | None=None) -> Path | None:
    """Дописать входящее. Никогда не бросает: приём сообщений важнее учёта."""
    try:
        d = inbox_dir(directory)
        d.mkdir(parents=True, exist_ok=True)
        path = inbox_file(d)
        if path.exists() and path.stat().st_size > MAX_BYTES:
            path.replace(path.with_name(path.name + '.1'))
        rec = {'ts': ts if ts is not None else time.time(), 'chat_id': chat_id, 'message_id': message_id, 'text': text, 'kind': kind}
        if extra:
            rec.update(extra)
        with path.open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
        return path
    except Exception:
        logger.warning('cannot write telegram inbox', exc_info=True)
        return None` — Дописать входящее. Никогда не бросает: приём сообщений важнее учёта.
- **function `annotate_text`** — `def annotate_text(message_id: int | None, text: str, directory: str | Path | None=None) -> bool:
    """Дописать текст (расшифровку голосового) в уже сохранённую запись.

    Файл маленький, поэтому перезапись целиком: зато запись остаётся одна и её
    так же отмечают прочитанной по номеру сообщения.
    """
    mid = _as_int(message_id)
    if not mid or not text:
        return False
    path = inbox_file(directory)
    if not path.exists():
        return False
    recs = read_messages(directory)
    changed = False
    for rec in recs:
        if _as_int(rec.get('message_id')) != mid:
            continue
        if str(rec.get('voice_text') or '').strip() == text.strip():
            continue
        marker = str(rec.get('text', ''))
        marker = marker.split(' Повтор')[0] if ' Повтор' in marker else marker
        for old_text in (rec.get('voice_text'),):
            if old_text:
                marker = marker.replace(str(old_text), '').strip()
        rec['text'] = f'{marker} {text}'.strip() if marker else text
        rec['voice_text'] = text
        rec['kind'] = 'voice_text'
        changed = True
    if not changed:
        return False
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text('\n'.join((json.dumps(r, ensure_ascii=False) for r in recs)) + '\n', encoding='utf-8')
    tmp.replace(path)
    return True` — Дописать текст (расшифровку голосового) в уже сохранённую запись. Файл маленький, поэтому перезапись целиком: зато запись остаётся одна и её так же отмечают прочитанной по номеру сообщения.
- **function `read_messages`** — `def read_messages(directory: str | Path | None=None) -> list[dict]:
    """Все записи, от старых к новым. Битые строки пропускаются."""
    path = inbox_file(directory)
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out` — Все записи, от старых к новым. Битые строки пропускаются.
- **function `seen_ids`** — `def seen_ids(directory: str | Path | None=None) -> set[int]:
    """Номера сообщений, которые уже обработаны."""
    try:
        data = json.loads(seen_file(directory).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return set()
    if not isinstance(data, list):
        return set()
    return {_as_int(x) for x in data if _as_int(x)}` — Номера сообщений, которые уже обработаны.
- **function `last_seen`** — `def last_seen(directory: str | Path | None=None) -> int:
    """Наибольший обработанный номер (0 — ничего не обработано). Только для справки."""
    ids = seen_ids(directory)
    return max(ids) if ids else 0` — Наибольший обработанный номер (0 — ничего не обработано). Только для справки.
- **function `mark_seen`** — `def mark_seen(message_id: int | None, directory: str | Path | None=None) -> int:
    """Отметить сообщение обработанным. Прочитанным становится ровно оно, не «всё до него»."""
    mid = _as_int(message_id)
    ids = seen_ids(directory)
    if mid:
        ids.add(mid)
    d = inbox_dir(directory)
    d.mkdir(parents=True, exist_ok=True)
    seen_file(d).write_text(json.dumps(sorted(ids)[-5000:]), encoding='utf-8')
    return mid` — Отметить сообщение обработанным. Прочитанным становится ровно оно, не «всё до него».
- **function `unread`** — `def unread(directory: str | Path | None=None, *, after: int | None=None) -> list[dict]:
    """Непрочитанные, от старых к новым.

    `after` — не показывать записи с номером не больше указанного (для точечных проверок).
    Записи без номера сообщения не возвращаются: их нельзя отметить.
    """
    ids = seen_ids(directory)
    skip_upto = _as_int(after)
    out: list[dict] = []
    for rec in read_messages(directory):
        mid = _as_int(rec.get('message_id'))
        if not mid or mid in ids:
            continue
        if skip_upto and mid <= skip_upto:
            continue
        out.append(rec)
    return out` — Непрочитанные, от старых к новым. `after` — не показывать записи с номером не больше указанного (для точечных проверок). Записи без номера сообщения не возвращаются: их нельзя отметить.
- **function `wait_for_new`** — `def wait_for_new(directory: str | Path | None=None, *, timeout: float=0.0, poll: float=2.0, after: int | None=None) -> dict | None:
    """Ждать сообщение новее отметки. `timeout=0` — ждать бесконечно."""
    deadline = None if timeout <= 0 else time.monotonic() + timeout
    while True:
        items = unread(directory, after=after)
        if items:
            return items[0]
        if deadline is not None and time.monotonic() >= deadline:
            return None
        time.sleep(poll)` — Ждать сообщение новее отметки. `timeout=0` — ждать бесконечно.
### `src/orchestrator/token_lifecycle.py`
- **class `TokenRecord`** — no class docstring
  - `usable` — `def usable(self, *, now: float | None=None) -> bool:
    if self.revoked or self.quarantined or (not self.access_token):
        return False
    now = time.time() if now is None else float(now)
    return self.expires_at is None or self.expires_at > now + 30` — no method docstring
- **class `TokenLifecycleStore`** — Account-scoped token persistence and lifecycle state.
  - `path` — `def path(self, platform: str, account_id: str) -> Path:
    if not account_id:
        raise ValueError('account_id is required for lifecycle storage')
    return self.root / f'{platform.strip().lower()}__{account_id}.json'` — no method docstring
  - `load` — `def load(self, platform: str, account_id: str) -> TokenRecord | None:
    p = self.path(platform, account_id)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
        rec = TokenRecord(platform=platform.strip().lower(), account_id=account_id, access_token=str(data.get('access_token') or data.get('token') or ''), refresh_token=str(data.get('refresh_token') or ''), expires_at=float(data['expires_at']) if data.get('expires_at') is not None else None, revoked=bool(data.get('revoked', False)), quarantined=bool(data.get('quarantined', False)), version=int(data.get('version') or 1), metadata=dict(data.get('metadata') or {}))
        return rec
    except Exception:
        return None` — no method docstring
  - `save` — `def save(self, rec: TokenRecord) -> None:
    p = self.path(rec.platform, rec.account_id)
    payload = {'version': int(rec.version), 'access_token': rec.access_token, 'refresh_token': rec.refresh_token, 'expires_at': rec.expires_at, 'revoked': bool(rec.revoked), 'quarantined': bool(rec.quarantined), 'metadata': rec.metadata or {}, 'updated_at': time.time()}
    fd, tmp = tempfile.mkstemp(prefix=f'.{p.name}.', dir=str(p.parent))
    try:
        os.fchmod(fd, 384)
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, ensure_ascii=False, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, p)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    self._sync_account(rec)` — no method docstring
  - `rotate` — `def rotate(self, platform: str, account_id: str, *, access_token: str, refresh_token: str='', expires_at: float | None=None, metadata: dict[str, Any] | None=None) -> TokenRecord:
    old = self.load(platform, account_id)
    rec = TokenRecord(platform=platform.strip().lower(), account_id=account_id, access_token=access_token, refresh_token=refresh_token, expires_at=expires_at, revoked=False, quarantined=False, version=old.version + 1 if old else 1, metadata=metadata or (old.metadata if old else {}))
    self.save(rec)
    return rec` — no method docstring
  - `revoke` — `def revoke(self, platform: str, account_id: str, *, reason: str='revoked') -> bool:
    rec = self.load(platform, account_id)
    if rec is None:
        return False
    rec.revoked = True
    rec.quarantined = False
    rec.metadata = {**(rec.metadata or {}), 'revoke_reason': reason, 'revoked_at': time.time()}
    self.save(rec)
    return True` — no method docstring
  - `quarantine` — `def quarantine(self, platform: str, account_id: str, *, reason: str='quarantined') -> bool:
    rec = self.load(platform, account_id)
    if rec is None:
        return False
    rec.quarantined = True
    rec.metadata = {**(rec.metadata or {}), 'quarantine_reason': reason, 'quarantined_at': time.time()}
    self.save(rec)
    return True` — no method docstring
### `src/orchestrator/voice_stt.py`
- **function `prepare_audio`** — `def prepare_audio(path: str | Path) -> Path:
    """Нормализовать звук через ffmpeg. Если ffmpeg нет — вернуть исходный файл."""
    audio = Path(path)
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg or not audio.is_file():
        return audio
    out = Path(tempfile.gettempdir()) / f'stt_{audio.stem}_norm.wav'
    cmd = [ffmpeg, '-y', '-v', 'error', '-i', str(audio), '-af', AUDIO_FILTER, '-ar', '16000', '-ac', '1', str(out)]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=120, check=False)
    except (OSError, subprocess.SubprocessError):
        return audio
    return out if r.returncode == 0 and out.exists() else audio` — Нормализовать звук через ffmpeg. Если ffmpeg нет — вернуть исходный файл.
- **function `enabled`** — `def enabled() -> bool:
    return bool(os.getenv('TG_VOICE_STT', '').strip())` — no docstring
- **function `python_path`** — `def python_path() -> str:
    return os.getenv('TG_VOICE_STT_PYTHON', '').strip() or DEFAULT_PYTHON` — no docstring
- **function `model_name`** — `def model_name() -> str:
    return os.getenv('TG_VOICE_STT_MODEL', '').strip() or DEFAULT_MODEL` — no docstring
- **function `available`** — `def available() -> bool:
    """Есть ли чем распознавать: интерпретатор и faster_whisper на месте."""
    py = python_path()
    if not Path(py).exists():
        return False
    try:
        r = subprocess.run([py, '-c', 'import faster_whisper'], capture_output=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0` — Есть ли чем распознавать: интерпретатор и faster_whisper на месте.
- **function `transcribe_file`** — `def transcribe_file(path: str | Path, *, language: str='ru') -> str | None:
    """Текст из аудиофайла. None — если не получилось (причина в журнале)."""
    audio = Path(path)
    if not audio.is_file():
        return None
    py = python_path()
    timeout = int(os.getenv('TG_VOICE_STT_TIMEOUT', '') or DEFAULT_TIMEOUT)
    cmd = [py, '-c', CHILD, model_name(), str(prepare_audio(audio)), language]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError) as e:
        logger.warning('voice stt failed (%s): %s', py, e)
        return None
    if r.returncode != 0:
        logger.warning('voice stt exit %s: %s', r.returncode, (r.stderr or '')[-300:])
        return None
    text = (r.stdout or '').strip()
    logger.info('voice stt (%s/%s): %s', Path(py).name, model_name(), shlex.quote(text[:120]))
    return text or None` — Текст из аудиофайла. None — если не получилось (причина в журнале).
### `src/orchestrator/watcher.py`
- **function `natural_key`** — `def natural_key(name: str) -> tuple:
    """Ключ сортировки с числами: «ш1 < ш2 < … < ш10» (а не «ш1 < ш10 < ш2»).

    Пробелы и регистр не влияют: «Ш 19 …», «ш1 …», «ш10…» → 1, 2, 10…
    """
    flat = re.sub('\\s+', '', name).lower()
    return tuple(((1, int(part)) if part.isdigit() else (0, part) for part in re.split('(\\d+)', flat) if part))` — Ключ сортировки с числами: «ш1 < ш2 < … < ш10» (а не «ш1 < ш10 < ш2»). Пробелы и регистр не влияют: «Ш 19 …», «ш1 …», «ш10…» → 1, 2, 10…
- **class `Watcher`** — no class docstring
  - `effective_root_specs` — `def effective_root_specs(self) -> list[dict[str, str]]:
    """Корни с типами: [{"path": ..., "kind": auto|series|shorts}] (legacy-строки → auto)."""
    raw = self.db.get_setting(WATCH_ROOTS_KEY)
    specs: list[dict[str, str]] = []
    if raw:
        try:
            items = json.loads(raw)
        except Exception:
            items = None
            logger.warning('Invalid %s setting', WATCH_ROOTS_KEY)
        if isinstance(items, list):
            for x in items:
                if isinstance(x, dict):
                    path = str(x.get('path') or '').strip()
                    kind = str(x.get('kind') or 'auto').strip().lower()
                    if path:
                        specs.append({'path': path, 'kind': kind if kind in ('auto', 'series', 'shorts') else 'auto'})
                elif isinstance(x, (str, Path)):
                    specs.append({'path': str(x), 'kind': 'auto'})
    if specs:
        return specs
    return [{'path': str(r), 'kind': 'auto'} for r in self.roots]` — Корни с типами: [{"path": ..., "kind": auto|series|shorts}] (legacy-строки → auto).
  - `effective_roots` — `def effective_roots(self) -> list[Path]:
    """Roots configured via webapp (DB) take precedence over CLI defaults."""
    out: list[Path] = []
    for spec in self.effective_root_specs():
        try:
            out.append(Path(spec['path']).resolve())
        except OSError:
            logger.warning('watch root недоступен: %s', spec.get('path'))
            out.append(Path(spec['path']))
    return out` — Roots configured via webapp (DB) take precedence over CLI defaults.
  - `scan` — `def scan(self) -> dict[str, int]:
    self._scan_seq += 1
    stats = {'long': 0, 'shorts': 0, 'standalone': 0, 'standalone_found': 0, 'checked': 0, 'unstable': 0}
    max_depth = getattr(self.cfg, 'watch_max_depth', 5)
    for spec in self.effective_root_specs():
        root = Path(spec['path'])
        mode = spec.get('kind', 'auto')
        if not root.exists():
            continue
        if root.name.lower().startswith('shortsmaker') or (root / '.shortsmaker').exists():
            if mode != 'series':
                n, found_n = self._scan_standalone_root(root)
                stats['standalone'] += n
                stats['standalone_found'] += found_n
            continue
        self._walk(root, 0, max_depth, stats, mode)
        if mode != 'series':
            self._renumber_standalone(root)
    linked = self._link_orphan_shorts()
    if linked:
        logger.info('Linked orphan shorts to series: %s', linked)
    filled = self._backfill_descriptions()
    if filled:
        logger.info('Backfilled descriptions: %s', filled)
    return stats` — no method docstring
### `src/orchestrator/webapp_api.py`
- **function `validate_init_data`** — `def validate_init_data(init_data: str, bot_token: str) -> dict[str, Any] | None:
    """Validate Telegram WebApp initData. Returns parsed dict or None."""
    if init_data == 'dev' and os.getenv('WEBAPP_DEV', '').lower() in ('1', 'true', 'yes'):
        return {'user': {'id': 0, 'first_name': 'Dev'}, 'dev': True}
    if not init_data or not bot_token:
        return None
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed.pop('hash', None)
        if not received_hash:
            return None
        check = '\n'.join((f'{k}={v}' for k, v in sorted(parsed.items())))
        secret = hmac.new(b'WebAppData', bot_token.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, received_hash):
            return None
        try:
            max_age = int(os.getenv('ORCH_WEBAPP_INIT_MAX_AGE_SEC', '86400'))
        except ValueError:
            max_age = 86400
        if max_age > 0:
            raw_date = str(parsed.get('auth_date') or '').strip()
            if not raw_date.isdigit():
                return None
            age = time.time() - int(raw_date)
            if age > max_age or age < -300:
                logger.warning('initData stale: age=%.0fs > %ss', age, max_age)
                return None
        if 'user' in parsed:
            parsed['user'] = json.loads(parsed['user'])
        return parsed
    except Exception:
        logger.exception('initData validation failed')
        return None` — Validate Telegram WebApp initData. Returns parsed dict or None.
- **class `WebAppAPI`** — no class docstring
  - `handle` — `def handle(self, method: str, path: str, headers: dict, body: bytes) -> tuple[int, dict | bytes, str]:
    """Return (status, payload, content_type)."""
    split = urlsplit(path)
    qpath = split.path
    query = dict(parse_qsl(split.query))
    _lang = str(query.get('lang') or 'ru').lower()
    self._tls.lang = _lang if _lang in ('ru', 'en') else 'ru'
    _safe_path = re.sub('(key=)[^&\\s]+', '\\1***', path)
    _safe_path = re.sub('(/webapp/k/)[^/\\s]+', '\\1***', _safe_path)
    logger.info('WEBAPP_REQ %s %s ua=%s ip=%s', method, _safe_path, (headers.get('User-Agent') or headers.get('user-agent') or '')[:70], headers.get('X-Forwarded-For') or headers.get('x-forwarded-for') or '')
    is_api = qpath.startswith('/webapp/api/')
    if is_api and len(body or b'') > 50 * 1024 * 1024:
        return (413, {'error': 'request body too large (max 50MB)'}, 'application/json')
    if not is_api:
        if method == 'GET' and qpath == '/webapp/diag':
            logger.warning('WEBAPP_DIAG href=%s tg=%s key=%s', re.sub('(key=)[^&\\s]+', '\\1***', str(query.get('u') or '')), query.get('tg'), query.get('k'))
            return (204, b'', 'text/plain')
        if method == 'GET':
            bprefix = f'/webapp/b/{WEBAPP_BUILD}'
            last = qpath.rstrip('/').rsplit('/', 1)[-1]
            is_asset = '.' in last
            _legacy_path_key = os.getenv('ORCH_LEGACY_PATH_KEY', '').strip().lower() in ('1', 'true', 'yes', 'on')
            is_page = not is_asset and (qpath in ('/webapp', '/webapp/', '/webapp/index.html') or (_legacy_path_key and qpath.startswith('/webapp/k/')) or qpath == bprefix or qpath.startswith(bprefix + '/'))
            if is_page:
                import secrets as _secrets
                from . import http_server as _hs
                nonce = _secrets.token_urlsafe(16)
                self._tls.nonce = nonce
                _hs._webapp_nonce.value = nonce
                return (200, self._compose_index(self._key_from_request(qpath, query), nonce), 'text/html; charset=utf-8')
            for prefix in (bprefix + '/', '/webapp/'):
                if qpath.startswith(prefix) and '..' not in qpath:
                    name = qpath[len(prefix):]
                    if name and '.' in name.rsplit('/', 1)[-1]:
                        ctype = {'css': 'text/css; charset=utf-8', 'js': 'application/javascript; charset=utf-8', 'html': 'text/html; charset=utf-8', 'svg': 'image/svg+xml', 'png': 'image/png'}.get(name.rsplit('.', 1)[-1], 'application/octet-stream')
                        return self._file(name, ctype)
        return (404, {'error': 'not found'}, 'application/json')
    route_early = qpath[len('/webapp/api/'):].strip('/') if is_api else ''
    _oauth_public = is_api and method == 'GET' and route_early.startswith('oauth/callback/')
    if _oauth_public:
        provider = route_early.split('/')[-1]
        params = dict(query or {})
        data_early: dict = {}
        if body:
            try:
                data_early = json.loads(body.decode() or '{}')
            except Exception:
                data_early = {}
        if isinstance(data_early, dict) and data_early:
            params.update({k: v for k, v in data_early.items() if v})
        return (200, self._oauth_callback(provider, params), 'application/json')
    auth = self._auth(headers, query)
    if not auth:
        return (401, {'error': 'unauthorized'}, 'application/json')
    if self._rate_limited(headers, auth):
        return (429, {'error': 'too many requests'}, 'application/json')
    route = qpath[len('/webapp/api/'):].strip('/')
    import os as _os
    _ro = _os.getenv('ORCH_READ_ONLY', '').strip() in ('1', 'true', 'yes') or bool(getattr(self.cfg, 'read_only', False))
    if _ro and method in ('POST', 'PUT', 'DELETE', 'PATCH'):
        return (403, {'error': 'read_only'}, 'application/json')
    data = {}
    if body:
        try:
            data = json.loads(body.decode() or '{}')
        except Exception:
            data = {}
    try:
        if method == 'GET' and route == 'version':
            from . import __version__
            return (200, {'version': __version__, 'build': WEBAPP_BUILD}, 'application/json')
        if method == 'GET' and route == 'metrics':
            return (200, self._metrics(), 'application/json')
        if method == 'GET' and route == 'status':
            return (200, self._status(), 'application/json')
        if method == 'GET' and route.startswith('oauth/') and route.endswith('/start'):
            provider = route.split('/')[1] if '/' in route else ''
            return (200, self._oauth_start(provider, account_hint=str(query.get('account_id') or '')), 'application/json')
        if method == 'GET' and route.startswith('oauth/callback/'):
            provider = route.split('/')[-1]
            params = dict(query or {})
            if isinstance(data, dict) and data:
                params.update({k: v for k, v in data.items() if v})
            return (200, self._oauth_callback(provider, params), 'application/json')
        if method == 'GET' and route == 'calendar':
            return (200, self._calendar(), 'application/json')
        if method == 'GET' and route in ('inventory', 'remote_inventory'):
            return (200, self._remote_inventory(), 'application/json')
        if method == 'POST' and route == 'inventory/scan':
            return (200, self._inventory_scan(), 'application/json')
        if method == 'POST' and route in ('inventory/claim', 'inventory/link', 'inventory/ignore'):
            return (200, self._inventory_action(route.split('/')[-1], data if isinstance(data, dict) else {}), 'application/json')
        if method == 'GET' and route == 'ops':
            return (200, self._ops_status(), 'application/json')
        if method == 'GET' and route == 'queue':
            return (200, self._queue(), 'application/json')
        if method == 'GET' and route == 'projects':
            return (200, self._projects(), 'application/json')
        if method == 'GET' and route == 'platforms':
            return (200, self._platforms(), 'application/json')
        if method == 'GET' and route == 'accounts/checklist':
            from .connection_control import ConnectionControl
            from .accounts.store import PlatformAccountStore
            cc = ConnectionControl(self.db, self.comps.get('module_registry'), self.comps.get('token_lifecycle'), PlatformAccountStore(self.db))
            return (200, cc.as_dict(cc.checklist(str(query.get('provider') or ''), str(query.get('account_id') or ''))), 'application/json')
        if method == 'POST' and route == 'accounts/disconnect':
            from .connection_control import ConnectionControl
            from .accounts.store import PlatformAccountStore
            cc = ConnectionControl(self.db, self.comps.get('module_registry'), self.comps.get('token_lifecycle'), PlatformAccountStore(self.db))
            return (200, {'ok': cc.disconnect(str(data.get('account_id') or ''))}, 'application/json')
        if method == 'GET' and route == 'platform_capabilities':
            return (200, self._platform_capabilities(), 'application/json')
        if method == 'GET' and route == 'tail':
            return (200, self._tail(), 'application/json')
        if method == 'GET' and route == 'failed':
            return (200, self._failed(), 'application/json')
        if method == 'POST' and route == 'pause':
            for p in self.cfg.platforms:
                self.comps['safety'].pause_platform(p, 'webapp')
            return (200, {'ok': True}, 'application/json')
        if method == 'POST' and route == 'resume':
            for p in self.cfg.platforms:
                self.comps['safety'].resume_platform(p)
            return (200, {'ok': True}, 'application/json')
        if method == 'POST' and route == 'resume_platform':
            p = (data.get('platform') or '').strip()
            if p not in self.cfg.platforms:
                return (400, {'error': 'unknown platform'}, 'application/json')
            self.comps['safety'].resume_platform(p)
            return (200, {'ok': True}, 'application/json')
        if method == 'POST' and route == 'cross_post':
            etype = str(data.get('entity_type') or '').strip()
            try:
                eid = int(data.get('entity_id') or 0)
            except Exception:
                eid = 0
            plats = data.get('platforms') or []
            if not isinstance(plats, list):
                plats = [plats]
            plats = [str(p).strip() for p in plats if str(p).strip()]
            ck = str(data.get('content_kind') or 'video_native').strip() or 'video_native'
            if etype not in ('long_video', 'short') or not eid or (not plats):
                return (400, {'error': 'entity_type, entity_id, platforms required'}, 'application/json')
            table = 'long_videos' if etype == 'long_video' else 'shorts'
            try:
                exists = self.db.fetchone(f'SELECT id FROM {table} WHERE id=?', (eid,))
            except Exception:
                exists = None
            if not exists:
                return (400, {'error': 'entity not found'}, 'application/json')
            known = set(self.cfg.platforms.keys()) if self.cfg else set()
            created = []
            for plat in plats:
                if known and plat not in known:
                    continue
                pc = self.cfg.platforms.get(plat) if self.cfg else None
                if pc is not None and (not bool(getattr(pc, 'enabled', True) if not isinstance(pc, dict) else pc.get('enabled', True))):
                    continue
                try:
                    self.db.execute("INSERT OR IGNORE INTO entity_platform_status (entity_type, entity_id, platform, status, content_kind, source) VALUES (?, ?, ?, 'ready', ?, 'cross_post')", (etype, eid, plat, ck))
                    created.append(plat)
                except Exception:
                    pass
            return (200, {'ok': True, 'platforms': created, 'content_kind': ck}, 'application/json')
        if method == 'POST' and route == 'distribute':
            n = self.comps['scheduler'].schedule_long_videos(scope_roots=self._scan_roots())
            return (200, {'ok': True, 'count': n}, 'application/json')
        if method == 'POST' and route == 'series_end':
            p = (data.get('platform') or 'youtube').strip()
            enable = bool(data.get('enable'))
            self.db.execute('UPDATE platform_queue_state SET series_tail_mode=?, pending_series_end_question=0, updated_at=? WHERE platform=?', (1 if enable else 0, self.comps['clock'].now().isoformat(), p))
            return (200, {'ok': True, 'tail': enable}, 'application/json')
        if method == 'POST' and route == 'force_link':
            try:
                fid = int(data.get('entity_id') or 0)
            except Exception:
                fid = 0
            fplat = str(data.get('platform') or '').strip()
            furl = str(data.get('url') or '').strip()
            ftype = str(data.get('entity_type') or '').strip() or None
            link_upd = self.comps.get('link_upd')
            if link_upd is None:
                return (503, {'error': 'link_updater unavailable'}, 'application/json')
            if not fid or not fplat or (not furl):
                return (400, {'error': 'entity_type/entity_id/platform/url required'}, 'application/json')
            if not re.match('^https?://', furl, re.I):
                return (400, {'error': 'url must be http(s)'}, 'application/json')
            ok = link_upd.force_update(fid, fplat, furl, entity_type=ftype)
            return (200, {'ok': True}, 'application/json') if ok else (400, {'error': 'force_link_failed'}, 'application/json')
        if method == 'GET' and route == 'job':
            jobs = self.comps.get('jobs')
            snap = jobs.snapshot() if jobs is not None else None
            return (200, {'job': snap}, 'application/json')
        if method == 'POST' and route == 'job/cancel':
            jobs = self.comps.get('jobs')
            ok = jobs.cancel() if jobs is not None else False
            return (200, {'ok': ok}, 'application/json')
        if method == 'GET' and route == 'roots':
            return (200, {'roots': self._roots(), 'items': self._root_items(), 'browse_roots': [str(r) for r in self._browse_roots()]}, 'application/json')
        if method == 'POST' and route == 'roots':
            source = data.get('items')
            if source is None:
                source = data.get('roots')
            if not isinstance(source, list):
                return (400, {'error': 'items must be a list'}, 'application/json')
            allowed = self._browse_roots()
            cleaned: list[dict[str, str]] = []
            for item in source:
                if isinstance(item, dict):
                    raw_path = item.get('path')
                    kind = str(item.get('kind') or 'auto').strip().lower()
                else:
                    raw_path = item
                    kind = 'auto'
                if kind not in ('auto', 'series', 'shorts'):
                    return (400, {'error': f'bad kind: {kind}'}, 'application/json')
                target = Path(str(raw_path or '')).expanduser()
                if not target.is_dir():
                    return (400, {'error': f'not a directory: {raw_path}'}, 'application/json')
                rp = target.resolve()
                if not allowed:
                    return (400, {'error': 'no browse roots configured'}, 'application/json')
                if not self._path_under_roots(rp, allowed):
                    return (400, {'error': f'outside allowed root: {raw_path}'}, 'application/json')
                cleaned.append({'path': str(rp), 'kind': kind})
            self.db.set_setting(WATCH_ROOTS_KEY, json.dumps(cleaned, ensure_ascii=False))
            return (200, {'ok': True, 'items': cleaned, 'roots': [it['path'] for it in cleaned]}, 'application/json')
        if method == 'GET' and route == 'schedule_settings':
            settings = sched_settings.load_schedule_settings(self.db)
            groups = sched_settings.load_groups(self.db)
            platforms = list(self.cfg.platforms.keys())
            effective = {}
            for p in platforms:
                effective[p] = {'long': sched_settings.effective(self.db, self.cfg, p, 'long'), 'thematic': sched_settings.effective(self.db, self.cfg, p, 'thematic'), 'standalone': sched_settings.effective(self.db, self.cfg, p, 'standalone'), 'daily_limit': sched_settings.effective_daily_limit(self.db, self.cfg, p)}
            return (200, {'settings': settings, 'groups': groups, 'platforms': platforms, 'mode': sched_settings.scheduling_mode(self.db), 'effective': effective}, 'application/json')
        if method == 'POST' and route == 'schedule_settings':
            payload = data.get('settings')
            ok, msg = sched_settings.validate_schedule_settings(payload)
            if not ok:
                return (400, {'error': msg}, 'application/json')
            known = list(self.cfg.platforms.keys())
            for key in payload:
                if key.startswith('group:'):
                    if key[6:] not in {g['name'] for g in sched_settings.load_groups(self.db)}:
                        return (400, {'error': f'unknown group: {key[6:]}'}, 'application/json')
                elif key not in known:
                    return (400, {'error': f'unknown platform: {key}'}, 'application/json')
            sched_settings.save_schedule_settings(self.db, payload)
            return (200, {'ok': True}, 'application/json')
        if method == 'POST' and route == 'queue/edit':
            etype = str(data.get('entity_type') or '').strip()
            platform_sel = str(data.get('platform') or '').strip()
            try:
                eid = int(data.get('entity_id') or 0)
            except Exception:
                eid = 0
            if etype not in ('long_video', 'short') or not eid:
                return (400, {'error': 'entity_type/entity_id required'}, 'application/json')
            table = 'long_videos' if etype == 'long_video' else 'shorts'
            title = str(data.get('title') or '')
            desc = str(data.get('description') or '')
            tags = str(data.get('hashtags') or '')
            cover = str(data.get('cover') or '').strip()
            if cover and (not Path(cover).is_file()):
                return (400, {'error': 'cover file not found'}, 'application/json')
            self.db.execute(f'UPDATE {table} SET title_text=?, description_text=?, hashtags_text=?, cover_path=? WHERE id=?', (title[:200], desc, tags, cover or None, eid))
            ck = str(data.get('content_kind') or '').strip()
            if ck and platform_sel:
                try:
                    self.db.set_content_kind(etype, eid, platform_sel, ck)
                except Exception:
                    try:
                        self.db.execute('UPDATE entity_platform_status SET content_kind=? WHERE entity_type=? AND entity_id=? AND platform=?', (ck, etype, eid, platform_sel))
                    except Exception:
                        pass
            placement = str(data.get('placement') or '').strip().lower()
            if placement in ('start', 'middle', 'end', 'default'):
                try:
                    self.db.execute(f'UPDATE {table} SET placement=? WHERE id=?', (placement if placement != 'default' else None, eid))
                except Exception:
                    try:
                        self.db.execute(f'ALTER TABLE {table} ADD COLUMN placement TEXT')
                        self.db.execute(f'UPDATE {table} SET placement=? WHERE id=?', (placement if placement != 'default' else None, eid))
                    except Exception:
                        pass
            sql = "SELECT platform, external_id AS external_id, scheduled_for AS scheduled_for, status FROM entity_platform_status WHERE entity_type=? AND entity_id=? AND status IN ('scheduled','updating','ready','error')"
            params: list = [etype, eid]
            if platform_sel:
                sql += ' AND platform=?'
                params.append(platform_sel)
            rows = self.db.fetchall(sql, tuple(params))
            sch = self.comps.get('scheduler')
            pub = getattr(sch, 'publisher', None) if sch else self.comps.get('publisher')
            updated = 0
            recreated = 0
            for r in rows:
                plat = r['platform']
                pid = r.get('external_id')
                if pid and pub is not None and hasattr(pub, 'cancel_or_delete'):
                    try:
                        pub.cancel_or_delete(plat, str(pid))
                    except Exception:
                        logger.warning('queue edit: cancel failed %s', pid, exc_info=True)
                self.db.execute("UPDATE entity_platform_status SET status='ready', external_id=NULL, last_error=NULL WHERE entity_type=? AND entity_id=? AND platform=?", (etype, eid, plat))
                self.db.log(etype, eid, plat, 'queue_edit', '')
                updated += 1
                if pub is None:
                    continue
                entity = self.db.fetchone(f'SELECT * FROM {table} WHERE id=?', (eid,))
                if not entity:
                    continue
                pcfg = self.cfg.platforms.get(plat)
                path = None
                if sch is not None and hasattr(sch, '_pick_path'):
                    try:
                        if etype == 'long_video':
                            path = sch._pick_path(entity, plat, pcfg)
                        else:
                            path = sch._pick_path(entity, plat) or entity.get('video_path')
                    except Exception:
                        path = entity.get('video_path')
                if not path:
                    path = entity.get('video_path') or entity.get('vertical_path') or entity.get('wide_path')
                when = r.get('scheduled_for')
                sched_dt = None
                new_date = str(data.get('date') or '').strip()
                new_time = str(data.get('time') or '').strip()
                if new_date and new_time:
                    try:
                        from datetime import date as _date
                        from .slots import local_to_utc, parse_time
                        y, m, d = (int(x) for x in new_date.split('-'))
                        sched_dt = local_to_utc(_date(y, m, d), parse_time(new_time), self.cfg.timezone)
                    except Exception:
                        sched_dt = None
                if sched_dt is None and when:
                    from datetime import datetime as _dt
                    try:
                        sched_dt = _dt.fromisoformat(str(when))
                    except Exception:
                        sched_dt = None
                if sched_dt is None and (not (r.get('external_id') and r.get('status') == 'scheduled')):
                    continue
                content = {'title': title, 'description': desc, 'hashtags': tags, 'cover': cover}
                _tcfg = self.cfg.platforms.get('telegram')
                _bot_tg = bool(plat == 'telegram' and _tcfg and (str(getattr(_tcfg, 'send_via', 'bot') or 'bot').lower() == 'bot'))
                if _bot_tg:
                    if sched_dt is not None:
                        self.db.execute('UPDATE entity_platform_status SET scheduled_for=? WHERE entity_type=? AND entity_id=? AND platform=?', (sched_dt.isoformat(), etype, eid, plat))
                    continue
                try:
                    post = pub.publish(etype, eid, plat, path, content, sched_dt)
                    if post:
                        recreated += 1
                    elif sched_dt is not None:
                        self.db.execute('UPDATE entity_platform_status SET scheduled_for=? WHERE entity_type=? AND entity_id=? AND platform=?', (sched_dt.isoformat(), etype, eid, plat))
                except Exception:
                    logger.exception('queue edit: пересоздание не удалось (%s/%s %s)', etype, eid, plat)
            return (200, {'ok': True, 'updated': updated, 'recreated': recreated}, 'application/json')
        if method == 'POST' and route == 'queue/cleanup_orphans':
            known = {r['external_id'] for r in self.db.fetchall("SELECT external_id FROM entity_platform_status WHERE external_id IS NOT NULL AND external_id != ''")}
            known |= self._active_test_post_ids()
            logger.info('cleanup_orphans: canonical remote ids tracked=%s', len(known))
            return (200, {'ok': True, 'deleted': 0, 'legacy_runtime_reads': 0}, 'application/json')
        if method == 'POST' and route == 'queue/restore':
            etype = str(data.get('entity_type') or '').strip()
            try:
                eid = int(data.get('entity_id') or 0)
            except Exception:
                eid = 0
            if etype in ('long_video', 'short') and eid:
                before = self.db.fetchone("SELECT COUNT(*) AS c FROM entity_platform_status WHERE status='skipped' AND entity_type=? AND entity_id=?", (etype, eid))
                self.db.execute("UPDATE entity_platform_status SET status='ready', external_id=NULL, external_sub_id=NULL, external_url=NULL, last_error=NULL, deleted_at=NULL, deleted_reason=NULL, cascade_from=NULL WHERE status='skipped' AND entity_type=? AND entity_id=?", (etype, eid))
            elif data.get('all'):
                before = self.db.fetchone("SELECT COUNT(*) AS c FROM entity_platform_status WHERE status='skipped'")
                self.db.execute("UPDATE entity_platform_status SET status='ready', external_id=NULL, external_sub_id=NULL, external_url=NULL, last_error=NULL, deleted_at=NULL, deleted_reason=NULL, cascade_from=NULL WHERE status='skipped'")
            else:
                return (400, {'error': 'entity_type/entity_id or all=true required'}, 'application/json')
            return (200, {'ok': True, 'restored': (before or {}).get('c', 0)}, 'application/json')
        if method == 'GET' and route == 'trash':
            rows = self.db.fetchall("\n                    SELECT eps.entity_type, eps.entity_id, eps.platform, eps.status,\n                           eps.deleted_at, eps.deleted_reason, eps.cascade_from,\n                           eps.scheduled_for AS scheduled_for,\n                           COALESCE(lv.title_text, lv.title, sh.title_text) AS title,\n                           sh.parent_video_id AS parent_id\n                    FROM entity_platform_status eps\n                    LEFT JOIN long_videos lv\n                           ON eps.entity_type='long_video' AND lv.id=eps.entity_id\n                    LEFT JOIN shorts sh\n                           ON eps.entity_type='short' AND sh.id=eps.entity_id\n                    WHERE eps.status='skipped'\n                    ORDER BY (eps.deleted_at IS NULL), eps.deleted_at DESC,\n                             eps.entity_type, eps.entity_id\n                    LIMIT 500\n                    ")
            items = []
            for r in rows:
                kind = self._kind_label(r['entity_type'])
                title = (r.get('title') or '').strip() or f"{kind} #{r['entity_id']}"
                items.append({'key': f"{r['entity_type']}|{r['entity_id']}|{r['platform']}", 'entity_type': r['entity_type'], 'entity_id': r['entity_id'], 'platform': r['platform'], 'title': title, 'deleted_at': r['deleted_at'], 'deleted_reason': r['deleted_reason'], 'cascade_from': r['cascade_from'], 'scheduled_for': r['scheduled_for'], 'parent_id': r['parent_id']})
            total_row = self.db.fetchone("SELECT COUNT(*) AS c FROM entity_platform_status WHERE status='skipped'")
            total = int((total_row or {}).get('c') or 0)
            return (200, {'items': items, 'total': total, 'shown': len(items)}, 'application/json')
        if method == 'POST' and route in ('trash/restore', 'trash/purge'):
            ids = data.get('ids') or []
            all_flag = bool(data.get('all'))
            if all_flag:
                rows = self.db.fetchall("SELECT entity_type, entity_id, platform FROM entity_platform_status WHERE status='skipped'")
            elif isinstance(ids, list) and ids:
                rows = []
                for item in ids:
                    parts = str(item).split('|')
                    if len(parts) == 3 and parts[0] in ('long_video', 'short'):
                        try:
                            rows.append({'entity_type': parts[0], 'entity_id': int(parts[1]), 'platform': parts[2]})
                        except ValueError:
                            continue
            else:
                return (400, {'error': 'ids or all=true required'}, 'application/json')
            n = 0
            affected: set[tuple[str, int]] = set()
            for r in rows:
                if route == 'trash/restore':
                    n += self.db.execute("UPDATE entity_platform_status SET status='ready', last_error=NULL, deleted_at=NULL, deleted_reason=NULL, cascade_from=NULL WHERE entity_type=? AND entity_id=? AND platform=? AND status='skipped'", (r['entity_type'], r['entity_id'], r['platform'])) or 0
                else:
                    n += self.db.execute("DELETE FROM entity_platform_status WHERE entity_type=? AND entity_id=? AND platform=? AND status='skipped'", (r['entity_type'], r['entity_id'], r['platform'])) or 0
                    affected.add((str(r['entity_type']), int(r['entity_id'])))
            gone = 0
            if route == 'trash/purge':
                gone = self._purge_from_base(affected)
            self.db.log('system', None, '', 'trash_restore' if route == 'trash/restore' else 'trash_purge', f'n={n}' + (f' entities={gone}' if route == 'trash/purge' else ''))
            key = 'restored' if route == 'trash/restore' else 'purged'
            return (200, {'ok': True, key: n, 'entities': gone}, 'application/json')
        if method == 'POST' and route == 'queue/remove':
            etype = str(data.get('entity_type') or '').strip()
            if etype not in ('long_video', 'short'):
                return (400, {'error': 'entity_type required'}, 'application/json')
            try:
                eid = int(data.get('entity_id') or 0)
            except Exception:
                eid = 0
            if not eid:
                return (400, {'error': 'entity_id required'}, 'application/json')
            platform = str(data.get('platform') or '').strip()
            if platform not in ('', 'youtube', 'telegram'):
                return (400, {'error': 'platform must be youtube|telegram|empty'}, 'application/json')
            if 'with_shorts' in data:
                with_shorts = bool(data.get('with_shorts'))
            elif platform:
                with_shorts = False
            else:
                with_shorts = not bool(data.get('keep_shorts'))
            also_youtube = bool(data.get('also_youtube'))
            plan = self._delete_plan(etype, eid, platform, also_youtube, with_shorts)
            if data.get('plan_only'):
                return (200, {'ok': True, 'plan_only': True, 'blocked': plan['blocked'], 'count': len(plan['targets']), 'targets': [{'entity_type': et, 'entity_id': ei, 'platform': p, 'status': st} for et, ei, p, st in plan['targets']]}, 'application/json')
            if not plan['targets']:
                return (200, {'ok': True, 'removed': 0, 'blocked': [], 'note': 'already'}, 'application/json')
            if plan['blocked']:
                return (200, {'ok': True, 'removed': 0, 'blocked': plan['blocked']}, 'application/json')
            reason = str(data.get('reason') or ('platform' if platform else 'everywhere'))
            cascade_from = 'youtube' if platform == 'youtube' else ''
            self._kill_targets(plan['targets'])
            now = self._now_iso()
            removed = 0
            for et, ei, p, _st in plan['targets']:
                cf = cascade_from if p == 'telegram' else ''
                self.db.execute("UPDATE entity_platform_status SET status='skipped', deleted_at=COALESCE(deleted_at, ?), deleted_reason=CASE WHEN deleted_reason='detached'   THEN 'detached' ELSE ? END, cascade_from=CASE WHEN deleted_reason='detached'   THEN cascade_from ELSE ? END, last_error=NULL WHERE entity_type=? AND entity_id=? AND platform=?", (now, reason, cf, et, ei, p))
                self.db.log(et, ei, p, 'queue_delete', reason)
                removed += 1
            guard = self.comps.get('guard')
            if guard is not None and hasattr(guard, 'invalidate'):
                guard.invalidate()
            dependents: dict[str, int] = {}
            if etype == 'long_video' and (not with_shorts):
                cnt = self.db.fetchone("SELECT COUNT(DISTINCT s.id) AS c FROM shorts s JOIN entity_platform_status e ON e.entity_type='short'   AND e.entity_id=s.id WHERE s.parent_video_id=? AND e.status IN   ('ready','scheduled','updating')", (eid,))
                if cnt and cnt['c']:
                    dependents['shorts'] = int(cnt['c'])
            logger.info('queue remove: %s#%s platform=%r -> trashed=%s blocked=%s', etype, eid, platform, removed, plan['blocked'])
            return (200, {'ok': True, 'removed': removed, 'blocked': [], 'cascade': ['telegram'] if platform == 'youtube' else [], 'dependents': dependents}, 'application/json')
        if method == 'POST' and route == 'queue/detach':
            etype = str(data.get('entity_type') or '').strip()
            platform = str(data.get('platform') or '').strip()
            try:
                eid = int(data.get('entity_id') or 0)
            except Exception:
                eid = 0
            if etype not in ('long_video', 'short') or not eid or (not platform):
                return (400, {'error': 'entity_type/entity_id/platform required'}, 'application/json')
            row = self.db.fetchone('SELECT status, release_url, external_id AS external_id FROM entity_platform_status WHERE entity_type=? AND entity_id=? AND platform=?', (etype, eid, platform))
            if not row:
                return (404, {'error': 'not found'}, 'application/json')
            if (row['status'] or '') != 'published':
                return (400, {'error': 'not_published'}, 'application/json')
            if platform == 'telegram':
                pid = row.get('external_id')
                logger.info('queue detach: telegram local clear id=%s', pid)
            else:
                pid = row.get('external_id')
                deleted_remote = False
                reg = (self.comps or {}).get('module_registry')
                mod = None
                if reg is not None:
                    try:
                        if hasattr(reg, 'has') and reg.has(platform):
                            mod = reg.create(platform)
                        elif hasattr(reg, 'get'):
                            mod = reg.get(platform)
                    except Exception:
                        mod = None
                if mod is not None and hasattr(mod, 'delete') and pid:
                    try:
                        from orchestrator.platforms.base import NotSupported
                        man = getattr(mod, 'manifest', None)
                        caps = dict(getattr(man, 'capabilities', {}) or {}) if man else {}
                        if man is not None and caps.get('delete') is False:
                            return (400, {'error': 'detach_unavailable', 'reason': 'delete_not_supported'}, 'application/json')
                        mod.delete(str(pid))
                        deleted_remote = True
                    except Exception as ex:
                        from orchestrator.platforms.base import NotSupported
                        if isinstance(ex, NotSupported) or type(ex).__name__ == 'NotSupported':
                            return (400, {'error': 'detach_unavailable', 'reason': 'delete_not_supported'}, 'application/json')
                        logger.warning('queue detach: module delete failed %s %s', platform, pid, exc_info=True)
                        return (502, {'error': 'detach_failed'}, 'application/json')
                if not deleted_remote:
                    sources = (self.comps or {}).get('manual_sources') or {}
                    eng = sources.get(platform)
                    vid = _youtube_id_from_url(str(row.get('release_url') or ''))
                    if eng is None or not hasattr(eng, 'delete') or (not vid):
                        return (400, {'error': 'detach_unavailable'}, 'application/json')
                    try:
                        eng.delete(vid)
                    except Exception:
                        logger.warning('queue detach: %s %s не снят', platform, vid, exc_info=True)
                        return (502, {'error': 'detach_failed'}, 'application/json')
            now = self._now_iso()
            self.db.execute("UPDATE entity_platform_status SET status='skipped', external_id=NULL, release_url=NULL, deleted_at=?, deleted_reason='detached', cascade_from=NULL, last_error=NULL WHERE entity_type=? AND entity_id=? AND platform=?", (now, etype, eid, platform))
            self.db.log(etype, eid, platform, 'queue_detach', platform)
            return (200, {'ok': True, 'detached': 1}, 'application/json')
        if method == 'POST' and route == 'scheduling_mode':
            mode = str(data.get('mode') or '').strip().lower()
            if mode not in ('auto', 'manual'):
                return (400, {'error': 'mode must be auto or manual'}, 'application/json')
            sched_settings.set_scheduling_mode(self.db, mode)
            return (200, {'ok': True, 'mode': mode}, 'application/json')
        if method == 'POST' and route == 'groups':
            payload = data.get('groups')
            ok, msg = sched_settings.validate_groups(payload, list(self.cfg.platforms.keys()))
            if not ok:
                return (400, {'error': msg}, 'application/json')
            sched_settings.save_groups(self.db, payload)
            return (200, {'ok': True, 'groups': payload}, 'application/json')
        if method == 'GET' and route == 'browse':
            roots = self._browse_roots()
            if not roots:
                return (403, {'error': 'no browse roots configured'}, 'application/json')
            metas = [self._root_meta(r) for r in roots]
            available = [Path(m['path']) for m in metas if m['available']]
            root = available[0] if available else roots[0]
            sel = query.get('root')
            if sel:
                try:
                    rp = Path(sel).expanduser().resolve()
                except Exception:
                    rp = None
                if rp is not None and rp in roots:
                    root = rp
            target = query.get('path') or str(root)
            try:
                base = Path(target).expanduser().resolve()
            except Exception:
                base = root
            if not base.is_dir():
                base = root
            for r in roots:
                try:
                    if base == r or base.is_relative_to(r):
                        root = r
                        break
                except (ValueError, TypeError):
                    continue
            if not self._path_under_roots(base, roots):
                base = root
            dirs = []
            warning = ''
            try:
                children = sorted(base.iterdir())
            except PermissionError:
                return (403, {'error': 'permission denied'}, 'application/json')
            except OSError:
                children = []
                warning = 'папка недоступна (диск отключён?)'
            for child in children:
                if not child.is_dir() or child.name.startswith('.'):
                    continue
                try:
                    dirs.append({'name': child.name, 'path': str(child.resolve())})
                except (PermissionError, OSError):
                    continue
            cur = next((m for m in metas if m['path'] == str(root)), None)
            if cur and (not cur['available']):
                warning = cur['note']
            return (200, {'path': str(base), 'parent': str(base.parent) if base != root else None, 'root': str(root), 'roots': [str(r) for r in roots], 'roots_meta': metas, 'warning': warning, 'dirs': dirs, 'selected': str(base) in self._roots()}, 'application/json')
        if method == 'GET' and route in ('cover/list', 'cover/thumb'):
            roots = self._browse_roots()
            if not roots:
                return (403, {'error': 'no browse roots configured'}, 'application/json')
            target = query.get('path') or str(roots[0])
            try:
                base = Path(target).expanduser().resolve()
            except Exception:
                base = roots[0]
            if not (self._path_under_roots(base, roots) and base.exists()):
                base = roots[0]
            if not self._path_under_roots(base, roots):
                return (403, {'error': 'path not allowed'}, 'application/json')
            if route == 'cover/thumb':
                if not base.is_file() or base.suffix.lower() not in IMG_EXTS:
                    return (404, {'error': 'not an image'}, 'application/json')
                try:
                    if base.stat().st_size > 25 * 1024 * 1024:
                        return (413, {'error': 'too large'}, 'application/json')
                    blob = base.read_bytes()
                except OSError:
                    return (404, {'error': 'read failed'}, 'application/json')
                ctype = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp'}.get(base.suffix.lower(), 'application/octet-stream')
                return (200, blob, ctype)
            dirs: list[dict] = []
            images: list[dict] = []
            warning = ''
            try:
                children = sorted(base.iterdir())
            except PermissionError:
                return (403, {'error': 'permission denied'}, 'application/json')
            except OSError:
                children = []
                warning = 'папка недоступна'
            for child in children:
                if child.name.startswith('.'):
                    continue
                try:
                    if child.is_dir():
                        dirs.append({'name': child.name, 'path': str(child.resolve())})
                    elif child.is_file() and child.suffix.lower() in IMG_EXTS:
                        images.append({'name': child.name, 'path': str(child.resolve()), 'size': child.stat().st_size})
                except OSError:
                    continue
            parent = str(base.parent) if base != base.parent and self._path_under_roots(base.parent, roots) else None
            return (200, {'path': str(base), 'parent': parent, 'roots': [str(r) for r in roots], 'dirs': dirs, 'images': images[:400], 'warning': warning}, 'application/json')
        if method == 'POST' and route == 'cover/frames':
            etype = str(data.get('entity_type') or '').strip()
            try:
                eid = int(data.get('entity_id') or 0)
            except Exception:
                eid = 0
            if etype not in ('long_video', 'short') or not eid:
                return (400, {'error': 'entity_type/entity_id required'}, 'application/json')
            if etype == 'short':
                row = self.db.fetchone('SELECT video_path FROM shorts WHERE id=?', (eid,))
            else:
                row = self.db.fetchone('SELECT COALESCE(vertical_path, wide_path) AS video_path FROM long_videos WHERE id=?', (eid,))
            video = (row or {}).get('video_path') if row else None
            if not video or not Path(str(video)).is_file():
                return (400, {'error': 'video file not found'}, 'application/json')
            import shutil as _shutil
            import subprocess as _sp
            if not _shutil.which('ffmpeg') or not _shutil.which('ffprobe'):
                return (500, {'error': 'ffmpeg/ffprobe not installed'}, 'application/json')
            try:
                dur_out = _sp.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=nw=1:nk=1', str(video)], capture_output=True, text=True, timeout=60)
                duration = float((dur_out.stdout or '0').strip() or 0)
            except Exception:
                duration = 0.0
            if duration <= 1:
                return (400, {'error': 'cannot read video duration'}, 'application/json')
            try:
                count = max(2, min(12, int(data.get('count') or 6)))
            except Exception:
                count = 6
            covers = self._covers_dir()
            if covers is None:
                return (500, {'error': 'cannot create covers dir'}, 'application/json')
            stamp = time.strftime('%Y%m%d-%H%M%S')
            outdir = covers / f'{etype}_{eid}_frames_{stamp}'
            try:
                outdir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                return (500, {'error': f'cannot create frames dir: {e}'}, 'application/json')
            frames: list[dict] = []
            for i in range(count):
                frac = 0.12 + (0.8 - 0.12) * (i / max(1, count - 1))
                ts = max(0.5, duration * frac)
                dst = outdir / f'frame_{i + 1:02d}.jpg'
                try:
                    _sp.run(['ffmpeg', '-v', 'error', '-ss', f'{ts:.2f}', '-i', str(video), '-frames:v', '1', '-q:v', '3', '-vf', "scale='min(1920,iw)':-2", '-y', str(dst)], capture_output=True, timeout=120)
                except Exception:
                    continue
                if dst.is_file() and dst.stat().st_size > 200:
                    frames.append({'name': dst.name, 'path': str(dst), 'at': round(ts, 1)})
            if not frames:
                return (500, {'error': 'no frames extracted'}, 'application/json')
            return (200, {'ok': True, 'dir': str(outdir), 'frames': frames, 'duration': round(duration, 1)}, 'application/json')
        if method == 'POST' and route in ('cover/upload', 'cover/fetch'):
            etype = str(data.get('entity_type') or '').strip()
            try:
                eid = int(data.get('entity_id') or 0)
            except Exception:
                eid = 0
            if etype not in ('long_video', 'short') or not eid:
                return (400, {'error': 'entity_type/entity_id required'}, 'application/json')
            blob: bytes | None = None
            ext = '.jpg'
            if route == 'cover/upload':
                raw = str(data.get('data') or '')
                m = re.match('^data:image/(png|jpe?g|webp);base64,(.+)$', raw, re.S)
                if m:
                    ext = {'png': '.png', 'jpg': '.jpg', 'jpeg': '.jpg', 'webp': '.webp'}[m.group(1)]
                    payload = m.group(2)
                else:
                    payload = raw
                    e = Path(str(data.get('filename') or '')).suffix.lower()
                    ext = e if e in IMG_EXTS else '.jpg'
                try:
                    blob = base64.b64decode(payload, validate=False)
                except Exception:
                    return (400, {'error': 'bad base64'}, 'application/json')
            else:
                url = str(data.get('url') or '').strip()
                if not re.match('^https?://', url, re.I):
                    return (400, {'error': 'http(s) url required'}, 'application/json')
                try:
                    blob, ctype, final_url = _fetch_image_pinned(url)
                    ext = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp'}.get(ctype, Path(urlsplit(final_url).path).suffix.lower())
                    if ext not in IMG_EXTS:
                        ext = '.jpg'
                except ValueError as e:
                    msg = str(e)
                    if 'too large' in msg:
                        return (413, {'error': 'image too large (>25MB)'}, 'application/json')
                    if 'not allowed' in msg or 'scheme' in msg or 'no addresses' in msg:
                        return (400, {'error': f'url not allowed: {msg}'}, 'application/json')
                    return (502, {'error': f'download failed: {msg}'}, 'application/json')
                except Exception as e:
                    return (502, {'error': f'download failed: {e}'}, 'application/json')
            if blob is None or len(blob) < 32:
                return (400, {'error': 'empty image'}, 'application/json')
            if len(blob) > 25 * 1024 * 1024:
                return (413, {'error': 'image too large (>25MB)'}, 'application/json')
            if not _is_image_bytes(blob):
                return (400, {'error': 'not an image'}, 'application/json')
            covers = self._covers_dir()
            if covers is None:
                return (500, {'error': 'cannot create covers dir'}, 'application/json')
            stamp = time.strftime('%Y%m%d-%H%M%S')
            dst = covers / f'{etype}_{eid}_{stamp}_{os.urandom(2).hex()}{ext}'
            try:
                dst.write_bytes(blob)
            except OSError as e:
                return (500, {'error': f'save failed: {e}'}, 'application/json')
            return (200, {'ok': True, 'path': str(dst), 'size': len(blob)}, 'application/json')
        if method == 'GET' and route == 'browse/search':
            q = (query.get('q') or '').strip().lower()
            if len(q) < 2:
                return (400, {'error': 'query too short (min 2 chars)'}, 'application/json')
            roots = self._browse_roots()
            if not roots:
                return (403, {'error': 'no browse roots configured'}, 'application/json')
            sel = query.get('root')
            if sel:
                rp = Path(sel).expanduser()
                try:
                    rp = rp.resolve()
                except Exception:
                    rp = None
                if rp in roots:
                    roots = [rp]
            try:
                limit = max(1, min(100, int(query.get('limit') or 50)))
            except Exception:
                limit = 50
            results: list[dict] = []
            for root in roots:
                if not root.is_dir():
                    continue
                base_depth = len(root.parts)
                for dirpath, dirnames, _files in os.walk(root):
                    d = Path(dirpath)
                    if len(d.parts) - base_depth > 5:
                        dirnames[:] = []
                        continue
                    dirnames[:] = [x for x in dirnames if not x.startswith('.')]
                    for name in dirnames:
                        if q in name.lower():
                            full = d / name
                            results.append({'name': name, 'path': str(full), 'root': str(root)})
                            if len(results) >= limit:
                                break
                    if len(results) >= limit:
                        break
                if len(results) >= limit:
                    break
            return (200, {'q': q, 'items': results[:limit]}, 'application/json')
        if method == 'POST' and route == 'scan':
            watcher = self.comps.get('watcher')
            if not watcher:
                return (500, {'error': 'watcher unavailable'}, 'application/json')
            stats = {'long': 0, 'shorts': 0, 'standalone': 0, 'standalone_found': 0, 'checked': 0, 'unstable': 0, 'no_final': 0}
            passes = max(2, int(getattr(self.cfg, 'file_stability_cycles', 2)))
            jobs = self.comps.get('jobs')
            job = jobs.start('scan', 'Сканирование папок', passes) if jobs is not None else None
            snapshots = ('standalone_found', 'checked', 'unstable', 'no_final')
            last: dict = {}
            for _ in range(passes):
                if job is not None and job.cancelled:
                    break
                st = watcher.scan()
                last = st
                for k in stats:
                    if k in snapshots:
                        continue
                    stats[k] += int(st.get(k, 0) or 0)
            if last:
                for k in snapshots:
                    if k in last:
                        stats[k] = int(last.get(k, 0) or 0)
                if job is not None:
                    job.tick(1, 'Поиск фильмов и шортсов')
            if job is not None:
                job.finish('done', 'Сканирование завершено')
            roots = [str(r) for r in watcher.effective_roots()]

            def _under(path: str) -> bool:
                return any((path == r or path.startswith(r.rstrip('/') + '/') for r in roots))
            longs = self.db.fetchall('SELECT folder_path FROM long_videos')
            shorts_rows = self.db.fetchall('SELECT folder_path FROM shorts')
            totals = {'long': sum((1 for r in longs if _under(r['folder_path'] or ''))), 'shorts': sum((1 for r in shorts_rows if _under(r['folder_path'] or '')))}
            missing = 0
            for r in longs + shorts_rows:
                fp = str(r['folder_path'] or '').split('::')[0]
                if _under(fp) and fp and (not Path(fp).exists()):
                    missing += 1
            skipped = self.db.fetchone("SELECT COUNT(*) AS c FROM entity_platform_status WHERE status='skipped'")
            last = self.db.fetchone("SELECT MAX(scheduled_for) AS m FROM entity_platform_status WHERE entity_type='long_video' AND status IN ('scheduled','updating','ready')")
            return (200, {'ok': True, 'stats': stats, 'totals': totals, 'skipped': (skipped or {}).get('c', 0), 'last_scheduled': (last or {}).get('m') if last else None, 'roots': roots, 'checked': int(stats.get('checked', 0) or 0), 'unstable': int(stats.get('unstable', 0) or 0), 'no_final': int(stats.get('no_final', 0) or 0), 'missing': missing, 'at': self._now_iso()}, 'application/json')
        if route == 'manual/plan' and method == 'GET':
            return (200, self._manual_plan(), 'application/json')
        if route == 'manual/uploads' and method == 'GET':
            manual = self.comps.get('manual')
            if not manual:
                return (500, {'error': 'manual service unavailable'}, 'application/json')
            rows = self.db.list_uploads(status=query.get('status'), platform=query.get('platform'))
            out = []
            for r in rows:
                item = {k: r.get(k) for k in ('id', 'engine', 'platform', 'platform_video_id', 'url', 'title', 'published_at', 'origin', 'match_status', 'confidence', 'matched_entity_type', 'matched_entity_id', 'claim_status')}
                item['candidates'] = manual.candidates(r['id']) if r['match_status'] in ('unmatched', 'suggested') else []
                out.append(item)
            return (200, {'items': out}, 'application/json')
        if route == 'manual/scan' and method == 'POST':
            manual = self.comps.get('manual')
            sources = self.comps.get('manual_sources') or {}
            if not manual:
                return (500, {'error': 'manual service unavailable'}, 'application/json')
            want = data.get('platform')
            targets = [want] if want else list(sources.keys())
            stats: dict = {}
            for p in targets:
                src = sources.get(p)
                if not src:
                    stats[p] = {'error': 'no source configured'}
                    continue
                caps = getattr(src, 'capabilities', lambda: {})()
                if not caps.get('list', False):
                    stats[p] = {'skipped': 'engine does not support listing uploads'}
                    continue
                try:
                    uploads = src.list_uploads()
                except Exception as e:
                    stats[p] = {'error': str(e)}
                    continue
                stats[p] = manual.scan(p, uploads, engine=self.cfg.engine_for(p))
            self.db.set_setting('manual_last_scan', json.dumps({'at': self.comps['clock'].now().isoformat(), 'stats': stats}))
            return (200, {'ok': True, 'stats': stats}, 'application/json')
        if route.startswith('manual/uploads/') and method in ('GET', 'POST'):
            manual = self.comps.get('manual')
            if not manual:
                return (500, {'error': 'manual service unavailable'}, 'application/json')
            seg = route.split('/')
            try:
                uid = int(seg[2])
            except (IndexError, ValueError):
                return (400, {'error': 'bad upload id'}, 'application/json')
            action = seg[3] if len(seg) > 3 else ''
            if action == 'candidates' and method == 'GET':
                return (200, {'items': manual.candidates(uid)}, 'application/json')
            row = self.db.get_upload(uid)
            if not row:
                return (404, {'error': 'upload not found'}, 'application/json')
            sources = self.comps.get('manual_sources') or {}
            engine = sources.get(row['platform'])
            if action in ('confirm', 'reassign') and method == 'POST':
                et = data.get('entity_type')
                eid = data.get('entity_id')
                if not et or eid is None:
                    return (400, {'error': 'entity_type/entity_id required'}, 'application/json')
                try:
                    ok = manual.confirm(uid, et, int(eid), apply_edits=bool(data.get('apply_edits')) if action == 'confirm' else False, engine=engine)
                except sqlite3.IntegrityError:
                    return (409, {'error': 'this entity is already linked to another upload on this platform'}, 'application/json')
                return (200, {'ok': ok}, 'application/json')
            if action == 'reject' and method == 'POST':
                return (200, {'ok': manual.reject(uid)}, 'application/json')
            if action == 'ignore' and method == 'POST':
                return (200, {'ok': manual.ignore(uid)}, 'application/json')
            if action == 'claim-mark' and method == 'POST':
                claimed = bool(data.get('claimed', True))
                self.db.execute('UPDATE platform_uploads SET claim_status=?, claim_info=? WHERE id=?', ('claimed' if claimed else 'none', 'manual', uid))
                return (200, {'ok': True}, 'application/json')
            if action == 'claim-action' and method == 'POST':
                act = data.get('action')
                if act == 'delete':
                    if engine is not None:
                        try:
                            engine.delete(str(row['platform_video_id']))
                        except Exception as e:
                            return (500, {'error': str(e)}, 'application/json')
                    self.db.execute("UPDATE platform_uploads SET claim_status='none', claim_info='deleted' WHERE id=?", (uid,))
                elif act == 'keep':
                    self.db.execute("UPDATE platform_uploads SET claim_status='claimed', claim_info='kept' WHERE id=?", (uid,))
                else:
                    self.db.execute("UPDATE platform_uploads SET claim_status='none', claim_info='ignored' WHERE id=?", (uid,))
                return (200, {'ok': True}, 'application/json')
            return (404, {'error': 'unknown manual action'}, 'application/json')
        if method == 'GET' and route == 'backlog':
            bl = self.comps.get('backlog')
            if not bl:
                return (500, {'error': 'backlog unavailable'}, 'application/json')
            out = []
            for p, pcfg in self.cfg.platforms.items():
                if not getattr(pcfg, 'enabled', False):
                    continue
                st = bl._state(p) or {}
                out.append({'platform': p, 'count': bl.has_backlog(p), 'awaiting': bool(st.get('pending_series_end_question')), 'slot': st.get('pending_series_end_at'), 'tail_mode': bool(st.get('series_tail_mode'))})
            return (200, {'platforms': out}, 'application/json')
        if method == 'POST' and route == 'backlog/answer':
            bl = self.comps.get('backlog')
            p = (data.get('platform') or '').strip()
            ans = (data.get('answer') or '').strip()
            if not bl or p not in self.cfg.platforms or ans not in ('distribute', 'wait', 'skip'):
                return (400, {'error': 'platform/answer invalid'}, 'application/json')
            if ans == 'distribute' and data.get('from_date'):
                n = bl.scheduler.schedule_backlog(p, start_date=str(data['from_date'])) if bl.scheduler else 0
                bl.db.execute('UPDATE platform_queue_state SET pending_series_end_question=0, pending_series_end_at=NULL, series_tail_mode=1 WHERE platform=?', (p,))
                bl.db.log('system', None, p, 'backlog_distribute', str(n))
            else:
                n = bl.resolve(p, ans)
            return (200, {'ok': True, 'scheduled': n}, 'application/json')
        if method == 'POST' and route == 'sync':
            ss = self.comps.get('status_sync')
            n = ss.sync() if ss else 0
            n2 = ss.sync(fresh_only=True) if ss else 0
            lu = self.comps.get('link_upd')
            if lu:
                lu.check_missing_urls()
            return (200, {'ok': True, 'updates': (n or 0) + (n2 or 0)}, 'application/json')
        if method == 'POST' and route == 'reconcile':
            rec = self.comps.get('recon')
            return (200, {'ok': True, 'result': rec.run() if rec else {}}, 'application/json')
        if method == 'POST' and route == 'backup':
            from .backup import run_backup
            bdir = Path(self.db.path).parent.parent / 'backups'
            p = run_backup(self.db, self.cfg, bdir)
            return (200, {'ok': True, 'path': str(p) if p else None}, 'application/json')
        if route in ('test/schedule', 'test/status', 'test/cancel'):
            from .test_publish import TestPublishError, cancel_test_post, schedule_test_post, test_recent
            tcfg = self.cfg.test_publish
            if method == 'GET' and route == 'test/status':
                return (200, {'enabled': bool(tcfg.enabled), 'default_delay_minutes': tcfg.default_delay_minutes, 'min_delay_minutes': tcfg.min_delay_minutes, 'max_delay_minutes': tcfg.max_delay_minutes, 'platforms': list(tcfg.platforms or []), 'title_prefix': tcfg.title_prefix, 'require_explicit_platforms': tcfg.require_explicit_platforms, 'allow_prod_channel': tcfg.allow_prod_channel, 'recent': test_recent(self.db, 10)}, 'application/json')
            if method != 'POST':
                return (404, {'error': 'unknown route'}, 'application/json')
            try:
                if route == 'test/schedule':
                    platforms = data.get('platforms') or []
                    platform = str(data.get('platform') or '').strip()
                    if not platform and isinstance(platforms, list) and platforms:
                        platform = str(platforms[0])
                    if not platform:
                        return (400, {'error': 'platform required'}, 'application/json')
                    try:
                        entity_id = int(data.get('entity_id') or 0)
                    except Exception:
                        entity_id = 0
                    if not entity_id:
                        return (400, {'error': 'entity_id required'}, 'application/json')
                    res = schedule_test_post(self.comps, platform=platform, entity_type=str(data.get('entity_type') or 'short').strip(), entity_id=entity_id, delay_minutes=data.get('delay_minutes'), scheduled_for=data.get('scheduled_for'), dry_run=bool(data.get('dry_run')))
                    return (200, res, 'application/json')
                pid = str(data.get('external_id') or '').strip()
                if not pid:
                    return (400, {'error': 'external_id required'}, 'application/json')
                return (200, cancel_test_post(self.comps, external_id=pid), 'application/json')
            except TestPublishError as e:
                _m = self.comps.get('metrics')
                if _m is not None and hasattr(_m, 'incr'):
                    try:
                        _m.incr('test_rejected')
                    except Exception:
                        pass
                return (e.code, {'error': str(e)}, 'application/json')
        if method == 'POST' and route == 'schedule':
            import re as _re
            sc = self.comps.get('scheduler')
            sd = str(data.get('start_date') or '').strip() or None
            shr = str(data.get('shorts_start_date') or '').strip() or None
            for name, val in (('start_date', sd), ('shorts_start_date', shr)):
                if val and (not _re.fullmatch('\\d{4}-\\d{2}-\\d{2}', val)):
                    return (400, {'error': f'{name} must be YYYY-MM-DD'}, 'application/json')
            if shr is not None:
                sched_settings.set_shorts_start_date(self.db, shr or '')
            guard = self.comps.get('guard')
            if guard is not None and hasattr(guard, 'invalidate'):
                guard.invalidate()
            if not _SCHEDULE_LOCK.acquire(blocking=False):
                return (200, {'ok': True, 'busy': True, 'started': False}, 'application/json')
            jobs = self.comps.get('jobs')
            job = jobs.start('schedule', 'Планирование публикаций') if jobs is not None else None
            before = self._sched_snapshot()

            def _run():
                try:
                    if sc is not None:
                        sc.job = job
                    roots = self._scan_roots()
                    sc.schedule_long_videos(start_date=sd, scope_roots=roots)
                    sc.schedule_standalone_shorts(self.comps.get('tail'), start_date=sd, scope_roots=roots)
                    pubs = self.db.fetchall("SELECT entity_id, platform FROM entity_platform_status WHERE entity_type='long_video' AND status IN ('published','scheduled')")
                    for r in pubs:
                        sc.schedule_thematic_shorts(r['entity_id'], r['platform'], scope_roots=roots)
                    sc.schedule_telegram_links()
                    sc.refresh_telegram_links()
                    sc.send_due_telegram_posts()
                    self._send_schedule_summary(before)
                    if job is not None:
                        job.finish('done', 'Готово')
                except Exception as e:
                    logger.exception('async schedule failed')
                    if job is not None:
                        job.finish('failed', str(e)[:200])
                finally:
                    _SCHEDULE_LOCK.release()
            if data.get('async'):
                import threading
                threading.Thread(target=_run, daemon=True).start()
                return (200, {'ok': True, 'started': True, 'start_date': sd, 'shorts_start_date': shr}, 'application/json')
            try:
                roots = self._scan_roots()
                n = sc.schedule_long_videos(start_date=sd, scope_roots=roots) if sc else 0
                n2 = sc.schedule_standalone_shorts(self.comps.get('tail'), start_date=sd, scope_roots=roots) if sc else 0
                nt = 0
                if sc:
                    pubs = self.db.fetchall("SELECT entity_id, platform FROM entity_platform_status WHERE entity_type='long_video' AND status IN ('published','scheduled')")
                    for r in pubs:
                        nt += sc.schedule_thematic_shorts(r['entity_id'], r['platform'], scope_roots=roots)
                    sc.schedule_telegram_links()
                    sc.refresh_telegram_links()
                    sc.send_due_telegram_posts()
                self._send_schedule_summary(before)
            finally:
                _SCHEDULE_LOCK.release()
            return (200, {'ok': True, 'long': n, 'standalone': n2, 'thematic': nt, 'start_date': sd, 'shorts_start_date': shr}, 'application/json')
        if method == 'POST' and route == 'pause_platform':
            p = (data.get('platform') or '').strip()
            if p not in self.cfg.platforms:
                return (400, {'error': 'unknown platform'}, 'application/json')
            self.comps['safety'].pause_platform(p, 'webapp')
            return (200, {'ok': True}, 'application/json')
        return (404, {'error': 'unknown route'}, 'application/json')
    except Exception as e:
        from .platforms.base import NotSupported
        if isinstance(e, NotSupported):
            logger.info('webapp api not supported: %s', e)
            return (501, {'error': 'engine_not_implemented', 'detail': str(e), 'method': getattr(e, 'method', '')}, 'application/json')
        logger.exception('webapp api')
        return (500, {'error': str(e)}, 'application/json')` — Return (status, payload, content_type).
### `src/orchestrator/webhook_ingress.py`
- **class `WebhookIngress`** — no class docstring
  - `handle` — `def handle(self, method: str, request_path: str, headers: dict[str, str], body: bytes) -> tuple[int, Any, str]:
    parsed = urlparse(request_path)
    parts = [x for x in parsed.path.split('/') if x]
    if len(parts) < 2 or parts[0] != 'webhooks':
        return (404, {'error': 'not found'}, 'application/json')
    provider = parts[1].lower()
    if method.upper() == 'GET':
        ok, challenge = self._verify(provider, request_path, headers, body, None)
        if ok and challenge is not None:
            return (200, challenge, 'text/plain; charset=utf-8')
        return (403, {'error': 'webhook verification failed'}, 'application/json')
    if method.upper() != 'POST':
        return (405, {'error': 'method not allowed'}, 'application/json')
    try:
        payload = json.loads(body.decode('utf-8')) if body else {}
    except Exception:
        return (400, {'error': 'invalid json'}, 'application/json')
    ok, _ = self._verify(provider, request_path, headers, body, payload)
    if not ok:
        return (403, {'error': 'invalid webhook signature'}, 'application/json')
    account_id = str(headers.get('X-Account-Id') or '').strip()
    event_id = self._event_id(provider, headers, body, payload)
    payload_hash = hashlib.sha256(body).hexdigest()
    try:
        self.db.execute("INSERT INTO webhook_events(provider, account_id, event_id, payload_hash, signature_valid, received_at, payload_json) VALUES (?, ?, ?, ?, 1, datetime('now'), ?) ON CONFLICT(provider, account_id, event_id) DO NOTHING", (provider, account_id, event_id, payload_hash, json.dumps(payload, ensure_ascii=False, sort_keys=True)))
    except Exception:
        logger.exception('webhook persistence failed for %s', provider)
        return (500, {'error': 'webhook persistence failed'}, 'application/json')
    return (202, {'accepted': True, 'provider': provider, 'event_id': event_id}, 'application/json')` — no method docstring
### `src/orchestrator/webhook_processor.py`
- **class `WebhookProcessResult`** — no class docstring
- **class `WebhookEventProcessor`** — Durable webhook normalizer/processor with replay-safe claiming and DLQ.
  - `claim` — `def claim(self, limit: int=50) -> list[dict[str, Any]]:
    rows = self.db.fetchall("SELECT * FROM webhook_events WHERE signature_valid=1 AND processed_at IS NULL AND processing_state IN ('queued','retry') ORDER BY received_at LIMIT ?", (max(1, int(limit)),))
    out = []
    for row in rows:
        n = self.db.execute("UPDATE webhook_events SET processing_state='processing', attempts=attempts+1 WHERE id=? AND processed_at IS NULL AND processing_state IN ('queued','retry')", (row['id'],))
        if n:
            out.append(row)
    return out` — no method docstring
  - `run` — `def run(self, *, limit: int=50) -> WebhookProcessResult:
    res = WebhookProcessResult()
    for row in self.claim(limit):
        res.checked += 1
        try:
            payload = json.loads(row.get('payload_json') or '{}')
            event_type, external_id, new_status = self.normalize(str(row['provider']), payload)
            self.db.execute("UPDATE webhook_events SET normalized_type=?, external_id=?, processing_state='done', processed_at=datetime('now'), processed_result=? WHERE id=?", (event_type, external_id, json.dumps({'status': new_status}, ensure_ascii=False), row['id']))
            if external_id:
                res.repaired += self._repair_eps(str(row['provider']), str(row.get('account_id') or ''), external_id, new_status)
            res.processed += 1
        except Exception as exc:
            attempts = int(row.get('attempts') or 1)
            if attempts >= self.max_attempts:
                self.db.execute("UPDATE webhook_events SET processing_state='dead', last_error=? WHERE id=?", (str(exc)[:1000], row['id']))
                res.dead += 1
            else:
                self.db.execute("UPDATE webhook_events SET processing_state='retry', last_error=? WHERE id=?", (str(exc)[:1000], row['id']))
                res.retried += 1
    return res` — no method docstring
  - `replay` — `def replay(self, event_id: int) -> bool:
    row = self.db.fetchone('SELECT id FROM webhook_events WHERE id=?', (int(event_id),))
    if not row:
        return False
    return bool(self.db.execute("UPDATE webhook_events SET processed_at=NULL, processing_state='retry', last_error=NULL WHERE id=?", (int(event_id),)))` — no method docstring
  - `normalize` — `@staticmethod
def normalize(provider: str, payload: dict[str, Any]) -> tuple[str, str, str]:
    event_type = str(payload.get('type') or payload.get('event') or payload.get('object') or 'unknown')
    external_id = str(payload.get('external_id') or payload.get('id') or '')
    status = str(payload.get('status') or payload.get('state') or '')
    data = payload.get('data')
    if isinstance(data, dict):
        event_type = str(data.get('event') or data.get('type') or event_type)
        external_id = str(data.get('id') or data.get('external_id') or external_id)
        status = str(data.get('status') or data.get('state') or status)
    return (event_type, external_id, status)` — no method docstring
  - `set_subscription` — `def set_subscription(self, provider: str, account_id: str, endpoint: str, *, desired: bool=True, verified: bool=False, error: str='') -> None:
    self.db.execute('INSERT INTO webhook_subscriptions(provider,account_id,endpoint,desired,verified,last_checked_at,last_error) VALUES(?,?,?,?,?,?,?) ON CONFLICT(provider,account_id) DO UPDATE SET endpoint=excluded.endpoint,desired=excluded.desired,verified=excluded.verified,last_checked_at=excluded.last_checked_at,last_error=excluded.last_error', (provider, account_id, endpoint, int(desired), int(verified), datetime.now(UTC).isoformat(), error[:1000]))` — no method docstring
### `src/orchestrator/yaml_utils.py`
- **class `DuplicateYAMLKeyError`** — Raised when a YAML mapping contains the same key more than once.
- **function `load_unique_yaml_text`** — `def load_unique_yaml_text(text: str, *, source: str='<string>') -> Any:
    """Load YAML and reject duplicate mapping keys."""
    try:
        return yaml.load(text, Loader=_UniqueKeyLoader)
    except DuplicateYAMLKeyError as exc:
        raise DuplicateYAMLKeyError(f'{source}: {exc}') from exc` — Load YAML and reject duplicate mapping keys.
- **function `load_unique_yaml`** — `def load_unique_yaml(path: str | Path) -> Any:
    """Read a YAML file and reject duplicate mapping keys."""
    p = Path(path)
    return load_unique_yaml_text(p.read_text(encoding='utf-8'), source=str(p))` — Read a YAML file and reject duplicate mapping keys.

## 7A. Provider operation matrix

| Provider | State | Publish | Update | Delete | Status | Inventory | Schedule | Video | Image | Messages |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| beehiiv | IMPLEMENTED_NATIVE | YES | YES | YES | YES | YES | — | — | YES | — |
| bluesky | PARTIAL_NATIVE | YES | — | YES | YES | — | — | — | YES | — |
| devto | IMPLEMENTED_NATIVE | YES | YES | — | YES | YES | — | — | — | — |
| discord | PARTIAL_NATIVE | — | — | — | — | — | — | — | — | YES |
| dribbble | IMPLEMENTED_NATIVE | YES | YES | YES | YES | YES | YES | — | YES | — |
| facebook | IMPLEMENTED | YES | YES | YES | YES | YES | YES | YES | — | — |
| farcaster | PARTNER | YES | — | YES | YES | YES | — | — | — | — |
| google_business | IMPLEMENTED_NATIVE | YES | — | YES | YES | — | — | — | YES | — |
| hashnode | IMPLEMENTED_NATIVE | YES | YES | YES | YES | YES | — | — | YES | — |
| instagram | IMPLEMENTED | YES | — | — | YES | YES | — | YES | YES | — |
| instagram_messaging | SCAFFOLD | — | — | — | — | — | — | — | — | — |
| kick | PARTIAL_NATIVE | — | YES | — | YES | YES | — | YES | — | — |
| lemmy | IMPLEMENTED_NATIVE | YES | YES | YES | YES | YES | — | — | — | — |
| line | PARTIAL_NATIVE | — | — | — | — | — | — | — | — | YES |
| linkedin | PARTIAL_NATIVE | YES | YES | YES | YES | — | — | — | YES | — |
| listmonk | IMPLEMENTED_NATIVE | YES | YES | YES | YES | — | — | — | — | — |
| mastodon | IMPLEMENTED_NATIVE | YES | — | YES | YES | — | — | YES | YES | — |
| medium | FEASIBILITY | — | — | — | YES | YES | — | — | — | — |
| messenger | SCAFFOLD | — | — | — | — | — | — | — | — | — |
| mewe | PARTIAL_NATIVE | YES | — | — | YES | YES | YES | — | YES | — |
| moltbook | IMPLEMENTED_NATIVE | YES | — | YES | YES | YES | — | — | — | — |
| nostr | IMPLEMENTED_NATIVE | YES | — | YES | YES | YES | — | — | — | — |
| pinterest | PARTIAL_NATIVE | YES | — | YES | YES | — | — | — | YES | — |
| reddit | PARTIAL_NATIVE | YES | — | YES | YES | — | — | — | YES | — |
| rutube | PARTNER | — | — | — | YES | YES | — | YES | — | — |
| signal | FEASIBILITY | — | — | — | — | — | — | — | — | — |
| skool | SCAFFOLD | — | — | — | — | — | — | — | — | — |
| slack | PARTIAL_NATIVE | — | — | — | — | — | — | — | — | YES |
| snapchat | PARTIAL_NATIVE | YES | — | — | YES | YES | — | YES | YES | — |
| telegram | IMPLEMENTED | YES | YES | YES | YES | YES | — | YES | YES | — |
| threads | IMPLEMENTED | YES | — | YES | YES | YES | — | YES | YES | — |
| tiktok | IMPLEMENTED_INBOX | YES | — | — | YES | YES | — | YES | — | — |
| tumblr | PARTIAL_NATIVE | YES | YES | YES | YES | — | — | — | — | — |
| twitch | PARTIAL_NATIVE | — | — | — | YES | YES | — | — | — | — |
| viber | PARTIAL_NATIVE | — | — | — | — | — | — | — | — | YES |
| vk | IMPLEMENTED | YES | YES | YES | YES | YES | — | YES | YES | — |
| wechat | IMPLEMENTED_NATIVE | YES | — | YES | YES | YES | — | — | — | — |
| whatsapp | PARTIAL_NATIVE | — | — | — | — | — | — | — | — | YES |
| whop | PARTIAL_NATIVE | YES | — | — | — | — | — | YES | YES | — |
| wordpress | IMPLEMENTED_NATIVE | YES | YES | YES | YES | YES | — | — | — | — |
| x | IMPLEMENTED | YES | — | YES | YES | YES | — | YES | YES | — |
| youtube | IMPLEMENTED | YES | YES | YES | YES | YES | YES | YES | — | — |

## 7. Provider-by-provider functionality

### beehiiv
- State: **IMPLEMENTED_NATIVE** — native transport implemented for declared scope.
- Module version: `0.1.0`; publish mode: `direct`; content kind: `article`.
- Declared capabilities: `publish=True`, `update_metadata=True`, `delete=True`, `image=True`, `text=True`, `list_private=True`, `scan_mode=auto`, `schedule_owner=orchestrator`, `content_kinds=['text', 'article']`, `content_kind_default=article`.
- Public module functions/methods: `auth_status`, `create_module`, `delete`, `get_status`, `list_remote_items`, `publish`, `update_metadata`.
### bluesky
- State: **PARTIAL_NATIVE** — native transport implemented but declared scope remains partial.
- Module version: `0.1.0`; publish mode: `direct`; content kind: `text`.
- Declared capabilities: `publish=True`, `delete=True`, `image=True`, `text=True`, `schedule_owner=orchestrator`, `content_kind_default=text`.
- Public module functions/methods: `create_module`, `delete`, `get_status`, `prepare`, `publish`.
- Module note: Bluesky: scaffold only. Native implementation requires provider-specific API/access/review work documented in the master roadmap.
### devto
- State: **IMPLEMENTED_NATIVE** — native transport implemented for declared scope.
- Module version: `0.2.0`; publish mode: `direct`; content kind: `article`.
- Declared capabilities: `publish=True`, `update_metadata=True`, `text=True`, `list_uploads=True`, `list_private=True`, `scan_mode=auto`, `schedule_owner=orchestrator`, `content_kinds=['text', 'article']`, `content_kind_default=article`.
- Public module functions/methods: `auth_status`, `create_module`, `get_status`, `list_remote_items`, `prepare`, `publish`, `update_metadata`, `validate_config`.
- Module note: # Dev.to Native Module  Uses Dev.to API v0 with `DEVTO_API_KEY`; supports article create/status/delete for the declared scope.
### discord
- State: **PARTIAL_NATIVE** — native transport implemented but declared scope remains partial.
- Module version: `0.2.0`; publish mode: `unsupported`; content kind: `text`.
- Declared capabilities: `schedule_owner=orchestrator`, `content_kind_default=text`, `messages=True`.
- Public module functions/methods: `auth_status`, `create_module`, `delete_message`, `send_message`, `update_message`.
- Module note: Discord native webhook messaging core: text and embeds with webhook health probe. Bot/OAuth channel features are a separate access strategy.
### dribbble
- State: **IMPLEMENTED_NATIVE** — native transport implemented for declared scope.
- Module version: `0.1.0`; publish mode: `direct`; content kind: `image`.
- Declared capabilities: `publish=True`, `schedule_publish=True`, `update_metadata=True`, `delete=True`, `image=True`, `text=True`, `list_uploads=True`, `list_scheduled=True`, `scan_mode=auto`, `schedule_owner=platform`, `content_kinds=['image']`, `content_kind_default=image`.
- Public module functions/methods: `auth_status`, `create_module`, `delete`, `get_status`, `list_remote_items`, `prepare`, `publish`, `schedule_publish`, `update_metadata`, `validate_config`.
- Module note: Dribbble: native API v2 adapter for image shots.  Supported: create, update metadata, delete, status reconciliation and remote inventory. Constraints: official shot creation requires upload scope; images must be GIF/JPEG/PNG and 400x300 or 800x600, <=8 MB. Video shot creation is intentionally unsupported because the current API contract does not provide it.
### facebook
- State: **IMPLEMENTED** — implemented core provider path; live access/canary still required.
- Module version: `0.3.0`; publish mode: `direct`; content kind: `unknown`.
- Declared capabilities: `publish=True`, `schedule_publish=True`, `update_metadata=True`, `delete=True`, `video=True`, `text=True`, `list_uploads=True`, `list_scheduled=True`, `scan_mode=auto`, `schedule_owner=platform`.
- Public module functions/methods: `auth_status`, `check_claims`, `create_facebook_module`, `delete`, `get_status`, `list_remote`, `list_remote_items`, `prepare`, `publish`, `schedule_publish`, `update_metadata`, `upload`.
- Explicit unsupported/deprecated boundaries: schedule_publish on existing id — use upload(when=...).
- Module note: facebook module skeleton 0.1.0\nPage token; [ЖДЁТ] Meta Contact email.\n
### farcaster
- State: **PARTNER** — transport requires external partner/commercial access.
- Module version: `0.1.0`; publish mode: `partner`; content kind: `text`.
- Declared capabilities: `publish=True`, `delete=True`, `text=True`, `list_uploads=True`, `scan_mode=auto`, `schedule_owner=orchestrator`, `content_kinds=['text']`, `content_kind_default=text`.
- Public module functions/methods: `auth_status`, `create_module`, `delete`, `get_status`, `list_remote_items`, `prepare`, `publish`, `update_metadata`, `validate_config`.
- Explicit unsupported/deprecated boundaries: update_metadata: Farcaster casts are immutable; create a new cast or delete the existing one.
- Module note: Farcaster: partner-backed adapter through Neynar v2.  Supported: create text casts with a managed signer, optional URL embeds/replies/channel, lookup/status, deletion and remote inventory for a configured FID. Native protocol publishing is intentionally not claimed here; the provider is marked PARTNER because this implementation depends on the Neynar API key + signer contract.
### google_business
- State: **IMPLEMENTED_NATIVE** — native transport implemented for declared scope.
- Module version: `0.1.0`; publish mode: `direct`; content kind: `text`.
- Declared capabilities: `publish=True`, `delete=True`, `image=True`, `text=True`, `public_media_required=True`, `scan_mode=auto`, `schedule_owner=orchestrator`, `content_kinds=['text', 'image', 'offer', 'event']`, `content_kind_default=text`.
- Public module functions/methods: `auth_status`, `create_module`, `delete`, `get_status`, `prepare`, `publish`, `validate_config`.
- Module note: Google Business Profile: scaffold only. Native implementation requires provider-specific API/access/review work documented in the master roadmap.
### hashnode
- State: **IMPLEMENTED_NATIVE** — native transport implemented for declared scope.
- Module version: `0.2.0`; publish mode: `direct`; content kind: `article`.
- Declared capabilities: `publish=True`, `update_metadata=True`, `delete=True`, `image=True`, `text=True`, `schedule_owner=orchestrator`, `content_kinds=['article']`, `content_kind_default=article`.
- Public module functions/methods: `auth_status`, `create_module`, `delete`, `get_status`, `list_remote_items`, `prepare`, `publish`, `update_metadata`, `validate_config`.
- Module note: Hashnode: scaffold only. Native implementation requires provider-specific API/access/review work documented in the master roadmap.
### instagram
- State: **IMPLEMENTED** — implemented core provider path; live access/canary still required.
- Module version: `0.3.0`; publish mode: `orchestrator`; content kind: `unknown`.
- Declared capabilities: `publish=True`, `video=True`, `image=True`, `list_uploads=True`, `scan_mode=published_only`, `schedule_owner=orchestrator`.
- Public module functions/methods: `auth_status`, `check_claims`, `create_instagram_module`, `delete`, `get_status`, `list_remote`, `list_remote_items`, `prepare`, `publish`, `schedule_publish`, `update_metadata`, `upload`.
- Explicit unsupported/deprecated boundaries: delete; schedule_publish; update_metadata.
- Module note: instagram module skeleton 0.1.0\nТребует B2 public URL (media_host). Live — [ЖДЁТ] Meta keys.\n
### instagram_messaging
- State: **SCAFFOLD** — registered/limited module without native production publish transport.
- Module version: `0.2.0`; publish mode: `unsupported`; content kind: `text`.
- Declared capabilities: `schedule_owner=orchestrator`, `content_kind_default=text`.
- Public module functions/methods: `auth_status`, `create_module`, `send_message`, `verify_webhook`.
- Module note: Instagram Messaging: scaffold only. Native implementation requires provider-specific API/access/review work documented in the master roadmap.
### kick
- State: **PARTIAL_NATIVE** — native transport implemented but declared scope remains partial.
- Module version: `1.0.0`; publish mode: `unsupported`; content kind: `video_native`.
- Declared capabilities: `update_metadata=True`, `video=True`, `text=True`, `list_uploads=True`, `scan_mode=auto`, `schedule_owner=orchestrator`, `content_kinds=['video_native', 'channel_metadata']`, `content_kind_default=video_native`.
- Public module functions/methods: `auth_status`, `create_module`, `get_status`, `list_remote_items`, `prepare`, `publish`, `update_metadata`, `validate_config`.
- Explicit unsupported/deprecated boundaries: prepare/publish: KICK public API does not expose arbitrary server-side video upload; publish.
- Module note: Kick: scaffold only. Native implementation requires provider-specific API/access/review work documented in the master roadmap.
### lemmy
- State: **IMPLEMENTED_NATIVE** — native transport implemented for declared scope.
- Module version: `0.1.0`; publish mode: `direct`; content kind: `text`.
- Declared capabilities: `publish=True`, `update_metadata=True`, `delete=True`, `text=True`, `schedule_owner=orchestrator`, `content_kind_default=text`.
- Public module functions/methods: `auth_status`, `create_module`, `delete`, `get_status`, `list_remote_items`, `prepare`, `publish`, `update_metadata`, `validate_config`.
- Module note: # Lemmy Native Module  Uses the Lemmy v3 REST API for authenticated text-post creation, status and delete on a configured instance/community. Production readiness depends on the selected instance access policy.
### line
- State: **PARTIAL_NATIVE** — native transport implemented but declared scope remains partial.
- Module version: `0.2.0`; publish mode: `unsupported`; content kind: `text`.
- Declared capabilities: `schedule_owner=orchestrator`, `content_kind_default=text`, `messages=True`.
- Public module functions/methods: `auth_status`, `create_module`, `get_webhook_endpoint`, `send_message`, `send_multicast`, `set_webhook_endpoint`, `validate_push`, `verify_webhook`.
- Module note: LINE Official Account native Messaging API core: push text/media messages, bot identity probe and channel-secret webhook signature verification. Configure channel access token and recipient.
### linkedin
- State: **PARTIAL_NATIVE** — native transport implemented but declared scope remains partial.
- Module version: `0.1.0`; publish mode: `direct`; content kind: `text`.
- Declared capabilities: `publish=True`, `update_metadata=True`, `delete=True`, `image=True`, `text=True`, `schedule_owner=orchestrator`, `content_kind_default=text`.
- Public module functions/methods: `auth_status`, `create_module`, `delete`, `get_status`, `prepare`, `publish`, `update_metadata`, `upload_image`, `validate_config`.
- Module note: LinkedIn: scaffold only. Native implementation requires provider-specific API/access/review work documented in the master roadmap.
### listmonk
- State: **IMPLEMENTED_NATIVE** — native transport implemented for declared scope.
- Module version: `0.2.0`; publish mode: `direct`; content kind: `newsletter`.
- Declared capabilities: `publish=True`, `update_metadata=True`, `delete=True`, `text=True`, `scan_mode=auto`, `schedule_owner=orchestrator`, `content_kinds=['text', 'newsletter']`, `content_kind_default=newsletter`.
- Public module functions/methods: `auth_status`, `create_module`, `delete`, `get_status`, `prepare`, `publish`, `update_metadata`, `validate_config`.
- Module note: Listmonk: scaffold only. Native implementation requires provider-specific API/access/review work documented in the master roadmap.
### mastodon
- State: **IMPLEMENTED_NATIVE** — native transport implemented for declared scope.
- Module version: `0.1.0`; publish mode: `direct`; content kind: `text`.
- Declared capabilities: `publish=True`, `delete=True`, `video=True`, `image=True`, `text=True`, `schedule_owner=orchestrator`, `content_kind_default=text`.
- Public module functions/methods: `auth_status`, `create_module`, `delete`, `get_status`, `prepare`, `publish`.
- Module note: # Mastodon Native Module  Native text/image/video status publishing using the Mastodon REST API. Configure `MASTODON_BASE_URL` and account-scoped bearer access token. Production readiness still depends on the selected instance/account policy.
### medium
- State: **FEASIBILITY** — explicit feasibility boundary; no native production publish advertised.
- Module version: `1.0.0-deprecated`; publish mode: `unsupported`; content kind: `text`.
- Declared capabilities: `schedule_owner=orchestrator`, `content_kind_default=text`.
- Public module functions/methods: `auth_status`, `create_module`, `get_status`, `list_remote_items`, `publish`, `validate_config`.
- Explicit unsupported/deprecated boundaries: API_DEPRECATED, "Medium: API is no longer supported").
- Module note: Medium is explicitly closed as API_DEPRECATED for this roadmap.  The official Medium API documentation repository is archived and warns that the Medium API is no longer supported. It also states that new integrations are not allowed. The orchestrator therefore fails closed and does not expose publish/list/status transport for Medium.
### messenger
- State: **SCAFFOLD** — registered/limited module without native production publish transport.
- Module version: `0.2.0`; publish mode: `unsupported`; content kind: `text`.
- Declared capabilities: `schedule_owner=orchestrator`, `content_kind_default=text`.
- Public module functions/methods: `auth_status`, `create_module`, `send_message`, `verify_webhook`.
- Module note: Facebook Messenger: scaffold only. Native implementation requires provider-specific API/access/review work documented in the master roadmap.
### mewe
- State: **PARTIAL_NATIVE** — native transport implemented but declared scope remains partial.
- Module version: `1.0.0`; publish mode: `direct`; content kind: `text`.
- Declared capabilities: `publish=True`, `schedule_publish=True`, `image=True`, `text=True`, `list_scheduled=True`, `list_private=True`, `scan_mode=auto`, `schedule_owner=orchestrator`, `content_kinds=['text', 'image']`, `content_kind_default=text`.
- Public module functions/methods: `auth_status`, `create_module`, `get_status`, `list_remote_items`, `prepare`, `publish`, `schedule_publish`, `validate_config`.
- Module note: MeWe Open API group-post adapter.  Confirmed official surface: - GET /api/dev/me - POST /api/dev/group/:groupId/post - GET /api/dev/group/:groupId/postsfeed - GET /api/dev/group/:groupId/scheduled/posts/calendar
### moltbook
- State: **IMPLEMENTED_NATIVE** — native transport implemented for declared scope.
- Module version: `1.0.0`; publish mode: `direct`; content kind: `text`.
- Declared capabilities: `publish=True`, `delete=True`, `text=True`, `list_uploads=True`, `list_private=True`, `scan_mode=auto`, `schedule_owner=orchestrator`, `content_kinds=['text', 'link']`, `content_kind_default=text`.
- Public module functions/methods: `auth_status`, `create_module`, `delete`, `get_status`, `list_remote_items`, `prepare`, `publish`, `validate_config`.
- Module note: Moltbook: scaffold only. Native implementation requires provider-specific API/access/review work documented in the master roadmap.
### nostr
- State: **IMPLEMENTED_NATIVE** — native transport implemented for declared scope.
- Module version: `1.0.0`; publish mode: `direct`; content kind: `text`.
- Declared capabilities: `publish=True`, `delete=True`, `text=True`, `list_uploads=True`, `list_private=True`, `scan_mode=auto`, `schedule_owner=orchestrator`, `content_kinds=['text', 'note', 'deletion']`, `content_kind_default=text`.
- Public module functions/methods: `auth_status`, `create_module`, `delete`, `get_status`, `list_remote_items`, `prepare`, `publish`, `query`, `validate_config`.
- Module note: Nostr: scaffold only. Native implementation requires provider-specific API/access/review work documented in the master roadmap.
### pinterest
- State: **PARTIAL_NATIVE** — native transport implemented but declared scope remains partial.
- Module version: `0.1.0`; publish mode: `direct`; content kind: `text`.
- Declared capabilities: `publish=True`, `delete=True`, `image=True`, `text=True`, `schedule_owner=orchestrator`, `content_kind_default=text`.
- Public module functions/methods: `auth_status`, `create_module`, `delete`, `get_status`, `prepare`, `publish`, `upload_media`, `validate_config`.
- Module note: Pinterest: scaffold only. Native implementation requires provider-specific API/access/review work documented in the master roadmap.
### reddit
- State: **PARTIAL_NATIVE** — native transport implemented but declared scope remains partial.
- Module version: `0.1.0`; publish mode: `direct`; content kind: `text`.
- Declared capabilities: `publish=True`, `delete=True`, `image=True`, `text=True`, `schedule_owner=orchestrator`, `content_kind_default=text`.
- Public module functions/methods: `auth_status`, `create_module`, `delete`, `get_status`, `prepare`, `publish`, `validate_config`.
- Module note: Reddit: scaffold only. Native implementation requires provider-specific API/access/review work documented in the master roadmap.
### rutube
- State: **PARTNER** — transport requires external partner/commercial access.
- Module version: `0.1.0`; publish mode: `partner`; content kind: `video_native`.
- Declared capabilities: `video=True`, `schedule_owner=orchestrator`, `content_kinds=['video_native']`, `content_kind_default=video_native`.
- Public module functions/methods: `auth_status`, `create_rutube_module`, `delete`, `get_status`, `list_remote_items`, `prepare`, `publish`, `schedule_publish`, `update_metadata`, `validate_config`.
- Explicit unsupported/deprecated boundaries: publish; schedule_publish; delete; get_status; list_remote_items; update_metadata.
- Module note: Rutube is closed as a PARTNER-gated provider.  Official Rutube partner documentation states that automatic upload API access is provided to partners when the relevant cooperation/API arrangement is established. The project therefore keeps the provider fail-closed until the partner endpoint/schema, credentials, legal account, and live canary are supplied.  No browser automation or guessed private endpoints are allowed.
### signal
- State: **FEASIBILITY** — explicit feasibility boundary; no native production publish advertised.
- Module version: `0.0.1-scaffold`; publish mode: `unsupported`; content kind: `text`.
- Declared capabilities: `schedule_owner=orchestrator`, `content_kind_default=text`.
- Public module functions/methods: `auth_status`, `create_module`, `publish`, `validate_config`.
- Module note: Signal remains a roadmap feasibility module.  Official Signal documentation currently exposes protocol specifications and software libraries, not a general server-side business/bot publishing API. The project therefore does not ship an unofficial transport, signal-cli integration, browser automation, or a fabricated Direct Publish contract. The module is intentionally non-publishing until Signal exposes an official server-side access contract suitable for this orchestrator.
### skool
- State: **SCAFFOLD** — registered/limited module without native production publish transport.
- Module version: `0.0.1-scaffold`; publish mode: `unsupported`; content kind: `text`.
- Declared capabilities: `schedule_owner=orchestrator`, `content_kind_default=text`.
- Public module functions/methods: `auth_status`, `create_module`, `publish`, `validate_config`.
- Module note: Skool remains a roadmap FEASIBILITY provider.  No official direct REST publishing contract was verified for this orchestrator. Current automation options encountered during the roadmap review are third-party/automation-specific paths, not a stable official provider API suitable for a native transport. The project therefore does not ship browser automation or an unofficial API dependency as a substitute.
### slack
- State: **PARTIAL_NATIVE** — native transport implemented but declared scope remains partial.
- Module version: `0.2.0`; publish mode: `unsupported`; content kind: `text`.
- Declared capabilities: `schedule_owner=orchestrator`, `content_kind_default=text`, `messages=True`.
- Public module functions/methods: `auth_status`, `create_module`, `delete_message`, `send_message`, `update_message`.
- Module note: Slack native Web API messaging core: auth.test and chat.postMessage with blocks/attachments/thread support. Configure bot token and channel.
### snapchat
- State: **PARTIAL_NATIVE** — native transport implemented but declared scope remains partial.
- Module version: `1.0.0`; publish mode: `direct`; content kind: `video`.
- Declared capabilities: `publish=True`, `video=True`, `image=True`, `stories=True`, `public_media_required=True`, `scan_mode=auto`, `schedule_owner=orchestrator`, `content_kinds=['image', 'video']`, `content_kind_default=video`.
- Public module functions/methods: `auth_status`, `create_module`, `get_status`, `list_remote_items`, `prepare`, `publish`, `validate_config`.
- Module note: Snapchat Public Profile API adapter.  Implemented native scope: - POST /v1/public_profiles/:profileId/stories using a provider media_id - POST /v1/public_profiles/:profileId/spotlights using a provider media_id - GET Stories / Spotlights inventory with cursor propagation - status reconciliation from inventory
### telegram
- State: **IMPLEMENTED** — implemented core provider path; live access/canary still required.
- Module version: `1.2.0`; publish mode: `orchestrator`; content kind: `unknown`.
- Declared capabilities: `publish=True`, `update_metadata=True`, `delete=True`, `video=True`, `image=True`, `text=True`, `schedule_owner=orchestrator`.
- Public module functions/methods: `auth_status`, `check_claims`, `create_telegram_module`, `delete`, `get_status`, `list_remote_items`, `prepare`, `publish`, `schedule_publish`, `update_media`, `update_metadata`, `upload`, `validate_config`.
- Explicit unsupported/deprecated boundaries: list_remote_items; upload; schedule_publish.
- Module note: Telegram module v1.0.0 ====================== Контракт PlatformModule: publish (at_slot), update_metadata (editMessageText), delete, auth_status (getMe+getChat). early_upload / schedule_publish — NotSupported.  Основной сценарий: post_mode=link — HTML-текст + link_preview_options.show_above_text + inline-кнопка на YouTube.
### threads
- State: **IMPLEMENTED** — implemented core provider path; live access/canary still required.
- Module version: `0.3.0`; publish mode: `direct`; content kind: `unknown`.
- Declared capabilities: `publish=True`, `delete=True`, `video=True`, `image=True`, `text=True`, `list_uploads=True`, `scan_mode=published_only`, `schedule_owner=orchestrator`.
- Public module functions/methods: `auth_status`, `check_claims`, `create_threads_module`, `delete`, `get_quota`, `get_status`, `list_remote`, `list_remote_items`, `prepare`, `publish`, `schedule_publish`, `update_metadata`, `upload`.
- Explicit unsupported/deprecated boundaries: early_upload; schedule_publish; update_metadata.
- Module note: threads module skeleton 0.1.0\nТребует B2; [ЖДЁТ] Meta.\n
### tiktok
- State: **IMPLEMENTED_INBOX** — implemented provider path with inbox/manual constraints.
- Module version: `0.4.0`; publish mode: `inbox`; content kind: `unknown`.
- Declared capabilities: `publish=True`, `video=True`, `list_uploads=True`, `scan_mode=published_only`, `schedule_owner=orchestrator`.
- Public module functions/methods: `auth_status`, `check_claims`, `create_tiktok_module`, `delete`, `get_status`, `list_remote`, `list_remote_items`, `prepare`, `publish`, `schedule_publish`, `update_metadata`, `upload`.
- Explicit unsupported/deprecated boundaries: schedule_publish — TikTok inbox is manual/confirm; update_metadata.
- Module note: tiktok module skeleton 0.1.0\ninbox v1; Direct Post audit — [ЖДЁТ].\n
### tumblr
- State: **PARTIAL_NATIVE** — native transport implemented but declared scope remains partial.
- Module version: `0.2.0`; publish mode: `direct`; content kind: `text`.
- Declared capabilities: `publish=True`, `update_metadata=True`, `delete=True`, `text=True`, `schedule_owner=orchestrator`, `content_kinds=['text']`, `content_kind_default=text`.
- Public module functions/methods: `auth_status`, `create_module`, `delete`, `get_status`, `prepare`, `publish`, `update_metadata`, `validate_config`.
- Module note: Tumblr: scaffold only. Native implementation requires provider-specific API/access/review work documented in the master roadmap.
### twitch
- State: **PARTIAL_NATIVE** — native transport implemented but declared scope remains partial.
- Module version: `0.1.0`; publish mode: `unsupported`; content kind: `clip`.
- Declared capabilities: `clips=True`, `scan_mode=auto`, `schedule_owner=platform`, `content_kinds=['clip']`, `content_kind_default=clip`.
- Public module functions/methods: `auth_status`, `create_clip`, `create_clip_from_vod`, `create_module`, `get_status`, `list_remote_items`, `prepare`, `publish`, `validate_config`.
- Explicit unsupported/deprecated boundaries: prepare/publish local media: Twitch Helix does not expose arbitrary file publishing; publish.
- Module note: Twitch: native Helix adapter for Clips.  The current Helix API supports creating clips from a live broadcaster stream and creating clips from VODs. It does not provide an arbitrary local-media upload/publish path, so PlatformModule.publish remains intentionally unsupported; use create_clip/create_clip_from_vod instead.
### viber
- State: **PARTIAL_NATIVE** — native transport implemented but declared scope remains partial.
- Module version: `0.1.0`; publish mode: `unsupported`; content kind: `text`.
- Declared capabilities: `schedule_owner=orchestrator`, `content_kind_default=text`, `messages=True`.
- Public module functions/methods: `auth_status`, `broadcast_message`, `create_module`, `get_user_details`, `handle_webhook`, `remove_webhook`, `send_message`, `set_webhook`, `verify_webhook`.
- Module note: Viber native Bot API messaging core: text/media/url send, account probe, webhook setup and HMAC-SHA256 webhook verification. Commercial bot access and HTTPS webhook remain external prerequisites.
### vk
- State: **IMPLEMENTED** — implemented core provider path; live access/canary still required.
- Module version: `0.2.0`; publish mode: `direct`; content kind: `video_native`.
- Declared capabilities: `publish=True`, `update_metadata=True`, `delete=True`, `video=True`, `image=True`, `text=True`, `list_uploads=True`, `scan_mode=published_only`, `schedule_owner=platform`, `content_kinds=['video_native', 'video_link', 'promo_text', 'image_carousel']`, `content_kind_default=video_native`.
- Public module functions/methods: `auth_status`, `create_vk_module`, `delete`, `get_status`, `list_remote_items`, `prepare`, `publish`, `publish_clip`, `schedule_publish`, `update_metadata`, `upload`.
- Explicit unsupported/deprecated boundaries: schedule_publish; vk clips: capability clips=false until API access.
- Module note: VK module 0.1.0 — video.save + wall.post + promo (text+image). Auth: community token (tokens/vk.json) or VK_ACCESS_TOKEN + VK_GROUP_ID. enabled: false by default until e2e + flood safety validated. See docs/runbooks/VK_SETUP.md
### wechat
- State: **IMPLEMENTED_NATIVE** — native transport implemented for declared scope.
- Module version: `1.0.0`; publish mode: `direct`; content kind: `text`.
- Declared capabilities: `publish=True`, `delete=True`, `text=True`, `scan_mode=auto`, `schedule_owner=orchestrator`, `content_kinds=['text']`, `content_kind_default=text`.
- Public module functions/methods: `auth_status`, `create_module`, `delete`, `get_status`, `list_remote_items`, `prepare`, `publish`, `update_metadata`, `validate_config`.
- Explicit unsupported/deprecated boundaries: update_metadata: published WeChat articles are managed through draft media_id before publication.
- Module note: WeChat Official Account: scaffold only. Native implementation requires provider-specific API/access/review work documented in the master roadmap.
### whatsapp
- State: **PARTIAL_NATIVE** — native transport implemented but declared scope remains partial.
- Module version: `0.1.0`; publish mode: `unsupported`; content kind: `text`.
- Declared capabilities: `schedule_owner=orchestrator`, `content_kind_default=text`, `messages=True`.
- Public module functions/methods: `auth_status`, `create_module`, `mark_read`, `send_message`, `upload_media`, `verify_webhook_signature`.
- Module note: WhatsApp Cloud API native messaging core: text, media-by-ID/link, templates, interactive payloads and phone identity probe. Production access still requires Meta Business/WABA/phone credentials and any required review/approval.
### whop
- State: **PARTIAL_NATIVE** — native transport implemented but declared scope remains partial.
- Module version: `1.0.0`; publish mode: `direct`; content kind: `text`.
- Declared capabilities: `publish=True`, `video=True`, `image=True`, `text=True`, `schedule_owner=orchestrator`, `content_kinds=['text', 'image', 'video']`, `content_kind_default=text`.
- Public module functions/methods: `auth_status`, `create_module`, `prepare`, `publish`, `validate_config`.
- Module note: Whop App API feed-content adapter.  Confirmed official surface: - POST /v5/app/feed_content_items - Bearer App API key authentication  The adapter maps feed content creation into the publish contract. It supports text and remote file attachments for image/video. Edit/delete/status are intentionally not claimed
### wordpress
- State: **IMPLEMENTED_NATIVE** — native transport implemented for declared scope.
- Module version: `0.2.0`; publish mode: `direct`; content kind: `article`.
- Declared capabilities: `publish=True`, `update_metadata=True`, `delete=True`, `text=True`, `list_uploads=True`, `list_private=True`, `scan_mode=auto`, `schedule_owner=orchestrator`, `content_kinds=['text', 'article']`, `content_kind_default=article`.
- Public module functions/methods: `auth_status`, `create_module`, `delete`, `get_status`, `list_remote_items`, `prepare`, `publish`, `update_metadata`, `validate_config`.
- Module note: # WordPress Native Module  Uses WordPress REST API with an Application Password. Configure `WORDPRESS_BASE_URL`, `WORDPRESS_USERNAME`, `WORDPRESS_APP_PASSWORD`.
### x
- State: **IMPLEMENTED** — implemented core provider path; live access/canary still required.
- Module version: `0.1.0`; publish mode: `direct`; content kind: `promo_text`.
- Declared capabilities: `publish=True`, `delete=True`, `video=True`, `image=True`, `text=True`, `schedule_owner=orchestrator`, `content_kinds=['promo_text', 'image_carousel']`, `content_kind_default=promo_text`.
- Public module functions/methods: `auth_status`, `create_x_module`, `delete`, `get_status`, `list_remote_items`, `prepare`, `publish`, `schedule_publish`, `update_metadata`.
- Explicit unsupported/deprecated boundaries: schedule_publish; update_metadata.
- Module note: X (Twitter) module 0.1.0 — text + up to 4 images. Auth: OAuth 2.0 PKCE user context (tokens/x.json) or X_ACCESS_TOKEN. enabled: false by default — Free/Basic tier limits; see docs/runbooks/X_API_TIER.md Schedule: orchestrator-side only (native schedule limited).
### youtube
- State: **IMPLEMENTED** — implemented core provider path; live access/canary still required.
- Module version: `2.3.0`; publish mode: `direct`; content kind: `unknown`.
- Declared capabilities: `publish=True`, `early_upload=True`, `schedule_publish=True`, `update_metadata=True`, `delete=True`, `thumbnail=True`, `claims_check=manual`, `video=True`, `list_uploads=True`, `list_scheduled=True`, `list_private=True`, `scan_mode=auto`, `schedule_owner=platform`.
- Public module functions/methods: `auth_status`, `check_claims`, `clear_schedule`, `create_youtube_module`, `delete`, `get_quota`, `get_status`, `list_remote_items`, `prepare`, `publish`, `schedule_publish`, `update_metadata`, `upload`, `validate_config`.

## 8. Capability semantics

- `publish`: provider can create the declared content type through its native/partner transport.
- `update_metadata`: provider exposes a supported update path for the declared resource.
- `delete`: provider can remove the remote resource within its scope.
- `schedule_publish`: provider supports create-time or native schedule semantics.
- `list_uploads` / `list_remote_items`: provider exposes remote inventory/reconciliation.
- `messages`: provider is message-oriented; publication semantics are intentionally separate from publishing modules.
- `public_media_required`: provider expects a publicly reachable media URL before create/publish.
- `claims_check`: claim verification is separate from ordinary status reconciliation.


## 9. Operational safety features

- read-only mode via `ORCH_READ_ONLY` / `--read-only`;
- single-instance pidfile;
- TLS verification enabled by default in shared HTTP client;
- correlation/request IDs on provider requests;
- retry/backoff only for safe/idempotent operations or explicitly idempotent POSTs;
- durable outbox + durable jobs + lease/retry/DLQ;
- provider/account isolation and circuit state;
- account-scoped token rotation/revoke/quarantine;
- webhook signature/challenge checks where provider supports them;
- remote reconciliation and lost-response recovery;
- SQLite backup + quick-check + restore tooling;
- readiness/liveness plus disk/backup/token-expiry health checks;
- static/dry canary for all 42 provider registrations;
- live canary is explicit opt-in and never implied by static/dry success.

## 10. External dependencies that are not code-completable

- real provider credentials and account identifiers;
- provider-side app review/advanced permissions/allowlist where required;
- production HTTPS redirect URIs and webhook endpoints;
- commercial/partner access for Rutube;
- live canary execution against real accounts;
- providers explicitly marked FEASIBILITY/API_DEPRECATED remain fail-closed rather than pretending to publish.

## 11. Audit interpretation

A green test suite proves the checked local contracts. It does not prove third-party account approval, quota, or live account acceptance. The catalog state and manifest capabilities are the canonical source for what the code claims to support.

