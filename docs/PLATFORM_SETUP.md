# Подключение площадок к Postiz (Фейсбук, ТикТок, Инстаграм)

## Коротко: почему пароля недостаточно

Postiz (наша ВМ 120, `postiz-*`) публикует в площадки через **официальные приложения площадок**.
Пароль от личного аккаунта для этого не подходит — нужны `Client ID/Secret` приложения-провайдера.

Факт по нашей установке (проверено 2026-09-23, `docker exec postiz printenv`):

| Провайдер | Ключи в контейнере | Канал подключён |
|---|---|---|
| Telegram | `TELEGRAM_TOKEN` | да — «Postiz Test Channel» |
| YouTube | `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET` | да — @testpostiz |
| Facebook | нет | нет |
| TikTok | нет | нет |
| Instagram | нет | нет |

Поэтому «Add channel» для Фейсбука/ТикТока/Инстаграма сейчас не заработает: приложение-провайдер
не зарегистрировано.

## Что нужно сделать владельцу (в его аккаунтах)

### 1. Meta (Фейсбук + Инстаграм)
1. Открыть https://developers.facebook.com/apps → **Create App** → тип «Business».
2. Добавить продукты: **Facebook Login** и (для Инстаграма) **Instagram Graph API**.
3. В настройках приложения взять **App ID** и **App Secret**.
4. В Basic Settings указать домен и Redirect URI нашего Postiz (тот же, где открывается панель Postiz,
   путь `/integrations/social/facebook` и `/integrations/social/instagram`).
5. Прислать App ID + App Secret (не пароль от личного аккаунта).

### 2. TikTok
1. Открыть https://developers.tiktok.com/ → **Manage apps** → **Connect an app**.
2. Добавить продукты: **Login Kit** и **Content Posting API** (scope `video.publish`/`video.upload`).
3. Взять **Client Key** и **Client Secret**.
4. Указать Redirect URI — тот же домен Postiz, путь `/integrations/social/tiktok`.
5. TikTok для прямой публикации обычно требует проверку приложения (audit): до неё доступна
   загрузка в черновики/приватно. Точные требования показывает кабинет на шаге подачи.
6. Прислать Client Key + Client Secret.

## Что делаю я, когда ключи получены

1. Вписываю их в `/home/postiz/postiz/docker-compose.yml` (переменные `FACEBOOK_APP_ID/SECRET`,
   `TIKTOK_CLIENT_ID/SECRET`, `INSTAGRAM_APP_ID/SECRET`), перезапускаю стек.
2. Проверяю, что в Postiz появились кнопки «Add channel» для этих площадок.
3. Владелец один раз входит и разрешает публикацию (вход и 2FA — только на его стороне).
4. Включаю площадки в конфиге оркестратора (`platforms.facebook.enabled`, `platforms.tiktok.enabled`),
   ставлю лимиты (Facebook 5/день, TikTok 7/день), добавляю в расписание.
5. Прогоняю тестовую публикацию и показываю результат.

## Адрес туннеля Postiz: он меняется, и это надо отслеживать

Postiz открывается наружу через **quick tunnel** Cloudflare (`cloudflared-postiz` на pve → `https://192.168.100.60`).
У quick-туннеля адрес вида `https://<случайное-имя>.trycloudflare.com` **меняется при каждом перезапуске**
(например `systemctl restart cloudflared-postiz`), а от него зависят две вещи:

1. **Контейнер Postiz (ВМ 120)** — три переменные в `/home/postiz/postiz/docker-compose.yml`:
   `MAIN_URL`, `NEXT_PUBLIC_BACKEND_URL` (тот же адрес + `/api`), `FRONTEND_URL`.
   После правки: `docker compose up -d` — пересоздаёт контейнер `postiz`.
2. **Кабинеты площадок** — Redirect URI (без него вход и подключение канала ломаются):

| Провайдер | Где менять | Что указать |
|---|---|---|
| Meta (Facebook + Instagram) | developers.facebook.com → приложение → Facebook Login → Valid OAuth Redirect URIs | `<адрес>/integrations/social/facebook` и `<адрес>/integrations/social/instagram` |
| TikTok | developers.tiktok.com → приложение → Login Kit → Redirect URI | `<адрес>/integrations/social/tiktok` |
| Google / YouTube | console.cloud.google.com → OAuth client → Authorized redirect URIs | `<адрес>/integrations/social/youtube` |

Проверка (скрипт только читает и печатает, что менять; ничего не правит и не перезапускает):

```bash
ssh root@<pve> 'bash /opt/orchestrator/scripts/postiz_tunnel_sync.sh'          # полный отчёт + готовые команды
ssh root@<pve> 'bash /opt/orchestrator/scripts/postiz_tunnel_sync.sh --check'  # как таймер: тихо, пока всё синхронно
```

Таймер `postiz-tunnel-sync.timer` запускает проверку каждые 30 минут и попадает в журнал **только**
при расхождении (`journalctl -u postiz-tunnel-sync.service`). Файл `/var/lib/cloudflared-postiz.url`
никто не обновляет автоматически — это просто заметка для человека, после смены адреса её стоит поправить.
Лучший способ не ловить эту проблему — не перезапускать `cloudflared-postiz` без необходимости.

## Хранение секретов

Пароли, присланные владельцем в Telegram, лежат в `/root/tg_media_owner/` (каталог `700`, файлы `600`),
в переписку и журналы не попадают. Ключи приложений идут в `docker-compose.yml` Postiz (на ВМ, права root).
