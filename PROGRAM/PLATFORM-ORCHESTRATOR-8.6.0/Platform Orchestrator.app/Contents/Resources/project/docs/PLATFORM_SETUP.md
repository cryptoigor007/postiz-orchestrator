# Full access/launch playbook

See `docs/API-AND-LAUNCH-GUIDE-2026-10-03.md` for the complete installation, one-click launch, API access, App Review, Advanced Access and per-provider runbook.

# Подключение площадок (module path)

**HARD_CUT:** публикация идёт через in-process **platform modules** (`engines.<platform>=module:<id>`).
Legacy Postiz VM / HTTP transport **не required** для работы оркестратора.

## Обзор

| Площадка | Engine | Auth | Примечание |
|----------|--------|------|------------|
| YouTube | `module:youtube` | OAuth (`tokens/youtube.json` или token-broker) | early upload + schedule |
| Telegram | `module:telegram` | Bot token + chat_id | link / media mode |
| TikTok | `module:tiktok` | OAuth / App Review | inbox ≠ published |
| Instagram | `module:instagram` | Meta Graph | container → finalize |
| Facebook | `module:facebook` | Meta Graph | |
| Threads | `module:threads` | Meta | |

## Токены

```bash
mkdir -p tokens
# tokens/<platform>.json — chmod 600
# optional: TOKEN_BROKER_URL + TOKEN_BROKER_SECRET
```

См. также `docs/TOKEN_BROKER.md` (если есть) и `config.example.yaml` → секция `engines`.

## Meta / TikTok (внешние ограничения)

- App Review, квоты API, redirect URI приложений — на стороне Meta/TikTok Developer Console.
- Оркестратор **не** зависит от Postiz docker-compose / cloudflared-postiz tunnel.

## Исторический appendix

Раньше документация описывала Postiz VM (ВМ 120), `postiz-tunnel-sync`, `cloudflared-postiz`.
Это **deprecated** operational path. Не использовать как required onboarding.

## OAuth redirect URI (required)

Set in Google / Meta / TikTok developer console:

```
{ORCH_PUBLIC_BASE_URL}/webapp/api/oauth/callback/{provider}
```

Example: `https://orch.example.com/webapp/api/oauth/callback/youtube`

Callback is public (CSRF via OAuth `state`); tokens saved to `tokens/{provider}.json` (chmod 600).

First boot: `ORCH_READ_ONLY=1` or `--dry-run`, then STAGE one YT + one TG live.

