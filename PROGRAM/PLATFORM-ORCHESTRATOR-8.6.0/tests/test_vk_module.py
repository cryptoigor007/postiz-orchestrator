"""VK module unit tests (mock / dry-run)."""
from __future__ import annotations

from orchestrator.platforms.base import MediaSpec, PublishMeta
from orchestrator.platforms.vk.module import VKModule, create_vk_module


def test_vk_create_and_auth():
    mod = create_vk_module(dry_run=True, group_id="123")
    assert mod.manifest.id == "vk"
    st = mod.auth_status()
    assert st.ok is True


def test_vk_publish_video_dry():
    mod = VKModule(dry_run=True, group_id="99")
    media = mod.prepare(MediaSpec(path="/tmp/none.mp4", kind="video"))
    res = mod.publish(media, PublishMeta(title="T", description="D"))
    assert res.external_id
    assert res.state == "published"
    assert "vk.com" in res.url


def test_vk_publish_promo_dry():
    mod = VKModule(dry_run=True, group_id="99", content_kind="promo_text")
    media = mod.prepare(MediaSpec(path="", kind="text"))
    res = mod.publish(media, PublishMeta(title="Promo", description="body"))
    assert res.state == "published"
    assert "wall" in res.url


def test_vk_delete_dry():
    mod = VKModule(dry_run=True, group_id="99")
    assert mod.delete("-99_1") is True


def test_vk_list_remote_dry():
    mod = VKModule(dry_run=True)
    page = mod.list_remote_items(limit=5)
    assert len(page.items) >= 1


def test_vk_upload_wall_photo_dry():
    from orchestrator.platforms.vk.api import VKApi
    api = VKApi("", group_id="99", dry_run=True)
    att = api.upload_wall_photo("/tmp/does-not-need-to-exist-in-dry.jpg")
    assert att.startswith("photo")
    assert "_" in att


def test_vk_publish_promo_with_image_path_dry(tmp_path):
    img = tmp_path / "cover.jpg"
    img.write_bytes(b"\xff\xd8\xff\xd9")  # minimal jpeg-ish
    mod = VKModule(dry_run=True, group_id="99", content_kind="promo_text")
    media = mod.prepare(MediaSpec(path=str(img), kind="image"))
    res = mod.publish(media, PublishMeta(title="Promo", description="body"))
    assert res.state == "published"
    assert "wall" in res.url
