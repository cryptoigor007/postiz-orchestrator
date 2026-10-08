# Чек-лист владельца — всё подготовлено на стороне Grok (90%)

Дата: 2026-09-25. Что сделать **вам** (каждый пункт — одно действие).

## A. Ключи и кабинеты (блокеры live)

| # | Действие | Куда вписать | После этого Grok |
|---|----------|--------------|------------------|
| 1 | Email для Meta Contact info (не mail.ru) | developers.facebook.com | дописать FACEBOOK_*/IG в compose |
| 2 | Email TikTok-аккаунта (developers.tiktok.com только email) | developers.tiktok.com | Login Kit + audit |
| 3 | YouTube: телефон на testPostiz + GCP app «In production» | YouTube Studio / Cloud Console | contract P2-R1 |
| 4 | B2: создать бакет + Application Key (без карты) | backblaze.com → .env B2_* | IG/Threads live |
| 5 | Стабильный tunnel/домен (named CF tunnel) | cloudflare + postiz compose | OAuth redirect не ломается |
| 6 | Ротация: POSTIZ_API_TOKEN, WEBAPP_ACCESS_KEY, TOKEN_BROKER_SECRET, TELEGRAM_BOT_TOKEN | .env 600 на сервере | передеплой broker |

## B. Contract (когда ключи есть)

```bash
export ORCH_CONTRACT=1
export TELEGRAM_BOT_TOKEN=...
export TELEGRAM_PUBLISH_CHAT_ID=...
PYTHONPATH=src python3 -m pytest tests/test_contract_templates.py -v
```

YouTube: tokens/youtube.json 600 + testPostiz channel.

## C. P5 (только после зелёных contract)

По одному:
1. `engines.telegram: module:telegram` → test-post → откат
2. `engines.youtube: module:youtube` → test-post → откат
3. Остальные

## D. Уже сделано без вас

- P2–P4 unit/registry/dry-run
- P6.1 B2 client dry-run
- IG/FB/TT/Threads API-каркас 0.2.0 dry-run
- daily_ahead (A2) чистая функция + unit
- Contract-шаблоны (skip без ORCH_CONTRACT)
- P7 HTML privacy/terms/support (плейсхолдеры)
- 70+ module unit tests

## E. Не делать

- Не коммитить .env/токены
- Не включать module:* в прод до P5
- Не обманывать TikTok review
