#!/usr/bin/env python3
"""Reject vacuous assertions in HARD_CUT critical regression tests."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_GLOBS = ("test_platform_zero*.py", "test_p0*.py")


def main() -> int:
    violations: list[str] = []
    for pattern in TEST_GLOBS:
        for path in sorted((ROOT / "tests").glob(pattern)):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Assert):
                    continue
                if isinstance(node.test, ast.Constant) and node.test.value is True:
                    violations.append(f"{path}:{node.lineno}: assert True")
                elif isinstance(node.test, ast.BoolOp) and isinstance(node.test.op, ast.Or):
                    if any(
                        isinstance(value, ast.Constant) and value.value is True
                        for value in node.test.values
                    ):
                        violations.append(f"{path}:{node.lineno}: tautological assert ... or True")
    if violations:
        print("[check] critical test tautologies found:")
        print("\n".join(violations))
        return 1
    print("[check] critical test tautologies: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
