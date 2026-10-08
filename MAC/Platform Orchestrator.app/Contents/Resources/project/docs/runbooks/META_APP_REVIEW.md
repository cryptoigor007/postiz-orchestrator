# Meta App Review (Instagram / Facebook / Threads)

## Required assets
- Privacy Policy, Terms, Support URLs — see `docs/audit_site/`
- Use case: scheduling **own** content from VideoMaker folders (no scrape)
- Permissions (exact): `instagram_content_publish`, `pages_manage_posts`, `pages_read_engagement`, Threads publish scopes as needed
- Test users + screencast of schedule → publish flow
- Data deletion instructions

## Code readiness
- Fail-closed without public `media_host` URL for IG Reels (IG-02)
- Token refresh path; rate limit → safety pause
- Delete: IG NotSupported → UI disabled
- Schedule: orchestrator hold + finalize for IG; FB upload(when)

## Checklist
1. App mode Development → Live only after Review
2. Do not request unused scopes
3. Stage e2e with test users before production enable
