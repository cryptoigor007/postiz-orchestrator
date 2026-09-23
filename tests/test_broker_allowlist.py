from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import token_broker


def test_ip_allowed():
    assert token_broker.ip_allowed("127.0.0.1", {"10.0.0.1"}) is True
    assert token_broker.ip_allowed("10.0.0.1", {"10.0.0.1"}) is True
    assert token_broker.ip_allowed("8.8.8.8", {"10.0.0.1"}) is False
    assert token_broker.ip_allowed("8.8.8.8", set()) is True  # empty = allow all
