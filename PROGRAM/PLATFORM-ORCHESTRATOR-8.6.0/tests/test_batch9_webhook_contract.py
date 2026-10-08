from __future__ import annotations

import inspect

from orchestrator.platforms import default_registry


def test_supported_webhook_modules_preserve_manifest_metadata_and_verifier_shape():
    reg = default_registry()
    expected = {"whatsapp", "messenger", "instagram_messaging", "line", "viber"}
    for mid in expected:
        mod = reg.create(mid, dry_run=True)
        assert getattr(mod.manifest, "webhooks", {}).get("supported") is True
        verify = getattr(mod, "verify_webhook", None)
        assert callable(verify), mid
        assert len(inspect.signature(verify).parameters) == 2, mid
