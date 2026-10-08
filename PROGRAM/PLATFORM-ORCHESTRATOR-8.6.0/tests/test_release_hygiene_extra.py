from pathlib import Path
import subprocess
import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_ci_workflow_is_valid_yaml():
    path = ROOT / ".github" / "workflows" / "ci.yml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["jobs"]["checks"]["steps"]


def test_infra_watchdog_has_no_bare_pass():
    proc = subprocess.run(
        ["python", "-m", "ast", str(ROOT / "scripts" / "infra_watchdog.py")],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    import ast
    tree = ast.parse((ROOT / "scripts" / "infra_watchdog.py").read_text(encoding="utf-8"))
    offenders = [
        n.lineno for n in ast.walk(tree)
        if isinstance(n, ast.ExceptHandler) and any(isinstance(stmt, ast.Pass) for stmt in n.body)
    ]
    assert offenders == []
