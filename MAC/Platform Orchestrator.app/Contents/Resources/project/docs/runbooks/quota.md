# Runbook: YouTube Quota
- Two buckets: upload_bucket (default 100), general_bucket
- posts_per_day is separate safety cap (not cost_upload 1600)
- daily_ahead reserves upload units; exhausted → stop
