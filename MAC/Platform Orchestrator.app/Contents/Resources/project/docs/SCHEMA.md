# Schema version policy

- Current: SCHEMA_VERSION in `src/orchestrator/db.py`
- On change: bump integer, add `if current < N:` migration, pre_migration backup
- Never lower SCHEMA_VERSION in released code
- Downgrade: restore SQLite backup only
- v20: `entity_platform_status.content_kind` (video_native|video_link|promo_text|image_carousel)
