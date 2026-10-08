# PLATFORM ORCHESTRATOR 8.6.0 — ALL-IN-ONE FINAL

Это ЕДИНЫЙ архив поставки. Внутри всё разделено по назначению.

## 00. START HERE
- `START-HERE.md`
- `START-HERE-MASTER.md`
- этот файл

## 01. PROGRAM — основная полная программа
- `PROGRAM/PLATFORM-ORCHESTRATOR-8.6.0-PROGRAM-FINAL-STAGED-2026-10-03-v2.zip`

## 02. STAGES — четыре самостоятельных этапа
Каждый этап — отдельный ZIP внутри этого единого архива:
- `STAGES/PO-8.6.0-R0-INTEGRATION-2026-10-03-v2.zip`
- `STAGES/PO-8.6.0-R1-REVIEW-2026-10-03-v2.zip`
- `STAGES/PO-8.6.0-R2-CORRECTION-2026-10-03-v2.zip`
- `STAGES/PO-8.6.0-R3-PRODUCTION-2026-10-03-v2.zip`

## 03. MAC
- `MAC/` содержит готовый macOS `.app` и его архив.

## 04. DOCS
- API / Launch / Review guide
- release manifest
- stage archive manifest
- release report

## 05. CHECKPOINT
- rollback checkpoint + SHA256

## 06. CHECKS / SHA256
- результаты финальной автоматической проверки
- контрольные SHA256 всех ключевых артефактов

## Как использовать
Для обычной работы не нужно искать четыре отдельных скачивания: скачивается этот один ZIP.

После распаковки:
1. Основная программа находится в `PROGRAM/`.
2. Этапы R0/R1/R2/R3 находятся в `STAGES/`.
3. Для macOS готовый `.app` находится в `MAC/`.
4. Полная API/review инструкция находится в `DOCS/`.

Финальный автоматический результат предыдущей проверки: 987 passed / 5 skipped / 0 failed; final audit RC=0.
