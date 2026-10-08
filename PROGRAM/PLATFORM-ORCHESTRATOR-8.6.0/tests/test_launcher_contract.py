from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_macos_command_launcher_is_executable_and_points_to_start_script():
    launcher = ROOT / "START.command"
    start = ROOT / "start.sh"
    assert launcher.is_file()
    assert start.is_file()
    assert launcher.stat().st_mode & 0o111
    assert start.stat().st_mode & 0o111
    text = launcher.read_text(encoding="utf-8")
    assert "bash ./start.sh" in text
    assert "set -u" in text


def test_macos_app_bundle_has_executable_entrypoint_and_valid_plist_contract():
    app = ROOT / "Platform Orchestrator.app"
    executable = app / "Contents" / "MacOS" / "Platform Orchestrator"
    plist = app / "Contents" / "Info.plist"
    assert app.is_dir()
    assert executable.is_file()
    assert executable.stat().st_mode & 0o111
    assert executable.read_text(encoding="utf-8").startswith("#!/bin/bash")
    plist_text = plist.read_text(encoding="utf-8")
    for needle in (
        "CFBundleExecutable",
        "Platform Orchestrator",
        "CFBundlePackageType",
        "APPL",
        "8.6.0",
    ):
        assert needle in plist_text


def test_macos_app_bundle_embeds_the_project():
    root = (ROOT / "Platform Orchestrator.app" / "Contents" / "Resources" / "project")
    assert (root / "start.sh").is_file()
    assert (root / "requirements.lock").is_file()
    assert (root / "src" / "orchestrator" / "main.py").is_file()
    assert (root / "START.command").stat().st_mode & 0o111
