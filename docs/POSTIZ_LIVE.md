# Postiz live adapter (v7.3.1)

## Confirmed
- BASE: https://192-168-100-60.sslip.io (self-signed cert → `POSTIZ_VERIFY_TLS=0`)
- Auth: `Authorization: <api_key>` (raw, not Bearer) → `POSTIZ_AUTH_STYLE=raw`
- Upload: POST /public/v1/upload (multipart field `file`) → media `{ id, path }`
- Posts: POST/GET/DELETE /public/v1/posts
- Status: PUT /public/v1/posts/{id}/status
- Release: PUT /public/v1/posts/{id}/release-id
- Rate limit: 30/hour
- **integrationId required** on create

## Create-post body (Postiz CreatePostDto)
`HttpPostizClient.create_post` sends:
```json
{
  "type": "schedule",
  "shortLink": false,
  "date": "2026-09-19T15:00:00Z",
  "tags": [],
  "posts": [
    {
      "integration": { "id": "<integrationId>" },
      "value": [
        { "content": "текст", "image": [{ "id": "<mediaId>", "path": "<mediaUrl>" }] }
      ],
      "settings": {}
    }
  ]
}
```
- `type`: `schedule` when a time is given, else `now`
- `value[].image` needs both `id` and `path` (path is required by MediaDto)
- `settings.__type` is added server-side from the channel provider
- create response: `[{ "postId": "...", "integration": "..." }]`

## .env
```
POSTIZ_BASE_URL=https://192-168-100-60.sslip.io
POSTIZ_API_TOKEN=<key>
POSTIZ_AUTH_STYLE=raw
POSTIZ_PATH_UPLOAD=/public/v1/upload
POSTIZ_PATH_POSTS=/public/v1/posts
POSTIZ_VERIFY_TLS=0
TELEGRAM_BOT_TOKEN=<orchestrator bot>
```

## config.yaml
- platforms.telegram.enabled: true
- platforms.*.integration_id: paste from Postiz UI after connecting channel
- telegram.allowed_chat_ids: [7004751908, -5565497388]
- limits.postiz_create_per_hour: 30

## Connected (verified)
- Postiz Telegram publisher bot `TELEGRAM_TOKEN` set in Postiz compose
- Channel connected: `Postiz Test Channel`
- integrationId: `cmu7g6kjq0001rw6wbwh46plb` → `config.yaml` `platforms.telegram.integration_id`
- `POSTIZ_API_TOKEN` (org apiKey) set in `.env`; `/public/v1/integrations` returns the channel
- Live create verified: upload → create (schedule) → delete against real Postiz

## Still waiting
1. Orchestrator control bot token (`TELEGRAM_BOT_TOKEN`) from BotFather
2. release URL field name after first real published post
3. WATCH_ROOTS paths (VideoMaker/ShortsMaker output dirs)

