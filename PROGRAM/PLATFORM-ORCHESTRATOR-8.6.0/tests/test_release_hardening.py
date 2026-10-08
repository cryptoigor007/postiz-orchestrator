from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "Platform Orchestrator.app"
APP_PROJECT = APP / "Contents" / "Resources" / "project"
APP_LAUNCHER = APP / "Contents" / "MacOS" / "Platform Orchestrator"


def test_unix_install_requires_real_venv_and_does_not_fallback_to_system_python():
    text = (ROOT / "install.sh").read_text()
    assert "Unable to create .venv" in text
    assert "USE_VENV=0" not in text
    assert "pip install --user" not in text
    assert "python -m pip install --user" not in text
    assert ".venv/bin/python" in text or "source .venv/bin/activate" in text


def test_unix_launchers_use_dependency_content_hash():
    for name in ("install.sh", "start.sh"):
        text = (ROOT / name).read_text()
        assert ".venv/.deps_hash" in text
        assert "sha256" in text
        assert "requirements.lock" in text


def test_windows_launchers_use_dependency_content_hash():
    for name in ("install.bat", "start.bat"):
        text = (ROOT / name).read_text().lower()
        assert ".venv\\.deps_hash" in text
        assert "get-filehash" in text
        assert "requirements.lock" in text
        assert ".venv\\.deps_ok" not in text


def test_macos_app_has_build_fingerprint_refresh_logic():
    launcher = APP_LAUNCHER.read_text()
    assert 'RELEASE-BUILD-ID.txt' in launcher
    assert 'BUNDLE_BUILD_ID' in launcher
    assert 'TARGET="$RELEASES/$VERSION-$BUNDLE_BUILD_ID"' in launcher
    assert 'INSTALLED_BUILD_ID' in launcher
    assert 'open -a "Terminal"' in launcher
    assert APP_LAUNCHER.stat().st_mode & 0o111


def test_macos_embedded_payload_contains_no_user_runtime_state():
    forbidden = (
        "config.yaml",
        ".env",
        "data",
        "tokens",
        "backups",
        "logs",
        "tests",
        ".pytest_cache",
        ".venv",
    )
    for name in forbidden:
        assert not (APP_PROJECT / name).exists(), f"runtime state leaked into app payload: {name}"
    assert (APP_PROJECT / "RELEASE-BUILD-ID.txt").is_file()
    assert (APP_PROJECT / "config.example.yaml").is_file()


def test_macos_build_script_rebuilds_from_external_launcher_template():
    text = (ROOT / "scripts/build_macos_app.sh").read_text()
    assert "scripts/macos_app_launcher.sh" in text
    assert "scripts/macos_app_Info.plist" in text
    assert "--exclude='tests/'" in text
    assert "--exclude='data/'" in text
    assert "--exclude='config.yaml'" in text
    assert "RELEASE-BUILD-ID.txt" in text


def test_review_gated_provider_metadata_is_explicit():
    expected = {
        "linkedin": "development_then_standard",
        "pinterest": "trial_then_standard",
        "google_business": "project_access_approval",
    }
    for provider, requirement in expected.items():
        text = (ROOT / "src" / "orchestrator" / "platforms" / provider / "manifest.yaml").read_text()
        assert f"review_requirement: {requirement}" in text
    reddit = (ROOT / "src" / "orchestrator" / "platforms" / "reddit" / "manifest.yaml").read_text()
    assert "access_state: REGISTRATION_REQUIRED" in reddit


def test_feasibility_provider_docs_do_not_claim_completed_native_access():
    docs = {
        "MODULE_MEWE.txt",
        "MODULE_WHOP.txt",
        "MODULE_SNAPCHAT.txt",
        "MODULE_RUTUBE_PARTNER.txt",
    }
    for name in docs:
        text = (ROOT / "docs" / "modules" / name).read_text()
        assert "intentionally exposes no publishing/messaging capabilities" not in text
        assert "fail-closed" in text.lower()


def test_master_access_playbook_is_present_and_authoritative():
    master = ROOT / "docs" / "API-APPROVAL-MASTER-2026-10-03.md"
    root_copy = ROOT / "API-AND-LAUNCH-GUIDE-2026-10-03.md"
    text = master.read_text()
    assert root_copy.read_text() == text
    assert "There is no truthful way to promise 100% approval" in text
    assert "R1" in text and "R2" in text and "R3" in text
    for provider in ("LinkedIn", "Pinterest", "TikTok", "YouTube", "Google Business Profile", "Reddit", "X"):
        assert provider in text
