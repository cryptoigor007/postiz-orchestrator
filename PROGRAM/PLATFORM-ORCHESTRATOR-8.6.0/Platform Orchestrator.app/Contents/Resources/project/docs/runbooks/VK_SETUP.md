# VK Setup

## Auth
1. Create standalone VK app or use community token with scopes: `video`, `wall`, `photos`, `offline`.
2. Store token in `tokens/vk.json` (mode 0600) or set `VK_ACCESS_TOKEN` + `VK_GROUP_ID`.
3. Set `platforms.vk.group_id` and `platforms.vk.enabled: true` after e2e.

## Modes
- `video` — video.save → upload → optional wallpost
- `promo` — wall.post text + photo from cover/frames (content_kind=promo_text)
- `link` — wall.post with YouTube URL attachment

## Flood / rate
API errors 6 / 9 / 29 → safety pause (module maps to RATE_LIMIT).

## Schedule
Native `publish_date` on wall.post; video schedule prefer orchestrator hold.

See also: platforms/vk/README.txt
