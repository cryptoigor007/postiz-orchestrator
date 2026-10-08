# F4 — postiz_* column retirement

schema_version: **18**

## Policy
- New writes use only: `external_id`, `external_sub_id`, `external_url`, `scheduled_for`, `source`, `lease_*`.
- Columns `postiz_post_id` / `postiz_scheduled_for` remain **nullable** (no SQLite DROP).
- Migration v17→v18 **backfills** external_id / scheduled_for from postiz_* when empty.
- StatusSync / Publisher / LinkUpdater do not require postiz_* (F2–F3).

## media_host_objects
Tracks B2 (and future hosts) file_id + file_name for TTL delete.
