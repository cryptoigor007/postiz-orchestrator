
"""Purge gate: no postiz transport imports on critical path."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "orchestrator"

CRITICAL = [
    "platforms/token_store.py",
    "platforms/youtube/token_store.py",
    "oauth/manager.py",
    "publisher.py",
    "status_sync.py",
    "main.py",
]

def test_critical_files_no_postiz_import():
    for rel in CRITICAL:
        p = SRC / rel
        if not p.exists():
            continue
        t = p.read_text(encoding="utf-8")
        assert "from .postiz" not in t
        assert "import postiz" not in t
        assert "PostizClient" not in t

def test_publisher_no_orch_legacy_env():
    pub = (SRC / "publisher.py").read_text(encoding="utf-8")
    assert "ORCH_POSTIZ_LEGACY" not in pub
    assert "ORCH_LEGACY_TRANSPORT" not in pub
