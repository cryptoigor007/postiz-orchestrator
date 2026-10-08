"""Unit расширенных IG/FB/TT/Threads 0.2.0."""

from orchestrator.media_host import create_media_host
from orchestrator.platforms import default_registry
from orchestrator.platforms.base import PreparedMedia, PublishMeta


def test_instagram_dry_publish_with_b2():
    host = create_media_host(dry_run=True, bucket_name="tmp")
    mod = default_registry().create("instagram", dry_run=True, media_host=host)
    assert mod.manifest.module_version == "0.3.0"
    res = mod.publish(PreparedMedia(path="", kind="video"), PublishMeta(title="Reel", description="#test"))
    assert res.external_id
    assert "instagram.com" in res.url or res.url == "" or res.state == "published"


def test_facebook_dry_feed():
    mod = default_registry().create("facebook", dry_run=True)
    res = mod.publish(
        PreparedMedia(path="", kind="text"),
        PublishMeta(title="Hi", extra={"link": "https://youtu.be/x"}),
    )
    assert res.external_id.startswith("fb-dry")


def test_tiktok_dry():
    mod = default_registry().create("tiktok", dry_run=True)
    assert mod.auth_status().ok
    res = mod.publish(PreparedMedia(path="", kind="video"), PublishMeta(title="t"))
    assert res.external_id


def test_threads_dry_with_host():
    host = create_media_host(dry_run=True)
    mod = default_registry().create("threads", dry_run=True, media_host=host)
    res = mod.publish(PreparedMedia(path="", kind="text"), PublishMeta(title="th"))
    assert res.external_id
