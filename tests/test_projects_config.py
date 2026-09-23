"""Проекты (ниши) в конфиге — этап 1: плумбинг без смены поведения.

Смысл: у каждого проекта свои каналы во всех сетях, поэтому платформа знает свой проект,
а сущность (серия или папка) — свой. Пока проект один, всё работает как раньше.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orchestrator.config import AppConfig, PlatformCfg, ProjectCfg, load_config

ROOT = Path(__file__).resolve().parents[1]


def _cfg(**kw) -> AppConfig:
    base = {
        "schedules": {},
        "platforms": {
            "telegram": PlatformCfg(),
            "youtube": PlatformCfg(video_variant="wide"),
            "telegram_anekdoty": PlatformCfg(project="anekdoty"),
            "youtube_anekdoty": PlatformCfg(project="anekdoty", video_variant="wide"),
        },
        "projects": {
            "tochka": ProjectCfg(title="Точка наблюдения", series_ids=[12, 13],
                                 folders=["/mnt/video/ютюб/точка"]),
            "anekdoty": ProjectCfg(title="Анекдоты", series_ids=[21],
                                   folders=["/mnt/video/ютюб/анекдоты"]),
        },
    }
    base.update(kw)
    return AppConfig(**base)


def test_project_of_series():
    cfg = _cfg()
    assert cfg.project_of_series(12) == "tochka"
    assert cfg.project_of_series(21) == "anekdoty"
    assert cfg.project_of_series(999) == ""
    assert cfg.project_of_series(None) == ""


def test_project_of_folder_prefix_and_nested():
    cfg = _cfg()
    assert cfg.project_of_folder("/mnt/video/ютюб/анекдоты") == "anekdoty"
    assert cfg.project_of_folder("/mnt/video/ютюб/анекдоты/выпуск 5/") == "anekdoty"
    assert cfg.project_of_folder("/mnt/video/ютюб/точка") == "tochka"
    assert cfg.project_of_folder("/mnt/video/broll_downloads/7") == ""
    assert cfg.project_of_folder("") == ""
    assert cfg.project_of_folder(None) == ""


def test_platform_without_project_accepts_everything():
    """Старое поведение: платформа без проекта берёт любой контент."""
    cfg = _cfg()
    assert cfg.platform_matches_project("telegram", series_id=21)
    assert cfg.platform_matches_project("telegram", folder="/mnt/video/что угодно")
    assert cfg.platform_matches_project("youtube", series_id=12)


def test_project_platform_takes_only_its_entities():
    cfg = _cfg()
    assert cfg.platform_matches_project("telegram_anekdoty", series_id=21)
    assert cfg.platform_matches_project("telegram_anekdoty", folder="/mnt/video/ютюб/анекдоты/1")
    # чужая серия и чужая папка — не публикуем
    assert not cfg.platform_matches_project("telegram_anekdoty", series_id=12)
    assert not cfg.platform_matches_project("telegram_anekdoty", folder="/mnt/video/ютюб/точка")
    # сущность вне проектов не попадает в проектные каналы
    assert not cfg.platform_matches_project("telegram_anekdoty", series_id=999)
    assert not cfg.platform_matches_project("telegram_anekdoty")


def test_platforms_of_project_and_title():
    cfg = _cfg()
    assert sorted(cfg.platforms_of_project("anekdoty")) == ["telegram_anekdoty", "youtube_anekdoty"]
    assert sorted(cfg.platforms_of_project("")) == ["telegram", "youtube"]
    assert cfg.project_title("anekdoty") == "Анекдоты"
    assert cfg.project_title("") == "Основной"
    assert cfg.project_title("неизвестный") == "неизвестный"


def test_unknown_project_in_platform_is_rejected():
    with pytest.raises(Exception) as e:
        AppConfig(schedules={}, platforms={"telegram": PlatformCfg(project="нет_такого")},
                  projects={"tochka": ProjectCfg()})
    assert "нет_такого" in str(e.value)


def test_live_config_loads_and_stays_single_project():
    """Боевой config.yaml: проекты описаны, но платформы пока без привязки."""
    cfg = load_config(ROOT / "config.yaml")
    assert "tochka" in cfg.projects
    assert cfg.projects["tochka"].title
    assert all((p.project or "") == "" for p in cfg.platforms.values())
    # значит ничей контент не отсекается
    assert all(cfg.platform_matches_project(name, series_id=1)
               for name in cfg.platforms)
