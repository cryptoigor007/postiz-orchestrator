from __future__ import annotations

from orchestrator.canary import ProviderContractCanary
from orchestrator.platforms import default_registry


def test_static_and_dry_canary_covers_all_registered_modules():
    reg = default_registry()
    runner = ProviderContractCanary(reg)
    results = runner.dry_all()
    assert len(results) == len(reg.ids()) == 42
    assert all(r.static_ok for r in results), [r for r in results if not r.static_ok]
    assert all(r.dry_ok for r in results), [r for r in results if not r.dry_ok]
    summary = runner.summary(results)
    assert summary["static_ok"] == 42
    assert summary["dry_ok"] == 42


def test_live_canary_is_opt_in_and_read_only(monkeypatch):
    monkeypatch.delenv("ORCH_CANARY_LIVE", raising=False)
    results = ProviderContractCanary(default_registry()).live_read_only(["youtube"])
    assert results[0].state == "disabled"

class _FakeCanaryModule:
    def __init__(self):
        self.deleted = []

    def auth_status(self):
        from orchestrator.platforms.base import AuthStatus
        return AuthStatus(ok=True, account="fake")

    def capabilities(self):
        return {"delete": True, "publish": True}

    def prepare(self, media):
        return media

    def publish(self, media, meta):
        from orchestrator.platforms.base import PublishResult
        return PublishResult(external_id="fake-1", url="https://example.invalid/fake-1")

    def upload(self, media, meta, when=None):
        from orchestrator.platforms.base import UploadResult
        return UploadResult(external_id="fake-1", url="https://example.invalid/fake-1", state="uploaded")

    def get_status(self, external_id):
        from orchestrator.platforms.base import PublishStatus
        return PublishStatus(state="published", url="https://example.invalid/fake-1")

    def delete(self, external_id):
        self.deleted.append(external_id)
        return True


class _FakeRegistry:
    def __init__(self, module):
        self.module = module

    def ids(self):
        return ["youtube"]

    def create(self, module_id, *, dry_run=False):
        return self.module


def test_live_write_canary_requires_explicit_double_opt_in(monkeypatch, tmp_path):
    monkeypatch.delenv("ORCH_CANARY_LIVE_WRITE", raising=False)
    monkeypatch.delenv("ORCH_CANARY_CONFIRM", raising=False)
    result = ProviderContractCanary(_FakeRegistry(_FakeCanaryModule())).live_write(["youtube"])
    assert result[0].state == "disabled"


def test_live_write_canary_exercises_publish_status_cleanup(monkeypatch, tmp_path):
    media = tmp_path / "canary.mp4"
    media.write_bytes(b"canary")
    monkeypatch.setenv("ORCH_CANARY_LIVE_WRITE", "1")
    monkeypatch.setenv("ORCH_CANARY_CONFIRM", "PUBLISH_A_CANARY")
    monkeypatch.setenv("ORCH_CANARY_MEDIA", str(media))
    fake = _FakeCanaryModule()
    result = ProviderContractCanary(_FakeRegistry(fake)).live_write(["youtube"])
    assert result[0].state == "live_write_ok"
    assert result[0].live_ok
    assert fake.deleted == ["fake-1"]
