# Подключение Facebook / Instagram / TikTok к Postiz — статус

Обновлено: 2026-09-23. Агент работал браузером на Mac (Chrome + CDP).

## Где что лежит

| Что | Где |
|---|---|
| Секреты владельца (пароли) | `/tmp/fbwork/.cred_fb`, `/tmp/fbwork/.cred_tt` (chmod 600) — **в git/отчёты не попадают** |
| Ключи приложений (когда будут) | `root@100.95.225.71:/root/tg_media_owner/apps.env` (chmod 600) |
| Скриншоты шагов | `/tmp/fbwork/shots/` |
| Профиль Chrome (с сессией Facebook) | `/tmp/fbwork` |

## Готово

- **Facebook: вход выполнен.** Аккаунт `Vasya Petrov`, логин — телефон `+37379799432` (он же логин, отдельная почта не потребовалась). Пароль из скриншота подошёл. Сессия сохранена в профиле `/tmp/fbwork`.
- **Регистрация разработчика Meta начата:** шаг `Register` пройден, остановились на шаге `Verify account` — Facebook отправил SMS-код на `0797 99 432 (Moldova)`. **Ждём код от владельца.**
- **TikTok:** портал `developers.tiktok.com/apps/` требует вход; форма входа имеет только `Email` + `Password`. Пароль есть, **нужен e-mail/логин владельца**.
- **Домен/OAuth решён:** Postiz доступен по `https://risks-missions-men-entire.trycloudflare.com` (валидный сертификат; `FRONTEND_URL` и `MAIN_URL` внутри контейнера уже обновлены). Проверено снаружи: медиа отдаётся HTTP 200.

- **Facebook: Страница создана** (см. раздел ниже).

## Facebook: Страница «Точка наблюдения» (создана)

| Параметр | Значение |
|---|---|
| Название | Точка наблюдения |
| ID Страницы | `61594683901231` |
| URL | https://www.facebook.com/profile.php?id=61594683901231 |
| Категория | «Автор видео Reels» (категории «Видеоблог» у Facebook нет — это ближайшая видеокатегория) |
| Описание | «Разборы психологии и поведения человека: короткие видео и полные выпуски.» |
| Аватар/обложка | не задавались |
| Привязки (WhatsApp, платежи, реклама) | не создавались, шаг WhatsApp пропущен |
| Публикация | опубликована (признаков «не опубликована»/черновика нет) |

Проверено: в разделе «Страницы, которыми вы управляете» ровно одна запись — «Точка наблюдения» (дубликата нет),
в правой панели профиля видны название, категория и описание.

## Redirect URI для приложений

```
https://risks-missions-men-entire.trycloudflare.com/integrations/social/facebook
https://risks-missions-men-entire.trycloudflare.com/integrations/social/instagram
https://risks-missions-men-entire.trycloudflare.com/integrations/social/tiktok
```
App Domains: `risks-missions-men-entire.trycloudflare.com`

> Бесплатный quick-туннель: при перезапуске адрес меняется — тогда правки нужны и в приложениях Meta/TikTok.

## Переменные окружения Postiz (имена; сейчас НЕ заданы ни одной)

```
FACEBOOK_APP_ID=      FACEBOOK_APP_SECRET=
INSTAGRAM_APP_ID=     INSTAGRAM_APP_SECRET=
TIKTOK_CLIENT_ID=     TIKTOK_CLIENT_SECRET=
FRONTEND_URL=https://risks-missions-men-entire.trycloudflare.com
```
После заполнения — перезапуск контейнера `postiz`.

## Права (scopes), которые запрашивает Postiz

- **Facebook** (`identifier = facebook`, отображается как «Facebook Page»): `pages_show_list`, `business_management`, `pages_manage_posts`, `pages_manage_engagement`, `pages_read_engagement`, `read_insights`
- **TikTok**: `video.list`, `user.info.basic`, `video.publish`, `video.upload`, `user.info.profile`, `user.info.stats`
- **Instagram**: `instagram.provider.ts` → `identifier = instagram`, redirect `/integrations/social/instagram`

## Блокеры, требующие владельца

1. **Код из СМС** для шага `Verify account` в регистрации Meta for Developers.
2. **E-mail/логин TikTok** — без него вход в портал разработчика невозможен.
3. ~~У аккаунта Facebook НЕТ ни одной Страницы~~ — **СНЯТО**: Страница создана (см. раздел ниже).
4. **App Review:** для сценария «владелец подключает свой собственный аккаунт/Страницу» приложение может оставаться в Development Mode (владелец — админ приложения). Проверка приложения и Business Verification понадобятся только если подключать чужие аккаунты.

## Побочно решённая задача: YouTube

Оба видео, загруженных Postiz 23.09.2026, найдены по ID из payload ошибки Postiz (в БД посты в состоянии `ERROR` — упал шаг `thumbnails.set`, поэтому `releaseURL` пуст, хотя видео опубликовано):

| URL | Название | Опубликовано (EEST) | Видимость |
|---|---|---|---|
| https://www.youtube.com/watch?v=7xbAkPUZ1Cc | В чём истинная причина зависти? | 23.09.2026 12:00 | публичное |
| https://www.youtube.com/watch?v=XMl5D9msO5E | Самое опасное слово в жизни | 23.09.2026 18:01 | публичное |

Обложки: кастомные НЕ применились (аккаунт YouTube не подтверждён), стоят автогенерированные кадры. Требуется верификация аккаунта (по телефону).
