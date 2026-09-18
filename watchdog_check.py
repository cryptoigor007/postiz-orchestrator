#!/usr/bin/env python3
"""Watchdog: restart orchestrator if main process is dead (called by systemd timer)."""
from __future__ import annotations
import subprocess
import sys

SERVICE = "orchestrator.service"


def main() -> int:
    r = subprocess.run(
        ["systemctl", "is-active", "--quiet", SERVICE],
        capture_output=True,
    )
    if r.returncode != 0:
        subprocess.run(["systemctl", "restart", SERVICE], check=False)
        print(f"Restarted {SERVICE}")
        return 1
    print(f"{SERVICE} ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
