#!/usr/bin/env python3
"""Расшифровка голосовых сообщений из Telegram — настройками видеомейкера.

Настройки взяты из проекта VideoMaker (`~/VideoMaker/video_maker/engines/transcription.py`,
там они зафиксированы как обязательные):
    path_or_hf_repo = mlx-community/whisper-large-v3-turbo
    temperature = 0.0
    language = ru
    condition_on_previous_text = False
    verbose = False
    word_timestamps = True

Запускать на Mac (MLX работает на Apple Silicon; модель уже скачана видеомейкером).
На сервере тот же движок недоступен — там голосовые только копятся в ящике,
а расшифровка идёт здесь.

Примеры:
  ./venv/bin/python tools/tg_voice.py --file ~/Downloads/voice.oga
  ./venv/bin/python tools/tg_voice.py --unread            # все непрочитанные голосовые с сервера
  ./venv/bin/python tools/tg_voice.py --unread --ack      # и сразу отметить их прочитанными
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

MLX_REPO = "mlx-community/whisper-large-v3-turbo"  # как в видеомейкере
HOST = "root@100.95.225.71"
REMOTE_APP = "/opt/orchestrator"


AUDIO_FILTER = "highpass=f=80,loudnorm=I=-18:TP=-2:LRA=11"


def prepare_audio(path: str) -> str:
    """Выровнять громкость и привести к 16 кГц моно: тихие голосовые разбираются заметно лучше."""
    import shutil
    import tempfile

    src = Path(path)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not src.is_file():
        return path
    out = Path(tempfile.gettempdir()) / f"{src.stem}_norm.wav"
    cmd = [ffmpeg, "-y", "-v", "error", "-i", str(src), "-af", AUDIO_FILTER,
           "-ar", "16000", "-ac", "1", str(out)]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=120, check=False)
    except (OSError, subprocess.SubprocessError):
        return path
    return str(out) if r.returncode == 0 and out.exists() else path


def transcribe(path: str, language: str = "ru") -> str:
    """Распознать файл настройками видеомейкера. Модель держим в памяти процесса."""
    import mlx_whisper  # импорт внутри: без MLX модуль просто не запустится

    result = mlx_whisper.transcribe(
        prepare_audio(path),
        path_or_hf_repo=MLX_REPO,
        temperature=0.0,
        language=language,
        condition_on_previous_text=False,
        verbose=False,
        word_timestamps=True,
    )
    parts = [str(seg.get("text", "")).strip() for seg in result.get("segments") or []]
    return " ".join(p for p in parts if p).strip()


def remote_unread() -> list[dict]:
    """Непрочитанные сообщения с сервера (JSON-строками)."""
    out = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", HOST,
         f"cd {REMOTE_APP} && ./venv/bin/python tools/tg_inbox.py --unread --json"],
        capture_output=True, text=True, timeout=120, check=False,
    )
    recs = []
    for line in out.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return recs


def fetch_voice(remote_path: str, dest: Path, *, tries: int = 3) -> bool:
    """Забрать файл с сервера. Путь может быть относительным — тогда считаем от /opt/orchestrator."""
    path = remote_path if remote_path.startswith("/") else f"{REMOTE_APP}/{remote_path}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(tries):
        res = subprocess.run(["ssh", "-o", "BatchMode=yes", HOST, f"cat {path}"],
                             capture_output=True, timeout=300, check=False)
        if res.returncode == 0 and res.stdout:
            dest.write_bytes(res.stdout)
            return True
        if attempt + 1 < tries:
            time.sleep(2)
    return False


def remote_follow(timeout: float = 0.0) -> dict | None:
    """Дождаться нового (или пропущенного) сообщения на сервере и вернуть его записью."""
    import subprocess as sp

    cmd = f"cd {REMOTE_APP} && ./venv/bin/python tools/tg_inbox.py --follow --json"
    if timeout:
        cmd += f" --timeout {int(timeout)}"
    out = sp.run(["ssh", "-o", "BatchMode=yes", HOST, cmd],
                 capture_output=True, text=True, timeout=(timeout + 300) if timeout else None,
                 check=False)
    recs = []
    for line in out.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return recs[-1] if recs else None


def remote_ack(ids: list[int]) -> None:
    if not ids:
        return
    subprocess.run(
        ["ssh", "-o", "BatchMode=yes", HOST,
         f"cd {REMOTE_APP} && ./venv/bin/python tools/tg_inbox.py --ack {' '.join(map(str, ids))}"],
        check=False, timeout=120,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Расшифровка голосовых из Telegram (настройки видеомейкера)")
    ap.add_argument("--file", help="локальный файл голосового")
    ap.add_argument("--unread", action="store_true", help="взять непрочитанные голосовые с сервера")
    ap.add_argument("--ack", action="store_true", help="отметить расшифрованные прочитанными")
    ap.add_argument("--follow", action="store_true",
                    help="сторож: ждать новое сообщение и, если это голосовое, расшифровать его")
    ap.add_argument("--language", default="ru")
    ap.add_argument("--timeout", type=float, default=0.0,
                    help="сколько секунд ждать в --follow (0 — бесконечно)")
    args = ap.parse_args()

    if args.file:
        print(transcribe(args.file, args.language))
        return 0

    if args.follow:
        rec = remote_follow(args.timeout)
        if rec is None:
            print("тишина: новых сообщений нет", file=sys.stderr)
            return 1
        print(f"msg {rec.get('message_id')} | chat {rec.get('chat_id')}")
        print(rec.get("text", ""))
        src = rec.get("voice_file")
        if src:
            local = Path("/tmp/tg_voice") / f"{rec.get('message_id')}{Path(src).suffix or '.oga'}"
            if fetch_voice(src, local):
                try:
                    print(transcribe(str(local), args.language))
                except Exception as e:  # noqa: BLE001 — показываем причину
                    print(f"(расшифровка не удалась: {e})")
            else:
                print("(не удалось скачать голосовое с сервера)")
        return 0

    if not args.unread:
        ap.error("укажи --file, --unread или --follow")

    recs = remote_unread()
    voices = [r for r in recs if r.get("voice_file")]
    if not voices:
        print("голосовых без расшифровки нет")
        return 0

    done: list[int] = []
    work = Path("/tmp/tg_voice")
    for rec in voices:
        mid = rec.get("message_id")
        src = rec["voice_file"]
        local = work / f"{mid}{Path(src).suffix or '.oga'}"
        print(f"== msg {mid} ({rec.get('text', '')})")
        if not fetch_voice(src, local):
            print("   не удалось скачать с сервера")
            continue
        try:
            text = transcribe(str(local), args.language)
        except Exception as e:  # noqa: BLE001 — показываем причину, а не падаем
            print(f"   расшифровка не удалась: {e}")
            continue
        print(f"   {text}")
        done.append(int(mid)) if mid else None

    if args.ack:
        remote_ack(done)
        print(f"отмечено прочитанными: {done}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
