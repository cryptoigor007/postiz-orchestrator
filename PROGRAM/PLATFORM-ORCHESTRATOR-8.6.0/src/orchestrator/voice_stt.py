"""Распознавание речи на сервере — резервный путь, когда Mac недоступен.

На Mac основная расшифровка идёт через MLX Whisper (`tools/tg_voice.py`, настройки видеомейкера).
Если Mac выключен, текст голосового всё равно нужен — тогда работает этот модуль: он зовёт
`faster-whisper` из отдельного окружения (по умолчанию `/opt/stt-venv`), чтобы не тащить
машинное обучение в окружение самого оркестратора.

Замеры на сервере (10-секундный файл, 4 ядра i7-7500U, int8): tiny — 10 с и 341 МБ,
base — 17 с и 458 МБ. Поэтому по умолчанию tiny: быстрее и легче.

Настройки через переменные окружения:
  TG_VOICE_STT=1                       — включить серверную расшифровку
  TG_VOICE_STT_PYTHON=/opt/stt-venv/bin/python
  TG_VOICE_STT_MODEL=base|small|tiny
  TG_VOICE_STT_TIMEOUT=180

Замеры на РЕАЛЬНОМ голосовом владельца (10 с, phone-запись) с VAD и без «условия на прошлый текст»:
  tiny — 7 с, 346 МБ, текст мусорный («3-дизма, где не через 7 врачом»);
  base — 2,6 с, 402 МБ, текст читаемый; small — 50 с, 1005 МБ, текст чуть лучше.
Эталон — MLX large-v3-turbo на Mac: «проверки связи сейчас как это все происходит через мак или
через сервис причем распознавание голоса и идет ли вообще» (расшифровано верно). Поэтому основной
путь — Mac, а серверный резерв работает на base: быстро и без мусора.
"""

from __future__ import annotations

import logging
import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_PYTHON = "/opt/stt-venv/bin/python"
DEFAULT_MODEL = "base"
DEFAULT_TIMEOUT = 180

#: Небольшая программа, которая выполняется отдельным окружением: без импорта в процесс оркестратора.
CHILD = (
    "import sys\n"
    "from faster_whisper import WhisperModel\n"
    "model = WhisperModel(sys.argv[1], device='cpu', compute_type='int8')\n"
    "segs, _ = model.transcribe(sys.argv[2], language=sys.argv[3], beam_size=5,\n"
    "                            condition_on_previous_text=False, vad_filter=True)\n"
    "print(' '.join(s.text.strip() for s in segs).strip())\n"
)


#: Приведение звука к 16 кГц моно с выравниванием громкости — заметно улучшает разбор
#: тихих голосовых (проверено на реальном сообщении владельца).
AUDIO_FILTER = "highpass=f=80,loudnorm=I=-18:TP=-2:LRA=11"


def prepare_audio(path: str | Path) -> Path:
    """Нормализовать звук через ffmpeg. Если ffmpeg нет — вернуть исходный файл."""
    audio = Path(path)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not audio.is_file():
        return audio
    out = Path(tempfile.gettempdir()) / f"stt_{audio.stem}_norm.wav"
    cmd = [ffmpeg, "-y", "-v", "error", "-i", str(audio), "-af", AUDIO_FILTER,
           "-ar", "16000", "-ac", "1", str(out)]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=120, check=False)
    except (OSError, subprocess.SubprocessError):
        return audio
    return out if r.returncode == 0 and out.exists() else audio


def enabled() -> bool:
    return bool(os.getenv("TG_VOICE_STT", "").strip())


def python_path() -> str:
    return os.getenv("TG_VOICE_STT_PYTHON", "").strip() or DEFAULT_PYTHON


def model_name() -> str:
    return os.getenv("TG_VOICE_STT_MODEL", "").strip() or DEFAULT_MODEL


def available() -> bool:
    """Есть ли чем распознавать: интерпретатор и faster_whisper на месте."""
    py = python_path()
    if not Path(py).exists():
        return False
    try:
        r = subprocess.run([py, "-c", "import faster_whisper"],
                           capture_output=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0


def transcribe_file(path: str | Path, *, language: str = "ru") -> str | None:
    """Текст из аудиофайла. None — если не получилось (причина в журнале)."""
    audio = Path(path)
    if not audio.is_file():
        return None
    py = python_path()
    timeout = int(os.getenv("TG_VOICE_STT_TIMEOUT", "") or DEFAULT_TIMEOUT)
    cmd = [py, "-c", CHILD, model_name(), str(prepare_audio(audio)), language]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError) as e:
        logger.warning("voice stt failed (%s): %s", py, e)
        return None
    if r.returncode != 0:
        logger.warning("voice stt exit %s: %s", r.returncode, (r.stderr or "")[-300:])
        return None
    text = (r.stdout or "").strip()
    logger.info("voice stt (%s/%s): %s", Path(py).name, model_name(),
                shlex.quote(text[:120]))
    return text or None
