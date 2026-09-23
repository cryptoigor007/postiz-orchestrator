# Финальный чеклист — ВЫПОЛНЕНО (v7.0.3)

## 1. Бизнес-логика и крайние случаи
- [x] 1.1 Авто-сброс pending series_end по TTL
- [x] 1.2 warmup после долгой паузы при resume
- [x] 1.3 e2e: long scheduled → published+url → thematic

## 2. БД
- [x] 2.1 Миграция schema_version (upgrade hook)
- [x] 2.2 Индексы на существующей БД

## 3. Postiz / устойчивость
- [x] 3.1 Mock: mark_published + release_url
- [x] 3.2 clear_orphan_media

## 4. Telegram
- [x] 4.1 /force_link_update тест
- [x] 4.2 status / platforms / tail

## 5. Проверки
- [x] 5.1 pytest зелёные (42)
- [x] 5.2 Smoke --version / --once
- [x] 5.3 Версия 7.0.3
