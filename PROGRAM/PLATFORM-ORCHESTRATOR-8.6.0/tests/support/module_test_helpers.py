"""HARD_CUT module-path test helpers."""
from __future__ import annotations
from typing import Any

def make_module_registry(dry_run: bool = True):
    from orchestrator.platforms import default_registry
    reg = default_registry()
    orig = reg.create
    def _create(module_id: str, **deps: Any):
        deps["dry_run"] = dry_run
        return orig(module_id, **deps)
    reg.create = _create  # type: ignore
    return reg

def patch_synthetic_paths(monkeypatch) -> None:
    import pathlib as _pl
    _real_is_file = _pl.Path.is_file
    _real_stat = _pl.Path.stat
    def _is_file(self):
        s = str(self)
        if s.startswith("/") and not s.startswith(("/home", "/tmp", "/usr", "/var", "/root", "/opt")):
            return True
        try:
            return _real_is_file(self)
        except Exception:
            return True
    def _stat(self, *a, **k):
        s = str(self)
        if s.startswith("/") and not s.startswith(("/home", "/tmp", "/usr", "/var", "/root", "/opt")):
            return type("S", (), {"st_size": 1024, "st_mtime": 0})()
        return _real_stat(self, *a, **k)
    monkeypatch.setattr(_pl.Path, "is_file", _is_file)
    monkeypatch.setattr(_pl.Path, "stat", _stat)
