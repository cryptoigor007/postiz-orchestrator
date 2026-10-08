"""F20: structural gates."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def test_no_legacy_transport_client_module():
    """No postiz transport module files in src."""
    src = ROOT / "src" / "orchestrator"
    banned = ["postiz.py", "postiz_factory.py", "postiz_http.py", "postiz_errors.py"]
    for name in banned:
        assert not (src / name).exists(), name
    assert not (src / "engines" / "postiz_engine.py").exists()


def test_schema_19():
    from orchestrator.db import SCHEMA_VERSION
    assert SCHEMA_VERSION >= 19


def test_main_has_module_recon():
    t = (ROOT / "src/orchestrator/main.py").read_text()
    assert "ModuleReconciliation" in t
