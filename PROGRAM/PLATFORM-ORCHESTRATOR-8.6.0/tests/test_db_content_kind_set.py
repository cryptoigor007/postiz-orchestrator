from pathlib import Path
from orchestrator.db import Database

def test_set_content_kind(tmp_path: Path):
    db = Database(str(tmp_path / "c.sqlite"))
    db.execute(
        "INSERT INTO entity_platform_status (entity_type, entity_id, platform, status) "
        "VALUES ('long_video', 9, 'vk', 'ready')"
    )
    db.set_content_kind("long_video", 9, "vk", "promo_text")
    row = db.fetchone(
        "SELECT content_kind FROM entity_platform_status WHERE entity_id=9 AND platform='vk'"
    )
    assert row["content_kind"] == "promo_text"
