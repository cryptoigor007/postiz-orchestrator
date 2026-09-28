"""Unit-тесты Postiz-адаптера (P4)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from orchestrator.platforms import default_registry, load_modules, resolve_engine
from orchestrator.platforms.base import (
    ModuleError,
    NotSupported,
    PreparedMedia,
    PublishMeta,
)
from orchestrator.platforms.postiz.module import PostizModule, create_postiz_module


def test_manifest():
    m = create_postiz_module(dry_run=True)
    assert m.manifest.id == "postiz"
    assert m.manifest.module_version == "1.0.0"
    caps = m.capabilities()
    assert caps.get("publish") is True
    assert caps.get("schedule_publish") is True
    assert caps.get("update_metadata") is False


def test_auth_dry_run():
    m = create_postiz_module(dry_run=True, platform="youtube")
    st = m.auth_status()
    assert st.ok is True


def test_publish_dry_run():
    m = create_postiz_module(dry_run=True, platform="telegram")
    res = m.publish(
        PreparedMedia(path="", kind="text"),
        PublishMeta(title="T", description="D"),
    )
    assert res.external_id.startswith("postiz-dry-")
    assert res.state in ("published", "scheduled")


def test_upload_with_schedule_dry_run():
    m = create_postiz_module(dry_run=True, platform="youtube")
    when = datetime(2030, 1, 1, 12, 0, tzinfo=UTC)
    up = m.upload(PreparedMedia(path="", kind="video"), PublishMeta(title="V"), when=when)
    assert up.external_id
    assert up.state == "scheduled"


def test_delete_and_status_dry_run():
    m = create_postiz_module(dry_run=True)
    res = m.publish(PreparedMedia(path="", kind="text"), PublishMeta(title="x"))
    assert m.delete(res.external_id) is True
    st = m.get_status(res.external_id)
    assert st.state == "published"


def test_update_not_supported():
    m = create_postiz_module(dry_run=True)
    with pytest.raises(NotSupported):
        m.update_metadata("id", PublishMeta(title="y"))


def test_registry():
    assert default_registry().has("postiz")
    mod = default_registry().create("postiz", dry_run=True, platform="youtube")
    assert isinstance(mod, PostizModule)


def test_load_modules():
    engines = {"youtube": "module:postiz", "telegram": "postiz"}
    mods = load_modules(engines, deps={"dry_run": True, "platform": "youtube"})
    assert "youtube" in mods
    assert "telegram" not in mods  # kind=postiz adapter, not module


def test_resolve():
    r = resolve_engine("module:postiz")
    assert r.kind == "module" and r.module_id == "postiz"


def test_mock_client_error_mapping():
    class BadClient:
        def upload_media(self, path, platform):
            return SimpleNamespace(id="m", path="")

        def create_post(self, platform, media, content, scheduled_for=None):
            raise RuntimeError("401 Unauthorized token invalid")

        def delete_post(self, post_id):
            pass

        def get_post(self, post_id):
            return None

    m = PostizModule(BadClient(), platform="youtube", dry_run=False)
    with pytest.raises(ModuleError) as ei:
        m.publish(PreparedMedia(path="", kind="text"), PublishMeta(title="t"))
    assert ei.value.code.value == "AUTH_REQUIRED"


def test_check_claims():
    m = create_postiz_module(dry_run=True)
    assert m.check_claims("x").supported is False
