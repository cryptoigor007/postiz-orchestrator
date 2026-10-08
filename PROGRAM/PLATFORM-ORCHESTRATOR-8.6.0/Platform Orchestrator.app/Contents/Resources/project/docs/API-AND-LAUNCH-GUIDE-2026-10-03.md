# Platform Orchestrator 8.6.0 — запуск, установка и API/Developer Access Playbook

**Версия документа:** 2026-10-03  
**Проект:** Platform Orchestrator 8.6.0  
**Назначение:** один практический runbook для запуска проекта и получения реального API / Developer Access / Review / Advanced Access по всем 42 провайдерам, присутствующим в этой сборке.

> В этом документе под «AP» понимается **API / Developer Access**. Это не одно универсальное разрешение: у разных платформ это может называться API access, Developer access, Trial/Standard tier, Advanced Access, App Review, Audit, partner access или просто token/app-password.

## 0. Главное: как запускать

### Linux / macOS из распакованного полного архива

Установка + запуск одним действием:

```bash
chmod +x install.sh start.sh START.command
./install.sh
```

`./install.sh` создаёт `.venv`, устанавливает зависимости из `requirements.lock`, создаёт базовые каталоги/конфиг, выполняет smoke и затем запускает daemon на `127.0.0.1:8080`.

Только установка/подготовка, **без запуска**:

```bash
./install.sh --no-start
```

Сразу запустить из уже подготовленного каталога:

```bash
./start.sh
```

`start.sh` сам создаёт `.venv` и устанавливает зависимости, если их ещё нет.

### Linux systemd

Подготовить и установить systemd:

```bash
sudo ./install.sh --systemd --prod
```

Обычный `./install.sh --no-start --systemd` только пишет unit и **не** включает/не запускает сервис.

### macOS Finder

Основной способ: **двойной клик по `Platform Orchestrator.app`**.

Запасной способ: **двойной клик по `START.command`**.

`.app` хранит runtime-релиз в:

```text
~/Library/Application Support/Platform Orchestrator/
```

Это сделано намеренно: при обновлении приложения пользовательские `config.yaml`, `.env`, `tokens/`, `data/`, `backups/` и `logs/` не должны лежать внутри неизменяемого App Bundle.

### Windows

Установка:

```text
install.bat
```

Запуск:

```text
start.bat
```

`start.bat` использует `requirements.lock`, если файл присутствует, создаёт `.venv` только при необходимости, выполняет smoke и останавливается при ошибке вместо запуска поверх сломанной установки.

### После запуска

```text
Panel:  http://127.0.0.1:8080/webapp/
Health: http://127.0.0.1:8080/health
```

До настройки реальных токенов первый запуск рекомендуется делать в dry-run/read-only режиме.

---

# 1. Как реально получать API Access: базовый принцип

Нет универсального правила «нужно отправить 4+ письма». Более того, повторные одинаковые обращения не дают технического права на доступ. Там, где доступ проверяется вручную, решают обычно:

1. **Правильное приложение.** Название, сайт, privacy policy, terms/contact должны быть реальными и совпадать с тем, что показано в демонстрации.
2. **Правильный use case.** Нужно описывать фактическое действие: например, публикация контента в собственные каналы/страницы, которыми владеет или управляет пользователь.
3. **Минимальные необходимые scopes.** Не запрашивать весь набор «на всякий случай».
4. **Реальный OAuth flow.** Не собирать логины и пароли пользователей, не использовать cookies/session scraping.
5. **Живая демонстрация.** Если платформа просит screencast/video demo, надо показать именно авторизацию и фактический API call.
6. **Business identity, когда она требуется.** Verified domain, business email, legal entity, owner/admin of the target Page/Business Account.
7. **Сначала тестовый/Development/Trial доступ, потом Standard/Advanced/Audit.** Для ряда платформ это специально задуманный путь.

### Что обычно повышает вероятность нормального review

Показывать один реальный сценарий целиком:

```text
Пользователь -> OAuth -> доступ к своему аккаунту/странице
           -> оркестратор создаёт один тестовый пост
           -> API возвращает ID
           -> оркестратор проверяет status
```

Для media-платформ:

```text
OAuth -> upload/init media -> publish -> status/reconcile
```

В заявке нужно писать именно это. Не стоит писать, что система делает то, чего текущий код не делает, или заявлять масштаб/число клиентов, которого нет.

### Почему может казаться, что «нужно много писем»

На некоторых платформах несколько независимых подтверждений создают ощущение «много писем»: например, business email verification, подтверждение организации/домена, Page admin verification, отдельная форма доступа и затем Standard/Advanced request. Это **несколько этапов процесса**, а не правило по числу писем.

---

# 2. Общий пакет для App Review / Advanced Access

Подготовить один набор и адаптировать его под платформу:

```text
App name: Platform Orchestrator
Company / owner: <реальное имя/юрлицо>
Website: https://<реальный-домен>
Privacy policy: https://<реальный-домен>/privacy
Terms: https://<реальный-домен>/terms
Support: https://<реальный-домен>/support или email
Callback: https://<реальный-домен>/webapp/api/oauth/callback/<provider>
```

### Описание use case

Пример для собственного проекта:

> Платформа используется владельцем для централизованного планирования и публикации собственного контента в аккаунты и страницы, которыми он управляет. Пользователь авторизует подключение через официальный OAuth/API flow. Сервис хранит OAuth/access tokens защищённо и использует их только для заявленных publish/read операций. Система не собирает пароли пользователей и не использует scraping/browser automation для обхода API.

Менять этот текст под реальную ситуацию. Не заявлять multi-user SaaS, если приложение используется только владельцем.

### Demo video

Показать:

1. Developer Console с названием приложения.
2. Реальный OAuth login.
3. Согласие со scopes.
4. Возврат на callback.
5. Один тестовый publish.
6. Полученный post/pin/video ID.
7. Status/reconciliation.
8. Где пользователь может отозвать доступ.

Не показывать секреты, client secret, refresh token или полный access token.

---

# 3. Все 42 системы

Статусы ниже — **статусы именно этой сборки**, а не обещание, что платформа сама по себе открыта для API.

- **IMPLEMENTED / IMPLEMENTED_NATIVE** — в коде есть рабочий transport для заявленной операции.
- **PARTIAL_NATIVE** — есть native transport, но есть существенные ограничения.
- **IMPLEMENTED_INBOX** — интеграция существует, но публикация зависит от отдельного approval/audit; текущая семантика может быть inbox/manual/private.
- **PARTNER** — нужен отдельный договор/partner access.
- **SCAFFOLD / FEASIBILITY** — не тратить время на получение токена для отсутствующей native publish-функции.
- **NOT_LIVE** — ни один провайдер в этой сборке не считается live только потому, что manifest существует.

---

## 3.1 YouTube

**Статус:** IMPLEMENTED  
**Auth:** OAuth 2.0 Authorization Code  
**Scopes в коде:** `youtube.upload`, `youtube`, `youtube.force-ssl`  
**Конфиг:** `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_TOKENS_PATH`

### Как получить доступ

1. Создать Google Cloud project.
2. Enable **YouTube Data API v3**.
3. Настроить OAuth consent screen.
4. Создать OAuth client.
5. Зарегистрировать redirect URI оркестратора.
6. Запустить OAuth authorization.
7. Авторизовать именно тот YouTube/Google account, чей канал должен публиковаться.
8. Получить refresh/access token.
9. Выполнить один реальный тестовый upload.
10. Для публичного стороннего приложения пройти требуемую Google verification для sensitive scopes.

### Правильная ситуация для review

Показывать загрузку одного собственного видео в собственный канал и объяснять scopes как необходимые для upload/status/update. Не просить лишние scopes.

### Важное

Публичные данные могут работать по API key, но **upload/update/delete требуют OAuth token**.

Official:
- https://developers.google.com/youtube/v3/getting-started
- https://developers.google.com/youtube/v3/guides/uploading_a_video
- https://developers.google.com/youtube/v3/guides/auth/server-side-web-apps

---

## 3.2 Instagram

**Статус:** IMPLEMENTED  
**Auth:** Meta OAuth  
**Scopes в текущем flow:** `instagram_basic`, `instagram_content_publish`, плюс page-related scopes, используемые Meta/IG связкой.  
**Конфиг:** `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_USER_ID`

### Как получать доступ

1. Создать Meta app.
2. Выбрать/подключить именно тот Meta product/login path, который соответствует текущему коду.
3. Подготовить Instagram professional account и соответствующую Meta/Facebook связку, если используется Facebook Login path.
4. Добавить OAuth redirect URI.
5. Получить тестовый user token.
6. Проверить identity/media permissions.
7. Для публикации пройти нужный Meta App Review/Advanced Access, если dashboard его требует.
8. Обеспечить **публичный media host** для media URL, поскольку текущий модуль создаёт media containers через URL.
9. Сделать один тестовый publish и reconcile.

### Критически важно

Не смешивать Instagram Login и Facebook Login/Pages flow в одной конфигурации вслепую. Сначала зафиксировать, какой Meta auth path использует приложение, какие account/page связи ему нужны, и только потом запрашивать scopes.

---

## 3.3 Facebook Pages

**Статус:** IMPLEMENTED  
**Auth:** Meta Page OAuth/token  
**Основные permissions в проекте:** `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`  
**Конфиг:** `FACEBOOK_PAGE_ID`, `FACEBOOK_PAGE_TOKEN`, `META_GRAPH_VERSION`

### Правильный путь

1. Создать Meta app.
2. Подключить Pages/Graph API functionality.
3. Авторизовать пользователя, который является реальным администратором/управляющим страницы.
4. Получить user/page access token.
5. Проверить `pages_show_list` → получить Page ID.
6. Проверить page token на `pages_read_engagement`/`pages_manage_posts`.
7. При необходимости пройти Meta App Review/Advanced Access.
8. Сделать один тестовый Page post.

### Для review

Показывать реальную страницу, реального admin пользователя и один проход OAuth → Page selection → publish.

---

## 3.4 Threads

**Статус:** IMPLEMENTED  
**Scopes:** `threads_basic`, `threads_content_publish`  
**Конфиг:** `THREADS_ACCESS_TOKEN`, `THREADS_USER_ID`

### Как получать

1. Создать Meta/Threads app.
2. Включить Threads API.
3. Настроить OAuth.
4. Запросить `threads_basic`.
5. Для публикации запросить `threads_content_publish`.
6. Если dashboard требует Advanced Access для publish — пройти его.
7. Токен должен быть **Threads token**, а не просто Facebook Page token.
8. Создать контейнер контента и затем выполнить publish.

Official:
- https://developers.facebook.com/documentation/threads/get-started
- https://developers.facebook.com/documentation/threads/get-started/get-access-tokens-and-permissions
- https://developers.facebook.com/documentation/threads/create-posts

---

## 3.5 TikTok

**Статус:** IMPLEMENTED_INBOX  
**API:** Content Posting API / Direct Post  
**Scopes:** `video.upload`, `video.publish`  
**Конфиг:** `TIKTOK_ACCESS_TOKEN`, `TIKTOK_CREATOR_INFO`

### Правильный маршрут

1. Создать TikTok for Developers app.
2. Подключить **Content Posting API**.
3. Включить Direct Post, если он доступен в dashboard.
4. Добавить нужный redirect URI.
5. Запросить `video.upload` / `video.publish`.
6. Авторизовать реальный TikTok creator account.
7. Реализовать и показать creator_info → upload/init → publish.
8. Подать client/app на audit.

### Почему здесь часто «не работает»

У TikTok есть отдельная разница между **unaudited client** и прошедшим audit client. Unaudited Direct Post может быть ограничен private visibility. Ошибка `unaudited_client_can_only_post_to_private_accounts` — ожидаемый сигнал, а не проблема токена.

### Для review

Показывать реальную публикацию собственного вертикального видео, официальный OAuth, отсутствие сбора пароля и соответствие Content Sharing Guidelines.

Official:
- https://developers.tiktok.com/doc/content-posting-api-get-started/
- https://developers.tiktok.com/doc/content-posting-api-reference-direct-post/
- https://developers.tiktok.com/doc/content-sharing-guidelines/

---

## 3.6 X

**Статус:** IMPLEMENTED  
**Auth:** OAuth 2.0 PKCE  
**Scopes:** `tweet.read`, `tweet.write`, `users.read`, `media.write`  
**Конфиг:** `X_ACCESS_TOKEN` или `tokens/x.json`

### Как получать

1. Создать Developer Project/App в X Developer Portal.
2. Включить write access, соответствующий текущему API plan.
3. Настроить OAuth 2.0 redirect URI.
4. Получить user authorization через PKCE.
5. Убедиться, что токен реально имеет `tweet.write` и `media.write`.
6. Сделать один text post, затем один media post.

### Важное

X API access и цена/лимиты зависят от текущего developer plan. Считать API «бесплатным навсегда» нельзя; проверять текущие условия в Developer Portal перед live.

---

## 3.7 VK

**Статус:** IMPLEMENTED  
**Auth:** Community token  
**Scopes в проекте:** `video`, `wall`, `photos`, `offline`  
**Конфиг:** `VK_ACCESS_TOKEN`, `VK_GROUP_ID` или `tokens/vk.json`

### Как получать

1. Создать/выбрать VK community.
2. Получить community token в API settings сообщества.
3. Выдать необходимые права (`wall`, `photos`, `video`, `offline`).
4. Указать Group ID.
5. Проверить `wall.post` и `video.save` на реальном тестовом материале.
6. Только после e2e-проверки включать provider в production config.

---

## 3.8 LinkedIn

**Статус:** PARTIAL_NATIVE  
**Auth:** OAuth 2.0  
**Основная задача:** organization/company-page publishing.  
**Конфиг:** `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_AUTHOR_URN`, `LINKEDIN_API_VERSION`

### Это один из самых важных review-провайдеров

LinkedIn Community Management имеет Development Tier и Standard Tier. Development требует vetting: approved use case, verified business email, verified organization, verified organization website/domain и LinkedIn Page associated with the same organization. Standard требует отдельный запрос и screencast use cases.

### Правильная стратегия

1. Создать приложение на реальную организацию.
2. Привязать правильную LinkedIn Page.
3. Использовать verified business email.
4. Настроить website/domain и privacy policy.
5. Получить Development Tier.
6. Создать **реальный тестовый пост** для страницы.
7. Только после работоспособного Development flow подать Standard request.
8. В Standard video показать каждый use case, указанный в форме.

### Важно

`r_member_social` в текущей программе закрыт для новых запросов. Не строить заявку вокруг чтения произвольных member posts, если это не предоставленный вам permission.

Также Marketing API Version 202510 должна перейти в sunset **15 октября 2026**; в этой сборке версия вынесена в `LINKEDIN_API_VERSION`, поэтому её нужно обновить перед live после этой даты.

Official:
- https://learn.microsoft.com/en-us/linkedin/marketing/community-management/community-management-overview
- https://learn.microsoft.com/en-us/linkedin/marketing/community-management/community-management-app-review
- https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api

---

## 3.9 Pinterest

**Статус:** PARTIAL_NATIVE  
**Auth:** OAuth 2.0  
**Конфиг:** `PINTEREST_ACCESS_TOKEN`, `PINTEREST_BOARD_ID`

### Правильная лестница доступа

1. Нужен Pinterest Business Account.
2. Подключить/создать developer app.
3. Подать на Trial access.
4. Настроить OAuth с точным redirect URI.
5. Получить token и создать sandbox/trial Pin.
6. Проверить реальный end-to-end flow.
7. Для Standard access подать upgrade.
8. В Standard request приложить **video recording OAuth flow + live Pinterest integration**.

Если вы единственный пользователь API, demo video всё равно требуется для Standard. Trial Pins/Boards имеют sandbox-ограничения.

### Media

Для video Pin официальная схема — register media → upload → confirm media → create Pin с `source_type=video_id`, `media_id` и `cover_image_url`.

Official:
- https://developers.pinterest.com/docs/key-concepts/access-tiers/
- https://developers.pinterest.com/docs/work-with-organic-content-and-users/create-boards-and-pins/
- https://developers.pinterest.com/docs/developer-tools/sandbox/

---

## 3.10 Reddit

**Статус:** PARTIAL_NATIVE  
**Auth:** OAuth 2.0  
**Конфиг:** `REDDIT_ACCESS_TOKEN`, `REDDIT_SUBREDDIT`, `REDDIT_USER_AGENT`

### Правильный путь

1. Создать/зарегистрировать приложение в Reddit Developer Platform.
2. Использовать OAuth.
3. Указать понятный User-Agent с названием приложения/версией.
4. Работать только с разрешёнными use cases и data access policies.
5. Проверить `/api/v1/me`.
6. Сделать один тестовый `api/submit` в контролируемый subreddit.

### Срочное изменение 2026

Для существующих Data API apps Reddit объявил отдельный Developer Platform registration process. В официальном объявлении указаны дедлайн регистрации **30 ноября 2026**, начало удаления доступа незарегистрированным apps/users **12 января 2027**, а дальнейшее прекращение оставшегося public API access — **март 2027**.

Не ждать последнего момента.

Official:
- https://developers.reddit.com/docs/next/faq
- https://support.reddithelp.com/hc/en-us/articles/49972004244244-Reddit-s-Developer-Platform-How-to-access-Reddit-data

---

## 3.11 Bluesky

**Статус:** PARTIAL_NATIVE  
**Auth:** App Password  
**Конфиг:** `BLUESKY_HANDLE`, `BLUESKY_APP_PASSWORD`, `BLUESKY_SERVICE`

Здесь не нужен классический enterprise App Review. Создайте Bluesky account, в настройках аккаунта создайте **App Password**, используйте handle + app password через AT Protocol.

Это один из самых простых provider access paths: не пытаться получать «Developer approval», которого для базового сценария нет.

---

## 3.12 Mastodon

**Статус:** IMPLEMENTED_NATIVE  
**Auth:** OAuth 2.0 per instance  
**Конфиг:** `MASTODON_BASE_URL`, `MASTODON_ACCESS_TOKEN`

### Как получать

1. Определить конкретный Mastodon instance.
2. Зарегистрировать приложение на instance через `/api/v1/apps`.
3. Запросить нужные scopes, минимум publish/write для вашего use case.
4. Пройти пользовательский OAuth на этом instance.
5. Получить bearer token.
6. Сохранить base URL instance и token для конкретного аккаунта.

Главная особенность: это **instance-scoped** access, а не единая центральная заявка.

Official:
- https://docs.joinmastodon.org/methods/apps/
- https://docs.joinmastodon.org/methods/statuses/

---

## 3.13 Tumblr

**Статус:** PARTIAL_NATIVE  
**Auth:** OAuth 1.0a  
**Конфиг:** `TUMBLR_CONSUMER_KEY`, `TUMBLR_CONSUMER_SECRET`, `TUMBLR_OAUTH_TOKEN`, `TUMBLR_OAUTH_TOKEN_SECRET`, `TUMBLR_BLOG`

Создать Tumblr application, настроить callback, пройти OAuth 1.0a, получить consumer key/secret и user access token/secret. Для этого модуля основной publish scope — text.

---

## 3.14 Telegram

**Статус:** IMPLEMENTED  
**Auth:** Bot token  
**Конфиг:** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_PUBLISH_CHAT_ID`

### Действия

1. Открыть `@BotFather`.
2. Создать bot.
3. Получить bot token.
4. Добавить bot администратором в целевой channel/group с нужными правами.
5. Указать `chat_id`.
6. Проверить `getMe` и `getChat`.
7. Сделать один тестовый message.

Здесь обычный bot flow не требует App Review. Главный источник отказов — неправильно выбранный channel/chat ID или недостаточные права бота.

---

## 3.15 WhatsApp Cloud API

**Статус:** PARTIAL_NATIVE; текущая сборка — messaging core, не generic social-post publisher.  
**Auth:** Meta Business / WABA credentials  
**Конфиг:** `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_GRAPH_BASE_URL`, `WHATSAPP_GRAPH_VERSION`

### Действия

1. Создать Meta Business.
2. Создать/подключить WhatsApp Business Account.
3. Добавить/верифицировать business phone number.
4. Создать Meta app и включить WhatsApp product.
5. Настроить system user/access token или требуемый Cloud API auth path.
6. Проверить phone number ID.
7. Отдельно пройти Meta business/app review, если конкретный production use case этого требует.
8. Тестировать messaging/templates, а не пытаться использовать WhatsApp как generic feed.

---

## 3.16 Viber

**Статус:** PARTIAL_NATIVE; messaging only  
**Auth:** Bot API token  
**Конфиг:** `VIBER_AUTH_TOKEN`, `VIBER_API_URL`

Создать bot/account через Viber business/bot tooling, получить auth token, поднять HTTPS webhook и зарегистрировать его. Для текущего проекта не считать Viber generic feed publisher.

---

## 3.17 Messenger

**Статус:** SCAFFOLD  
**Auth:** Page access token path предусмотрен metadata, но publish transport для этой сборки не заявлен.

Не тратить время на попытку «включить» Messenger в конфиге как publishing provider. Сначала нужен отдельный native implementation.

---

## 3.18 Instagram Messaging

**Статус:** SCAFFOLD  
**Auth metadata:** Meta access token  

Messaging/API access может быть получен через Meta, но в этой сборке это **не** live publish module. Не считать получение токена закрытием задачи Instagram Messaging.

---

## 3.19 LINE

**Статус:** PARTIAL_NATIVE; Messaging API  
**Auth:** Channel Access Token  
**Конфиг:** `LINE_API_URL`, `LINE_CHANNEL_SECRET`

### Действия

1. Создать LINE Official Account.
2. Создать/подключить Messaging API channel.
3. Получить channel access token.
4. Получить channel secret для webhook signature verification.
5. Настроить HTTPS webhook.
6. Указать recipient/user/group.
7. Проверить push message.

Официальные LINE docs отдельно описывают создание Official Account + Messaging API channel и виды channel access tokens.

---

## 3.20 WeChat Official Account

**Статус:** IMPLEMENTED_NATIVE  
**Auth:** App credentials → server access token  
**Конфиг:** `WECHAT_APP_ID`, `WECHAT_APP_SECRET`, `WECHAT_ACCESS_TOKEN`

Получается не обычный «личный social token»: нужен подходящий Official Account, AppID/AppSecret и server-side access token. Eligibility и доступность API зависят от типа аккаунта/рынка/актуальной политики WeChat. Сначала проверить, что именно ваш Official Account имеет нужный content API, затем получить token и выполнить identity probe.

---

## 3.21 Signal

**Статус:** FEASIBILITY; publish disabled  

Не получать токены через сторонние «Signal auto-post» сервисы и не строить browser automation. В текущем проекте нет официального server-side publish contract, на который можно честно опереться.

---

## 3.22 Discord

**Статус:** PARTIAL_NATIVE; webhook messaging core  
**Auth:** Webhook URL  
**Конфиг:** `DISCORD_WEBHOOK_URL`

Создать webhook в нужном Discord channel и использовать его URL. Это не полноценный bot/OAuth content publishing module. Если нужен именно bot-level access, потребуется отдельный native implementation.

---

## 3.23 Slack

**Статус:** PARTIAL_NATIVE; messaging core  
**Auth:** Bot token  
**Конфиг:** `SLACK_CHANNEL_ID`

1. Create Slack App.
2. Add Bot Token Scopes, включая нужный `chat:write`.
3. Install app to workspace.
4. Получить Bot User OAuth Token.
5. Добавить bot в channel.
6. Проверить `auth.test` и `chat.postMessage`.

Current module is messaging core, not generic social-feed publisher.

Official:
- https://api.slack.com/authentication/token-types
- https://api.slack.com/methods/chat.postMessage

---

## 3.24 Lemmy

**Статус:** IMPLEMENTED_NATIVE  
**Auth:** account credentials → JWT  
**Конфиг:** `LEMMY_BASE_URL`, `LEMMY_USERNAME`, `LEMMY_PASSWORD`, `LEMMY_COMMUNITY_ID`

Нет центрального developer review как у Meta. Выбирается конкретный Lemmy instance, регистрируется аккаунт, затем используется официальный REST login/JWT для post/create. Дальше всё зависит от policy конкретного instance/community.

---

## 3.25 MeWe

**Статус:** PARTIAL_NATIVE  
**Auth:** reviewed/beta API token + app id  
**Конфиг:** `MEWE_API_TOKEN`, `MEWE_APP_ID`, `MEWE_GROUP_ID`

Это не обычный public anonymous API. Нужен доступ к MeWe Open API / developer program, app id и token. В заявке честно указывать group-posting use case и показывать, что публикация идёт только в настроенную группу.

---

## 3.26 Whop

**Статус:** PARTIAL_NATIVE  
**Auth:** App API key  
**Конфиг:** `WHOP_API_KEY`, `WHOP_EXPERIENCE_ID`

Создать Whop developer app/experience, получить App API key и использовать official App API feed-content endpoint. Это community/feed API, а не universal social network publisher.

---

## 3.27 Skool

**Статус:** SCAFFOLD / FEASIBILITY  

Для этой сборки нет подтверждённого стабильного official direct REST publish contract. Не использовать browser automation или приватные endpoints, чтобы «обойти» отсутствие API.

---

## 3.28 Farcaster

**Статус:** PARTNER  
**Provider:** Neynar  
**Конфиг:** `NEYNAR_API_KEY`, `FARCASTER_FID`, `FARCASTER_SIGNER_UUID`

Это не чистый native protocol path в данном проекте. Нужен Neynar account/API key и signer для FID. В review/partner заявке честно указывать внешний provider dependency.

---

## 3.29 Nostr

**Статус:** IMPLEMENTED_NATIVE  
**Auth:** private key + relay URLs  
**Конфиг:** `NOSTR_PRIVATE_KEY`, `NOSTR_RELAY_URLS`

Нет центрального App Review. Создаётся keypair, выбираются relays и публикуются events. Основной риск — безопасность private key и выбор relay set.

---

## 3.30 Moltbook

**Статус:** IMPLEMENTED_NATIVE  
**Auth:** bearer API key  
**Конфиг:** `MOLTBOOK_API_KEY`, `MOLTBOOK_SUBMOLT`, `MOLTBOOK_API_BASE`

Получить developer/API key у сервиса, привязать нужный submolt и проверить identity/list/publish. Не пытаться использовать сторонние private endpoints.

---

## 3.31 Twitch

**Статус:** PARTIAL_NATIVE; Clips only  
**Auth:** OAuth 2.0 user token  
**Конфиг:** `TWITCH_CLIENT_ID`, `TWITCH_ACCESS_TOKEN`, `TWITCH_BROADCASTER_ID`

### Критично

Этот модуль **не загружает произвольный локальный видеофайл как новый Twitch video**. Он работает с Clips.

1. Зарегистрировать Twitch application.
2. Настроить OAuth.
3. Получить user access token с нужным Clips scope.
4. Указать broadcaster id.
5. Создать clip из live stream/VOD.

Текущая документация Twitch также требует user access token с Clips permissions для clip creation.

Official:
- https://dev.twitch.tv/docs/authentication/register-app/
- https://dev.twitch.tv/docs/api/reference
- https://dev.twitch.tv/docs/api/clips/

---

## 3.32 Kick

**Статус:** PARTIAL_NATIVE; channel metadata, publish disabled  
**Конфиг:** `KICK_ACCESS_TOKEN`, `KICK_BROADCASTER_USER_ID`, `KICK_CHANNEL_SLUG`

Для текущей сборки получение developer OAuth token не превращает Kick в local-video uploader: publish=false. Получать access только ради generic autoupload сейчас бессмысленно; сначала нужен отдельный native publish implementation и проверенный official endpoint.

---

## 3.33 Google Business Profile

**Статус:** IMPLEMENTED_NATIVE  
**Auth:** OAuth 2.0 + approved project access  
**Конфиг:** `GOOGLE_BUSINESS_ACCOUNT_ID`, `GOOGLE_BUSINESS_LOCATION_ID`

### Один из самых сложных Google access paths

Google Business Profile APIs доступны не любому проекту автоматически. Нужны:

1. Google account.
2. Реальный Business Profile и business reason.
3. Google Cloud project.
4. Organization/business identity, когда требуется.
5. Реальный business website.
6. Запрос access через официальный Google Business Profile API access process.
7. Email пользователя должен иметь нужную роль Owner/Manager на Business Profile.
8. После одобрения включить нужные APIs и OAuth.
9. Использовать `business.manage`.
10. Выполнить тестовый post/location action и проверить response.

Google отдельно отмечает, что API access approved на уровне проекта; при отсутствии approval можно видеть quota/access problems.

Official:
- https://developers.google.com/my-business/content/prereqs
- https://developers.google.com/my-business/content/basic-setup
- https://developers.google.com/my-business/reference/rest

---

## 3.34 Dribbble

**Статус:** IMPLEMENTED_NATIVE  
**Auth:** OAuth 2.0 bearer token  
**Config:** `DRIBBBLE_ACCESS_TOKEN`, `DRIBBBLE_TEAM_ID`

Создать developer application, получить OAuth access token со scope, позволяющим shot creation/upload. Текущий модуль ориентирован на image shots и не заявляет video shot creation.

---

## 3.35 WordPress

**Статус:** IMPLEMENTED_NATIVE  
**Auth:** Application Password для self-hosted WordPress  
**Конфиг:** `WORDPRESS_BASE_URL`, `WORDPRESS_USERNAME`, `WORDPRESS_APP_PASSWORD`

### Для собственного сайта

1. WordPress admin → Users → Profile.
2. Создать Application Password.
3. Убедиться, что HTTPS работает.
4. Использовать username + application password в модуле.
5. Проверить REST endpoint с Authorization.

### Для WordPress.com / multi-user third-party

Нужен полноценный OAuth2 app с client id/secret/redirect. Application Password shortcut не следует использовать как generic multi-user production auth.

Official:
- https://developer.wordpress.com/docs/api/getting-started/
- https://developer.wordpress.com/docs/api/oauth2/
- https://developer.wordpress.org/rest-api/using-the-rest-api/authentication/

---

## 3.36 Medium

**Статус:** FEASIBILITY / API_DEPRECATED

Не тратить время на попытки получить новый publish API token: проект намеренно fail-closed. В этой сборке Medium не считается рабочим destination для automated publish.

---

## 3.37 DEV.to

**Статус:** IMPLEMENTED_NATIVE  
**Auth:** API key  
**Конфиг:** `DEVTO_API_KEY`

Получить API key в настройках DEV account, проверить `/api/articles/me`, затем сделать один draft/published article через official API.

Official:
- https://developers.forem.com/api/v0

---

## 3.38 Hashnode

**Статус:** IMPLEMENTED_NATIVE  
**Auth:** Personal Access Token  
**Конфиг:** `HASHNODE_API_TOKEN`, `HASHNODE_PUBLICATION_ID`

Создать/получить PAT в аккаунте Hashnode, выбрать publication ID и проверить GraphQL/API mutation на один тестовый article. Не запрашивать более широкие permissions, чем реально требуются publication actions.

---

## 3.39 Listmonk

**Статус:** IMPLEMENTED_NATIVE  
**Auth:** API user + token / Basic Auth  
**Конфиг:** `LISTMONK_BASE_URL`, `LISTMONK_API_USER`, `LISTMONK_API_TOKEN`, `LISTMONK_LIST_IDS`

Это self-hosted system: никакой внешней App Review обычно не требуется. В Admin → Users создать API user/token и назначить только нужные list/campaign permissions.

Official:
- https://listmonk.app/docs/apis/apis/
- https://listmonk.app/docs/apis/campaigns/

---

## 3.40 RUTUBE

**Статус:** PARTNER  

Для автоматической загрузки нужен официальный partner arrangement. Не использовать reverse-engineered/private endpoints и не подменять partner access браузерной автоматизацией. В проекте provider остаётся fail-closed до получения официального partner contract + endpoint/schema + credentials.

---

## 3.41 beehiiv

**Статус:** IMPLEMENTED_NATIVE  
**Auth:** API key  
**Scopes/permissions в проекте:** publication/post read/write  
**Конфиг:** `BEEHIIV_API_KEY`, `BEEHIIV_ACCOUNT_ID`, `BEEHIIV_PUBLICATION_ID`

Создать developer/API key на аккаунте beehiiv, убедиться, что план/роль разрешает требуемые API operations, указать publication ID и проверить создание одного тестового post/article.

---

## 3.42 Snapchat Public Profile

**Статус:** PARTIAL_NATIVE  
**Auth:** OAuth bearer  
**Конфиг:** `SNAPCHAT_ACCESS_TOKEN`, `SNAPCHAT_PROFILE_ID`

### Особенность

Current module does not pretend to upload an arbitrary local file itself. Official flow uses provider-side media IDs / media upload containers and associated encryption/multipart metadata.

### Что делать

1. Create/enable Snapchat Public Profile API access.
2. Complete required business/developer application/allowlist process.
3. OAuth the public profile owner.
4. Implement official media upload flow and obtain provider media ID.
5. Use that media ID in Stories/Spotlight publish.
6. Verify inventory/status.

В текущей сборке arbitrary local-file → Snapchat publish одним вызовом не обещается.

---

# 4. Что именно писать в запросах на доступ

## LinkedIn — Development / Standard

**Формулировка должна быть правдивой.** Пример, если вы реально публикуете только в собственную Company Page:

> We are building an internal content scheduling and publishing tool for a company-owned LinkedIn Page. The application uses LinkedIn OAuth, stores access tokens securely, and creates organic Page posts on behalf of Page administrators. We do not collect LinkedIn passwords, use scraping, or access member data beyond the permissions required for the Page publishing use case. We can provide a live screencast showing OAuth authorization and the complete publish flow.

Для Standard добавьте конкретный список use cases из формы и покажите каждый в demo.

## TikTok — Direct Post / Audit

> The application is used by the account owner to publish original short-form video content to their TikTok account through the official Content Posting API. Users authenticate through TikTok OAuth. The app does not collect TikTok passwords and does not use browser automation or scraping. We can demonstrate creator_info, upload/init, publish, and status handling in a live environment. The content is owner-authored and the integration follows TikTok Content Sharing Guidelines.

## Pinterest — Standard

> The application creates Pins for a Pinterest Business account managed by the owner. The user authenticates through the official Pinterest OAuth flow. The application does not collect Pinterest passwords or session cookies. Our demo shows the live OAuth flow and the complete create-Pin integration, including media upload for supported Pin types.

## Google Business Profile — API access

> We use the Business Profile APIs to publish owner-authored updates to business locations that we manage. The Google account used for OAuth is an owner/manager of the Business Profile. The integration uses the minimum required Google APIs and the `business.manage` scope, does not scrape Search/Maps, and does not collect credentials. We can provide the business website, privacy policy, Cloud project details, and a live API demonstration.

## YouTube — OAuth / verification

> The application uploads and manages videos on channels authorized by the channel owner via Google OAuth. We request only the YouTube scopes required for upload and status management. We can demonstrate the complete OAuth flow and one real upload to an owner-controlled channel. The app does not collect Google passwords.

## Reddit — Developer access / registration

> The application accesses Reddit through the official OAuth Data API for a controlled content-publishing use case. The app uses a descriptive User-Agent, respects rate limits and Reddit Developer Terms, does not scrape the site, and does not bypass safety controls. We can demonstrate authentication, one controlled submission, and status reconciliation.

---

# 5. Как не получить отказ почти наверняка

1. Не писать «нам нужен полный API для автопостинга во все соцсети».
2. Не просить 10–20 scopes, если реально нужен только publish.
3. Не показывать моковый интерфейс вместо настоящего API.
4. Не скрывать, что это scheduler/orchestrator. Описывать реальные действия.
5. Не делать demo на чужом аккаунте без законного доступа.
6. Не использовать пароль пользователя вместо OAuth.
7. Не использовать scraping/cookies/private endpoints там, где официального API нет.
8. Не создавать несколько приложений только для обхода отказа, если правила провайдера запрещают такой путь.
9. Не отправлять одно и то же письмо в поддержку четыре раза. Сначала исправить конкретную причину отказа и подать корректный повторный request, если процедура разрешает.
10. Не путать sandbox/trial/dev access с production/standard/advanced access.

---

# 6. Идеальный порядок подключения именно для этого оркестратора

## Этап A — локально

```text
install → start → panel/health → dry-run → provider auth test
```

## Этап B — один тестовый destination

Подключить только один аккаунт/страницу/канал. Сделать:

```text
AUTH
IDENTITY
ONE TEST PUBLISH
STATUS CHECK
DELETE/cleanup where supported
```

## Этап C — review/upgrade

Только после реально работающего Development/Trial flow отправлять:

```text
App Review / Advanced Access / Standard Tier / Audit
```

## Этап D — live canary

Отдельно провести один real publish на владельческом аккаунте. После успешного canary подключать дополнительные account_id.

---

# 7. Быстрая таблица: что реально нужно получить

| Provider | Что нужно добыть | Review/approval | Что реально делает текущий модуль |
|---|---|---|---|
| YouTube | Google OAuth client + user refresh token | Для public app scopes — Google verification по требованиям | native video publish |
| Instagram | Meta app + IG/page OAuth token | Meta review/advanced access по dashboard | image/video publish |
| Facebook | Meta app + Page token | Meta review/advanced access по dashboard | Page publish |
| Threads | Threads OAuth token | `threads_content_publish` advanced access по требованиям | text/image/video publish |
| TikTok | TikTok OAuth token + Direct Post access | Direct Post audit для нужной visibility | currently inbox/manual semantics |
| X | OAuth2 PKCE user token | зависит от API plan | text + images |
| VK | Community token + Group ID | account/policy dependent | video/image/text |
| LinkedIn | OAuth2 + Page/org authorization | Development → Standard review | org/page posts; partial |
| Pinterest | OAuth2 token + Board ID | Trial → Standard + demo | Pins; partial |
| Reddit | OAuth2 token + subreddit + User-Agent | Developer Platform registration/policy | self/link posts |
| Bluesky | Handle + App Password | usually no centralized review for basic ATProto access | text/image |
| Mastodon | app token per instance | instance policy | text/image/video |
| Tumblr | OAuth1 consumer + user token | developer app | text |
| Telegram | Bot token + chat ID | no generic app review for bot basics | bot messages/publish |
| WhatsApp | WABA + phone + Meta auth | business/app review as required | messaging core, not feed |
| Viber | Bot token + HTTPS webhook | provider commercial/bot access | messaging core |
| Messenger | Page token | Meta requirements | scaffold only |
| Instagram Messaging | Meta token | Meta messaging requirements | scaffold only |
| LINE | Channel access token + secret | account/channel dependent | messaging core |
| WeChat | AppID + AppSecret + access token | account/API eligibility | text |
| Signal | none suitable for this project | no official publish contract | disabled |
| Discord | Webhook URL | no generic review for webhook | messaging core |
| Slack | Bot token + channel | workspace app install | messaging core |
| Lemmy | instance account + JWT | instance moderation/policy | text posts |
| MeWe | reviewed Open API app + token | reviewed/beta | group text/image |
| Whop | App API key + Experience ID | developer/app policy | text/image/video feed |
| Skool | none verified | no stable official publish API | scaffold |
| Farcaster | Neynar API key + FID + signer | partner/provider account | text casts |
| Nostr | private key + relays | none centralized | events/notes |
| Moltbook | API key + submolt | provider policy | text/link |
| Twitch | client ID + user token | account/app setup | clips, not local video upload |
| Kick | OAuth token | provider API eligibility | metadata only |
| Google Business | approved Cloud project + OAuth + business access | Google access request | business posts |
| Dribbble | OAuth2 token + upload scope | developer app | image shots |
| WordPress | Application Password for own site | none for own-site REST auth | article/text |
| Medium | none | API deprecated | disabled |
| DEV.to | API key | none for basic API key | article publish |
| Hashnode | PAT + publication ID | account access | article |
| Listmonk | API user/token | self-hosted admin | newsletter |
| RUTUBE | partner credentials | partner agreement | disabled until partner |
| beehiiv | API key + publication ID | plan/role dependent | text/article |
| Snapchat | OAuth + Public Profile/media IDs | allowlist/business/API access | Stories/Spotlight with provider media IDs |

---

# 8. Security rules for tokens

Никогда не помещать:

- client secret;
- refresh token;
- access token;
- private key;
- API key

в README, issue, demo video, git commit или screenshot review form.

Использовать `.env`, `tokens/*.json` или broker storage согласно config проекта. После live-canary удалить тестовые токены, если они больше не нужны.

---

# 9. Контроль перед тем, как объявлять provider «готовым»

```text
[ ] API/developer access obtained
[ ] OAuth/token works
[ ] identity probe works
[ ] one real publish works
[ ] status reconciliation works
[ ] error 401/403/429/5xx tested
[ ] token stored outside source
[ ] provider enabled explicitly in config
[ ] one live canary completed
[ ] only then multi-account enable
```

**Не считать provider live-ready только по наличию token.**

---

# 10. Источники и дата проверки

Этот playbook сверялся с локальным кодом/manifest'ами Platform Orchestrator 8.6.0 и с актуальными официальными developer-документами, доступными на **2026-10-03**.

Ключевые официальные источники:

- YouTube Data API: https://developers.google.com/youtube/v3/getting-started
- YouTube OAuth: https://developers.google.com/youtube/v3/guides/auth/server-side-web-apps
- YouTube upload: https://developers.google.com/youtube/v3/guides/uploading_a_video
- Meta Threads: https://developers.facebook.com/documentation/threads/get-started
- Meta Threads permissions: https://developers.facebook.com/documentation/threads/get-started/get-access-tokens-and-permissions
- Meta Threads publishing: https://developers.facebook.com/documentation/threads/create-posts
- TikTok Direct Post: https://developers.tiktok.com/doc/content-posting-api-reference-direct-post/
- TikTok Content Posting API: https://developers.tiktok.com/doc/content-posting-api-get-started/
- LinkedIn Community Management overview: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/community-management-overview
- LinkedIn App Review: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/community-management-app-review
- LinkedIn Posts API: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api
- Pinterest access tiers: https://developers.pinterest.com/docs/key-concepts/access-tiers/
- Pinterest Create Pins: https://developers.pinterest.com/docs/work-with-organic-content-and-users/create-boards-and-pins/
- Pinterest sandbox: https://developers.pinterest.com/docs/developer-tools/sandbox/
- Twitch API reference: https://dev.twitch.tv/docs/api/reference
- Twitch Clips: https://dev.twitch.tv/docs/api/clips/
- WordPress REST/OAuth: https://developer.wordpress.com/docs/api/oauth2/
- DEV API: https://developers.forem.com/api/v0
- listmonk API: https://listmonk.app/docs/apis/apis/
- Google Business Profile API: https://developers.google.com/my-business/content/basic-setup
- Mastodon Apps: https://docs.joinmastodon.org/methods/apps/
- LINE Messaging API: https://developers.line.biz/en/docs/messaging-api/getting-started/

---

# 11. Final rule

**Наша цель — не «выбить API любой ценой», а пройти официальный access path с минимально необходимыми разрешениями и реальным, демонстрируемым use case.**

Там, где provider официально не даёт подходящий server-side publishing contract, проект должен оставаться fail-closed. Это нормальный и безопасный результат, а не недоработка launcher'а.

## 13. Stage archives in the final distribution

The final distribution now includes four self-contained stage archives under `release-stages/`:

- `R0-INTEGRATION`: prove one real provider operation against an owner-controlled test destination.
- `R1-REVIEW`: provider-specific minimum-scope review build; unrelated providers/features stay disabled for the submission.
- `R2-CORRECTION`: only after rejection; change only the reviewer-requested blocker and preserve the exact evidence trail.
- `R3-PRODUCTION`: only after approval; add approved live accounts, perform the live canary, then enable scheduling/automation.

The stage archives are controlled states of the same core product, not separate architecture forks. The stage index and stage passports are in `docs/release-stages/`.
