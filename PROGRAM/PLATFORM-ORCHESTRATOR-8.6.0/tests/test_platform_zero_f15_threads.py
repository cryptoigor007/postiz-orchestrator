
"""F15 Threads: dry publish + daily_limit 3 + list."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from orchestrator.platforms.threads.module import ThreadsModule
from orchestrator.platforms.base import MediaSpec, PublishMeta

def test_threads_daily_default_3():
    m = ThreadsModule(dry_run=True)
    assert int(m.manifest.limits.get("daily_default") or 0) == 3

def test_threads_dry_text_publish():
    m = ThreadsModule(dry_run=True)
    prep = m.prepare(MediaSpec(path="", kind="text"))
    pr = m.publish(prep, PublishMeta(title="hello threads"))
    assert pr.external_id
    assert pr.state == "published"

def test_threads_auth_dry():
    m = ThreadsModule(dry_run=True)
    assert m.auth_status().ok
