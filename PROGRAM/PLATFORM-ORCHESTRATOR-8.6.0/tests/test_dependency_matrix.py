from pathlib import Path
import re


def test_test_dependency_matrix_matches_lock():
    req = Path("requirements.txt").read_text()
    lock = Path("requirements.lock").read_text()
    assert "pytest==8.3.5" in req
    assert "pytest-asyncio==0.25.3" in req
    assert "pytest==8.3.5" in lock
    assert "pytest-asyncio==0.25.3" in lock
