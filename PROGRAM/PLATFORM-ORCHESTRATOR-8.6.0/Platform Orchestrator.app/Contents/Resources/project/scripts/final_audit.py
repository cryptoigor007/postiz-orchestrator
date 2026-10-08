#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TESTS = ROOT / "tests"

def run(name: str, cmd: list[str], *, timeout: int = 300, env=None) -> None:
    print(f"\n=== {name} ===")
    merged = os.environ.copy()
    merged["PYTHONPATH"] = f"{ROOT/'src'}:{ROOT/'scripts'}"
    if env:
        merged.update(env)
    proc = subprocess.run(cmd, cwd=ROOT, env=merged, text=True)
    if proc.returncode:
        raise SystemExit(f"{name} FAILED rc={proc.returncode}")


def static_audit() -> None:
    # Python parse + compile inventory.
    py = sorted(SRC.rglob("*.py"))
    for p in py:
        ast.parse(p.read_text(encoding="utf-8", errors="replace"), filename=str(p))
    subprocess.run([sys.executable, "-m", "compileall", "-q", "src", "scripts", "tests"], cwd=ROOT, check=True)
    print(f"python parse/compile: {len(py)} source modules")

    # No tautological assertions / no silent bare except pass in runtime source.
    taut = []
    bare = []
    for p in TESTS.rglob("test_*.py"):
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if re.search(r"\bassert\s+True\b", line):
                taut.append(f"{p}:{i}")
    for p in [*SRC.rglob("*.py"), *(ROOT / "scripts").rglob("*.py")]:
        tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        for n in ast.walk(tree):
            if isinstance(n, ast.ExceptHandler) and len(n.body) == 1 and isinstance(n.body[0], ast.Pass):
                bare.append(f"{p}:{getattr(n, 'lineno', '?')}")
    if taut:
        raise SystemExit("tautological assertions remain: " + ", ".join(taut[:10]))
    if bare:
        raise SystemExit("runtime bare except: pass remain: " + ", ".join(bare[:10]))
    print("tautologies=0; runtime bare-except-pass=0")

    # Active source/script query-key and obvious secret scans.
    active = [*(SRC.rglob("*.py")), *(ROOT / "scripts").rglob("*.py"), *(ROOT / "scripts").rglob("*.sh"), *(ROOT / "webapp").rglob("*.js"), *(ROOT / "deploy").rglob("*.sh") ]
    active = [p for p in active if p.name != "final_audit.py"]
    active_lines = []
    for fp in active:
        if not fp.exists():
            continue
        for line in fp.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if s.startswith("#") or s.startswith("//") or s.startswith("/*") or s.startswith("*"):
                continue
            active_lines.append(line)
    text = "\n".join(active_lines)
    bad = []
    for pat in (r"\?key=", r"sk_live_[A-Za-z0-9]", r"AIza[0-9A-Za-z_-]{20,}", r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"):
        if re.search(pat, text):
            bad.append(pat)
    if bad:
        raise SystemExit("active secret/query-key patterns found: " + ", ".join(bad))
    print("active secret/query-key scan=0")

    # Critical infrastructure fingerprints.
    forbidden_ips = ("100.95.225.71", "192.168.100.50", "192.168.100.40", "192.168.100.60")
    ip_hits = [x for x in forbidden_ips if x in text]
    if ip_hits:
        raise SystemExit("owner-specific infra IPs in active code: " + ", ".join(ip_hits))
    print("owner-specific active IP scan=0")

    # Current schema and manifest/catalog integrity.
    db_py = (SRC / "orchestrator" / "db.py").read_text()
    if "SCHEMA_VERSION = 28" not in db_py:
        raise SystemExit("schema version is not 28")
    import yaml  # type: ignore
    manifests = list((SRC / "orchestrator" / "platforms").glob("*/manifest.yaml"))
    if len(manifests) != 42:
        raise SystemExit(f"manifest count={len(manifests)} != 42")
    catalog = yaml.safe_load((ROOT / "docs" / "provider-catalog.yaml").read_text())
    providers = catalog.get("providers") or []
    if len(providers) != 42:
        raise SystemExit(f"catalog count={len(providers)} != 42")
    if not all(str(p.get("live_status")) == "NOT_LIVE" for p in providers):
        raise SystemExit("catalog advertises a provider as LIVE")
    print("catalog/manifests/live_status=42/42/NOT_LIVE")


def check_provider_list_observability() -> None:
    """Provider list/scheduled inventory failures must be observable, never silent."""
    bad: list[str] = []
    base = SRC / "orchestrator" / "platforms"
    for path in sorted(base.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if "list_remote" not in node.name and "list_scheduled" not in node.name:
                continue
            for handler in [x for x in ast.walk(node) if isinstance(x, ast.ExceptHandler)]:
                catches_exception = handler.type is None or (isinstance(handler.type, ast.Name) and handler.type.id == "Exception")
                if not catches_exception:
                    continue
                logged = any(
                    isinstance(x, ast.Call)
                    and isinstance(x.func, ast.Attribute)
                    and isinstance(x.func.value, ast.Name)
                    and x.func.value.id == "logger"
                    and x.func.attr in {"warning", "error", "exception"}
                    for x in ast.walk(handler)
                )
                if not logged:
                    bad.append(f"{path}:{handler.lineno}:{node.name}")
    if bad:
        raise SystemExit("provider list exception paths without logging: " + ", ".join(bad[:20]))
    print("provider list exception logging=0 unlogged")

def check_dependency_pins() -> None:
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    lock = (ROOT / "requirements-test.lock").read_text(encoding="utf-8")
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    expected = {"pytest": "8.3.5", "pytest_asyncio": "0.25.3"}
    if "pytest==8.3.5" not in req or "pytest-asyncio==0.25.3" not in req:
        raise SystemExit("requirements.txt pytest pins are not exact")
    if "pytest==8.3.5" not in lock or "pytest-asyncio==0.25.3" not in lock:
        raise SystemExit("requirements-test.lock pytest pins are not exact")
    if "pytest.__version__ == '8.3.5'" not in ci or "pytest_asyncio.__version__ == '0.25.3'" not in ci:
        raise SystemExit("CI pytest version gate missing")
    print("pytest pins: requirements/lock/CI exact=8.3.5 + 0.25.3")



def main() -> int:
    static_audit()
    print("\n=== provider list observability ===")
    check_provider_list_observability()
    print("\n=== dependency pins ===")
    check_dependency_pins()
    run("check_test_tautologies", [sys.executable, "scripts/check_test_tautologies.py"])
    run("capability audit", [sys.executable, "scripts/audit_capabilities.py"])
    run("platform gate", ["bash", "scripts/gate_platform_zero.sh"], timeout=180)
    run("social gate", ["bash", "scripts/gate_social_architecture.sh"], timeout=180)
    run("full pytest", [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=short"], timeout=300)
    print("\nFINAL AUDIT: ALL AUTOMATED CHECKS PASSED")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
