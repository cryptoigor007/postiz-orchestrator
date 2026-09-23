"""Проверки надёжного ящика входящих сообщений из Telegram."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from orchestrator import tg_inbox
from orchestrator.telegram_transport import TelegramTransport


def test_append_read_and_unread(tmp_path):
    tg_inbox.append_message(7004751908, 10, "первое", directory=tmp_path)
    tg_inbox.append_message(7004751908, 11, "второе", directory=tmp_path)
    recs = tg_inbox.read_messages(tmp_path)
    assert [r["text"] for r in recs] == ["первое", "второе"]
    assert [r["message_id"] for r in tg_inbox.unread(tmp_path)] == [10, 11]
    assert (tmp_path / "inbox.jsonl").exists()


def test_mark_seen_marks_exactly_that_message(tmp_path):
    for mid, text in ((10, "a"), (11, "b"), (12, "c")):
        tg_inbox.append_message(1, mid, text, directory=tmp_path)
    tg_inbox.mark_seen(11, tmp_path)
    assert tg_inbox.last_seen(tmp_path) == 11
    # прочитанным стало ровно 11, остальные остаются непрочитанными
    assert [r["message_id"] for r in tg_inbox.unread(tmp_path)] == [10, 12]
    assert tg_inbox.seen_ids(tmp_path) == {11}
    assert len(tg_inbox.read_messages(tmp_path)) == 3


def test_big_test_id_does_not_hide_real_messages(tmp_path):
    """Регресс: тестовый номер 9001 однажды «съел» реальные сообщения владельца.

    Раньше отметка была одним максимумом, и всё, что меньше него, считалось прочитанным.
    Теперь прочитанным становится ровно отмеченное сообщение.
    """
    tg_inbox.append_message(1, 9001, "тестовое", directory=tmp_path)
    tg_inbox.mark_seen(9001, tmp_path)
    tg_inbox.append_message(1, 238, "реальное сообщение владельца", directory=tmp_path)
    tg_inbox.append_message(1, 239, "и ещё одно", directory=tmp_path)
    mids = [r["message_id"] for r in tg_inbox.unread(tmp_path)]
    assert mids == [238, 239], mids


def test_state_survives_repeated_acks(tmp_path):
    for mid in (5, 7, 6):
        tg_inbox.append_message(1, mid, f"msg {mid}", directory=tmp_path)
        tg_inbox.mark_seen(mid, tmp_path)
    assert tg_inbox.unread(tmp_path) == []
    assert tg_inbox.seen_ids(tmp_path) == {5, 6, 7}


def test_unread_after_and_broken_lines(tmp_path):
    tg_inbox.append_message(1, 1, "старое", directory=tmp_path)
    tg_inbox.append_message(1, 2, "новое", directory=tmp_path)
    path = tmp_path / "inbox.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write("{это не json}\n")
    assert [r["message_id"] for r in tg_inbox.unread(tmp_path, after=1)] == [2]
    assert [r["message_id"] for r in tg_inbox.unread(tmp_path)] == [1, 2]
    assert tg_inbox.read_messages(tmp_path) == [
        {"ts": tg_inbox.read_messages(tmp_path)[0]["ts"], "chat_id": 1, "message_id": 1,
         "text": "старое", "kind": "message"},
        {"ts": tg_inbox.read_messages(tmp_path)[1]["ts"], "chat_id": 1, "message_id": 2,
         "text": "новое", "kind": "message"},
    ]


def test_wait_for_new_returns_message_appearing_later(tmp_path):
    def writer():
        time.sleep(0.3)
        tg_inbox.append_message(1, 42, "пришло позже", directory=tmp_path)

    threading.Thread(target=writer, daemon=True).start()
    rec = tg_inbox.wait_for_new(tmp_path, timeout=10, poll=0.1)
    assert rec is not None and rec["message_id"] == 42 and rec["text"] == "пришло позже"


def test_wait_for_new_times_out_quietly(tmp_path):
    assert tg_inbox.wait_for_new(tmp_path, timeout=0.2, poll=0.05) is None


def test_rotation_keeps_size(tmp_path, monkeypatch):
    monkeypatch.setattr(tg_inbox, "MAX_BYTES", 10)
    tg_inbox.append_message(1, 1, "первое сообщение", directory=tmp_path)
    tg_inbox.append_message(1, 2, "второе сообщение", directory=tmp_path)
    assert (tmp_path / "inbox.jsonl.1").exists()
    assert [r["message_id"] for r in tg_inbox.read_messages(tmp_path)] == [2]


def test_transport_writes_inbox(tmp_path, monkeypatch):
    """Входящее сообщение попадает и в очередь, и в надёжный ящик."""
    monkeypatch.setenv("TG_INBOX_DIR", str(tmp_path))
    tr = TelegramTransport("tok", on_message=lambda chat, text: None)
    tr._enqueue(7004751908, "привет", 777)
    recs = tg_inbox.read_messages(tmp_path)
    assert len(recs) == 1 and recs[0]["message_id"] == 777 and recs[0]["text"] == "привет"
    queued = tr._q.get_nowait()
    assert queued == (7004751908, "привет", 777)


def test_transport_inbox_failure_does_not_break_delivery(tmp_path, monkeypatch):
    """Даже если ящик недоступен, сообщение всё равно уходит в обработку."""
    monkeypatch.setattr(tg_inbox, "inbox_dir",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("нет места")))
    tr = TelegramTransport("tok", on_message=lambda chat, text: None)
    tr._enqueue(1, "важное", 5)
    assert tr._q.get_nowait() == (1, "важное", 5)


def test_cli_unread_and_ack(tmp_path, capsys):
    import runpy

    tg_inbox.append_message(1, 20, "пропущенное", directory=tmp_path)
    import sys

    argv = sys.argv
    try:
        sys.argv = ["tg_inbox.py", "--unread", "--dir", str(tmp_path)]
        try:
            runpy.run_path("tools/tg_inbox.py", run_name="__main__")
        except SystemExit as e:
            assert e.code == 0
        out = capsys.readouterr().out
        assert "msg 20" in out and "пропущенное" in out

        sys.argv = ["tg_inbox.py", "--ack", "20", "--dir", str(tmp_path)]
        try:
            runpy.run_path("tools/tg_inbox.py", run_name="__main__")
        except SystemExit as e:
            assert e.code == 0
        assert tg_inbox.unread(tmp_path) == []
    finally:
        sys.argv = argv


def test_cli_follow_returns_missed_immediately(tmp_path, capsys):
    import runpy
    import sys

    tg_inbox.append_message(1, 30, "пропущено пока меня не было", directory=tmp_path)
    argv = sys.argv
    try:
        sys.argv = ["tg_inbox.py", "--follow", "--dir", str(tmp_path)]
        try:
            runpy.run_path("tools/tg_inbox.py", run_name="__main__")
        except SystemExit as e:
            assert e.code == 0
        out = capsys.readouterr().out
        assert "msg 30" in out and "пропущено пока меня не было" in out
    finally:
        sys.argv = argv


def test_message_text_labels_voice_and_media():
    """Голосовые и прочие нетекстовые сообщения должны быть видимыми, а не пустыми."""
    T = TelegramTransport
    assert T._message_text({"text": "привет"}) == "привет"
    assert T._message_text({"caption": "подпись"}) == "подпись"
    voice = T._message_text({"voice": {"duration": 12, "file_id": "x"}})
    assert "голосовое" in voice and "12 сек" in voice
    assert "видео-кружок" in T._message_text({"video_note": {"duration": 5}})
    assert "аудио" in T._message_text({"audio": {"duration": 30, "file_name": "song.mp3"}})
    assert "song.mp3" in T._message_text({"audio": {"duration": 30, "file_name": "song.mp3"}})
    assert "фото" in T._message_text({"photo": [{"file_id": "p"}]})
    assert "стикер" in T._message_text({"sticker": {"file_id": "s"}})
    assert T._message_text({}) == ""


def test_voice_download_saves_into_data_dir(tmp_path, monkeypatch):
    """Голосовое скачивается в data/tg_voice, чтобы его можно было расшифровать."""
    import httpx

    monkeypatch.setenv("TG_INBOX_DIR", str(tmp_path / "inbox"))

    class FakeResp:
        def __init__(self, payload=None):
            self._payload = payload or {}

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

        def iter_bytes(self, _n):
            yield b"OggS"
            yield b"voice-bytes"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_get(url, **kw):
        assert url.endswith("/getFile")
        return FakeResp({"ok": True, "result": {"file_path": "voice/file_9.oga", "file_size": 15}})

    def fake_stream(method, url, **kw):
        assert url.endswith("/voice/file_9.oga"), url
        return FakeResp()

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "stream", fake_stream)
    tr = TelegramTransport("tok:1")
    saved = tr._download_voice({"voice": {"file_id": "fid"}, "message_id": 501})
    assert saved is not None and saved.endswith("501.oga")
    with open(saved, "rb") as fh:
        assert fh.read() == b"OggSvoice-bytes"


def test_voice_too_big_is_refused(tmp_path, monkeypatch):
    import httpx

    monkeypatch.setenv("TG_INBOX_DIR", str(tmp_path / "inbox"))

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True, "result": {"file_path": "voice/big.oga",
                                           "file_size": 50 * 1024 * 1024}}

    monkeypatch.setattr(httpx, "get", lambda url, **kw: FakeResp())
    tr = TelegramTransport("tok:1")
    assert tr._download_voice({"voice": {"file_id": "fid"}, "message_id": 502}) is None


def test_enqueue_keeps_voice_file_path(tmp_path, monkeypatch):
    """Путь к голосовому сохраняется в ящике — по нему потом работает расшифровка."""
    monkeypatch.setenv("TG_INBOX_DIR", str(tmp_path))
    tr = TelegramTransport("tok:1")
    tr._enqueue(1, "[голосовое 12 сек — текст не расшифрован]", 55,
                extra={"voice_file": "/opt/orchestrator/data/tg_voice/55.oga"})
    rec = tg_inbox.read_messages(tmp_path)[0]
    assert rec["voice_file"].endswith("55.oga")
    assert rec["kind"] == "message"


def test_annotate_text_adds_transcript_to_existing_record(tmp_path):
    """Расшифровка, пришедшая позже, дописывается в ту же запись ящика."""
    tg_inbox.append_message(1, 77, "[голосовое 8 сек — текст не расшифрован]",
                            directory=tmp_path, extra={"voice_file": "/x/77.oga"})
    assert tg_inbox.annotate_text(77, "привет это расшифровка", tmp_path) is True
    recs = tg_inbox.read_messages(tmp_path)
    assert len(recs) == 1
    assert "привет это расшифровка" in recs[0]["text"]
    assert recs[0]["kind"] == "voice_text"
    assert recs[0]["voice_file"] == "/x/77.oga"
    # повторная вставка того же текста ничего не портит
    assert tg_inbox.annotate_text(77, "привет это расшифровка", tmp_path) is False
    assert len(tg_inbox.read_messages(tmp_path)) == 1
    # а новый (лучший) вариант расшифровки заменяет прежний, а не наслаивается
    assert tg_inbox.annotate_text(77, "привет это точная расшифровка", tmp_path) is True
    recs = tg_inbox.read_messages(tmp_path)
    assert len(recs) == 1
    assert recs[0]["voice_text"] == "привет это точная расшифровка"
    assert "привет это расшифровка " not in recs[0]["text"]
    assert recs[0]["text"].endswith("привет это точная расшифровка")


def test_voice_stt_disabled_by_default(monkeypatch):
    from orchestrator import voice_stt

    monkeypatch.delenv("TG_VOICE_STT", raising=False)
    assert voice_stt.enabled() is False
    monkeypatch.setenv("TG_VOICE_STT", "1")
    assert voice_stt.enabled() is True
    assert voice_stt.model_name() == "base"
    monkeypatch.setenv("TG_VOICE_STT_MODEL", "small")
    assert voice_stt.model_name() == "small"


def test_voice_stt_transcribe_uses_env_python(tmp_path, monkeypatch):
    """transcribe_file зовёт отдельное окружение и возвращает текст; ошибки не пробрасывает."""
    from orchestrator import voice_stt

    fake_py = tmp_path / "py"
    fake_py.write_text("#!/bin/sh\necho '  расшифрованный текст  '\n", encoding="utf-8")
    fake_py.chmod(0o755)
    monkeypatch.setenv("TG_VOICE_STT_PYTHON", str(fake_py))
    audio = tmp_path / "v.oga"
    audio.write_bytes(b"x")
    assert voice_stt.transcribe_file(audio) == "расшифрованный текст"
    assert voice_stt.available() is True
    assert voice_stt.transcribe_file(tmp_path / "нет.oga") is None


def test_voice_stt_reports_failure_quietly(tmp_path, monkeypatch):
    from orchestrator import voice_stt

    bad = tmp_path / "py"
    bad.write_text("#!/bin/sh\nexit 3\n", encoding="utf-8")
    bad.chmod(0o755)
    monkeypatch.setenv("TG_VOICE_STT_PYTHON", str(bad))
    monkeypatch.setenv("TG_VOICE_STT_TIMEOUT", "30")
    audio = tmp_path / "v.oga"
    audio.write_bytes(b"x")
    assert voice_stt.transcribe_file(audio) is None


def test_voice_download_returns_absolute_path(tmp_path, monkeypatch):
    """Путь в ящике должен быть абсолютным: по нему файл забирают с сервера по ssh."""
    import httpx

    monkeypatch.chdir(tmp_path)

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True, "result": {"file_path": "voice/f.oga", "file_size": 10}}

        def iter_bytes(self, _n):
            yield b"data"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(httpx, "get", lambda url, **kw: FakeResp())
    monkeypatch.setattr(httpx, "stream", lambda method, url, **kw: FakeResp())
    monkeypatch.delenv("TG_INBOX_DIR", raising=False)
    tr = TelegramTransport("tok:1")
    saved = tr._download_voice({"voice": {"file_id": "f"}, "message_id": 33})
    assert saved and saved.startswith("/"), saved
    assert os.path.isabs(saved)


def test_recover_voices_transcribes_pending(tmp_path, monkeypatch):
    """После перезапуска службы недоделанные голосовые расшифровываются заново."""
    from orchestrator import telegram_transport as tt
    from orchestrator import voice_stt

    monkeypatch.setenv("TG_INBOX_DIR", str(tmp_path / "inbox"))
    monkeypatch.setenv("TG_VOICE_STT", "1")
    monkeypatch.setattr(voice_stt, "available", lambda: True)
    monkeypatch.setattr(voice_stt, "transcribe_file", lambda path, **kw: "текст из голосового")
    tg_inbox.append_message(1, 88, "[голосовое 5 сек — текст не расшифрован]",
                            directory=tmp_path / "inbox", extra={"voice_file": "/x/88.oga"})
    tg_inbox.append_message(1, 89, "обычное сообщение", directory=tmp_path / "inbox")
    tr = tt.TelegramTransport("tok:1")
    assert tr.recover_voices(str(tmp_path / "inbox")) == 1
    for _ in range(200):
        recs = tg_inbox.read_messages(tmp_path / "inbox")
        if any("текст из голосового" in str(r.get("text")) for r in recs):
            break
        time.sleep(0.05)
    recs = tg_inbox.read_messages(tmp_path / "inbox")
    assert any("текст из голосового" in str(r.get("text")) for r in recs)
    # обычное сообщение не тронули
    assert any(r["message_id"] == 89 and r["text"] == "обычное сообщение" for r in recs)


def test_voice_stt_prepare_audio_uses_ffmpeg(tmp_path, monkeypatch):
    """Звук перед разбором выравнивается по громкости; без ffmpeg берём исходный файл."""
    from orchestrator import voice_stt

    audio = tmp_path / "v.oga"
    audio.write_bytes(b"x")
    fake = tmp_path / "ffmpeg"
    fake.write_text("#!/bin/sh\nfor a in \"$@\"; do last=\"$a\"; done\nprintf wav > \"$last\"\n",
                    encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ.get('PATH', '')}")
    out = voice_stt.prepare_audio(audio)
    assert out != audio and out.suffix == ".wav" and out.read_bytes() == b"wav"
    # ffmpeg нет — возвращаем исходный путь, ничего не ломаем
    monkeypatch.setenv("PATH", str(tmp_path / "пусто"))
    assert voice_stt.prepare_audio(audio) == audio


def test_prepare_audio_for_mac_tool(tmp_path, monkeypatch):
    """Тот же шаг в инструменте на Mac."""
    import importlib.util
    import sys as _sys

    spec = importlib.util.spec_from_file_location(
        "tg_voice_tool", str(Path(__file__).resolve().parents[1] / "tools" / "tg_voice.py"))
    mod = importlib.util.module_from_spec(spec)
    _sys.modules["tg_voice_tool"] = mod
    spec.loader.exec_module(mod)
    audio = tmp_path / "v.oga"
    audio.write_bytes(b"x")
    monkeypatch.setenv("PATH", str(tmp_path / "пусто"))
    assert mod.prepare_audio(str(audio)) == str(audio)


def test_photo_download_saves_largest_size(tmp_path, monkeypatch):
    """Скриншот владельца сохраняется (самый крупный размер) — чтобы я мог посмотреть панель."""
    import httpx

    monkeypatch.setenv("TG_INBOX_DIR", str(tmp_path / "inbox"))

    class FakeResp:
        def __init__(self, payload=None):
            self._payload = payload or {}

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

        def iter_bytes(self, _n):
            yield b"\xff\xd8jpeg-bytes"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    seen = {}

    def fake_get(url, params=None, **kw):
        seen["file_id"] = (params or {}).get("file_id")
        return FakeResp({"ok": True, "result": {"file_path": "photos/big.jpg", "file_size": 100}})

    def fake_stream(method, url, **kw):
        seen["url"] = url
        return FakeResp()

    monkeypatch.setattr(httpx, "get", fake_get)
    monkeypatch.setattr(httpx, "stream", fake_stream)
    tr = TelegramTransport("tok:1")
    msg = {"message_id": 601, "photo": [
        {"file_id": "small", "file_size": 10, "width": 90, "height": 60},
        {"file_id": "big", "file_size": 9000, "width": 1280, "height": 900},
    ]}
    saved = tr._download_photo(msg)
    assert saved is not None and saved.endswith("601.jpg")
    assert seen["file_id"] == "big"
    with open(saved, "rb") as fh:
        assert fh.read() == b"\xff\xd8jpeg-bytes"
