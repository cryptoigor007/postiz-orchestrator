

def test_send_post_falls_back_to_plain_text_on_parse_error():
    """Регресс: «<проект>» в тексте ломало разметку — сообщение не уходило.

    Теперь при ошибке разбора Telegram повторяем отправку без HTML, чтобы текст дошёл.
    """
    import json

    from orchestrator.telegram_publish import TelegramPublisher

    calls = []

    class FakeResp:
        def __init__(self, code, payload):
            self.status_code = code
            self._payload = payload
            # настоящий ответ Telegram в теле содержит описание ошибки — повторяем это
            self.text = json.dumps(payload, ensure_ascii=False)

        def json(self):
            return self._payload

    def fake_post(url, json):  # noqa: A002 - имитация httpx
        calls.append(dict(json))
        if len(calls) == 1:
            return FakeResp(400, {"ok": False, "error_code": 400,
                                  "description": "Bad Request: can't parse entities: Unsupported start tag"})
        return FakeResp(200, {"ok": True, "result": {"message_id": 77}})

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json):  # noqa: A002
            return fake_post(url, json)

    import orchestrator.telegram_publish as tp

    monkey = tp.httpx.Client
    tp.httpx.Client = FakeClient
    try:
        pub = TelegramPublisher("tok:1", "1")
        post_id = pub.send_post("текст с <проект> внутри")
    finally:
        tp.httpx.Client = monkey
    assert post_id == "tg:77"
    assert calls[0].get("parse_mode") == "HTML"
    assert "parse_mode" not in calls[1]
    assert calls[1]["text"] == "текст с <проект> внутри"


def test_send_chat_action_shows_typing():
    """Владелец просил видеть, что работа идёт: бот показывает «печатает…» (sendChatAction)."""
    from orchestrator.telegram_publish import TelegramPublisher

    calls = []

    class FakeResp:
        status_code = 200
        text = "{}"

        def json(self):
            return {"ok": True, "result": True}

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json):  # noqa: A002
            calls.append((url, json))
            return FakeResp()

    import orchestrator.telegram_publish as tp

    monkey = tp.httpx.Client
    tp.httpx.Client = FakeClient
    try:
        pub = TelegramPublisher("tok:1", "5")
        assert pub.send_chat_action() is True
    finally:
        tp.httpx.Client = monkey
    assert calls[0][0].endswith("/sendChatAction")
    assert calls[0][1] == {"chat_id": "5", "action": "typing"}


def test_send_photo_uploads_screenshot(tmp_path):
    """Владельцу можно показать результат картинкой: sendPhoto уходит multipart-ом."""
    from orchestrator.telegram_publish import TelegramPublisher

    shot = tmp_path / "after.png"
    shot.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
    calls = []

    class FakeResp:
        status_code = 200
        text = "{}"

        def json(self):
            return {"ok": True, "result": {"message_id": 987}}

    class FakeClient:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, data=None, files=None, json=None):  # noqa: A002
            calls.append({"url": url, "data": dict(data or {}), "files": dict(files or {}), "json": json})
            return FakeResp()

    import orchestrator.telegram_publish as tp

    monkey = tp.httpx.Client
    tp.httpx.Client = FakeClient
    try:
        pub = TelegramPublisher("tok:1", "5")
        assert pub.send_photo(shot, "как стало") == "tg:987"
    finally:
        tp.httpx.Client = monkey

    call = calls[0]
    assert call["url"].endswith("/sendPhoto")
    assert call["json"] is None
    assert call["data"]["chat_id"] == "5"
    assert call["data"]["caption"] == "как стало"
    assert call["files"]["photo"][0] == "after.png"

    import pytest

    with pytest.raises(RuntimeError):
        TelegramPublisher("tok:1", "5").send_photo(tmp_path / "missing.png")
