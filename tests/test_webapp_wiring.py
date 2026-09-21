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


def test_trash_view_is_wired():
    """Корзина: view, пункт шторки «Ещё», загрузка и рендер."""
    js = _js()
    assert "function renderTrash(" in js
    assert 'state.view === "trash"' in js
    assert 'else if (v === "trash") data = await api("/trash");' in js
    assert '["trash", "trash"]' in js          # пункт шторки «Ещё»
    assert "title_trash" in js


def test_trash_actions_are_wired():
    js = _js()
    for act in ("trash-select", "trash-check", "trash-check-all",
                "trash-restore", "trash-restore-all", "trash-purge"):
        assert f'act === "{act}"' in js, act
    assert '"/trash/restore"' in js and '"/trash/purge"' in js


def test_delete_dialog_uses_plan_and_scope():
    """Интерактивное окно удаления: план с сервера, выбор объёма и правило YouTube→Telegram."""
    js = _js()
    assert "function openDeleteDialog(" in js
    assert "plan_only: true" in js
    assert 'data-dd="scope|all"' in js
    assert "with_shorts: scopeAll" in js
    assert "also_youtube: alsoYt" in js
    assert "del_yt_note" in js and "del_tg_ask" in js


def test_audit_fixes_8_4_11_wiring():
    """F1/F2/F5–F11: блокировка по выбранному, fallback confirm, i18n, a11y, favicon, SDK-guards."""
    js = _js()
    # F1: блокировка считается по chosen(), а не по полному плану
    assert "ch.some((x) => x.status === \"published\")" in js
    assert "blockedList" not in js
    # F2: showConfirm только внутри confirmDialog (через локальную w + guard), прямой вызов убран
    assert "window.Telegram.WebApp.showConfirm" not in js
    assert 'typeof w.showConfirm === "function"' in js
    assert 'tgOk("6.1")' in js
    # F5/F6: человекочитаемые коды и локализованные сущности
    assert "function errText(" in js and "errText(it.last_error)" in js
    assert "const entityLabel =" in js and "dow_" in js
    # F7: плюрализация
    assert "function postsLabel(" in js and "postsLabel(cnt)" in js
    # F8: пустая дата не оставляет висячий разделитель
    assert "(deleted ? ` · ${esc(deleted)}` : \"\")" in js
    # F9: Escape и фокус в окне
    assert 'document.addEventListener("keydown", onKey)' in js
    # F11: guards
    assert 'const tgOk = (v) =>' in js and 'tgOk("7.7")' in js
    # F10: favicon
    html = (APP_JS.parent / "index.html").read_text(encoding="utf-8")
    assert 'rel="icon"' in html



def test_n1_n2_n3_wiring():
    """N1/N2/N3: снятие с платформы в окне, локализация ошибок, дружелюбный Media."""
    js = _js()
    assert '"/queue/detach"' in js            # N1: вызов снятия
    assert 'data-dd="detach"' in js           # N1: чекбокс в окне
    assert "function apiErrorText(" in js and "function toastErr(" in js  # N2
    assert 'error_prefix")}: ${e.message}' not in js                      # N2: сырых тостов нет
    assert "state.browseError" in js          # N3
    assert "no browse roots configured (WEBAPP_BROWSE_ROOT)" not in js


def test_n1_abc_n2_n4_wiring():
    """N1-a/b/c, остаток N2 и путь N4: метка detached, закрытие окна, локализация, /browse."""
    js = _js()
    assert 'it.deleted_reason === "detached"' in js   # N1-a: метка в корзине
    assert "trash_detached" in js
    assert "toast(e.message)" not in js               # N2: сырых тостов больше нет
    assert "N1-c: закрываем только при успехе" in js  # N1-c
    assert "nRoots === 0" in js                       # N4: не дёргаем /browse без корней
