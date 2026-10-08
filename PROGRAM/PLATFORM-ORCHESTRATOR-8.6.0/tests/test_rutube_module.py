"""Rutube scaffold — honest NotSupported."""
from __future__ import annotations

import pytest

from orchestrator.platforms.base import MediaSpec, NotSupported, PublishMeta
from orchestrator.platforms.rutube.module import create_rutube_module


def test_rutube_auth_not_ok():
    mod = create_rutube_module(dry_run=True)
    st = mod.auth_status()
    assert st.ok is False
    assert "partner" in (st.details or "").lower() or "access" in (st.details or "").lower()


def test_rutube_publish_not_supported():
    mod = create_rutube_module()
    with pytest.raises(NotSupported):
        mod.publish(mod.prepare(MediaSpec(path="/x.mp4")), PublishMeta(title="t"))
