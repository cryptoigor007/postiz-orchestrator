# TikTok Content Posting API / App Review

## Modes
- **Direct Post**: creator_info/query required before init; audit may force SELF_ONLY
- **Inbox / draft**: uploaded_inbox ≠ published; user confirms in TikTok app

## Code
- EPS persists publish_id (not RAM-only)
- UI legend: uploaded_inbox / waiting_manual_publish distinct from published
- Rate ~6/min token; daily_limit in safety

## Review package
Consent screen wording, audit trail, product = Content Posting API.
See docs/dev/05_TIKTOK_AUDIT_PACKAGE.txt
