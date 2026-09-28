AGENT HANDOFF — postiz-orchestrator 2026-09-25
==============================================
Грунт агента: docs/dev/13_AGENT_HANDOFF_PROMPT.txt
  §B запреты | §C можно | §D версии | §E анти-деградация | §F матрица тестов
  §G стандарты кода | §H очередь H1–H11 | §I цикл | §L bootstrap

Установка:
  cd postiz-orchestrator && git pull
  (cd /path/to/extracted/agent-pack && tar cf - .) | (cd /path/to/repo && tar xf -)

Анти-деградация:
  PYTHONPATH=src python3 -m pytest tests/test_youtube_module.py tests/test_youtube_p2_extra.py \
    tests/test_manual_sources_module.py tests/test_telegram_module.py tests/test_postiz_module.py \
    tests/test_b2_media_host.py tests/test_platform_skeletons.py tests/test_ig_fb_expanded.py \
    tests/test_daily_ahead.py tests/test_contract_templates.py -q
  # ≥74 passed, 3 skipped
  ./scripts/check.sh

НЕ engines.*=module:* до P5. Секреты не в git.
