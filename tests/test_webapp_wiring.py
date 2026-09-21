"""Регресс-проверки проводки UI (P1-10…P1-14 из аудита 2026-09-21).

Проверяют, что найденные «мёртвые» кнопки/экраны снова подключены: статические
инварианты по исходнику `webapp/app.js` (jsdom-smoke дополнительно гоняет поведение).
"""
from __future__ import annotations

from pathlib import Path

APP_JS = Path(__file__).resolve().parents[1] / "webapp" / "app.js"


def _js() -> str:
    return APP_JS.read_text(encoding="utf-8")


def test_backlog_answer_has_handler():
    """P1-11: кнопки «Распределить/Ждать/Не публиковать» должны вызывать /backlog/answer."""
    js = _js()
    assert 'data-act="backlog-answer"' in js
    assert 'act === "backlog-answer"' in js
    assert '"/backlog/answer"' in js


def test_errors_and_help_have_own_views():
    """P1-13: «Ошибки» и «Справка» — отдельные экраны, а не «Настройки»."""
    js = _js()
    assert 'state.view === "failed"' in js
    assert "failedHtml(" in js
    assert 'state.view === "help"' in js
    assert "helpHtml()" in js


def test_load_has_generation_guard():
    """P1-14: поздний ответ прошлого экрана не должен перерисовывать текущий."""
    assert "_loadGen" in _js()


def test_overlay_delegates_actions():
    """P1-12: делегат [data-act] должен ловить клики внутри оверлея (кнопка «Отмена»)."""
    js = _js()
    idx = js.index("function _overlay()")
    block = js[idx:idx + 700]
    assert "addEventListener" in block and "[data-act]" in block


def test_queue_edit_save_releases_busy():
    """P1-10: ошибка /queue/edit не должна оставлять вечный busy-оверлей."""
    js = _js()
    idx = js.index('act === "queue-edit-save"')
    block = js[idx:idx + 1600]
    assert "finally" in block
    assert "unbusy()" in block
