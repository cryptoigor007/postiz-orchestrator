"""Unit скелетов P6 + registry."""

from orchestrator.platforms import default_registry, load_modules
from orchestrator.platforms.base import NotSupported, PreparedMedia, PublishMeta


def test_all_registered():
    reg = default_registry()
    for pid in ("youtube", "telegram", "postiz", "instagram", "tiktok", "facebook", "threads"):
        assert reg.has(pid), pid


def test_skeletons_dry_run_publish():
    reg = default_registry()
    for pid in ("instagram", "tiktok", "facebook", "threads"):
        mod = reg.create(pid, dry_run=True)
        st = mod.auth_status()
        assert st.ok is True
        res = mod.publish(PreparedMedia(path="", kind="text"), PublishMeta(title="t"))
        assert res.external_id
        try:
            mod.delete(res.external_id)
        except NotSupported:
            pass  # IG/TikTok v1


def test_load_modules_multi():
    engines = {
        "instagram": "module:instagram",
        "tiktok": "module:tiktok",
        "facebook": "postiz",
    }
    mods = load_modules(engines, deps={"dry_run": True})
    assert "instagram" in mods and "tiktok" in mods
    assert "facebook" not in mods
