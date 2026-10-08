from __future__ import annotations

from orchestrator.db import Database
from orchestrator.media_transfer import MediaTransferManager, SSRFBlocked


def test_media_ingest_records_hash_and_size(tmp_path):
    db = Database(tmp_path / "m.sqlite")
    src = tmp_path / "a.bin"
    src.write_bytes(b"abc" * 100)
    mgr = MediaTransferManager(db, temp_dir=tmp_path / "tmp")
    art = mgr.ingest_local(src, kind="video")
    assert art.size_bytes == 300
    row = db.fetchone("SELECT sha256,size_bytes FROM media_artifacts WHERE id=?", (art.id,))
    assert row["size_bytes"] == 300
    assert row["sha256"] == art.sha256


def test_media_ssrf_blocks_private_address(tmp_path):
    mgr = MediaTransferManager(temp_dir=tmp_path / "tmp")
    import socket
    real = socket.getaddrinfo
    socket.getaddrinfo = lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 80))]
    try:
        try:
            mgr.validate_url("https://example.test/a.mp4")
            raise AssertionError("expected SSRFBlocked")
        except SSRFBlocked:
            pass
    finally:
        socket.getaddrinfo = real


def test_media_chunks_have_monotonic_offsets(tmp_path):
    src = tmp_path / "chunk.bin"
    src.write_bytes(b"0123456789")
    chunks = list(MediaTransferManager.iter_chunks(src, chunk_size=4))
    assert [o for o, _ in chunks] == [0, 4, 8]
    assert b"".join(c for _, c in chunks) == b"0123456789"
