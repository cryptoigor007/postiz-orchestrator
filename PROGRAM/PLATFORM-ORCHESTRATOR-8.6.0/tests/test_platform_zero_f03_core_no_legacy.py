
"""Core has no legacy transport client dependency."""
from __future__ import annotations
import ast
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_main_module_importable_without_legacy_client():
    src = (ROOT / "src/orchestrator/main.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "postiz" not in node.module
        if isinstance(node, ast.Import):
            for a in node.names:
                assert "postiz" not in a.name
    assert "StatusSync(" in src

def test_publisher_no_legacy_kwarg():
    from orchestrator.publisher import Publisher
    import inspect
    assert "postiz" not in inspect.signature(Publisher.__init__).parameters
