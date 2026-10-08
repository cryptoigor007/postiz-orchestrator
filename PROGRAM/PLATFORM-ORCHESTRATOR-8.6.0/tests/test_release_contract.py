from __future__ import annotations

import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_install_no_start_is_real_no_start():
    s = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert "--no-start|--prepare-only" in s
    assert "install.sh --skip-smoke --no-start" in (ROOT / "start.sh").read_text(encoding="utf-8")
    assert 'if [ "$NO_START" -eq 1 ]; then' in s

def test_launchers_are_executable():
    for name in ("START.command", "start.sh", "install.sh"):
        mode = stat.S_IMODE((ROOT / name).stat().st_mode)
        assert mode & stat.S_IXUSR, f"{name} is not user-executable"

def test_native_auth_metadata_matches_runtime_credentials():
    expected = {
        "bluesky": "app_password",
        "linkedin": "oauth2",
        "mastodon": "oauth2",
        "pinterest": "oauth2",
        "reddit": "oauth2",
    }
    for module, method in expected.items():
        text = (ROOT / "src" / "orchestrator" / "platforms" / module / "manifest.yaml").read_text(encoding="utf-8")
        assert f"  method: {method}" in text
        assert "  method: planned" not in text

def test_macos_app_payload_is_present():
    app = ROOT / "Platform Orchestrator.app"
    assert (app / "Contents" / "Info.plist").is_file()
    launcher = app / "Contents" / "MacOS" / "Platform Orchestrator"
    assert launcher.is_file()
    mode = stat.S_IMODE(launcher.stat().st_mode)
    assert mode & stat.S_IXUSR
    text = launcher.read_text(encoding="utf-8")
    assert "Library/Application Support/Platform Orchestrator" in text
    assert "ditto" in text


def test_publishable_provider_metadata_has_real_auth_strategy():
    import yaml
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for manifest in sorted((root / "src/orchestrator/platforms").glob("*/manifest.yaml")):
        data = yaml.safe_load(manifest.read_text()) or {}
        caps = data.get("capabilities") or {}
        if caps.get("publish"):
            method = str((data.get("auth") or {}).get("method") or "")
            assert method not in {"planned", "none", ""}, f"{manifest}: publish=true but auth.method={method!r}"


def test_reddit_does_not_advertise_unsupported_media_upload():
    import yaml
    from pathlib import Path
    manifest = Path(__file__).resolve().parents[1] / "src/orchestrator/platforms/reddit/manifest.yaml"
    data = yaml.safe_load(manifest.read_text()) or {}
    caps = data.get("capabilities") or {}
    assert caps.get("image") is False
    assert caps.get("video") is False


def test_start_smoke_is_fail_fast():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    start = (root / "start.sh").read_text()
    assert "--dry-run --once 2>&1 | tail" not in start
    assert "exec python -m orchestrator.main" in start
