# Manual Uploads — Plan 1: Engines core + data model

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use `- [ ]`.
> **Spec:** `docs/superpowers/specs/2026-09-19-manual-upload-matching-design.md`

**Goal:** Заложить ядро движков публикации и минимальную таблицу реестра ручных загрузок.

**Architecture:** Интерфейс `Destination` (publish/list/update/delete/claims/capabilities), реестр возможностей и выбор движка из конфига. Одна новая таблица `platform_uploads`. Существующий Postiz-путь не переписываем (только адаптер-обёртка).

**Tech Stack:** Python 3.12, sqlite3, pydantic, pytest.

**Global Constraints:**
- Не раздувать: 1 новая таблица; альтернативы кандидатов не храним.
- Идемпотентность: ключ `(engine, platform, external_id)`.
- Не ломать существующие тесты (`pytest -q`).

---

### Task 1: Таблица `platform_uploads` + доступ к данным

**Files:**
- Modify: `src/orchestrator/db.py` (SCHEMA, `_migrate`, методы)
- Test: `tests/test_uploads_db.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_uploads_db.py
from orchestrator.db import Database

def test_upsert_upload_idempotent(tmp_path):
    db = Database(tmp_path / "u.sqlite")
    a = db.upsert_upload(engine="direct", platform="youtube", external_id="vid1",
                         url="https://y/vid1", title="T", published_at="2026-09-01T10:00:00+00:00",
                         origin="manual", view=[])
    assert a["match_status"] == "unmatched"
    b = db.upsert_upload(engine="direct", platform="youtube", external_id="vid1",
                         url="https://y/vid1", title="T2", published_at="2026-09-01T10:00:00+00:00",
                         origin="manual", view=[])
    assert b["id"] == a["id"] and b["title"] == "T2"
    assert len(db.list_uploads()) == 1
```

- [ ] **Step 2: Run — FAIL** (`upsert_upload` missing)

- [ ] **Step 3: Implement** — добавить в `SCHEMA` (и поднять `SCHEMA_VERSION = 9`):

```sql
CREATE TABLE IF NOT EXISTS platform_uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    engine TEXT NOT NULL,
    platform TEXT NOT NULL,
    platform_video_id TEXT NOT NULL,
    url TEXT, title TEXT, description TEXT,
    published_at TEXT, duration_sec REAL, width INTEGER, height INTEGER,
    thumbnail_url TEXT,
    origin TEXT NOT NULL DEFAULT 'manual',
    match_status TEXT NOT NULL DEFAULT 'unmatched',
    confidence REAL,
    matched_entity_type TEXT, matched_entity_id INTEGER,
    claim_status TEXT NOT NULL DEFAULT 'unknown',
    claim_info TEXT, edit_error TEXT, raw_json TEXT,
    first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
    UNIQUE(engine, platform, platform_video_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_upload_confirmed
    ON platform_uploads(engine, platform, matched_entity_type, matched_entity_id)
    WHERE match_status = 'confirmed';
```

Методы `Database`: `upsert_upload(...)`, `get_upload(id)`, `list_uploads(status=None, platform=None)`,
`set_upload_match(id, entity_type, entity_id, confidence, status)`. Upsert: `INSERT ... ON CONFLICT
(engine, platform, platform_video_id) DO UPDATE SET url/title/... , last_seen_at=excluded.last_seen_at`.

- [ ] **Step 4: Run — PASS**
- [ ] **Step 5: Commit** `feat(db): platform_uploads registry + upsert (schema v9)`

---

### Task 2: Конфиг движков

**Files:** Modify `src/orchestrator/config.py`, `config.yaml`; Test `tests/test_engines_config.py`

- [ ] **Step 1: Failing test** — `AppConfig` принимает `engines: dict[str,str]` (по умолч. `{}`), метод
`engine_for(platform)` возвращает `engines.get(platform,"postiz")`.
- [ ] **Step 2: Run — FAIL**
- [ ] **Step 3: Implement** — поле `engines: dict[str,str] = {}` + метод; в `config.yaml` добавить:
```yaml
engines:
  youtube: direct
  telegram: postiz
```
- [ ] **Step 4: PASS**  - [ ] **Step 5: Commit** `feat(config): engines per platform`

---

### Task 3: Интерфейс движков + реестр возможностей

**Files:** Create `src/orchestrator/engines/__init__.py`, `base.py`, `registry.py`;
Test `tests/test_engines_registry.py`

- [ ] **Step 1: Failing test**

```python
from orchestrator.engines.registry import REGISTRY, capabilities, select_engine

def test_capabilities_matrix():
    caps = capabilities("postiz")
    assert caps["publish"] is True
    assert capabilities("direct")["list"] is True
    assert capabilities("browser")["experimental"] is True

def test_select_engine_from_config():
    class C:  # минимальный стаб
        def engine_for(self, p): return {"youtube": "direct"}.get(p, "postiz")
    assert select_engine(C(), "youtube") == "direct"
    assert select_engine(C(), "telegram") == "postiz"
```

- [ ] **Step 2: Run — FAIL**
- [ ] **Step 3: Implement** — `base.py`:

```python
from dataclasses import dataclass
from typing import Protocol, Any

@dataclass
class PublishResult:
    engine: str; platform: str; external_id: str; url: str | None; state: str

class Destination(Protocol):
    def capabilities(self) -> dict[str, bool]: ...
    def publish(self, media_path: str, content: dict[str, Any], scheduled_for=None) -> PublishResult: ...
    def list_uploads(self, params: dict | None = None) -> list[dict]: ...
    def update_metadata(self, external_id: str, data: dict) -> bool: ...
    def delete(self, external_id: str) -> bool: ...
    def check_claims(self, external_id: str) -> dict: ...
```

`registry.py`:
```python
REGISTRY = {
  "postiz":  {"publish": True,  "list": False, "update": False, "delete": False, "claims": False, "experimental": False},
  "direct":  {"publish": True,  "list": True,  "update": True,  "delete": True,  "claims": True,  "experimental": False},
  "n8n":     {"publish": True,  "list": True,  "update": False, "delete": False, "claims": False, "experimental": False},
  "browser": {"publish": True,  "list": True,  "update": False, "delete": False, "claims": False, "experimental": True},
}
def capabilities(engine): return REGISTRY.get(engine, {})
def select_engine(cfg, platform): return cfg.engine_for(platform)
```

- [ ] **Step 4: PASS**  - [ ] **Step 5: Commit** `feat(engines): base interface + capability registry`

---

### Task 4: Адаптер Postiz через интерфейс (без регрессий)

**Files:** Create `src/orchestrator/engines/postiz_engine.py`; Test `tests/test_postiz_engine.py`
- [ ] **Step 1: Failing test** — `PostizEngine(client).publish(...)` делегирует `client.upload_media`+`create_post`
и возвращает `PublishResult(engine="postiz", platform=..., external_id=post.id, url=release_url)`.
- [ ] **Step 2: FAIL** - [ ] **Step 3: Implement** обёртку над `PostizClient`.
- [ ] **Step 4: PASS** + весь `pytest -q` зелёный (регрессий нет).
- [ ] **Step 5: Commit** `feat(engines): postiz adapter`

---

**Acceptance Plan 1:** все тесты зелёные; `platform_uploads` существует; движки описаны и выбираются; Postiz-путь не сломан.

**Далее:** Plan 2 — direct:youtube (list/update/delete/claims) и модуль ручных загрузок (scan/match/confirm);
Plan 3 — UI/API/MCP + плейсмент; Plan 4 — n8n, Plan 5 — browser (эксперимент).
