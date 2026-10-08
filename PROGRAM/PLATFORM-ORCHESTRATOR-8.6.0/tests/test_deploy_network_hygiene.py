from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
FILES = [ROOT / "deploy/lan-default.sh", ROOT / "deploy/lan-fix.sh", ROOT / "deploy/vm-nat.sh"]


def test_network_scripts_require_runtime_network_parameters():
    for path in FILES:
        src = path.read_text(encoding="utf-8")
        assert not re.search(r"\b(?:100\.95\.\d+\.\d+|192\.168\.\d+\.\d+)\b", src)
    assert 'LAN_GW' in (ROOT / 'deploy/lan-default.sh').read_text()
    assert 'LAN_CIDR' in (ROOT / 'deploy/lan-fix.sh').read_text()
    assert 'VM_NET_CIDR' in (ROOT / 'deploy/vm-nat.sh').read_text()
