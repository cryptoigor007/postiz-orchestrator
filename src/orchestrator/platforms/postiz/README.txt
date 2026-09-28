Postiz adapter module v1.0.0 (P4)
=================================
Оборачивает существующий PostizClient (postiz_http / Mock) в контракт PlatformModule.
engines.<platform>=module:postiz — только на P5; до этого unit + dry-run.

Зависимости фабрики:
  client: PostizClient (или mock)
  platform: str  (youtube|telegram|...)
  integration_id: optional
  dry_run: bool

Не заменяет engines/postiz_engine.py в проде до явного переключения.
