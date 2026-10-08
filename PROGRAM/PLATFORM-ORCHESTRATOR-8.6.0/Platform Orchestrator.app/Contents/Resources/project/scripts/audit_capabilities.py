#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from orchestrator.platforms import default_registry
from orchestrator.platforms.base import PlatformModule
from orchestrator.platforms.manifest import load_manifest
from orchestrator.platforms.module_sdk import ModuleSDK

CAP_METHODS = {"publish": "publish", "schedule_publish": "schedule_publish", "update_metadata": "update_metadata", "delete": "delete"}

def main() -> int:
    reg = default_registry()
    errors: list[str] = []
    for module_id in reg.ids():
        manifest = load_manifest(ROOT / "src" / "orchestrator" / "platforms" / module_id / "manifest.yaml")
        ModuleSDK.validate_manifest(manifest)
        try:
            mod = reg.create(module_id, dry_run=True)
        except Exception as exc:
            errors.append(f"{module_id}: create failed: {type(exc).__name__}: {exc}")
            continue
        for cap, method_name in CAP_METHODS.items():
            advertised = bool(manifest.capabilities.get(cap, False))
            impl = getattr(type(mod), method_name, None)
            base = getattr(PlatformModule, method_name, None)
            if advertised and impl is base:
                errors.append(f"{module_id}: capability {cap}=true inherits base {method_name}()")
        publish_mode = str(manifest.publish_mode or "unsupported")
        if publish_mode not in ("unsupported", "partner") and not bool(manifest.capabilities.get("publish", False)):
            errors.append(f"{module_id}: publish_mode={publish_mode} but publish=false")
    print(f"capability audit: modules={len(reg.ids())} errors={len(errors)}")
    for item in errors:
        print(item)
    return 1 if errors else 0

if __name__ == "__main__":
    raise SystemExit(main())
