(() => {
  const tg = window.Telegram?.WebApp;

  const I18N = {
    ru: {
      queue_remove_film_only: "Только фильм",
      confirm_film_only: "Удалить только фильм? Все его шортсы останутся в базе. Telegram-пост со ссылкой на фильм тоже будет удалён.",
      confirm_delete_short: "Удалить этот ролик и его посты (включая базу)?",
      warn_tg_link: "Внимание: в Telegram стоит пост со ссылкой на этот ролик — он тоже будет удалён, и ссылка не выйдет.",
      edit_cover: "Обложка", cover_none: "Без обложки",
      cover_pick: "Выбрать обложку…", cover_picker_title: "Выбор обложки",
      cover_tab_server: "Папки на сервере", cover_tab_device: "С устройства",
      cover_tab_url: "По ссылке", cover_choose: "Выбрать", cover_close: "Закрыть",
      cover_tab_frames: "Кадры", cover_frames_hint: "Кадры из видео — выбери понравившийся",
      cover_frames_regen: "Ещё кадры", cover_frames_btn: "Сделать кадры из видео",
      cover_no_images: "Картинок нет", cover_up: "↑ Вверх", cover_loading: "Загрузка…",
      cover_added: "Обложка выбрана", cover_upload: "Загрузить с устройства",
      request_timeout: "Сервер не ответил (таймаут). Проверь связь и повтори.",
      session_stale: "Сессия устарела — открой панель заново из бота.",
      t_bulk_failed: "Ошибок: %s",
      cant_delete_published: "Нельзя удалить: уже опубликовано",
      already_removed: "Уже удалено ранее", retrying: "Повторяю…",
      cover_fetch: "Скачать", cover_url_hint: "Вставьте ссылку на картинку (http/https)",
      cover_dirs: "Папки", cover_images: "Картинки", cover_start_hint: "Начало: папка видео",
      pick_file: "Файл не выбран",
      cancel: "Отменить", left: "осталось", sec_short: "с", min_short: "мин",
      job_scheduling: "Планирование публикаций", job_restore: "Возврат удалённого",
      job_cancelling: "Отменяем…", job_cancelled: "Отменено", job_done: "Готово",
      scan_date_films: "Фильмы с", scan_date_shorts: "Шортсы с", scan_run_dates: "Запустить с дат",
      t_started_async: "Запущено — посты добавляются постепенно", working: "Выполняется…",
      confirm_delete_film: "Удалить фильм, все его шортсы и посты (включая базу)? После этого скан добавит его заново.",
      scan_none_new_hint: "Новых не найдено: всё уже в базе. Если хочешь добавить заново — удали из очереди (кнопка «Убрать» удаляет и из базы).",
      scan_empty_hint: "В этих папках видео не найдено. Проверь структуру: серия/vertical+wide, серия/shorts/short_001, или папка шортсов.",
      scan_in_base: "В базе по этим папкам", scan_skipped: "удалённых", scan_restore_btn: "Вернуть удалённое и запустить скан", t_restored: "Возвращено",
      folders_hint: "Как это работает: добавь папку (кнопки «+ Сериалы», «+ Шортсы», «+ Авто») → нажми «Сканировать» → появится панель «Найдено» и кнопка «Да, запустить» (или выбери дату). Система сама найдёт фильмы и шортсы и разложит их по расписанию.",
      queue_edit: "Редактировать", queue_edit_save: "Сохранить", queue_edit_cancel: "Отмена",
      edit_title: "Название", edit_desc: "Описание", edit_tags: "Хэштеги", t_saved: "Сохранено",
      queue_remove: "Убрать", queue_remove_series: "Убрать серию", queue_removed: "Убрано из очереди", edit_date: "Дата", edit_time: "Время", confirm_series: "Убрать фильм и ВСЕ его шортсы со всех платформ?",
      mode_auto: "Авто: вкл", mode_manual: "Авто: выкл",
      mode_hint: "ВКЛ — система сама раскладывает видео по слотам. ВЫКЛ — ждёт, пока ты нажмёшь «Запустить» или выберешь дату после сканирования.",
      settings_tab_sched: "Группы и расписание", settings_tab_errors: "Ошибки", settings_tab_help: "Справка",
      scan_found: "Найдено", scan_films: "фильмов", scan_shorts: "шортсов", scan_standalone: "самостоятельных шортсов",
      scan_last: "Последнее запланированное видео", scan_none: "нет",
      scan_run_q: "Запускать последовательно?", scan_run_now: "Да, запустить", scan_run_from: "С даты", scan_run_go: "Запустить с даты",
      t_sched_started: "Запущено", t_error_date: "Выбери дату",
      nav_settings: "Настройки", title_settings: "Настройки",
      entity_film: "Фильм", entity_short: "Шортс",
      dow_mon: "Пн", dow_tue: "Вт", dow_wed: "Ср", dow_thu: "Чт", dow_fri: "Пт", dow_sat: "Сб", dow_sun: "Вс",
      post_one: "пост", post_few: "поста", post_many: "постов",
      err_non_canonical_slot: "слот не совпадает с расписанием",
      err_reconciliation_missing: "пост не найден в Postiz",
      err_waiting_for_youtube: "ждёт выхода на YouTube",
      err_create_failed_no_post: "Postiz не создал пост",
      err_upload_failed: "не удалось загрузить медиа",
      err_safety_block: "заблокировано лимитами или расписанием",
      err_postiz_error: "ошибка на стороне Postiz",
      err_missing_in_postiz: "пост пропал из Postiz",
      err_already_removed: "уже удалено",
      e_no_media: "нет медиа для этой сущности/платформы",
      e_failed: "не удалось — проверьте данные",
      e_not_published: "пост ещё не опубликован",
      e_no_postiz_id: "нет ID поста в Postiz",
      e_detach_unavailable: "снять нельзя: нет движка или ссылки на видео",
      e_detach_failed: "не удалось снять с платформы",
      e_no_roots: "корни обзора не настроены — обратитесь к администратору",
      e_args: "заполните все поля",
      e_too_large: "слишком большой запрос",
      e_force_link_failed: "не удалось сохранить ссылку",
      e_url_http: "ссылка должна начинаться с http(s)",
      del_detach: "Снять опубликованное с платформы",
      del_detach_note: "Необратимо: пост будет удалён с платформы.",
      title_trash: "Корзина", trash_selected: "выбрано", trash_restore: "Восстановить",
      trash_restore_all: "Восстановить всё", trash_purge: "Удалить навсегда",
      trash_hint: "Удалённое можно вернуть в очередь или убрать окончательно. Файлы на диске не трогаем.",
      trash_empty: "Корзина пуста", trash_cascade_yt: "снято за YouTube",
      trash_detached: "снято с платформы",
      trash_shown: "показаны первые %s из %s",
      confirm_purge: "Удалить выбранное из корзины навсегда? Файлы на диске останутся.",
      del_title: "Удалить «%s»?", del_scope: "Что удаляем",
      del_scope_series: "Только серию", del_scope_all: "Серию и связанные шорты (%s)",
      del_yt_note: "Удаление с YouTube автоматически удалит Telegram (они связаны).",
      del_tg_ask: "Удалить также с YouTube", del_will_delete: "Будет удалено",
      del_confirm: "Удалить", del_tg_btn: "Удалить из Telegram",
      del_all_btn: "Удалить везде", del_posts_n: "%s постов",
      del_blocked: "Нельзя: есть опубликованное. Сначала снимите с платформы.",
      sched_title: "Расписание постинга",
      sched_explain: "Настройки постинга по каждой соцсети отдельно: серии (фильмы), шортсы серии (тематические) и обычные шортсы. Группы задают общий таймер — соцсети из одной группы публикуются одновременно.",
      sched_long: "Серии (фильмы)", sched_thematic: "Шортсы серии", sched_standalone: "Обычные шортсы",
      sched_time: "Время", sched_times: "Времена (через запятую)",
      sched_limit: "Максимум публикаций в день", limit_day: "Лимит в день", pa_on: "Включено", pa_off: "Выключено", sched_save: "Сохранить", sched_reset: "Сбросить", sched_saved: "Сохранено",
      sched_days: "дни", sched_count: "Сколько в день", sched_limit_hint: "Максимум публикаций платформы в сутки (глобально; настройки группы/платформы важнее).",
      sched_priority: "Приоритет настроек: конкретная платформа → группа → глобально. Что не задано ниже — берётся из более общего уровня.",
      group_platforms: "Соцсети группы", groups_hint: "Соцсети одной группы публикуются одновременно (общий таймер).",
      groups_header: "Группы соцсетей (одновременный постинг)", group_name: "Название группы",
      group_add: "Добавить группу", group_remove: "Удалить", groups_none: "Групп нет",
      errors_header: "Ошибки публикаций", help_header: "Справка",
      kind_label: "Тип", kind_auto: "Авто", kind_series: "Сериалы", kind_shorts: "Шортсы",
      add_series: "+ Сериалы", add_shorts: "+ Шортсы", add_auto: "+ Авто",
      t_kind_changed: "Тип папки обновлён", t_group_added: "Группа добавлена", t_group_removed: "Группа удалена",
      nav_status: "Обзор", nav_folders: "Видео", nav_calendar: "План", nav_queue: "Очередь",
      nav_platforms: "Сети", nav_tail: "Остаток", nav_failed: "Ошибки", nav_metrics: "Стат.",
      nav_actions: "Действия", nav_help: "Справка",
      title_status: "Статус", title_folders: "Папки с видео", title_calendar: "Календарь",
      title_queue: "Очередь", title_platforms: "Платформы", title_tail: "Остаток шортсов серии",
      title_failed: "Ошибки", title_actions: "Действия", title_metrics: "Метрики", title_help: "Справка",
      loading: "Загрузка…", error_prefix: "Ошибка", refresh: "Обновить", no_data: "Нет данных",
      platforms: "Платформы", no_platforms: "Нет платформ", limit: "лимит",
      remove: "Убрать", open: "Открыть", up: "↑ Вверх", add_folder: "+ Добавить эту папку",
      scan: "Сканировать", no_subfolders: "Нет подпапок", folders_to_scan: "Папки для сканирования",
      folders_none: "Папки не выбраны", browse: "Обзор папок",
      backlog_unposted: "Не опубликовано шортсов", backlog_awaiting: "Ждём ответа до",
      backlog_distribute: "Распределить остаток", backlog_wait: "Ждать ещё",
      backlog_skip: "Не публиковать", backlog_from: "Распределять с даты (необязательно)", backlog_on: "распределение вкл", backlog_off: "распределение выкл",
      calendar_empty: "Календарь пуст", cal_day: "День", cal_week: "Неделя", cal_month: "Месяц", cal_today: "Сегодня", calendar_explain: "Показаны запланированные и опубликованные посты (из оркестратора и Postiz), сгруппированные по дням. Пометка справа — статус поста.", queue_empty: "Пусто", restore_posts: "Вернуть удалённые посты", restored: "Восстановлено", cleanup_orphans: "Убрать лишние посты из Postiz", confirm_cleanup_orphans: "Удалить из Postiz посты, которых нет в базе (лишние)? Живые публикации не трогаются.", cleaned: "Убрано постов", confirm_cascade_shorts: "У этой серии есть шортсы (%s). Удалить их тоже — со всех платформ и из базы?", shorts_deleted: "Шортсы серии удалены", confirm_cascade_tg_bulk: "У %s роликов есть уже поставленные Telegram-посты со ссылкой. Удалить их тоже?", confirm_cascade_tg: "На этот ролик уже стоит Telegram-пост со ссылкой. Удалить его тоже?", cascade_deleted: "Удалено вместе с Telegram-ссылкой", confirm_delete_row: "Удалить только этот пост (%s)? Другие платформы и запись в базе останутся.",
      delete_everywhere: "Удалить везде (все платформы + база)",
      confirm_delete_everywhere: "Удалить ролик со ВСЕХ платформ? Он попадёт в корзину — можно будет восстановить. Файлы на диске не трогаем.",
      remove_posts: "Удалить посты", search: "Найти", search_placeholder: "Поиск папки по имени…", search_none: "Ничего не найдено", searching: "Ищу…", search_short: "Введите минимум 2 символа", queue_all: "Все", queue_select: "Выбрать", queue_done: "Готово",
      queue_selected: "выбрано", queue_bulk_tags: "Хештеги…", queue_bulk_apply: "Применить",
      delete_everywhere_hint: "Опасная зона: удаление из базы и со всех платформ.",
      queue_bulk_clear: "Снять выделение",
      queue_bulk_del: "Удалить выбранные посты (%s)? Удаляются только выбранные платформы; файлы и другие посты остаются.",
      queue_bulk_tagp: "Новые хештеги для выбранных (%s):",
      queue_bulk_prog: "Обрабатываю %s из %s…",
      q_today: "Сегодня", q_tomorrow: "Завтра", q_yesterday: "Вчера",
      resume: "Возобновить", pause_all: "Пауза всем", resume_all: "Возобновить все", none: "Нет",
      tail_title: "Остаток шортсов серии", tail_explain: "Шортсы уже нарезаны для серии, но ещё не опубликованы. Когда новых серий больше нет, система распределяет остаток по слотам (в слот основной серии — обычные шортсы, в 20:30 — шортсы к другим сериям), и только после этого запускается следующая серия. Перед запуском она спросит подтверждение.", enable: "Включить", disable: "Выключить",
      tail_off: "выкл", no_errors: "Ошибок нет",
      quick_actions: "Быстрые действия", act_sync: "Обновить статусы",
      act_group_plan: "Планирование", act_group_data: "Данные и синхронизация", act_group_service: "Обслуживание",
      h_distribute: "Разложить длинные видео по свободным слотам расписания.",
      h_schedule: "Разложить всю очередь по слотам сейчас (без ожидания авто-режима).",
      h_sync: "Забрать статусы постов из Postiz (вышло или нет).",
      h_reconcile: "Сверить базу и Postiz: найти потерянные и лишние посты.",
      h_restore: "Вернуть ранее удалённые посты обратно в очередь.",
      h_cleanup: "Удалить из Postiz посты, которых нет в базе (живые публикации не трогает).",
      h_backup: "Сделать резервную копию базы сейчас.",
      h_refresh: "Перечитать данные с сервера без других действий.",
      errors_hint: "Здесь только неудавшиеся публикации. Полный текст ошибки — под номером поста.",
      m_ok: "ОК",
      test_title: "Проверка (тестовый пост)", test_hint: "Пробный пост в Postiz с выбранной задержкой. Боевая очередь не затрагивается.",
      test_schedule: "Тест-пост", test_dry: "Dry-run", test_disabled: "Тестовый контур выключен (test_publish.enabled=false).",
      test_recent: "Последние тестовые посты", test_cancel: "Отменить", test_entity: "Что публикуем", test_delay: "задержка, мин",
      t_test_sched: "Тест-пост поставлен:", t_test_dry: "Dry-run:", t_test_cancelled: "Тестовый пост удалён", t_test_failed: "Ошибка теста:",
      act_reconcile: "Сверка с Postiz", act_backup: "Резервная копия", act_schedule: "Разложить по слотам",
      pa_pause: "Пауза", distribute: "Распределить длинные", refresh_data: "Обновить данные",
      force_link_title: "Обновить ссылку вручную", save: "Сохранить",
      m_uptime: "Аптайм", m_cycles: "Циклов сканирования", m_queue_now: "В очереди сейчас",
      m_cycle_errors: "Сбоев цикла", m_publications: "Публикации", m_published: "Опубликовано",
      m_queue_row: "В очереди (готово / запланировано)", m_failed: "Ошибок публикаций",
      m_scheduler: "Планировщик (с запуска)", m_last_cycle: "Последний цикл",
      m_sched_long: "Запланировано длинных видео", m_sched_short: "Запланировано шортсов",
      m_sync: "Обновлений статуса из Postiz", m_err_pill: "Ошибка", m_no_err: "Сбоев не было",
      t_folder_added: "Папка добавлена", t_folder_removed: "Папка убрана",
      t_paused: "Все платформы на паузе", t_resumed: "Все платформы возобновлены",
      t_resume: "Возобновлено", t_tail_on: "Распределение остатка включено", t_tail_off: "Распределение остатка выключено",
      t_distributed: "Распределено", t_saved: "Ссылка сохранена", t_scan: "Скан",
      fl_hint: "Укажи ID видео (номер из «Очереди» или «Календаря»), платформу и ссылку — она подставится в описания.",
      fl_id_ph: "ID видео",
      st_ok: "ок", st_published: "опубликовано", st_scheduled: "запланировано",
      st_updating: "обновляется", st_queue: "в очереди", st_ready: "в ожидании",
      st_draft: "черновик", st_failed: "ошибка", st_error: "ошибка", st_paused: "пауза",
      st_waiting: "ждёт премьеру",
      st_publishing: "публикуется",
      waiting_hint: "Telegram-пост уйдёт автоматически после выхода видео на YouTube",
      st_skipped: "пропущено", st_on: "включено", st_off: "выключено",
      st_manual: "ручная", st_postiz: "из Postiz", st_suggested: "предложено",
      st_unmatched: "не найдено", st_confirmed: "подтверждено", st_rejected: "отклонено",
      st_ignored: "проигнорировано", st_claimed: "клейм", st_none: "нет",
      nav_manual: "Ручные", title_manual: "Ручные загрузки",
      nav_more: "Ещё", more_title: "Ещё разделы",
      folders_stepper: "Папка → Сканировать → Запустить. Дальше само.",
      status_cta_add: "Добавить видео", status_cta_queue: "Очередь",
      mu_scan_all: "Сканировать всё", mu_scan: "Сканировать", mu_total: "Всего",
      mu_postiz: "От Postiz", mu_suggested: "Предложено",
      mu_confirmed: "Подтверждено", mu_none: "Ничего не найдено", mu_confirm: "Подтвердить",
      mu_reject: "Не моё", mu_ignore: "Игнорировать", mu_candidates: "Кандидаты",
      mu_claim: "клейм", mu_claim_title: "Обнаружен клейм", mu_claim_mark: "Отметить клейм",
      mu_claim_delete: "Удалить видео", mu_claim_keep: "Оставить", mu_last_scan: "Последний скан",
      gate_msg: "Откройте приложение из Telegram-бота.",
      help: "Справка", help_nav: "Навигация", help_folders: "Раздел «Папки»",
      help_platforms: "Раздел «Платформы»", help_tail: "Раздел «Остаток»",
      help_actions: "Раздел «Действия»", help_common: "Общее", help_status: "Статусы",
      help_nav_status: "Сводка: сколько постов в каждом статусе и состояние платформ.",
      help_nav_folders: "Выбор папок с видео и запуск сканирования.",
      help_nav_calendar: "Что и когда запланировано к публикации.",
      help_nav_queue: "Посты, которые ждут отправки.",
      help_nav_platforms: "Каналы (Telegram/YouTube/…), лимиты и пауза.",
      help_nav_tail: "Остаток шортсов: неопубликованные шортсы серии. Когда серия закончилась, система распределяет их по слотам перед запуском следующей серии.",
      help_nav_failed: "Посты, которые не отправились, и текст ошибки.",
      help_nav_metrics: "Показатели работы оркестратора и очереди.",
      help_nav_actions: "Ручные операции: распределить, обновить ссылку.",
      help_nav_help: "Эта справка — описание каждого раздела и кнопки.",
      help_nav_manual: "Найденные в соцсетях ручные загрузки: сопоставление и подтверждение.",
      help_manual: "Раздел «Ручные»",
      help_a_manual_scan: "Найти ручные загрузки на одной платформе.",
      help_a_manual_scan_all: "Найти по всем подключённым платформам.",
      help_a_manual_confirm: "Подтвердить, что найденное = сущность (запись в базу, ссылка).",
      help_a_manual_reject: "Не моё — отклонить сопоставление.",
      help_a_manual_claim: "При клейме: удалить видео / оставить / игнорировать.",
      help_a_add: "Добавить текущую открытую папку в список сканирования.",
      help_a_scan: "Просканировать выбранные папки и поставить найденные видео в очередь.",
      help_a_open: "Открыть подпапку.",
      help_a_up: "Подняться на уровень выше (выше сетевого корня не пускает).",
      help_a_remove: "Убрать папку из списка сканирования.",
      help_a_root: "Переключить корень обзора: сетевая папка или локальный сервер.",
      help_a_pause_all: "Поставить все платформы на паузу (публикации временно прекращаются).",
      help_a_resume_all: "Снять паузу со всех платформ.",
      help_a_resume: "Снять паузу с одной платформы.",
      help_a_tail_on: "Разрешить распределять остаток шортсов этой серии.",
      help_a_tail_off: "Не распределять остаток (ждать ручного решения).",
      help_a_distribute: "Разложить длинные видео по свободным слотам расписания.",
      help_a_refresh: "Перечитать данные с сервера.",
      help_a_save: "Сохранить ссылку на полное видео для указанного поста (entity_id + платформа).",
      help_st_published: "Опубликовано.",
      help_st_scheduled: "Запланировано / в очереди.",
      help_st_failed: "Ошибка публикации.",
      help_st_paused: "Платформа на паузе.",
      },
    en: {
      queue_remove_film_only: "Film only",
      confirm_film_only: "Delete only the film? All its shorts stay in the database. The Telegram post linking to the film will be deleted too.",
      confirm_delete_short: "Delete this video and its posts (including the database)?",
      warn_tg_link: "Note: a Telegram post with a link to this video exists — it will be deleted too and the link will not be published.",
      edit_cover: "Cover", cover_none: "No cover",
      cover_pick: "Choose cover…", cover_picker_title: "Choose cover",
      cover_tab_server: "Server folders", cover_tab_device: "From device",
      cover_tab_url: "From URL", cover_choose: "Choose", cover_close: "Close",
      cover_tab_frames: "From video", cover_frames_hint: "Video frames — pick the one you like",
      cover_frames_regen: "Regenerate", cover_frames_btn: "Extract frames from video",
      cover_no_images: "No images", cover_up: "↑ Up", cover_loading: "Loading…",
      cover_added: "Cover selected", cover_upload: "Upload from device",
      request_timeout: "Server did not respond (timeout). Check connection and retry.",
      session_stale: "Session expired — reopen the panel from the bot.",
      t_bulk_failed: "Errors: %s",
      cant_delete_published: "Cannot delete: already published",
      already_removed: "Already removed", retrying: "Retrying…",
      cover_fetch: "Download", cover_url_hint: "Paste an image URL (http/https)",
      cover_dirs: "Folders", cover_images: "Images", cover_start_hint: "Starts at the video folder",
      pick_file: "No file selected",
      cancel: "Cancel", left: "left", sec_short: "s", min_short: "min",
      job_scheduling: "Scheduling posts", job_restore: "Restoring removed",
      job_cancelling: "Cancelling…", job_cancelled: "Cancelled", job_done: "Done",
      scan_date_films: "Films from", scan_date_shorts: "Shorts from", scan_run_dates: "Start from dates",
      t_started_async: "Started — posts are being added gradually", working: "Working…",
      confirm_delete_film: "Delete the film, all its shorts and posts (including the database)? A scan can re-add it later.",
      scan_none_new_hint: "Nothing new: everything is already in the database. To re-add, delete from the queue (Remove also deletes from the database).",
      scan_empty_hint: "No videos found in these folders. Check the structure: series/vertical+wide, series/shorts/short_001, or a shorts folder.",
      scan_in_base: "In base for these folders", scan_skipped: "removed", scan_restore_btn: "Restore removed and start", t_restored: "Restored",
      folders_hint: "How it works: add a folder (+ Series / + Shorts / + Auto) → press Scan → you will see the Found panel with a Start button (or pick a date). The system finds films and shorts and schedules them automatically.",
      queue_edit: "Edit", queue_edit_save: "Save", queue_edit_cancel: "Cancel",
      edit_title: "Title", edit_desc: "Description", edit_tags: "Hashtags", t_saved: "Saved",
      queue_remove: "Remove", queue_remove_series: "Remove series", queue_removed: "Removed from queue", edit_date: "Date", edit_time: "Time", confirm_series: "Remove the film and ALL its shorts from all networks?",
      mode_auto: "Auto-scheduling: ON", mode_manual: "Auto-scheduling: OFF",
      mode_hint: "ON — the system places videos into slots automatically. OFF — waits for you to press Start or pick a date after scanning.",
      settings_tab_sched: "Groups and schedule", settings_tab_errors: "Errors", settings_tab_help: "Help",
      scan_found: "Found", scan_films: "films", scan_shorts: "shorts", scan_standalone: "standalone shorts",
      scan_last: "Last scheduled video", scan_none: "none",
      scan_run_q: "Start sequentially?", scan_run_now: "Yes, start", scan_run_from: "From date", scan_run_go: "Start from date",
      t_sched_started: "Started", t_error_date: "Pick a date",
      nav_settings: "Settings", title_settings: "Settings",
      entity_film: "Film", entity_short: "Short",
      dow_mon: "Mon", dow_tue: "Tue", dow_wed: "Wed", dow_thu: "Thu", dow_fri: "Fri", dow_sat: "Sat", dow_sun: "Sun",
      post_one: "post", post_few: "posts", post_many: "posts",
      err_non_canonical_slot: "slot does not match the schedule",
      err_reconciliation_missing: "post not found in Postiz",
      err_waiting_for_youtube: "waiting for the YouTube release",
      err_create_failed_no_post: "Postiz did not create the post",
      err_upload_failed: "media upload failed",
      err_safety_block: "blocked by limits or schedule",
      err_postiz_error: "Postiz-side error",
      err_missing_in_postiz: "post disappeared from Postiz",
      err_already_removed: "already removed",
      e_no_media: "no media for this entity/platform",
      e_failed: "failed — check the input",
      e_not_published: "the post is not published yet",
      e_no_postiz_id: "no Postiz post id",
      e_detach_unavailable: "cannot detach: no engine or video link",
      e_detach_failed: "detach from the platform failed",
      e_no_roots: "browse roots are not configured — ask the administrator",
      e_args: "fill in all fields",
      e_too_large: "request is too large",
      e_force_link_failed: "could not save the link",
      e_url_http: "the link must start with http(s)",
      del_detach: "Detach published from the platform",
      del_detach_note: "Irreversible: the post will be removed from the platform.",
      title_trash: "Trash", trash_selected: "selected", trash_restore: "Restore",
      trash_restore_all: "Restore all", trash_purge: "Delete permanently",
      trash_hint: "Deleted items can be restored to the queue or removed permanently. Files on disk are kept.",
      trash_empty: "Trash is empty", trash_cascade_yt: "removed with YouTube",
      trash_detached: "detached from platform",
      trash_shown: "showing %s of %s",
      confirm_purge: "Permanently delete the selected items? Files on disk are kept.",
      del_title: "Delete “%s”?", del_scope: "What to delete",
      del_scope_series: "Series only", del_scope_all: "Series and related shorts (%s)",
      del_yt_note: "Deleting from YouTube also removes Telegram (they are linked).",
      del_tg_ask: "Also delete from YouTube", del_will_delete: "Will be deleted",
      del_confirm: "Delete", del_tg_btn: "Delete from Telegram",
      del_all_btn: "Delete everywhere", del_posts_n: "%s posts",
      del_blocked: "Blocked: something is already published. Detach it first.",
      sched_title: "Posting schedule",
      sched_explain: "Posting settings per network: series (films), series shorts (thematic) and regular shorts. Groups share one timer — networks in one group publish simultaneously.",
      sched_long: "Series (films)", sched_thematic: "Series shorts", sched_standalone: "Regular shorts",
      sched_time: "Time", sched_times: "Times (comma separated)",
      sched_limit: "Max posts per day", limit_day: "Daily limit", pa_on: "Enabled", pa_off: "Disabled", sched_save: "Save", sched_reset: "Reset", sched_saved: "Saved",
      sched_days: "days", sched_count: "Times per day", sched_limit_hint: "Max posts per platform per day (global; group/platform settings take priority).",
      sched_priority: "Priority: platform → group → global. Anything not set below is inherited from the broader level.",
      group_platforms: "Networks in group", groups_hint: "Networks in one group publish simultaneously (shared timer).",
      groups_header: "Network groups (simultaneous posting)", group_name: "Group name",
      group_add: "Add group", group_remove: "Remove", groups_none: "No groups",
      errors_header: "Publishing errors", help_header: "Help",
      kind_label: "Kind", kind_auto: "Auto", kind_series: "Series", kind_shorts: "Shorts",
      add_series: "+ Series", add_shorts: "+ Shorts", add_auto: "+ Auto",
      t_kind_changed: "Folder kind updated", t_group_added: "Group added", t_group_removed: "Group removed",
      nav_status: "Home", nav_folders: "Media", nav_calendar: "Plan", nav_queue: "Queue",
      nav_platforms: "Social", nav_tail: "Backlog", nav_failed: "Errors", nav_metrics: "Stats",
      nav_actions: "Actions", nav_help: "Help",
      title_status: "Status", title_folders: "Video folders", title_calendar: "Calendar",
      title_queue: "Queue", title_platforms: "Platforms", title_tail: "Unposted series shorts",
      title_failed: "Errors", title_actions: "Actions", title_metrics: "Metrics", title_help: "Help",
      loading: "Loading…", error_prefix: "Error", refresh: "Refresh", no_data: "No data",
      platforms: "Platforms", no_platforms: "No platforms", limit: "limit",
      remove: "Remove", open: "Open", up: "↑ Up", add_folder: "+ Add this folder",
      scan: "Scan", no_subfolders: "No subfolders", folders_to_scan: "Folders to scan",
      folders_none: "No folders selected", browse: "Browse",
      backlog_unposted: "Unposted shorts", backlog_awaiting: "Awaiting answer until",
      backlog_distribute: "Distribute backlog", backlog_wait: "Wait more",
      backlog_skip: "Do not publish", backlog_from: "Distribute from date (optional)", backlog_on: "distribution on", backlog_off: "distribution off",
      calendar_empty: "Calendar is empty", cal_day: "Day", cal_week: "Week", cal_month: "Month", cal_today: "Today", calendar_explain: "Scheduled and published posts (from the orchestrator and Postiz), grouped by day. The badge shows the post status.", queue_empty: "Empty", restore_posts: "Restore deleted posts", restored: "Restored", cleanup_orphans: "Remove leftover posts from Postiz", confirm_cleanup_orphans: "Delete Postiz posts that are not in the DB (leftovers)? Published ones are kept.", cleaned: "Cleaned posts", confirm_cascade_shorts: "This series has %s shorts. Delete them too — from all platforms and the DB?", shorts_deleted: "Series shorts deleted", confirm_cascade_tg_bulk: "%s items have a scheduled Telegram link post. Delete those too?", confirm_cascade_tg: "A Telegram post with the link is already scheduled. Delete it too?", cascade_deleted: "Deleted together with the Telegram link", confirm_delete_row: "Delete only this post (%s)? Other platforms and the DB record stay.",
      delete_everywhere: "Delete everywhere (all platforms + DB)",
      confirm_delete_everywhere: "Delete the item from ALL platforms? It goes to Trash and can be restored. Files on disk are kept.",
      remove_posts: "Delete posts", search: "Search", search_placeholder: "Find folder by name…", search_none: "Nothing found", searching: "Searching…", search_short: "Type at least 2 characters", queue_all: "All", queue_select: "Select", queue_done: "Done",
      queue_selected: "selected", queue_bulk_tags: "Hashtags…", queue_bulk_apply: "Apply",
      delete_everywhere_hint: "Danger zone: removes from the DB and every platform.",
      queue_bulk_clear: "Clear selection",
      queue_bulk_del: "Delete selected posts (%s)? Only the selected platforms are removed; files and other posts stay.",
      queue_bulk_tagp: "New hashtags for selected (%s):",
      queue_bulk_prog: "Processing %s of %s…",
      q_today: "Today", q_tomorrow: "Tomorrow", q_yesterday: "Yesterday",
      resume: "Resume", pause_all: "Pause all", resume_all: "Resume all", none: "None",
      tail_title: "Unposted series shorts", tail_explain: "Shorts already cut for the series but not published yet. When no new episodes appear, the system distributes the backlog into slots (standard shorts in the main-series slot, other series' shorts at 20:30) and only then starts the next series. It asks for confirmation first.", enable: "Enable", disable: "Disable",
      tail_off: "off", no_errors: "No errors",
      quick_actions: "Quick actions", act_sync: "Sync now",
      act_group_plan: "Planning", act_group_data: "Data & sync", act_group_service: "Maintenance",
      h_distribute: "Spread long videos into free schedule slots.",
      h_schedule: "Schedule the whole queue now (no waiting for auto mode).",
      h_sync: "Pull post statuses from Postiz (published or failed).",
      h_reconcile: "Compare DB and Postiz: find missing and leftover posts.",
      h_restore: "Return previously deleted posts back to the queue.",
      h_cleanup: "Delete Postiz posts that are not in the DB (published kept).",
      h_backup: "Make a database backup right now.",
      h_refresh: "Re-read server data without other actions.",
      errors_hint: "Only failed publications are listed. The full error text is under the post id.",
      m_ok: "OK",
      test_title: "Test (trial post)", test_hint: "Creates a trial post in Postiz with the chosen delay. The live queue is untouched.",
      test_schedule: "Test post", test_dry: "Dry run", test_disabled: "Test contour is off (test_publish.enabled=false).",
      test_recent: "Recent test posts", test_cancel: "Cancel", test_entity: "Publish what", test_delay: "delay, min",
      t_test_sched: "Test post scheduled:", t_test_dry: "Dry run:", t_test_cancelled: "Test post removed", t_test_failed: "Test failed:",
      act_reconcile: "Check against Postiz", act_backup: "Backup now", act_schedule: "Schedule now",
      pa_pause: "Pause", distribute: "Distribute long", refresh_data: "Refresh data",
      force_link_title: "Update link manually", save: "Save",
      m_uptime: "Uptime", m_cycles: "Scan cycles", m_queue_now: "In queue now",
      m_cycle_errors: "Loop errors", m_publications: "Publications", m_published: "Published",
      m_queue_row: "In queue (ready / scheduled)", m_failed: "Publish errors",
      m_scheduler: "Scheduler (since start)", m_last_cycle: "Last cycle",
      m_sched_long: "Long videos scheduled", m_sched_short: "Shorts scheduled",
      m_sync: "Status updates from Postiz", m_err_pill: "Error", m_no_err: "No failures",
      t_folder_added: "Folder added", t_folder_removed: "Folder removed",
      t_paused: "All platforms paused", t_resumed: "All platforms resumed",
      t_resume: "Resumed", t_tail_on: "Tail enabled", t_tail_off: "Tail disabled",
      t_distributed: "Distributed", t_saved: "Link saved", t_scan: "Scan",
      fl_hint: "Provide the video ID (number from Queue or Calendar), platform and URL — it will be added to descriptions.",
      fl_id_ph: "video ID",
      st_ok: "ok", st_published: "published", st_scheduled: "scheduled",
      st_updating: "updating", st_queue: "queued", st_ready: "waiting",
      st_draft: "draft", st_failed: "failed", st_error: "error", st_paused: "paused",
      st_waiting: "waiting for premiere",
      st_publishing: "publishing",
      waiting_hint: "The Telegram post will be published automatically after the YouTube video goes live",
      st_skipped: "skipped", st_on: "on", st_off: "off",
      st_manual: "manual", st_postiz: "from Postiz", st_suggested: "suggested",
      st_unmatched: "not found", st_confirmed: "confirmed", st_rejected: "rejected",
      st_ignored: "ignored", st_claimed: "claim", st_none: "none",
      nav_manual: "Manual", title_manual: "Manual uploads",
      nav_more: "More", more_title: "More sections",
      folders_stepper: "Folder → Scan → Run. The rest is automatic.",
      status_cta_add: "Add video", status_cta_queue: "Queue",
      mu_scan_all: "Scan all", mu_scan: "Scan", mu_total: "Total",
      mu_postiz: "From Postiz", mu_suggested: "Suggested",
      mu_confirmed: "Confirmed", mu_none: "Nothing found", mu_confirm: "Confirm",
      mu_reject: "Not mine", mu_ignore: "Ignore", mu_candidates: "Candidates",
      mu_claim: "claim", mu_claim_title: "Claim detected", mu_claim_mark: "Mark claim",
      mu_claim_delete: "Delete video", mu_claim_keep: "Keep", mu_last_scan: "Last scan",
      gate_msg: "Open the app from the Telegram bot.",
      help: "Help", help_nav: "Navigation", help_folders: "“Folders” section",
      help_platforms: "“Platforms” section", help_tail: "“Backlog” section",
      help_actions: "“Actions” section", help_common: "Common", help_status: "Statuses",
      help_nav_status: "Overview: post counts per status and platform state.",
      help_nav_folders: "Pick video folders and run a scan.",
      help_nav_calendar: "What is scheduled and when.",
      help_nav_queue: "Posts waiting to be sent.",
      help_nav_platforms: "Channels (Telegram/YouTube/…), limits and pause.",
      help_nav_tail: "Unposted series shorts: the backlog of a finished series. The system distributes it before starting the next series.",
      help_nav_failed: "Posts that failed, with the error text.",
      help_nav_metrics: "Orchestrator and queue metrics.",
      help_nav_actions: "Manual operations: distribute, update link.",
      help_nav_help: "This help — how every section and button works.",
      help_nav_manual: "Manual uploads found in social networks: matching and confirmation.",
      help_manual: "“Manual” section",
      help_a_manual_scan: "Find manual uploads on one platform.",
      help_a_manual_scan_all: "Find across all connected platforms.",
      help_a_manual_confirm: "Confirm the match (record in DB, save link).",
      help_a_manual_reject: "Not mine — reject the match.",
      help_a_manual_claim: "On a claim: delete video / keep / ignore.",
      help_a_add: "Add the currently open folder to the scan list.",
      help_a_scan: "Scan selected folders and queue the videos found.",
      help_a_open: "Open a subfolder.",
      help_a_up: "Go one level up (cannot go above the network root).",
      help_a_remove: "Remove a folder from the scan list.",
      help_a_root: "Switch browse root: network folder or local server.",
      help_a_pause_all: "Pause all platforms (publications stop temporarily).",
      help_a_resume_all: "Resume all platforms.",
      help_a_resume: "Resume a single platform.",
      help_a_tail_on: "Allow distributing this series' unposted shorts.",
      help_a_tail_off: "Do not distribute the backlog (wait for a manual decision).",
      help_a_distribute: "Spread long videos into free schedule slots.",
      help_a_refresh: "Reload data from the server.",
      help_a_save: "Save the full-video link for a given post (entity_id + platform).",
      help_st_published: "Published.",
      help_st_scheduled: "Scheduled / queued.",
      help_st_failed: "Publish failed.",
      help_st_paused: "Platform paused.",
      },
  };

  const state = {
    view: "status",
    lang: localStorage.getItem("lang") || "ru",
    initData: tg?.initData || "",
    key: window.__WEBAPP_KEY__ || readKey() || "",
    user: tg?.initDataUnsafe?.user || null,
    data: {},
    queueFilter: (() => { try { return localStorage.getItem("queueFilter") || "all"; } catch (_) { return "all"; } })(),
    calView: (() => { try { return localStorage.getItem("calView") || "day"; } catch (_) { return "day"; } })(),
    calDate: null,
    schedCount: {},
    queueSelect: false,
    queueSelected: {},
    queueBulkTags: null,
  };

  const $ = (id) => document.getElementById(id);

  // ===== B2: слой нативности — тема, инсеты, хаптики, нативный back =====
  // Тема: берём цвета из themeParams — панель совпадает с темой пользователя.
  function applyTgTheme() {
    try {
      const tp = (tg && tg.themeParams) || {};
      const root = document.documentElement.style;
      const map = {
        "--tg-bg": tp.bg_color,
        "--tg-card": tp.section_bg_color || tp.secondary_bg_color,
        "--tg-card2": tp.secondary_bg_color,
        "--tg-text": tp.text_color,
        "--tg-hint": tp.hint_color,
        "--tg-sep": tp.section_separator_color,
        "--tg-accent": tp.button_color,
        "--tg-accent-text": tp.button_text_color,
        "--tg-danger": tp.destructive_text_color,
        "--tg-subtitle": tp.subtitle_text_color,
        "--tg-header": tp.header_bg_color,
        "--tg-bottom": tp.bottom_bar_bg_color,
      };
      Object.entries(map).forEach(([k, v]) => { if (v) root.setProperty(k, String(v)); });
      const dark = (tg && tg.colorScheme === "dark")
        || (!tg && window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
      document.documentElement.classList.toggle("tg-dark", !!dark);
      document.documentElement.classList.toggle("tg-native", !!tg);
    } catch (_) {}
  }

  // Инсеты: safeArea + contentSafeAreaInset — второй учитывает кнопки Telegram ✕ и ⋮
  function applyTgInsets() {
    try {
      const s0 = tg && tg.safeAreaInset;
      const c0 = tg && tg.contentSafeAreaInset;
      const px = (v) => (typeof v === "number" && v > 0 ? Math.round(v) : 0);
      const root = document.documentElement.style;
      const hasSA = !!(s0 && typeof s0.top === "number");
      const hasCS = !!(c0 && typeof c0.top === "number");
      const fs = !!(tg && (tg.isFullscreen === true || (window.__fsRequested && tg.isFullscreen !== false)));
      document.body.classList.toggle("tg-fs", fs);
      if (hasSA || hasCS) {
        // свежий клиент: берём инсеты SDK — contentSafeAreaInset уже учитывает кнопки Telegram
        root.setProperty("--sa-top", Math.max(px(s0 && s0.top), px(c0 && c0.top)) + "px");
        root.setProperty("--sa-bottom", Math.max(px(s0 && s0.bottom), px(c0 && c0.bottom)) + "px");
        root.setProperty("--sa-right", Math.max(px(s0 && s0.right), px(c0 && c0.right)) + "px");
        root.setProperty("--sa-left", Math.max(px(s0 && s0.left), px(c0 && c0.left)) + "px");
        root.setProperty("--chrome-top", "0px");
      } else {
        // старый клиент или веб: НЕ затираем фолбэк env; в fullscreen резервируем полосу
        // под кнопку Telegram ✕ — вертикально, чтобы не разъезжалось выравнивание по правому краю
        root.removeProperty("--sa-top");
        root.removeProperty("--sa-bottom");
        root.removeProperty("--sa-right");
        root.removeProperty("--sa-left");
        root.setProperty("--chrome-top", fs && tg ? "60px" : "0px");
      }
    } catch (_) {}
  }

  // Хаптики: тактильный отклик как в нативном Telegram
  // F11: вне Telegram/на старом SDK методы бросают ошибки — проверяем версию
  const tgOk = (v) => !!(tg && tg.isVersionAtLeast && tg.isVersionAtLeast(v));

  function haptic(kind) {
    try {
      if (!tgOk("6.1")) return;
      const h = tg && tg.HapticFeedback;
      if (!h) return;
      if (kind === "select") h.selectionChanged();
      else if (kind === "success") h.notificationOccurred("success");
      else if (kind === "error") h.notificationOccurred("error");
      else if (kind === "heavy") h.impactOccurred("heavy");
      else if (kind === "medium") h.impactOccurred("medium");
      else h.impactOccurred("light");
    } catch (_) {}
  }

  // Нативная кнопка «Назад» для шторок — вместо своих ✕ внутри Telegram
  let _backHandlers = [];
  function nativeBackAvailable() {
    return !!(tg && tg.BackButton && tg.isVersionAtLeast && tg.isVersionAtLeast("6.1"));
  }
  function showNativeBack(fn) {
    if (!nativeBackAvailable()) return false;
    try {
      tg.BackButton.onClick(fn);
      _backHandlers.push(fn);
      tg.BackButton.show();
      return true;
    } catch (_) { return false; }
  }
  function hideNativeBack() {
    if (!nativeBackAvailable()) return;
    try {
      _backHandlers.forEach((f) => tg.BackButton.offClick(f));
      _backHandlers = [];
      tg.BackButton.hide();
    } catch (_) {}
  }
  const content = () => $("content");
  function esc(s) {
    return String(s == null ? "" : s)
      .split("&").join("&amp;")
      .split("<").join("&lt;")
      .split(">").join("&gt;")
      .split('"').join("&quot;")
      .split("'").join("&#39;");
  }
  const t = (k) => (I18N[state.lang] && I18N[state.lang][k]) || I18N.ru[k] || k;
  const entityLabel = (k) => t(k === "long_video" ? "entity_film" : "entity_short");
  function errText(raw) {
    const code = String(raw || "").split(":")[0].trim();
    const dict = I18N[state.lang] || {};
    return dict["err_" + code] || raw || "";
  }
  function postsLabel(n) {
    const m100 = n % 100;
    const form = (m100 >= 11 && m100 <= 14) ? "many"
      : (n % 10 === 1 ? "one" : (n % 10 >= 2 && n % 10 <= 4 ? "few" : "many"));
    return `${n} ${t("post_" + form)}`;
  }
  // N2: серверные коды ошибок -> человекочитаемый локализованный текст
  function apiErrorText(raw) {
    const msg = String(raw || "").trim();
    const dict = I18N[state.lang] || {};
    const keys = {
      "no media for entity/platform": "e_no_media",
      "failed": "e_failed",
      "not_published": "e_not_published",
      "no_postiz_id": "e_no_postiz_id",
      "detach_unavailable": "e_detach_unavailable",
      "detach_failed": "e_detach_failed",
      "no browse roots configured": "e_no_roots",
      "entity_type/entity_id/platform/url required": "e_args",
      "url must be http(s)": "e_url_http",
      "force_link_failed": "e_force_link_failed",
      "request body too large (max 50MB)": "e_too_large",
    };
    const k = keys[msg];
    return (k && dict[k]) || msg || t("error_prefix");
  }
  function toastErr(e) {
    toast(`${t("error_prefix")}: ${apiErrorText(e && e.message)}`);
  }

  function readKey() {
    const q = new URLSearchParams(location.search).get("key");
    if (q) return q;
    const m = location.pathname.match(/\/webapp\/k\/([^/]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function toast(msg) {
    haptic("light");
    const el = $("toast");
    el.textContent = msg;
    el.classList.add("show");
    setTimeout(() => el.classList.remove("show"), 2400);
  }

  function api(path, opts = {}) {
    const headers = {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": state.initData,
      ...(state.key ? { "X-Webapp-Key": state.key } : {}),
      ...(opts.headers || {}),
    };
    const timeoutMs = opts.timeoutMs
      || ((opts.method && opts.method !== "GET") ? 45000 : 25000);
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    const rest = { ...opts };
    delete rest.timeoutMs;
    // F6c: сообщаем язык — серверные подписи сущностей локализуются
    const _sep = path.includes("?") ? "&" : "?";
    return fetch(`/webapp/api${path}${_sep}lang=${state.lang}`, { ...rest, headers, signal: ctrl.signal }).then((r) => {
      if (r.status === 401 && !r.__notified) {
        r.__notified = true;
        try { toast(t("session_stale")); } catch (_) {}
      }
      return r;
    })
      .then(async (r) => {
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data.error || r.statusText || "error");
        return data;
      })
      .catch((e) => {
        if (e && e.name === "AbortError") throw new Error(t("request_timeout"));
        throw e;
      })
      .finally(() => clearTimeout(timer));
  }

  let _jobTimer = null;

  function _overlay() {
    let el = document.getElementById("busy");
    if (!el) {
      el = document.createElement("div");
      el.id = "busy";
      el.className = "busy-overlay";
      document.body.appendChild(el);
      // P1-12: оверлей живёт на body, а делегат [data-act] — только на #content,
      // поэтому кнопка «Отмена» в прогрессе была мертва.
      el.addEventListener("click", (e) => {
        const btn = e.target.closest("[data-act]");
        if (btn) onAction(btn.dataset.act, btn);
      });
    }
    return el;
  }

  function busy(text) {
    const el = _overlay();
    el.innerHTML = `<div class="busy-box"><div class="busy-row">${icon("spinner", 20)}<span>${esc(text || t("working"))}</span></div></div>`;
    el.style.display = "flex";
  }

  function openCoverPicker(opts) {
    const { select, startPath, entityType, entityId } = opts;
    const old = document.getElementById("coverPicker");
    if (old) old.remove();
    const dir0 = (startPath || "").replace(/\/[^/]+\.[A-Za-z0-9]+$/, "") || "";
    let tab = "server";
    let curPath = dir0;
    let listData = null;

    const root = document.createElement("div");
    root.id = "coverPicker";
    root.className = "cover-overlay";
    root.setAttribute("role", "dialog");
    root.setAttribute("aria-modal", "true");
    root.setAttribute("aria-label", t("cover_picker_title"));
    root.innerHTML = `
      <div class="cover-panel">
        <div class="cover-grab" aria-hidden="true"></div>
        <div class="cover-head">
          <strong>${t("cover_picker_title")}</strong>
          <button class="cover-x" data-cp="close" aria-label="${t("cover_close")}" title="${t("cover_close")}">${icon("x", 20)}</button>
        </div>
        <div class="cover-tabs">
          <button class="btn cp-tab" data-cp="tab" data-tab="server">${t("cover_tab_server")}</button>
          <button class="btn cp-tab" data-cp="tab" data-tab="device">${t("cover_tab_device")}</button>
          <button class="btn cp-tab" data-cp="tab" data-tab="url">${t("cover_tab_url")}</button>
          <button class="btn cp-tab" data-cp="tab" data-tab="frames">${t("cover_tab_frames")}</button>
        </div>
        <div class="cover-body" id="cpBody"></div>
      </div>`;
    document.body.appendChild(root);

    function close() { root.remove(); hideNativeBack(); }
    root.dataset.nativeBack = showNativeBack(() => close()) ? "1" : "";
    function apply(path) {
      if (!path) return;
      let found = Array.from(select.options).find((o) => o.value === path);
      if (!found) {
        found = document.createElement("option");
        found.value = path;
        found.textContent = path.split("/").pop();
        select.appendChild(found);
      }
      select.value = path;
      toast(t("cover_added"));
      close();
    }
    function renderTabs() {
      root.querySelectorAll(".cp-tab").forEach((b) => {
        b.classList.toggle("primary", b.dataset.tab === tab);
      });
    }
    async function loadServer(path) {
      const body = root.querySelector("#cpBody");
      body.innerHTML = `<div class="empty">${t("cover_loading")}</div>`;
      try {
        const q = path ? `?path=${encodeURIComponent(path)}` : "";
        const d = await api(`/cover/list${q}`);
        listData = d;
        curPath = d.path;
        const key = encodeURIComponent(state.key || "");
        const dirs = (d.dirs || []).map((x) =>
          `<button class="btn secondary cp-dir" data-cp="dir" data-path="${esc(x.path)}">📁 ${esc(x.name)}</button>`).join("");
        const imgs = (d.images || []).map((x) =>
          `<button class="cp-thumb" data-cp="pick" data-path="${esc(x.path)}" title="${esc(x.name)}">
             <img loading="lazy" src="/webapp/api/cover/thumb?key=${key}&path=${encodeURIComponent(x.path)}" alt=""/>
             <span>${esc(x.name.length > 22 ? x.name.slice(0, 20) + "…" : x.name)}</span>
           </button>`).join("");
        body.innerHTML = `
          <div class="cp-path mono">${esc(d.path)}</div>
          <div class="cp-row">
            ${d.parent ? `<button class="btn secondary" data-cp="dir" data-path="${esc(d.parent)}">${t("cover_up")}</button>` : ""}
            ${d.warning ? `<span class="meta">${esc(d.warning)}</span>` : ""}
          </div>
          <div class="cp-sec">${t("cover_dirs")}</div>
          <div class="cp-dirs">${dirs || `<span class="meta">${t("no_subfolders")}</span>`}</div>
          <div class="cp-sec">${t("cover_images")}</div>
          <div class="cp-grid">${imgs || `<span class="meta">${t("cover_no_images")}</span>`}</div>`;
      } catch (e) {
        body.innerHTML = `<div class="empty">${t("error_prefix")}: ${esc(e.message)}</div>`;
      }
    }
    function renderDevice() {
      root.querySelector("#cpBody").innerHTML = `
        <div class="cp-sec">${t("cover_upload")}</div>
        <input type="file" id="cpFile" accept="image/*"/>
        <div class="form-row"><span class="meta" id="cpFileInfo">${t("pick_file")}</span></div>
        <button class="btn primary" data-cp="upload">${t("cover_upload")}</button>`;
      const inp = root.querySelector("#cpFile");
      inp.addEventListener("change", () => {
        const info = root.querySelector("#cpFileInfo");
        const f = inp.files && inp.files[0];
        info.textContent = f ? `${f.name} · ${Math.round(f.size / 1024)} КБ` : t("pick_file");
      });
    }
    function renderUrl() {
      root.querySelector("#cpBody").innerHTML = `
        <div class="cp-sec">${t("cover_tab_url")}</div>
        <input type="url" id="cpUrl" class="w-full" placeholder="https://…"/>
        <div class="form-row"><span class="meta">${t("cover_url_hint")}</span></div>
        <button class="btn primary" data-cp="fetch">${t("cover_fetch")}</button>`;
    }
    async function renderFrames() {
      const body = root.querySelector("#cpBody");
      body.innerHTML = `<div class="empty">${t("cover_loading")}</div>`;
      try {
        const d = await api("/cover/frames", {
          method: "POST",
          body: JSON.stringify({ entity_type: entityType,
                                 entity_id: Number(entityId), count: 6 }),
        });
        const key = encodeURIComponent(state.key || "");
        const imgs = (d.frames || []).map((x) => `
          <button class="cp-thumb" data-cp="pick"
                  data-path="${esc(x.path)}" title="${esc(x.name)} · ${esc(x.at)} ${t("sec_short")}">
            <img loading="lazy" src="/webapp/api/cover/thumb?key=${key}&path=${encodeURIComponent(x.path)}" alt=""/>
            <span>${esc(x.at)} ${t("sec_short")}</span>
          </button>`).join("");
        body.innerHTML = `
          <div class="cp-sec">${t("cover_frames_hint")}${d.duration ? " (" + d.duration + " " + t("sec_short") + ")" : ""}</div>
          <div class="cp-grid">${imgs || `<span class="meta">${t("cover_no_images")}</span>`}</div>
          <div class="form-row"><button class="btn secondary" data-cp="frames">${t("cover_frames_regen")}</button></div>`;
      } catch (e) {
        body.innerHTML = `<div class="empty">${t("error_prefix")}: ${esc(e.message)}</div>`;
      }
    }
    function renderBody() {
      renderTabs();
      if (tab === "server") loadServer(curPath);
      else if (tab === "device") renderDevice();
      else if (tab === "frames") renderFrames();
      else renderUrl();
    }

    root.addEventListener("click", async (e) => {
      const el = e.target.closest("[data-cp]");
      if (!el) return;
      const act = el.dataset.cp;
      if (act === "close") return close();
      if (act === "tab") { tab = el.dataset.tab; return renderBody(); }
      if (act === "frames") return renderFrames();
      if (act === "dir") return loadServer(el.dataset.path);
      if (act === "pick") return apply(el.dataset.path);
      if (act === "upload") {
        const inp = root.querySelector("#cpFile");
        const f = inp && inp.files && inp.files[0];
        if (!f) return toast(t("pick_file"));
        const reader = new FileReader();
        reader.onload = async () => {
          try {
            busy(t("cover_loading"));
            const r = await api("/cover/upload", {
              method: "POST",
              body: JSON.stringify({ entity_type: entityType, entity_id: Number(entityId),
                                     filename: f.name, data: reader.result }),
            });
            unbusy();
            apply(r.path);
          } catch (err) {
            unbusy();
            toastErr(err);
          }
        };
        reader.readAsDataURL(f);
        return;
      }
      if (act === "fetch") {
        const url = (root.querySelector("#cpUrl") || {}).value || "";
        if (!url) return toast(t("cover_url_hint"));
        try {
          busy(t("cover_loading"));
          const r = await api("/cover/fetch", {
            method: "POST",
            body: JSON.stringify({ entity_type: entityType, entity_id: Number(entityId), url }),
          });
          unbusy();
          apply(r.path);
        } catch (err) {
          unbusy();
          toastErr(err);
        }
      }
    });
    document.addEventListener("keydown", function _esc(ev) {
      if (ev.key === "Escape") { close(); document.removeEventListener("keydown", _esc); }
    });
    renderBody();
    const x = root.querySelector('[data-cp="close"]');
    if (x) x.focus();
  }

  function unbusy() {
    const el = document.getElementById("busy");
    if (el) el.style.display = "none";
  }

  function busyJob(title) {
    const el = _overlay();
    el.innerHTML = `<div class="busy-box">
      <div class="busy-row">${icon("spinner", 20)}<span id="job-title">${esc(title || t("working"))}</span></div>
      <div class="pbar" id="job-bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><div class="pbar-fill" id="job-fill"></div></div>
      <div class="busy-row busy-meta" aria-live="polite"><span id="job-count"></span><span id="job-eta"></span></div>
      <div class="form-row"><button class="btn danger" data-act="job-cancel">${t("cancel")}</button></div>
    </div>`;
    el.style.display = "flex";
    if (_jobTimer) clearInterval(_jobTimer);
    _jobTimer = setInterval(_pollJob, 1000);
    _pollJob();
  }

  function _fmtSec(n) {
    if (n == null) return "";
    if (n < 60) return `${n} ${t("sec_short")}`;
    const m = Math.floor(n / 60), sec = n % 60;
    return `${m} ${t("min_short")} ${sec} ${t("sec_short")}`;
  }

  async function _pollJob() {
    try {
      const r = await api("/job");
      const j = r.job;
      if (!j) { stopJob(); return; }
      const fill = document.getElementById("job-fill");
      const cnt = document.getElementById("job-count");
      const eta = document.getElementById("job-eta");
      const title = document.getElementById("job-title");
      if (title && j.title) title.textContent = j.title;
      if (fill) fill.style.width = `${j.percent || 0}%`;
      const bar = document.getElementById("job-bar");
      if (bar) bar.setAttribute("aria-valuenow", String(j.percent || 0));
      if (cnt) cnt.textContent = j.total ? `${j.done} / ${j.total} · ${j.percent}%` : `${j.done}`;
      if (eta) eta.textContent = j.status === "running" && j.eta ? `${t("left")} ~${_fmtSec(j.eta)}` : "";
      if (j.status !== "running") {
        stopJob();
        const msg = j.status === "cancelled" ? t("job_cancelled")
          : j.status === "failed" ? `${t("error_prefix")}: ${j.message}` : t("job_done");
        toast(msg);
        load();
      }
    } catch (e) { /* сеть — попробуем снова */ }
  }

  function stopJob() {
    if (_jobTimer) { clearInterval(_jobTimer); _jobTimer = null; }
    unbusy();
  }

  function statusText(status) {
    const s = (status || "").toLowerCase();
    const key = "st_" + s;
    return (I18N[state.lang] && I18N[state.lang][key]) || I18N.ru[key] || status || "—";
  }

  function statusBadge(status, waiting) {
    // C3: статус — бейдж (не кнопка), «ждёт премьеру» — отдельным бейджем ниже
    const s = (status || "").toLowerCase();
    let cls = "badge";
    if (["published", "ok", "ready"].includes(s)) cls += " ok";
    else if (["scheduled", "updating", "publishing", "queue"].includes(s)) cls += " info";
    else if (["failed", "error"].includes(s)) cls += " err";
    else if (["paused", "skipped", "overflow"].includes(s)) cls += " warn";
    let out = `<span class="${cls}">${statusText(status)}</span>`;
    if (waiting) {
      out += ` <span class="badge warn" title="${esc(t("waiting_hint"))}">${t("st_waiting")}</span>`;
    }
    return out;
  }

  function pill(status) {
    const s = (status || "").toLowerCase();
    let cls = "pill";
    if (["published", "ok", "ready"].includes(s)) cls += " ok";
    else if (["scheduled", "updating", "queue"].includes(s)) cls += " info";
    else if (["failed", "error"].includes(s)) cls += " err";
    else if (["paused", "skipped"].includes(s)) cls += " warn";
    const key = "st_" + s;
    const label = (I18N[state.lang] && I18N[state.lang][key]) || I18N.ru[key] || status || "—";
    return `<span class="${cls}">${label}</span>`;
  }

  const titles = () => ({
    status: t("title_status"), folders: t("title_folders"), calendar: t("title_calendar"),
    queue: t("title_queue"), platforms: t("title_platforms"), tail: t("title_tail"),
    failed: t("title_failed"), actions: t("title_actions"), metrics: t("title_metrics"),
    help: t("title_help"), manual: t("title_manual"), settings: t("title_settings"),
    trash: t("title_trash"),
  });

  let _loadGen = 0;  // P1-14: поколение запроса — поздний ответ прошлого экрана игнорируем

  async function load() {
    const v = state.view;
    const gen = ++_loadGen;
    content().innerHTML = `<div class="empty">${t("loading")}</div>`;
    try {
      let data;
      if (v === "status") data = await api("/status");
      else if (v === "folders") {
        data = await api("/roots");
        state.browseError = "";
        const nRoots = (data && Array.isArray(data.browse_roots)) ? data.browse_roots.length : -1;
        if (!state.browse) {
          if (nRoots === 0) {
            // N4: корней нет — не дёргаем /browse и не получаем 403 в консоли
            state.browse = { path: "", parent: null, dirs: [], root: "", roots: [] };
            state.browseError = t("e_no_roots");
          } else {
            try { state.browse = await api("/browse"); }
            catch (e) {
              state.browse = { path: "", parent: null, dirs: [], root: "", roots: [] };
              state.browseError = apiErrorText(e.message);
            }
          }
        }
      }
      else if (v === "calendar") data = await api("/calendar");
      else if (v === "queue") data = await api("/queue");
      else if (v === "platforms") data = await api("/platforms");
      else if (v === "settings" || v === "failed" || v === "help" || v === "schedule") {
        const sched = await api("/schedule_settings");
        const failed = await api("/failed");
        data = { sched, failed };
      }
      else if (v === "tail") {
        const tail = await api("/tail");
        const backlog = await api("/backlog");
        data = { items: tail.items || [], backlog: backlog.platforms || [] };
      }
      else if (v === "actions") {
        const status = await api("/status");
        let queue = { items: [] };
        let test = { enabled: false, recent: [] };
        try { queue = await api("/queue"); } catch (_) {}
        try { test = await api("/test/status"); } catch (_) {}
        data = { ...status, queue, test };
      }
      else if (v === "metrics") data = await api("/metrics");
      else if (v === "trash") data = await api("/trash");
      else if (v === "manual") {
        const plan = await api("/manual/plan");
        const uploads = await api("/manual/uploads");
        data = { plan, items: uploads.items || [] };
      }
      if (gen !== _loadGen) return;  // пришёл ответ устаревшего экрана — не перерисовываем
      state.data = data;
      render();
    } catch (e) {
      if (gen !== _loadGen) return;
      content().innerHTML = `<div class="empty">${t("error_prefix")}: ${esc(e.message)}</div>`;
    }
  }

  const SVG = {
    spinner: '<svg viewBox="0 0 24 24" class="spin"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2.5" opacity="0.25"/><path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg>',
    users: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="8" r="3.2"/><path d="M2.8 20a6.2 6.2 0 0 1 12.4 0"/><path d="M16 5.2a3.2 3.2 0 0 1 0 5.6"/><path d="M17.6 14.2A6.2 6.2 0 0 1 21.2 20"/></svg>',
    warn: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.6 2.4 20h19.2z"/><path d="M12 9.4v4.4"/><circle cx="12" cy="17" r="0.6" fill="currentColor" stroke="none"/></svg>',
    folder: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>',
    swap: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M7 4v13"/><path d="M4 14l3 3 3-3"/><path d="M17 20V7"/><path d="M14 10l3-3 3 3"/></svg>',
    edit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h4L19 9a2.1 2.1 0 0 0-3-3L5 17z"/><path d="M14.5 6.5l3 3"/></svg>',
    trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 7h14"/><path d="M9 7V5h6v2"/><path d="M7 7l1 13h8l1-13"/><path d="M10.5 11v5M13.5 11v5"/></svg>',
    check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l4 4L19 7"/></svg>',
    x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>',
    film: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M8 5v14M16 5v14M3 12h18"/></svg>',
    gear: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1.2l2-1.5-2-3.4-2.3 1a7 7 0 0 0-2-1.2L14 3h-4l-.6 2.7a7 7 0 0 0-2 1.2l-2.3-1-2 3.4 2 1.5A7 7 0 0 0 5 12c0 .4 0 .8.1 1.2l-2 1.5 2 3.4 2.3-1a7 7 0 0 0 2 1.2L10 21h4l.6-2.7a7 7 0 0 0 2-1.2l2.3 1 2-3.4-2-1.5c.1-.4.1-.8.1-1.2z"/></svg>',
    chart: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 20V10M12 20V4M19 20v-7"/></svg>',
    help: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M9.6 9.2a2.5 2.5 0 1 1 3.4 2.3c-.7.3-1 .8-1 1.5"/><circle cx="12" cy="16.6" r="0.7" fill="currentColor" stroke="none"/></svg>',
  };
  const ICON_SIZES = [12, 13, 14, 15, 16, 18, 20, 22, 26];
  function icon(name, size) {
    const sz = ICON_SIZES.includes(+size) ? +size : 16;
    return `<span class="pico pico-${sz}">${SVG[name] || ""}</span>`;
  }

  const PLATFORM_ICONS = {
    telegram: '<svg viewBox="0 0 24 24"><path d="M21.9 4.6 18.7 19c-.2 1-.9 1.2-1.7.8l-4.6-3.4-2.2 2.1c-.2.2-.5.5-.9.5l.3-4.7 8.5-7.7c.4-.3-.1-.5-.6-.2L6.8 12.9l-4.5-1.4c-1-.3-1-1 .2-1.5l17.7-6.8c.8-.3 1.6.2 1.7 1.4z"/></svg>',
    youtube: '<svg viewBox="0 0 24 24"><path d="M23 12s0-3.8-.5-5.6c-.3-1-1-1.8-2-2C18.6 4 12 4 12 4s-6.6 0-8.5.4c-1 .2-1.7 1-2 2C1 8.2 1 12 1 12s0 3.8.5 5.6c.3 1 1 1.8 2 2 1.9.4 8.5.4 8.5.4s6.6 0 8.5-.4c1-.2 1.7-1 2-2 .5-1.8.5-5.6.5-5.6zM9.8 15.5v-7l6 3.5-6 3.5z"/></svg>',
    instagram: '<svg viewBox="0 0 24 24"><path d="M12 2c-2.7 0-3 .01-4.1.06-1 .05-1.7.2-2.3.44-.6.24-1.1.56-1.6 1.06-.5.5-.8 1-1.06 1.6-.24.6-.4 1.3-.44 2.3C2 8.6 2 8.9 2 12s.01 3.4.06 4.5c.05 1 .2 1.7.44 2.3.24.6.56 1.1 1.06 1.6.5.5 1 .8 1.6 1.06.6.24 1.3.4 2.3.44 1.1.05 1.4.06 4.1.06s3-.01 4.1-.06c1-.05 1.7-.2 2.3-.44.6-.24 1.1-.56 1.6-1.06.5-.5.8-1 1.06-1.6.24-.6.4-1.3.44-2.3.05-1.1.06-1.4.06-4.5s-.01-3.4-.06-4.5c-.05-1-.2-1.7-.44-2.3-.24-.6-.56-1.1-1.06-1.6-.5-.5-1-.8-1.6-1.06-.6-.24-1.3-.4-2.3-.44C15.4 2 15.1 2 12 2zm0 5a5 5 0 1 1 0 10 5 5 0 0 1 0-10zm0 8.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4zm5.2-8.4a1.2 1.2 0 1 1-2.4 0 1.2 1.2 0 0 1 2.4 0z"/></svg>',
    tiktok: '<svg viewBox="0 0 24 24"><path d="M16.6 3c.3 2 1.5 3.6 3.4 4.2v3c-1.3 0-2.5-.4-3.4-1v6.3c0 3.3-2.4 5.5-5.5 5.5S5.6 18.8 5.6 15.5c0-2.9 1.9-5.1 4.7-5.4v3c-.3.06-.6.1-.9.1-1.4 0-2.4 1-2.4 2.3 0 1.4 1 2.4 2.4 2.4s2.5-1 2.5-2.4V3h4.7z"/></svg>',
    facebook: '<svg viewBox="0 0 24 24"><path d="M13.5 21v-7h2.3l.4-3h-2.7V9.2c0-.9.3-1.5 1.6-1.5h1.2V5.2c-.6-.1-1.4-.2-2.3-.2-2.3 0-3.8 1.4-3.8 3.9V11H8v3h2.2v7h3.3z"/></svg>',
  };
  function pIcon(name) {
    const key = String(name || "").toLowerCase();
    const svg = PLATFORM_ICONS[key] || '<svg viewBox="0 0 24 24"><path d="M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16z"/></svg>';
    return `<span class="pico" title="${esc(name || "")}">${svg}</span>`;
  }

  function renderStatus(d) {
    const counts = d.counts || {};
    const cards = Object.entries(counts)
      .map(([k, v]) => {
        const key = "st_" + k;
        const label = (I18N[state.lang] && I18N[state.lang][key]) || I18N.ru[key] || k;
        return `<div class="card"><div class="label">${label}</div><div class="value">${v}</div></div>`;
      })
      .join("");
    const plats = (d.platforms || [])
      .map((p) => {
        const off = !p.enabled;
        const badge = off
          ? `<span class="badge off">${t("pa_off")}</span>`
          : (p.paused ? `<span class="badge warn">${t("st_paused")}</span>`
                      : `<span class="badge ok">${t("pa_on")}</span>`);
        return `<div class="item${off ? " is-off" : ""}">
          <span class="q-plat big">${pIcon(p.name)}</span>
          <div class="item__main">
            <div class="item__title">${esc(p.name)}</div>
            <div class="item__meta">${t("limit_day")}: ${p.daily_limit}</div>
          </div>
          <div class="item__actions row">${badge}</div>
        </div>`;
      })
      .join("");
    content().innerHTML = `<div class="view-enter">
      <div class="grid cta-grid">
        <button class="btn primary" data-goto="folders">${esc(t("status_cta_add"))}</button>
        <button class="btn secondary" data-goto="queue">${esc(t("status_cta_queue"))}</button>
      </div>
      <div class="grid">${cards || `<div class="empty">${t("no_data")}</div>`}</div>
      <div class="panel"><div class="panel-head"><h3>${t("platforms")}</h3></div>
        ${plats || `<div class="empty">${t("no_platforms")}</div>`}
      </div>`;
  }

  function renderFolders(d) {
    const stepper = `<div class="row row-plain"><span class="meta">${esc(t("folders_stepper"))}</span></div>`;
    const items = d.items || (d.roots || []).map((x) => ({ path: x, kind: "auto" }));
    const roots = items
      .map((it) => `<div class="row"><div class="title mono flex-1 wrap-any">${esc(it.path)}</div>
        <span class="meta">${t("kind_label")}: ${t("kind_" + (it.kind || "auto"))}</span>
        <button class="btn secondary" data-act="folder-kind" data-p="${esc(it.path)}" title="${t("kind_label")}">${icon("swap", 14)}</button>
        <button class="btn danger" data-act="folder-remove" data-p="${esc(it.path)}">${t("remove")}</button></div>`)
      .join("");
    const b = state.browse || { path: "", parent: null, dirs: [], root: "", roots: [] };
    const metaByPath = {};
    (b.roots_meta || []).forEach((m) => { metaByPath[m.path] = m; });
    const rsel = (b.roots || []).length > 1
      ? `<div class="form-row roots-row">${(b.roots || []).map((r) => {
          const m = metaByPath[r] || { available: true };
          const warn = m.available ? "" : ` ${icon("warn", 14)}`;
          return `<button class="btn ${r === b.root ? "primary" : "secondary"}" data-act="folder-open" data-p="${esc(r)}"${m.available ? "" : " disabled"}>${esc(r)}${warn}</button>`;
        }).join("")}</div>`
      : "";
    const warnRow = b.warning ? `<div class="row"><span class="meta warn-text">${icon("warn", 14)} ${esc(b.warning)}</span></div>` : "";
    const browseWarn = state.browseError
      ? `<div class="row"><span class="meta warn-text">${icon("warn", 14)} ${esc(state.browseError)}</span></div>` : "";
    const sc = state.scan;
    const st = sc ? (sc.stats || {}) : null;
    const tot = sc ? (sc.totals || {}) : {};
    const scanPanel = sc ? `<div class="panel"><div class="panel-header">${t("scan")}</div>
      <div class="row"><span class="meta">${t("scan_found")}: ${t("scan_films")} ${st.long || 0} · ${t("scan_shorts")} ${st.shorts || 0} · ${t("scan_standalone")} ${st.standalone || 0}</span></div>
      <div class="row"><span class="meta">${t("scan_in_base")}: ${t("scan_films")} ${tot.long || 0} · ${t("scan_shorts")} ${tot.shorts || 0} · ${t("scan_skipped")}: ${sc.skipped || 0}</span></div>
      <div class="row"><span class="meta">${t("scan_last")}: ${(sc.last_scheduled || "").slice(0, 16).replace("T", " ") || t("scan_none")}</span></div>
      ${((st.long || 0) + (st.shorts || 0) + (st.standalone || 0)) === 0
          ? `<div class="row"><span class="meta">${(tot.long || 0) + (tot.shorts || 0) > 0 ? t("scan_none_new_hint") : t("scan_empty_hint")}</span></div>`
          : ""}
      <div class="row"><span class="meta">${t("scan_run_q")}</span></div>
      <div class="form-row">
        <button class="btn primary" data-act="scan-start">${t("scan_run_now")}</button>
      </div>
      <div class="form-row">
        <label class="meta">${t("scan_date_films")} <input id="scan-date-films" type="date" /></label>
        <label class="meta">${t("scan_date_shorts")} <input id="scan-date-shorts" type="date" /></label>
        <button class="btn secondary" data-act="scan-start-dates">${t("scan_run_dates")}</button>
        ${(sc.skipped || 0) > 0 ? `<button class="btn secondary" data-act="scan-restore">${t("scan_restore_btn")} (${sc.skipped})</button>` : ""}
      </div></div>` : "";

    const dirs = (b.dirs || [])
      .map((x) => `<div class="row"><div class="title">${icon("folder", 15)} ${esc(x.name)}</div>
        <button class="btn secondary" data-act="folder-open" data-p="${esc(x.path)}">${t("open")}</button></div>`)
      .join("");
    // поиск папки по имени (внутри текущего корня, до 5 уровней)
    const sq = state.folderSearch || { q: "", items: null };
    const searchResults = sq.items === null ? "" : (sq.items.length
      ? `<div class="search-list">${sq.items.map((x) =>
          `<div class="row"><div class="title flex-1 min-0 wrap-any">${icon("folder", 15)} ${esc(x.name)}<div class="meta mono fs-11">${esc(x.path)}</div></div>
            <button class="btn secondary" data-act="folder-open" data-p="${esc(x.path)}">${t("open")}</button>
            <button class="btn secondary" data-act="folder-add" data-p="${esc(x.path)}" data-kind="auto">${t("add_auto")}</button></div>`).join("")}</div>`
      : `<div class="empty">${t("search_none")}</div>`);
    const searchBlock = `<div class="q-toolbar pt-8">
        <input id="folder-q" class="search-input" type="search" placeholder="${t("search_placeholder")}" value="${esc(sq.q || "")}"/>
        <button class="btn secondary" data-act="folder-search">${t("search")}</button>
      </div>${searchResults}`;
    content().innerHTML = `
      ${stepper}
      <div class="panel"><div class="panel-header">${t("folders_to_scan")}</div>
        <div class="row"><span class="meta">${t("folders_hint")}</span></div>
        ${roots || `<div class="empty">${t("folders_none")}</div>`}
      </div>
      <div class="panel">
        <div class="panel-header">${t("browse")} · <span class="mono fs-12">${esc(b.path || "")}</span></div>
        ${rsel}
        <div class="row"><div class="title mono fs-12 wrap-any">${esc(b.path || "")}</div></div>
        ${searchBlock}
        ${warnRow}${browseWarn}
        <div class="btn-grid">
          <button class="btn secondary" data-act="folder-up" data-p="${esc(b.parent || "")}" ${b.parent ? "" : "disabled"}>${t("up")}</button>
          <button class="btn primary" data-act="folder-add" data-p="${esc(b.path || "")}" data-kind="series">${t("add_series")}</button>
          <button class="btn secondary" data-act="folder-add" data-p="${esc(b.path || "")}" data-kind="shorts">${t("add_shorts")}</button>
          <button class="btn secondary" data-act="folder-add" data-p="${esc(b.path || "")}" data-kind="auto">${t("add_auto")}</button>
        </div>
        <div class="btn-grid one">
          <button class="btn secondary success-text" data-act="folder-scan">${t("scan")}</button>
        </div>
        ${dirs || `<div class="empty">${t("no_subfolders")}</div>`}
      </div>
      ${scanPanel}`;
  }

  async function runFolderSearch() {
    const q = ((state.folderSearch || {}).q || "").trim();
    if (q.length < 2) { toast(t("search_short")); return; }
    const root = (state.browse || {}).root || "";
    busy(t("searching"));
    try {
      const d = await api(`/browse/search?q=${encodeURIComponent(q)}${root ? `&root=${encodeURIComponent(root)}` : ""}`);
      state.folderSearch = { q, items: d.items || [] };
    } catch (e) {
      toastErr(e);
    }
    unbusy();
    renderFolders(state.data || {});
  }

  async function browseTo(path) {
    const q = path ? `?path=${encodeURIComponent(path)}` : "";
    state.browse = await api("/browse" + q);
    renderFolders(state.data || {});
  }

  // C11: План — День / Неделя / Месяц (визуализация)
  const isoOf = (dt) => {
    const p = (n) => String(n).padStart(2, "0");
    return `${dt.getFullYear()}-${p(dt.getMonth() + 1)}-${p(dt.getDate())}`;
  };
  const addDaysIso = (iso, delta) => {
    const [y, m, d] = iso.split("-").map(Number);
    const dt = new Date(y, m - 1, d + delta, 12, 0, 0);
    return isoOf(dt);
  };
  const weekdayIso = (iso) => {
    const [y, m, d] = iso.split("-").map(Number);
    return new Date(y, m - 1, d, 12, 0, 0).getDay();
  };
  const humanDate = (iso) => {
    try {
      const [y, m, d] = iso.split("-").map(Number);
      return new Intl.DateTimeFormat(state.lang === "ru" ? "ru-RU" : "en-US",
        { weekday: "short", day: "numeric", month: "long" }).format(new Date(y, m - 1, d, 12));
    } catch (_) { return iso; }
  };
  const DAY_SHORT = (iso) => {
    try {
      const [y, m, d] = iso.split("-").map(Number);
      return new Intl.DateTimeFormat(state.lang === "ru" ? "ru-RU" : "en-US",
        { weekday: "short" }).format(new Date(y, m - 1, d, 12));
    } catch (_) { return ""; }
  };

  function calPostGroups(items) {
    // один пост видео = одна строка: YT+TG рядом (парные иконки), а не вразнобой
    const groups = new Map();
    (items || []).forEach((it) => {
      const k = (it.entity_type && it.entity_id)
        ? `${it.entity_type}#${it.entity_id}` : `t:${it.title || ""}`;
      if (!groups.has(k)) groups.set(k, { title: it.title || "", time: it.time || "", items: [] });
      const g = groups.get(k);
      if (!g.time && it.time) g.time = it.time;
      g.items.push(it);
    });
    return Array.from(groups.values()).sort((a, b) => String(a.time).localeCompare(String(b.time)));
  }

  function calRow(g) {
    const icons = g.items.map((it) => `<span class="q-plat">${pIcon(it.platform)}</span>`).join("");
    const badges = g.items.map((it) => statusBadge(it.status, false)).join(" ");
    const link = g.items.map((it) => it.url
      ? `<a href="${esc(it.url)}" target="_blank" rel="noopener" class="mono">↗</a>` : "").join(" ");
    return `<div class="item">
      <span class="mono">${esc(g.time || "—")}</span>
      <div class="item__main">
        <div class="item__title">${esc(g.title)}</div>
        <div class="item__meta">${icons}</div>
        <div class="item__meta">${badges} ${link}</div>
      </div>
    </div>`;
  }

  function renderCalendar(d) {
    const days = d.days || [];
    const view = state.calView || "day";
    const byDate = new Map(days.map((x) => [x.date, x]));
    const todayIso = isoOf(new Date());
    const cur = state.calDate || (byDate.has(todayIso) ? todayIso : (days[0] && days[0].date) || todayIso);
    const seg = (keys) => `<div class="seg" role="group">${keys.map(([k, l]) =>
      `<button class="${view === k ? "on" : ""}" data-act="cal-view" data-v="${k}" aria-pressed="${view === k}">${l}</button>`).join("")}</div>`;
    const bar = `<div class="panel"><div class="cal-bar">${seg([
      ["day", t("cal_day")], ["week", t("cal_week")], ["month", t("cal_month")]])}</div></div>`;
    if (!days.length) {
      content().innerHTML = bar + `<div class="panel"><div class="empty">${t("calendar_empty")}</div></div>`;
      return;
    }
    let body = "";
    if (view === "day") {
      const day = byDate.get(cur);
      const nav = `<div class="cal-nav">
        <button class="btn secondary sm" data-act="cal-shift" data-n="-1">‹</button>
        <b>${esc(humanDate(cur))}${cur === todayIso ? " · " + t("cal_today") : ""}</b>
        <button class="btn secondary sm" data-act="cal-shift" data-n="1">›</button></div>`;
      const groups = day ? calPostGroups(day.items) : [];
      body = `<div class="panel"><div class="panel-head"><h3>${t("cal_day")}</h3></div>${nav}
        ${groups.map(calRow).join("") || `<div class="empty">${t("calendar_empty")}</div>`}</div>`;
    } else if (view === "week") {
      const wd = weekdayIso(cur);
      const start = addDaysIso(cur, -((wd + 6) % 7)); // понедельник
      const cells = Array.from({ length: 7 }, (_v, i) => {
        const ds = addDaysIso(start, i);
        const day = byDate.get(ds);
        const groups = day ? calPostGroups(day.items) : [];
        const chips = groups.map((g) => `<button class="cal-witem" data-act="cal-day" data-d="${ds}">
            <span class="mono">${esc(g.time || "")}</span>
            <span class="q-plat">${g.items.map((it) => pIcon(it.platform)).join("")}</span></button>`).join("");
        return `<div class="cal-wcol${ds === todayIso ? " today" : ""}">
          <div class="cal-whead">${esc(DAY_SHORT(ds))} ${ds.slice(8)}</div>${chips}</div>`;
      }).join("");
      body = `<div class="panel"><div class="panel-head"><h3>${t("cal_week")}</h3>
        <button class="btn secondary sm" data-act="cal-today">${t("cal_today")}</button></div>
        <div class="cal-week">${cells}</div></div>`;
    } else {
      const [y, m] = cur.split("-").map(Number);
      const first = new Date(y, m - 1, 1, 12);
      const daysInMonth = new Date(y, m, 0, 12).getDate();
      const lead = (first.getDay() + 6) % 7;
      const cells = [];
      for (let i = 0; i < lead; i++) cells.push(`<div class="cal-cell empty"></div>`);
      for (let dd = 1; dd <= daysInMonth; dd++) {
        const ds = `${y}-${String(m).padStart(2, "0")}-${String(dd).padStart(2, "0")}`;
        const day = byDate.get(ds);
        const groups = day ? calPostGroups(day.items) : [];
        const dots = groups.slice(0, 4).map((g) => `<span class="cal-dot">${g.items.map((it) => pIcon(it.platform)).join("")}</span>`).join("");
        cells.push(`<button class="cal-cell${day ? " has" : ""}${ds === todayIso ? " today" : ""}" data-act="cal-day" data-d="${ds}">
          <span class="cal-d">${dd}</span>${dots}
          ${groups.length > 4 ? `<span class="cal-cnt">+${groups.length - 4}</span>` : ""}</button>`);
      }
      const wdays = (state.lang === "ru" ? ["пн", "вт", "ср", "чт", "пт", "сб", "вс"] : ["mo", "tu", "we", "th", "fr", "sa", "su"])
        .map((l) => `<span class="cal-wday-label">${l}</span>`).join("");
      body = `<div class="panel"><div class="panel-head"><h3>${t("cal_month")}</h3>
        <button class="btn secondary sm" data-act="cal-today">${t("cal_today")}</button></div>
        <div class="cal-month"><div class="cal-wdays">${wdays}</div>${cells.join("")}</div></div>`;
    }
    content().innerHTML = `<div class="view-enter">${bar}${body}</div>`;
  }

  async function bulkDelete() {
    const all = state.data?.items || [];
    const sel = state.queueSelected || {};
    const chosen = all.filter((it) => sel[`${it.entity_type}|${it.entity_id}|${it.platform}`]);
    if (!chosen.length) return;
    const ask = t("queue_bulk_del").replace("%s", chosen.length);
    if (!(await confirmDialog(ask))) return;
    const uniq = chosen.slice();
    const prog = (n) => t("queue_bulk_prog").replace("%s", n).replace("%s", uniq.length);
    busy(prog(1));
    let done = 0;
    let cascaded = 0;
    let failed = 0;
    const deps = [];
    for (const it of uniq) {
      done++;
      const el = document.getElementById("busy");
      if (el) el.innerHTML = `<div class="busy-box"><div class="busy-row">${icon("spinner", 20)}<span>${prog(done)}</span></div></div>`;
      try {
        const r = await api("/queue/remove", { method: "POST",
          body: JSON.stringify({ entity_type: it.entity_type, entity_id: it.entity_id,
                                 platform: it.platform }) });
        if (r && r.cascade && r.cascade.length) cascaded++;
        if (r && r.dependent && r.dependent.includes("telegram")) deps.push(it);
      } catch (e) {
        failed++;
        console.warn("queue remove failed", it.entity_type, it.entity_id, it.platform, e);
      }
    }
    if (deps.length) {
      const ask2 = t("confirm_cascade_tg_bulk").replace("%s", deps.length);
      if (await confirmDialog(ask2)) {
        for (const it of deps) {
          try {
            await api("/queue/remove", { method: "POST", body: JSON.stringify({
              entity_type: it.entity_type, entity_id: it.entity_id, platform: "telegram" }) });
            cascaded++;
          } catch (e) {
            failed++;
            console.warn("telegram cascade remove failed", it.entity_id, e);
          }
        }
      }
    }
    unbusy();
    state.queueSelected = {};
    const base = cascaded ? t("cascade_deleted") : `${t("queue_removed")}: ${uniq.length}`;
    toast(failed ? `${base} · ${t("t_bulk_failed").replace("%s", failed)}` : base);
    return load();
  }

  async function bulkEditTags(tags) {
    const all = state.data?.items || [];
    const sel = state.queueSelected || {};
    const chosen = all.filter((it) => sel[`${it.entity_type}|${it.entity_id}|${it.platform}`]);
    if (!chosen.length) return;
    const prog = (n) => t("queue_bulk_prog").replace("%s", n).replace("%s", chosen.length);
    busy(prog(1));
    let done = 0;
    let failed = 0;
    for (const it of chosen) {
      done++;
      const el = document.getElementById("busy");
      if (el) el.innerHTML = `<div class="busy-box"><div class="busy-row">${icon("spinner", 20)}<span>${prog(done)}</span></div></div>`;
      try {
        await api("/queue/edit", { method: "POST", body: JSON.stringify({
          entity_type: it.entity_type, entity_id: it.entity_id, platform: it.platform,
          title: it.title_text || "", description: it.description_text || "",
          hashtags: tags, date: it.date || "", time: it.time || "",
          cover: it.cover_path || "",
        }) });
      } catch (e) {
        failed++;
        console.warn("bulk tag edit failed", it.entity_type, it.entity_id, it.platform, e);
      }
    }
    unbusy();
    state.queueBulkTags = null;
    state.queueSelected = {};
    toast(failed ? `${t("t_saved")} · ${t("t_bulk_failed").replace("%s", failed)}` : t("t_saved"));
    return load();
  }

  function renderQueue(d) {
    const edit = state.queueEdit;
    const all = d.items || [];
    const filter = state.queueFilter || "all";
    const items = filter === "all" ? all : all.filter((it) => it.platform === filter);
    const sel = state.queueSelected || {};
    const selKeys = Object.keys(sel).filter((k) => sel[k]);
    const select = !!state.queueSelect;
    const keyOf = (it) => `${it.entity_type}|${it.entity_id}|${it.platform}`;
    const tgl = state.queueBulkTags !== null && state.queueBulkTags !== undefined;

    // фильтры-чипы (минимально кнопок: «Все» + по платформе, с количеством)
    const plats = Array.from(new Set(all.map((it) => it.platform)));
    const chips = [
      `<button class="chip${filter === "all" ? " on" : ""}" data-act="queue-filter" data-p="all" aria-pressed="${filter === "all"}">${t("queue_all")}<span class="cnt">${all.length}</span></button>`,
      ...plats.map((p) => {
        const n = all.filter((it) => it.platform === p).length;
        return `<button class="chip${filter === p ? " on" : ""}" data-act="queue-filter" data-p="${p}" aria-pressed="${filter === p}">${pIcon(p)}<span class="cnt">${n}</span></button>`;
      }),
    ].join("");

    const toolbar = `<div class="q-toolbar">
        <div class="chips">${chips}</div>
        <button class="btn ${select ? "primary" : "secondary"} q-sel-btn" data-act="queue-select">${select ? t("queue_done") : t("queue_select")}</button>
      </div>`;

    const bulkBar = !select ? "" : `<div class="bulk-bar">
        <span class="meta"><b>${selKeys.length}</b> ${t("queue_selected")}</span>
        <button class="btn secondary" data-act="queue-check-all">${t("queue_all")}</button>
        <button class="btn secondary" data-act="queue-bulk-tags" ${selKeys.length ? "" : "disabled"}>${t("queue_bulk_tags")}</button>
        <button class="btn danger" data-act="queue-bulk-delete" ${selKeys.length ? "" : "disabled"}>${t("queue_remove")}</button>
      </div>`;

    const bulkTags = !tgl ? "" : `<div class="bulk-tags">
        <label class="meta">${t("queue_bulk_tagp").replace("%s", selKeys.length)}
          <input id="qb-tags" type="text" value="${esc(state.queueBulkTags || "")}"/></label>
        <div class="form-row">
          <button class="btn primary" data-act="queue-bulk-tags-apply">${t("queue_bulk_apply")}</button>
          <button class="btn secondary" data-act="queue-bulk-tags-cancel">${t("cancel")}</button>
        </div>
      </div>`;

    const dayLabel = (ds) => {
      if (!ds) return t("no_data");
      let d;
      try { d = new Date(ds + "T12:00:00"); } catch (_) { return ds; }
      const today = new Date(); today.setHours(12, 0, 0, 0);
      const diff = Math.round((d - today) / 86400000);
      const rel = diff === 0 ? t("q_today") : diff === 1 ? t("q_tomorrow") : diff === -1 ? t("q_yesterday") : "";
      let human = ds;
      try {
        human = new Intl.DateTimeFormat(state.lang === "ru" ? "ru-RU" : "en-US",
          { weekday: "short", day: "numeric", month: "long" }).format(d);
      } catch (_) {}
      return (rel ? rel + " · " : "") + human;
    };

    const rowHtml = (it) => {
      const key = keyOf(it);
      const checked = !!sel[key];
      const form = (edit && edit.key === key)
        ? `<div class="q-edit-panel">
             <label class="field"><span class="field__label">${t("edit_title")}</span>
               <input id="qe-title" type="text" value="${esc(it.title_text || "")}"/></label>
             <label class="field"><span class="field__label">${t("edit_desc")}</span>
               <textarea id="qe-desc" rows="4">${esc(it.description_text || "")}</textarea></label>
             <label class="field"><span class="field__label">${t("edit_tags")}</span>
               <input id="qe-tags" type="text" value="${esc(it.hashtags_text || "")}"/></label>
             <label class="field"><span class="field__label">${t("edit_cover")}</span>
               <select id="qe-cover">
                 <option value="">${t("cover_none")}</option>
                 ${(it.covers || []).map((c) => `<option value="${esc(c)}" ${c === it.cover_path ? "selected" : ""}>${esc(c.split("/").pop())}</option>`).join("")}
               </select></label>
             <div class="btn-grid">
               <button class="btn secondary" data-act="cover-pick"
                       data-et="${it.entity_type}" data-eid="${it.entity_id}"
                       data-video="${esc(it.video_path || "")}">${t("cover_pick")}</button>
               <button class="btn secondary" data-act="queue-edit-cancel">${t("queue_edit_cancel")}</button>
             </div>
             <div class="btn-grid" style-x>
               <label class="field" style-nopad><span class="field__label">${t("edit_date")}</span><input id="qe-date" type="date" value="${it.date || ""}"/></label>
               <label class="field" style-nopad><span class="field__label">${t("edit_time")}</span><input id="qe-time" type="time" value="${it.time || ""}"/></label>
             </div>
             <div class="btn-grid">
               <button class="btn primary" data-act="queue-edit-save" data-et="${it.entity_type}" data-eid="${it.entity_id}" data-p="${it.platform}">${t("queue_edit_save")}</button>
             </div>
             <div class="divider"></div>
             <div class="hint">${t("delete_everywhere_hint")}</div>
             <div class="btn-grid">
               <button class="btn secondary danger-text" data-act="queue-remove-everywhere" data-et="${it.entity_type}" data-eid="${it.entity_id}" data-tg="${it.has_tg ? "1" : "0"}" data-title="${esc(it.title || "")}">${t("delete_everywhere")}</button>
               ${it.entity_type === "long_video" ? `<button class="btn secondary danger-text" data-act="queue-remove-film-only" data-eid="${it.entity_id}" data-tg="${it.has_tg ? "1" : "0"}" data-title="${esc(it.title || "")}">${t("queue_remove_film_only")}</button>` : ""}
             </div>
           </div>`
        : "";
      const check = !select ? "" : `<button class="q-check${checked ? " on" : ""}" data-act="queue-check"
          data-key="${key}" aria-pressed="${checked}" aria-label="${t("queue_select")}">${checked ? icon("check", 13) : ""}</button>`;
      const cover = it.cover_path
        ? `<button class="q-cover-btn" data-act="queue-edit" data-key="${key}" title="${t("edit_cover")}">
             <img class="q-cover" loading="lazy" alt=""
               src="/webapp/api/cover/thumb?key=${encodeURIComponent(state.key || "")}&path=${encodeURIComponent(it.cover_path)}"/></button>`
        : `<button class="q-cover-btn q-cover-empty" data-act="queue-edit" data-key="${key}" title="${t("cover_pick")}"></button>`;
      const col = select ? "" : `<div class="item__actions">
          <button class="icon-btn" data-act="queue-edit" data-key="${key}" title="${t("queue_edit")}" aria-label="${t("queue_edit")}">${icon("edit", 18)}</button>
          <button class="icon-btn danger" data-act="queue-remove" data-et="${it.entity_type}" data-eid="${it.entity_id}" data-p="${it.platform}" data-title="${esc(it.title || "")}" title="${t("queue_remove")}" aria-label="${t("queue_remove")}">${icon("trash", 18)}</button>
        </div>`;
      return `<div class="item q-item${checked ? " picked" : ""}${select ? " with-check" : ""}">
        ${check}${cover}
        <div class="item__main">
          <div class="item__title" title="${esc(it.title || "")}">${esc(it.title || (it.entity_type + "#" + it.entity_id))}</div>
          <div class="item__meta">
            <span class="mono">${esc(it.date || "")}</span>
            <span class="mono">${esc(it.time || "")}</span>
            <span class="q-plat">${pIcon(it.platform)}</span>
          </div>
          <div class="item__meta">${statusBadge(it.status, it.waiting)}</div>
        </div>
        ${col}
        ${form}</div>`;
    };

    const groups = [];
    for (const it of items) {
      let g = groups[groups.length - 1];
      if (!g || g.date !== it.date) { g = { date: it.date, items: [] }; groups.push(g); }
      g.items.push(it);
    }
    const body = groups.map((g) => `
      <div class="day-sep"><span>${dayLabel(g.date)}</span><span class="cnt">${g.items.length}</span></div>
      ${g.items.map(rowHtml).join("")}`).join("");

    content().innerHTML = `<div class="panel">${toolbar}${bulkBar}${bulkTags}${
      body || `<div class="empty">${t("queue_empty")}</div>`}</div>`;
  }

  function renderPlatforms(d) {
    const rows = (d.platforms || []).map((p) => {
      const off = !p.enabled;
      const badge = off
        ? `<span class="badge off">${t("pa_off")}</span>`
        : (p.paused ? `<span class="badge warn">${t("st_paused")}</span>`
                    : `<span class="badge ok">${t("pa_on")}</span>`);
      const action = off ? "" : (p.paused
        ? `<button class="btn secondary sm" data-act="resume-one" data-p="${esc(p.name)}">${t("resume")}</button>`
        : `<button class="btn secondary sm" data-act="pause-one" data-p="${esc(p.name)}">${t("pa_pause")}</button>`);
      return `<div class="item${off ? " is-off" : ""}">
        <span class="q-plat big">${pIcon(p.name)}</span>
        <div class="item__main">
          <div class="item__title">${esc(p.name)}</div>
          <div class="item__meta">${t("limit_day")}: ${p.daily_limit}</div>
        </div>
        <div class="item__actions row">${badge}${action}</div>
      </div>`;
    }).join("");
    content().innerHTML = `
      <div class="panel">
        <div class="panel-head"><h3>${t("platforms")}</h3></div>
        <div class="btn-grid">
          <button class="btn secondary danger-text" data-act="pause-all">${t("pause_all")}</button>
          <button class="btn secondary success-text" data-act="resume-all">${t("resume_all")}</button>
        </div>
        ${rows || `<div class="empty">${t("none")}</div>`}
      </div>`;
  }

  function renderTail(d) {
    const dateRow = `<div class="form-row"><label class="meta">${t("backlog_from")}
        <input id="backlog-date" type="date" /></label></div>`;
    const rows = (d.backlog || []).map((p) => {
      const state = p.awaiting
        ? `<span class="badge warn">${t("backlog_awaiting")}</span>`
        : (p.tail_mode ? `<span class="badge info">${t("backlog_on")}</span>`
                       : `<span class="badge">${t("backlog_off")}</span>`);
      const slot = p.slot ? `<span class="mono">${esc(String(p.slot).slice(0, 16).replace("T", " "))}</span>` : "";
      const pname = String(p.platform || "");
      const title = pname ? pname.charAt(0).toUpperCase() + pname.slice(1) : "—";
      const tailBtn = p.tail_mode
        ? `<button class="btn secondary" data-act="tail-off" data-p="${esc(p.platform)}">${t("disable")}</button>`
        : `<button class="btn secondary" data-act="tail-on" data-p="${esc(p.platform)}">${t("enable")}</button>`;
      return `<div class="item">
        <span class="q-plat big">${pIcon(p.platform)}</span>
        <div class="item__main">
          <div class="item__title">${esc(title)}</div>
          <div class="item__meta">${t("backlog_unposted")}: <b>${p.count}</b>${slot ? " · " + slot : ""}</div>
          <div class="item__meta">${state}</div>
        </div>
      </div>
      <div class="btn-grid cols-3">
        <button class="btn primary" data-act="backlog-answer" data-p="${esc(p.platform)}" data-a="distribute">${t("backlog_distribute")}</button>
        <button class="btn secondary" data-act="backlog-answer" data-p="${esc(p.platform)}" data-a="wait">${t("backlog_wait")}</button>
        <button class="btn secondary danger-text" data-act="backlog-answer" data-p="${esc(p.platform)}" data-a="skip">${t("backlog_skip")}</button>
      </div>
      <div class="btn-grid">${tailBtn}</div>`;
    }).join("");
    content().innerHTML = `<div class="panel"><div class="panel-head"><h3>${t("tail_title")}</h3></div>
      <div class="hint">${t("tail_explain")}</div>
      ${rows ? dateRow : ""}
      ${rows || `<div class="empty">${t("no_data")}</div>`}</div>`;
  }

  function failedHtml(d) {
    const items = (d && d.items) || [];
    if (!items.length) {
      return `<div class="panel"><div class="panel-head"><h3>${t("errors_header")}</h3></div>
        <div class="empty">${t("no_errors")}</div></div>`;
    }
    const byPlat = {};
    items.forEach((it) => { (byPlat[it.platform] = byPlat[it.platform] || []).push(it); });
    const panels = Object.entries(byPlat).map(([plat, list]) => `
      <div class="panel">
        <div class="panel-head">
          <h3><span class="q-plat big">${pIcon(plat)}</span> ${esc(plat.charAt(0).toUpperCase() + plat.slice(1))}</h3>
          <span class="badge err">${list.length}</span>
        </div>
        ${list.map((it) => `<div class="item">
          <span></span>
          <div class="item__main">
            <div class="item__title">${esc(entityLabel(it.entity_type))} #${esc(String(it.entity_id))}</div>
            <div class="item__hint">${esc(errText(it.last_error))}</div>
          </div>
          <div class="item__actions row">${statusBadge(it.status, false)}</div>
        </div>`).join("")}
      </div>`).join("");
    return `<div class="panel"><div class="panel-head"><h3>${t("errors_header")}</h3>
        <span class="badge err">${items.length}</span></div>
      <div class="hint">${t("errors_hint")}</div></div>${panels}`;
  }

  function actCell(act, labelKey, hintKey, cls) {
    return `<div class="act">
      <button class="btn ${cls || "secondary"}" data-act="${act}">${t(labelKey)}</button>
      <span class="item__hint">${t(hintKey)}</span>
    </div>`;
  }

  function renderActions(d) {
    const opts = ((d && d.platforms) || [])
      .map((p) => `<option>${esc(p.name)}</option>`).join("")
      || `<option>youtube</option>`;
    content().innerHTML = `
      <div class="panel"><div class="panel-head"><h3>${t("act_group_plan")}</h3></div>
        <div class="act-grid">
          ${actCell("distribute", "distribute", "h_distribute", "primary")}
          ${actCell("schedule", "act_schedule", "h_schedule")}
        </div>
      </div>
      <div class="panel"><div class="panel-head"><h3>${t("act_group_data")}</h3></div>
        <div class="act-grid">
          ${actCell("sync", "act_sync", "h_sync")}
          ${actCell("reconcile", "act_reconcile", "h_reconcile")}
          ${actCell("queue-restore-all", "restore_posts", "h_restore")}
          ${actCell("queue-cleanup-orphans", "cleanup_orphans", "h_cleanup")}
        </div>
      </div>
      <div class="panel"><div class="panel-head"><h3>${t("act_group_service")}</h3></div>
        <div class="act-grid">
          ${actCell("backup", "act_backup", "h_backup")}
          ${actCell("refresh", "refresh_data", "h_refresh")}
        </div>
      </div>
      <div class="panel"><div class="panel-header">${t("test_title")}</div>
        ${(d && d.test && d.test.enabled) ? `
          <div class="row"><span class="meta">${t("test_hint")}</span></div>
          <div class="form-row">
            <select id="tp-p">${((d.test.platforms || []).map((p) => `<option>${esc(p)}</option>`).join("")) || `<option>youtube</option>`}</select>
            <input id="tp-delay" type="number" min="${d.test.min_delay_minutes || 1}" max="${d.test.max_delay_minutes || 120}"
              value="${d.test.default_delay_minutes || 1}" title="${t("test_delay")}" class="w-86" />
            <select id="tp-e" class="flex-1 min-180" title="${t("test_entity")}">${testEntityOpts(d.queue)}</select>
          </div>
          <div class="form-row">
            <button class="btn primary" data-act="test-schedule">${t("test_schedule")}</button>
            <button class="btn secondary" data-act="test-dry">${t("test_dry")}</button>
          </div>
          ${testRecent(d.test)}`
        : `<div class="row"><span class="meta">${t("test_disabled")}</span></div>`}
      </div>
      <div class="panel"><div class="panel-header">${t("force_link_title")}</div>
        <div class="row"><span class="meta">${t("fl_hint")}</span></div>
        <div class="form-row">
          <input id="fl-id" type="number" placeholder="${t("fl_id_ph")}" class="w-120" />
          <select id="fl-p">${opts}</select>
          <input id="fl-url" type="url" placeholder="https://..." class="flex-1 min-140" />
          <button class="btn primary" data-act="force-link">${t("save")}</button>
        </div>
      </div>`;
  }

  function testEntityOpts(queue) {
    const seen = new Set();
    const out = [];
    for (const it of ((queue && queue.items) || [])) {
      const key = `${it.entity_type}:${it.entity_id}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const label = `${entityLabel(it.entity_type)} #${it.entity_id} · ${(it.title || "").slice(0, 42)}`;
      out.push(`<option value="${esc(key)}">${esc(label)}</option>`);
      if (out.length >= 120) break;
    }
    return out.join("") || `<option value="">—</option>`;
  }

  function testRecent(test) {
    const items = (test && test.recent) || [];
    if (!items.length) return "";
    const rows = items.map((r) => {
      const pid = String(r.details || "").split(" ")[0];
      return `<div class="row row-center-8">
        <span class="meta">${esc(r.platform)} · ${esc(r.entity_type)}#${esc(String(r.entity_id))} · ${esc(pid)}</span>
        <button class="btn secondary" data-act="test-cancel" data-pid="${esc(pid)}">${t("test_cancel")}</button>
      </div>`;
    }).join("");
    return `<div class="row"><span class="meta">${t("test_recent")}</span></div>${rows}`;
  }

  function fmtDuration(sec) {
    sec = Math.max(0, Math.floor(sec));
    const d = Math.floor(sec / 86400);
    const h = Math.floor((sec % 86400) / 3600);
    const m = Math.floor((sec % 3600) / 60);
    if (d) return `${d}${state.lang === "ru" ? " д " : "d "}${h}${state.lang === "ru" ? " ч" : "h"}`;
    if (h) return `${h}${state.lang === "ru" ? " ч " : "h "}${m}${state.lang === "ru" ? " м" : "m"}`;
    if (m) return `${m}${state.lang === "ru" ? " м " : "m "}${sec % 60}${state.lang === "ru" ? " с" : "s"}`;
    return `${sec}${state.lang === "ru" ? " с" : "s"}`;
  }

  function fmtTime(ts) {
    if (!ts) return "—";
    try {
      return new Date(ts * 1000).toLocaleString(state.lang === "ru" ? "ru-RU" : "en-GB", {
        day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
      });
    } catch (_) {
      return "—";
    }
  }

  function metric(label, value) {
    return `<div class="card"><div class="label">${label}</div><div class="value">${value ?? "—"}</div></div>`;
  }

  function renderMetrics(d) {
    d = d || {};
    const live = d.live || {};
    const now = Date.now() / 1000;
    const uptime = d.started_at ? fmtDuration(now - d.started_at) : "—";
    const cards = [
      metric(t("m_uptime"), uptime),
      metric(t("m_cycles"), d.cycles ?? 0),
      metric(t("m_queue_now"), live.queue ?? 0),
      metric(t("m_cycle_errors"), d.errors ?? 0),
    ].join("");
    const errRow = d.last_error
      ? `<div class="item"><span></span><div class="item__main"><div class="item__title">${t("m_err_pill")}</div>
           <div class="item__hint">${esc(d.last_error)}</div></div><div class="item__actions row"><span class="badge err">!</span></div></div>`
      : `<div class="item"><span></span><div class="item__main"><div class="item__title">${t("m_no_err")}</div></div>
           <div class="item__actions row"><span class="badge ok">${t("m_ok")}</span></div></div>`;
    content().innerHTML = `
      <div class="grid">${cards}</div>
      <div class="panel"><div class="panel-header">${t("m_publications")}</div>
        <div class="row"><div class="title">${t("m_published")}</div><span class="meta">${live.published ?? 0}</span></div>
        <div class="row"><div class="title">${t("m_queue_row")}</div><span class="meta">${live.queue ?? 0}</span></div>
        <div class="row"><div class="title">${t("m_failed")}</div><span class="meta">${live.failed ?? 0}</span></div>
      </div>
      <div class="panel"><div class="panel-header">${t("m_scheduler")}</div>
        <div class="row"><div class="title">${t("m_last_cycle")}</div><span class="meta">${fmtTime(d.last_cycle_at)}</span></div>
        <div class="row"><div class="title">${t("m_sched_long")}</div><span class="meta">${d.scheduled_long || 0}</span></div>
        <div class="row"><div class="title">${t("m_sched_short")}</div><span class="meta">${d.scheduled_short || 0}</span></div>
        <div class="row"><div class="title">${t("m_sync")}</div><span class="meta">${d.sync_updates || 0}</span></div>
        ${errRow}
      </div>`;
  }

  function helpSection(titleKey, items) {
    const rows = items.map(([nameKey, descKey]) =>
      `<div class="item help-item">
        <span></span>
        <div class="item__main">
          <div class="item__title">${t(nameKey)}</div>
          <div class="item__hint">${t(descKey)}</div>
        </div>
      </div>`).join("");
    return `<div class="panel"><div class="panel-head"><h3>${t(titleKey)}</h3></div>${rows}</div>`;
  }

  function renderManual(d) {
    const plan = d.plan || {};
    const items = d.items || [];
    const statusRow = Object.entries(plan.by_status || {})
      .map(([k, v]) => `${pill(k)} <span class="meta">${v}</span>`).join(" ");
    const platforms = plan.platforms || [];
    const scanBtns = platforms
      .map((p) => `<button class="btn secondary" data-act="manual-scan" data-p="${p}">${t("mu_scan")} · ${p}</button>`)
      .join(" ");
    const scanAll = platforms.length
      ? `<button class="btn primary" data-act="manual-scan-all">${t("mu_scan_all")}</button>` : "";
    const last = plan.last_scan
      ? `${t("mu_last_scan")}: ${fmtTime(Date.parse(plan.last_scan.at) / 1000)}` : "";
    const rows = items.map((it) => {
      const claim = it.claim_status === "claimed"
        ? `<div class="form-row"><span class="pill err">${t("mu_claim_title")}</span>
             <button class="btn danger" data-act="manual-claim" data-id="${it.id}" data-c="delete">${t("mu_claim_delete")}</button>
             <button class="btn secondary" data-act="manual-claim" data-id="${it.id}" data-c="keep">${t("mu_claim_keep")}</button>
             <button class="btn secondary" data-act="manual-claim" data-id="${it.id}" data-c="ignore">${t("mu_ignore")}</button></div>`
        : "";
      let actions = "";
      if (it.match_status === "suggested" && (it.candidates || []).length) {
        const cands = it.candidates.map((c, i) =>
          `<button class="btn ${i === 0 ? "primary" : "secondary"}" data-act="manual-confirm"
             data-id="${it.id}" data-et="${c.entity_type}" data-eid="${c.entity_id}">${esc(c.title)} · ${Math.round((c.score || 0) * 100)}%</button>`
        ).join(" ");
        actions = `<div class="form-row">${cands}
          <button class="btn danger" data-act="manual-reject" data-id="${it.id}">${t("mu_reject")}</button>
          <button class="btn secondary" data-act="manual-ignore" data-id="${it.id}">${t("mu_ignore")}</button></div>`;
      } else if (it.match_status === "confirmed") {
        actions = `<div class="row"><span class="pill ok">${t("mu_confirmed")}</span>
          <span class="meta">${it.matched_entity_type}#${it.matched_entity_id}</span></div>`;
      } else if (it.match_status === "unmatched") {
        actions = `<div class="form-row"><span class="meta">${t("mu_none")}</span>
          <button class="btn secondary" data-act="manual-ignore" data-id="${it.id}">${t("mu_ignore")}</button></div>`;
      }
      const claimMark = it.claim_status !== "claimed"
        ? `<button class="btn secondary" data-act="manual-claim-mark" data-id="${it.id}">${t("mu_claim_mark")}</button>`
        : "";
      return `<div class="panel">
        <div class="panel-header">${esc(it.title || it.platform_video_id)} ${pill(it.origin === "postiz" ? "postiz" : "manual")} ${pill(it.match_status)}</div>
        <div class="row"><div class="title">${it.platform} · ${it.published_at || ""}</div>
          ${it.url ? `<a href="${esc(it.url)}" target="_blank" rel="noopener">↗</a>` : ""}${claimMark}</div>
        ${claim}${actions}
      </div>`;
    }).join("");
    content().innerHTML = `
      <div class="panel">
        <div class="panel-header">${t("mu_total")}: ${plan.total ?? 0} <span class="meta">${statusRow}</span></div>
        <div class="form-row">${scanBtns} ${scanAll}</div>
        ${last ? `<div class="row"><span class="meta">${last}</span></div>` : ""}
      </div>
      ${rows || `<div class="panel"><div class="empty">${t("mu_none")}</div></div>`}`;
  }

  const DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
  function dayChips(scope, kind, selected) {
    const sel = selected || [];
    return `<div class="chips day-chips">${DAY_KEYS.map((k) =>
      `<label class="chip${sel.includes(k) ? " on" : ""}"><input type="checkbox" class="chip__input" data-day="${scope}|${kind}" value="${k}"${sel.includes(k) ? " checked" : ""}/>${t("dow_" + k)}</label>`
    ).join("")}</div>`;
  }
  function schedBlock(key, title, eff, block, withLimit) {
    const long = (block && block.long) || {};
    const th = (block && block.thematic) || {};
    const sa = (block && block.standalone) || {};
    const effLong = (eff && eff.long) || {};
    const effTh = (eff && eff.thematic) || {};
    const effSa = (eff && eff.standalone) || {};
    const longDays = long.days || effLong.days || [];
    const longTime = long.time || effLong.time || "";
    const thTime = th.time || effTh.time || "";
    const saDays = sa.days || effSa.days || [];
    const saTimesArr = (sa.times || effSa.times || []).slice(0, 3);
    const cnt = Number(state.schedCount && state.schedCount[key]) || Math.max(saTimesArr.length, 1);
    const limit = withLimit ? ((block && block.daily_limit) ?? ((eff && eff.daily_limit) ?? "")) : "";
    const timeInputs = Array.from({ length: cnt }, (_v, i) =>
      `<input type="time" data-time-n="${key}|standalone|${i}" value="${esc(saTimesArr[i] || "")}"/>`).join("");
    const seg = [1, 2, 3].map((x) =>
      `<button class="${x === cnt ? "on" : ""}" data-act="sched-count" data-p="${esc(key)}" data-n="${x}"
        aria-pressed="${x === cnt}">${x}</button>`).join("");
    return `<div class="panel"><div class="panel-head"><h3>${title}</h3></div>
      <div class="field"><span class="field__label">${t("sched_long")} · ${t("sched_days")}</span>
        ${dayChips(key, "long", longDays)}
        <input type="time" data-time="${key}|long" value="${longTime}"/></div>
      <div class="field"><span class="field__label">${t("sched_thematic")}</span>
        <input type="time" data-time="${key}|thematic" value="${thTime}"/></div>
      <div class="field"><span class="field__label">${t("sched_standalone")} · ${t("sched_days")}</span>
        ${dayChips(key, "standalone", saDays)}</div>
      <div class="field"><span class="field__label">${t("sched_count")}</span>
        <div class="seg" role="group">${seg}</div>
        <div class="times-row">${timeInputs}</div>
        <input type="hidden" data-times="${key}|standalone" value="${esc(saTimesArr.join(", "))}"/></div>
      ${withLimit ? `<div class="field"><span class="field__label">${t("sched_limit")}</span>
        <input type="number" min="0" max="50" data-limit="${key}" value="${limit}"/>
        <span class="item__hint">${t("sched_limit_hint")}</span></div>` : ""}
      <div class="btn-grid">
        <button class="btn primary" data-act="sched-save" data-p="${key}">${t("sched_save")}</button>
        <button class="btn secondary" data-act="sched-reset" data-p="${key}">${t("sched_reset")}</button>
      </div></div>`;
  }
  function groupsHtml(d) {
    const groups = d.groups || [];
    const plats = d.platforms || [];
    const groupRows = groups.map((g) => {
      const chips = (g.platforms || []).map((p) =>
        `<span class="badge info"><span class="q-plat">${pIcon(p)}</span>${esc(p)}</span>`).join(" ");
      return `<div class="item">
        <span class="q-plat big">${icon("users", 20)}</span>
        <div class="item__main">
          <div class="item__title">${esc(g.name)}</div>
          <div class="item__meta">${chips || "—"}</div>
        </div>
        <div class="item__actions row">
          <button class="btn secondary danger-text sm" data-act="group-remove" data-p="${esc(g.name)}">${t("group_remove")}</button>
        </div>
      </div>`;
    }).join("");
    const groupForm = `<div class="field"><span class="field__label">${t("group_name")}</span>
        <input id="group-name" placeholder="${t("group_name")}"/></div>
      <div class="field"><span class="field__label">${t("group_platforms")}</span>
        <div class="chips">${plats.map((p) =>
          `<label class="chip"><input type="checkbox" class="chip__input" data-gplat value="${esc(p)}"/><span class="q-plat">${pIcon(p)}</span>${esc(p)}</label>`).join("")}</div></div>
      <div class="btn-grid one"><button class="btn primary" data-act="group-add">${t("group_add")}</button></div>`;
    return `<div class="panel"><div class="panel-head"><h3>${t("groups_header")}</h3></div>
      <div class="hint">${t("groups_hint")}</div>
      ${groupRows || `<div class="empty">${t("groups_none")}</div>`}${groupForm}</div>`;
  }
  function scheduleHtml(d) {
    const settings = d.settings || {};
    const groups = d.groups || [];
    const eff = d.effective || {};
    const plats = d.platforms || [];
    const platformsHtml = plats.map((p) => schedBlock(p, `<span class="q-plat">${pIcon(p)}</span>`, eff[p] || {}, settings[p] || {}, true)).join("");
    const groupsHtmlBlocks = groups.map((g) => schedBlock(`group:${g.name}`, `${icon("users", 15)} ${esc(g.name)}`, null, settings[`group:${g.name}`] || {}, false)).join("");
    return platformsHtml + groupsHtmlBlocks;
  }
  function renderSettings(d) {
    const tab = state.settingsTab || "sched";
    const sched = d.sched || {};
    const tabs = [["sched", t("settings_tab_sched")], ["help", t("settings_tab_help")]];
    const tabBtns = `<div class="panel"><div class="form-row">${tabs.map(([k, label]) =>
      `<button class="btn ${tab === k ? "primary" : "secondary"}" data-act="settings-tab" data-p="${k}">${label}</button>`).join("")}</div></div>`;
    let body = "";
    if (tab === "help") body = helpHtml();
    else {
      const mode = (sched.mode === "auto") ? "auto" : "manual";
      const modePanel = `<div class="panel"><div class="panel-header">${t("sched_title")}</div>
        <div class="row"><span class="meta">${t("mode_hint")}</span></div>
        <div class="form-row"><button class="btn ${mode === "auto" ? "success" : "secondary"}" data-act="toggle-mode">${mode === "auto" ? t("mode_auto") : t("mode_manual")}</button></div></div>`;
      body = `<div class="panel"><div class="hint">${t("sched_priority")}</div></div>`
        + groupsHtml(sched)
        + modePanel
        + `<div class="panel"><div class="hint">${t("sched_explain")}</div></div>`
        + scheduleHtml(sched);
    }
    content().innerHTML = `<div class="view-enter">${tabBtns}${body}</div>`;
  }
  function helpHtml() {
    return [
      helpSection("help_nav", [
        ["nav_status", "help_nav_status"], ["nav_folders", "help_nav_folders"],
        ["nav_calendar", "help_nav_calendar"], ["nav_queue", "help_nav_queue"],
        ["nav_platforms", "help_nav_platforms"], ["nav_tail", "help_nav_tail"],
        ["nav_failed", "help_nav_failed"], ["nav_metrics", "help_nav_metrics"],
        ["nav_actions", "help_nav_actions"], ["nav_manual", "help_nav_manual"],
        ["nav_help", "help_nav_help"],
      ]),
      helpSection("help_folders", [
        ["add_folder", "help_a_add"], ["scan", "help_a_scan"], ["open", "help_a_open"],
        ["up", "help_a_up"], ["remove", "help_a_remove"], ["browse", "help_a_root"],
      ]),
      helpSection("help_manual", [
        ["mu_scan_all", "help_a_manual_scan_all"], ["mu_scan", "help_a_manual_scan"],
        ["mu_confirm", "help_a_manual_confirm"], ["mu_reject", "help_a_manual_reject"],
        ["mu_ignore", "help_a_manual_claim"],
      ]),
      helpSection("help_platforms", [
        ["pause_all", "help_a_pause_all"], ["resume_all", "help_a_resume_all"], ["resume", "help_a_resume"],
      ]),
      helpSection("help_tail", [
        ["enable", "help_a_tail_on"], ["disable", "help_a_tail_off"],
      ]),
      helpSection("help_actions", [
        ["distribute", "help_a_distribute"], ["refresh_data", "help_a_refresh"], ["save", "help_a_save"],
      ]),
      helpSection("help_common", [
        ["refresh", "help_a_refresh"],
        ["published", "help_st_published"], ["scheduled", "help_st_scheduled"],
        ["failed", "help_st_failed"], ["paused", "help_st_paused"],
      ]),
    ].join("");
  }

  function render() {
    $("title").textContent = titles()[state.view] || state.view;
    syncTabs();
    const d = state.data;
    if (state.view === "status") renderStatus(d);
    else if (state.view === "folders") renderFolders(d);
    else if (state.view === "calendar") renderCalendar(d);
    else if (state.view === "queue") renderQueue(d);
    else if (state.view === "platforms") renderPlatforms(d);
    else if (state.view === "failed") {
      content().innerHTML = `<div class="view-enter">${failedHtml(d && d.failed)}</div>`;
    }
    else if (state.view === "help") {
      content().innerHTML = `<div class="view-enter">${helpHtml()}</div>`;
    }
    else if (state.view === "settings" || state.view === "schedule") renderSettings(d);
    else if (state.view === "tail") renderTail(d);
    else if (state.view === "actions") renderActions(d);
    else if (state.view === "metrics") renderMetrics(d);
    else if (state.view === "trash") renderTrash(d);
    else if (state.view === "manual") renderManual(d);
    const root = content();
    root.classList.remove("view-enter");
    void root.offsetWidth;
    root.classList.add("view-enter");
    root.querySelectorAll(".row").forEach((el) => el.classList.add("stagger"));
  }

  function setLang(l) {
    state.lang = l;
    localStorage.setItem("lang", l);
    document.documentElement.lang = l;
    updateNavLabels();
    syncTabs();
    setRefreshLabel();
    $("gate-msg").textContent = t("gate_msg");
    $("lang").querySelectorAll("button").forEach((b) =>
      b.classList.toggle("active", b.dataset.lang === l));
    load();
  }

  function updateNavLabels() {
    document.querySelectorAll("#nav button[data-view], #tabbar button[data-view]")
      .forEach((b) => {
        const span = b.querySelector(".label");
        if (span) span.textContent = t("nav_" + b.dataset.view);
      });
    const more = $("tab-more");
    if (more) {
      const lbl = more.querySelector(".label");
      if (lbl) lbl.textContent = t("nav_more");
    }
  }

  const TAB_PRIMARY = ["status", "folders", "queue", "calendar"];

  function syncTabs() {
    const tb = $("tabbar");
    if (!tb) return;
    const primary = TAB_PRIMARY.indexOf(state.view) >= 0;
    tb.querySelectorAll("button[data-view]").forEach((b) =>
      b.classList.toggle("active", b.dataset.view === state.view));
    const more = $("tab-more");
    if (more) more.classList.toggle("active", !primary);
  }

  async function confirmDialog(msg) {
    // F2: вне клиента Telegram — или на SDK < 6.1 — showConfirm идёт через showPopup и падает;
    // проверяем версию и в любом сбое уходим в window.confirm.
    try {
      const w = window.Telegram && window.Telegram.WebApp;
      if (w && typeof w.showConfirm === "function" && tgOk("6.1")) {
        const res = await new Promise((resolve) => w.showConfirm(msg, resolve));
        if (typeof res === "boolean") return res;
      }
    } catch (_) { /* fall through to window.confirm */ }
    if (typeof window.confirm === "function") return window.confirm(msg);
    return true;
  }

  // Интерактивное окно удаления: сначала объём (только серия / +шорты), затем платформы.
  // Направление: с YouTube Telegram уходит автоматически; с Telegram — спрашиваем про YouTube.
  function openDeleteDialog(opts) {
    const etype = opts.etype;
    const eid = Number(opts.eid);
    const trigger = opts.platform || "";
    const title = opts.title || `${etype} #${eid}`;
    const old = document.getElementById("delDialog");
    if (old) old.remove();
    let all = [];
    let shortsN = 0;
    let scopeAll = false;
    let alsoYt = false;
    let detach = false;
    let loaded = false;

    const ov = document.createElement("div");
    ov.className = "sheet-overlay";
    ov.id = "delDialog";
    document.body.appendChild(ov);
    const _useBack = showNativeBack(() => close());
    ov.dataset.nativeBack = _useBack ? "1" : "";

    function onKey(e) { if (e.key === "Escape") close(); }
    document.addEventListener("keydown", onKey);
    function close() { document.removeEventListener("keydown", onKey); ov.remove(); hideNativeBack(); }
    function inScope(x) {
      if (scopeAll) return true;
      return x.entity_type === etype && Number(x.entity_id) === eid;
    }
    function decorated(x) {
      if (trigger === "telegram") return x.platform === "telegram" || alsoYt;
      return true;  // youtube: Telegram всегда; "": все платформы
    }
    function chosen() { return all.filter((x) => inScope(x) && decorated(x)); }

    function body() {
      if (!loaded) {
        return `<div class="sheet"><div class="sheet-grab"></div>
          <div class="sheet-title">${esc(t("del_title").replace("%s", title))}</div>
          <div class="empty">${t("loading")}</div></div>`;
      }
      const ch = chosen();
      const plats = Array.from(new Set(ch.map((x) => x.platform)));
      const cnt = ch.length;
      const hasPub = ch.some((x) => x.status === "published");
      const scopeBlock = shortsN ? `
        <div class="field"><span class="field__label">${t("del_scope")}</span>
          <div class="seg" role="group">
            <button class="${!scopeAll ? "on" : ""}" data-dd="scope|series" aria-pressed="${!scopeAll}">${t("del_scope_series")}</button>
            <button class="${scopeAll ? "on" : ""}" data-dd="scope|all" aria-pressed="${scopeAll}">${t("del_scope_all").replace("%s", shortsN)}</button>
          </div></div>` : "";
      const platBlock = trigger === "telegram"
        ? `<label class="field"><span class="field__label">${t("del_tg_ask")}</span>
             <input type="checkbox" data-dd="yt" ${alsoYt ? "checked" : ""}/></label>`
        : `<div class="hint">${t("del_yt_note")}</div>`;
      const platsHtml = plats.map((p) => `<span class="badge info"><span class="q-plat">${pIcon(p)}</span>${esc(p)}</span>`).join(" ");
      return `<div class="sheet" role="dialog" aria-modal="true" aria-label="${esc(t("del_confirm"))}">
        <div class="sheet-grab"></div>
        <div class="sheet-title">${esc(t("del_title").replace("%s", title))}</div>
        ${scopeBlock}${platBlock}
        <div class="field"><span class="field__label">${t("del_will_delete")}</span>
          <div class="row row-center-8">${platsHtml || `<span class="meta">${t("none")}</span>`}
            <span class="meta">${postsLabel(cnt)}</span></div></div>
        ${hasPub && !detach ? `<div class="hint danger-text">${t("del_blocked")}</div>` : ""}
        ${hasPub ? `<label class="field"><span class="field__label">${t("del_detach")}</span>
             <input type="checkbox" data-dd="detach" ${detach ? "checked" : ""}/></label>
           <div class="hint danger-text">${t("del_detach_note")}</div>` : ""}
        <div class="btn-grid">
          <button class="btn secondary" data-dd="cancel">${t("cancel")}</button>
          <button class="btn danger" data-dd="ok" ${cnt && (!hasPub || detach) ? "" : "disabled"}>${
            trigger === "telegram" ? (alsoYt ? t("del_all_btn") : t("del_tg_btn")) : t("del_confirm")}</button>
        </div>
      </div>`;
    }
    let focused = false;
    function paint() {
      ov.innerHTML = body();
      if (loaded && !focused) {
        focused = true;
        const c = ov.querySelector('[data-dd="cancel"]');
        if (c && c.focus) c.focus();
      }
    }

    async function submit() {
      const ch = chosen();
      const pubs = ch.filter((x) => x.status === "published");
      if (!ch.length || (pubs.length && !detach)) return;
      busy(t("working"));
      try {
        // N1: сначала снимаем опубликованное с платформы, затем удаляем набор
        for (const p of pubs) {
          await api("/queue/detach", { method: "POST", body: JSON.stringify({
            entity_type: p.entity_type, entity_id: p.entity_id, platform: p.platform }) });
        }
        const r = await api("/queue/remove", { method: "POST", body: JSON.stringify({
          entity_type: etype, entity_id: eid, platform: trigger,
          with_shorts: scopeAll, also_youtube: alsoYt }) });
        close();  // N1-c: закрываем только при успехе
        if (r && r.blocked && r.blocked.length) toast(t("cant_delete_published"));
        else toast(`${t("queue_removed")}: ${r.removed || 0}`);
      } catch (e) {
        toastErr(e);
        return;   // окно остаётся открытым — можно снять галочку/повторить
      } finally {
        unbusy();
      }
      state.queueEdit = null;
      return load();
    }

    ov.addEventListener("click", (e) => {
      const b = e.target.closest("[data-dd]");
      if (!b) { if (e.target === ov) close(); return; }
      const a = b.dataset.dd;
      if (a === "cancel") return close();
      if (a === "scope|series") { scopeAll = false; return paint(); }
      if (a === "scope|all") { scopeAll = true; return paint(); }
      if (a === "ok") return submit();
      // yt-чекбокс обрабатываем в change, чтобы не было двойного переключения
    });
    ov.addEventListener("change", (e) => {
      const b = e.target.closest("[data-dd]");
      if (!b) return;
      if (b.dataset.dd === "yt") { alsoYt = !!e.target.checked; paint(); }
      else if (b.dataset.dd === "detach") { detach = !!e.target.checked; paint(); }
    });

    paint();
    api("/queue/remove", { method: "POST", body: JSON.stringify({
      entity_type: etype, entity_id: eid, platform: trigger,
      with_shorts: true, also_youtube: true, plan_only: true }) })
      .then((plan) => {
        all = plan.targets || [];
        shortsN = all.filter((x) => x.entity_type === "short").length;
        loaded = true;
        paint();
      })
      .catch((e) => { close(); toastErr(e); });
  }

  function renderTrash(d) {
    const items = (d && d.items) || [];
    const sel = state.trashSelected || {};
    const select = !!state.trashSelect;
    const keys = Object.keys(sel).filter((k) => sel[k]);
    const fmt = (iso) => {
      if (!iso) return "";
      const ts = Date.parse(iso);
      if (isNaN(ts)) return "";
      try {
        return new Intl.DateTimeFormat(state.lang === "ru" ? "ru-RU" : "en-GB",
          { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })
          .format(new Date(ts));
      } catch (_) { return ""; }
    };
    const groups = [];
    for (const it of items) {
      const gk = `${it.entity_type}|${it.entity_id}`;
      let g = groups.find((x) => x.key === gk);
      if (!g) { g = { key: gk, type: it.entity_type, id: it.entity_id, title: it.title, items: [] }; groups.push(g); }
      g.items.push(it);
    }
    const toolbar = `<div class="q-toolbar">
        <button class="btn secondary" data-act="trash-restore-all" ${items.length ? "" : "disabled"}>${t("trash_restore_all")}</button>
        <button class="btn ${select ? "primary" : "secondary"} q-sel-btn" data-act="trash-select" ${items.length ? "" : "disabled"}>${select ? t("queue_done") : t("queue_select")}</button>
      </div>`;
    const bulk = !select ? "" : `<div class="bulk-bar">
        <span class="meta"><b>${keys.length}</b> ${t("trash_selected")}</span>
        <button class="btn secondary" data-act="trash-check-all">${t("queue_all")}</button>
        <button class="btn primary" data-act="trash-restore" ${keys.length ? "" : "disabled"}>${t("trash_restore")}</button>
        <button class="btn danger" data-act="trash-purge" ${keys.length ? "" : "disabled"}>${t("trash_purge")}</button>
      </div>`;
    const kindOf = (t2) => entityLabel(t2);
    const body = groups.map((g) => {
      const rows = g.items.map((it) => {
        const k = it.key;
        const on = !!sel[k];
        const check = !select ? "" : `<button class="q-check${on ? " on" : ""}" data-act="trash-check"
            data-key="${esc(k)}" aria-pressed="${on}" aria-label="${t("queue_select")}">${on ? icon("check", 13) : ""}</button>`;
        const casc = it.cascade_from === "youtube"
          ? ` · <span class="badge">${t("trash_cascade_yt")}</span>` : "";
        const detached = it.deleted_reason === "detached"
          ? ` · <span class="badge info">${t("trash_detached")}</span>` : "";
        const deleted = fmt(it.deleted_at);
        const metaLine = esc(it.platform) + (deleted ? ` · ${esc(deleted)}` : "") + casc + detached;
        return `<div class="item${on ? " picked" : ""}${select ? " with-check" : ""}">
          ${check}
          <span class="q-plat big">${pIcon(it.platform)}</span>
          <div class="item__main">
            <div class="item__title">${esc(g.title || (kindOf(g.type) + " #" + g.id))}</div>
            <div class="item__meta">${metaLine}</div>
          </div>
        </div>`;
      }).join("");
      return `<div class="panel"><div class="panel-head"><h3>${kindOf(g.type)} #${g.id}</h3>
        <span class="badge">${g.items.length}</span></div>${rows}</div>`;
    }).join("");
    const more = (d && d.total > items.length)
      ? `<div class="hint">${t("trash_shown").replace("%s", items.length).replace("%s", d.total)}</div>` : "";
    content().innerHTML = `<div class="view-enter">${toolbar}${bulk}
      <div class="hint">${t("trash_hint")}</div>
      ${more}
      ${body || `<div class="empty">${t("trash_empty")}</div>`}</div>`;
  }

  function openMoreSheet() {
    if ($("more-sheet")) { closeMoreSheet(); return; }  // повторный тап = закрыть
    const items = [
      ["platforms", "users"], ["tail", "folder"], ["manual", "edit"],
      ["actions", "swap"], ["metrics", "chart"], ["failed", "warn"],
      ["help", "help"], ["settings", "gear"], ["trash", "trash"],
    ];
    const rows = items.map(([v, ic]) =>
      `<button class="sheet-item" data-view="${v}">${icon(ic, 22)}<span>${esc(t("title_" + v))}</span><span class="chev">›</span></button>`
    ).join("");
    const ov = document.createElement("div");
    ov.className = "sheet-overlay";
    ov.id = "more-sheet";
    ov.innerHTML = `<div class="sheet" role="dialog" aria-modal="true" aria-label="${esc(t("more_title"))}">
      <div class="sheet-grab"></div>
      <div class="sheet-title">${esc(t("more_title"))}</div>
      ${rows}
      <div class="sheet-lang">
        <button class="lang-btn${state.lang === "ru" ? " active" : ""}" data-lang="ru">RU</button>
        <button class="lang-btn${state.lang === "en" ? " active" : ""}" data-lang="en">EN</button>
      </div>
    </div>`;
    const _useBack = showNativeBack(() => closeMoreSheet());
    ov.dataset.nativeBack = _useBack ? "1" : "";
    ov.addEventListener("click", (e) => {
      if (e.target === ov) { closeMoreSheet(); return; }
      const langBtn = e.target.closest("button[data-lang]");
      if (langBtn) { setLang(langBtn.dataset.lang); closeMoreSheet(); return; }
      const nav = e.target.closest("button[data-view]");
      if (nav) {
        closeMoreSheet();
        gotoView(nav.dataset.view);
      }
    });
    document.body.appendChild(ov);
  }

  function closeMoreSheet() {
    const el = $("more-sheet");
    if (el) el.remove();
    hideNativeBack();
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeMoreSheet();
  });

  function gotoView(v) {
    if (!v || !titles()[v]) return;
    state.view = v;
    document.querySelectorAll("#nav button[data-view]").forEach((b) =>
      b.classList.toggle("active", b.dataset.view === v));
    syncTabs();
    load();
  }

  async function onAction(act, el) {
    try {
      if (act === "refresh") return load();
      if (act === "pause-one") {
        await api("/pause_platform", { method: "POST", body: JSON.stringify({ platform: el.dataset.p }) });
        toast(`${t("pa_pause")} · ${el.dataset.p}`);
        return load();
      }
      if (act === "sync") {
        const r = await api("/sync", { method: "POST", body: "{}" });
        toast(`${t("act_sync")}: ${r.updates ?? 0}`);
        return load();
      }
      if (act === "reconcile") {
        const r = await api("/reconcile", { method: "POST", body: "{}" });
        const res = r.result || {};
        toast(`${t("act_reconcile")}: missing ${res.missing ?? 0}, orphans ${res.orphans ?? 0}`);
        return load();
      }
      if (act === "backup") {
        const r = await api("/backup", { method: "POST", body: "{}" });
        toast(`${t("act_backup")}: ${r.path ? "ok" : "skip"}`);
        return load();
      }
      if (act === "schedule") {
        const r = await api("/schedule", { method: "POST", body: "{}" });
        toast(`${t("act_schedule")}: ${r.long ?? 0}/${r.standalone ?? 0}`);
        return load();
      }
      if (act === "manual-scan-all") {
        await api("/manual/scan", { method: "POST", body: "{}" });
        toast(t("t_scan"));
        return load();
      }
      if (act === "manual-scan") {
        await api("/manual/scan", { method: "POST", body: JSON.stringify({ platform: el.dataset.p }) });
        toast(`${t("t_scan")} · ${el.dataset.p}`);
        return load();
      }
      if (act === "manual-confirm") {
        await api(`/manual/uploads/${el.dataset.id}/confirm`, {
          method: "POST",
          body: JSON.stringify({ entity_type: el.dataset.et, entity_id: Number(el.dataset.eid) }),
        });
        toast(t("mu_confirmed"));
        return load();
      }
      if (act === "manual-reject") {
        await api(`/manual/uploads/${el.dataset.id}/reject`, { method: "POST", body: "{}" });
        return load();
      }
      if (act === "manual-ignore") {
        await api(`/manual/uploads/${el.dataset.id}/ignore`, { method: "POST", body: "{}" });
        return load();
      }
      if (act === "manual-claim-mark") {
        await api(`/manual/uploads/${el.dataset.id}/claim-mark`, {
          method: "POST", body: JSON.stringify({ claimed: true }),
        });
        return load();
      }
      if (act === "manual-claim") {
        await api(`/manual/uploads/${el.dataset.id}/claim-action`, {
          method: "POST", body: JSON.stringify({ action: el.dataset.c }),
        });
        return load();
      }
      if (act === "lang") return setLang(el.dataset.lang);
      if (act === "folder-open") return browseTo(el.dataset.p);
      if (act === "folder-search") return runFolderSearch();
      if (act === "folder-up") return browseTo(el.dataset.p || "/");
      if (act === "folder-add") {
        const p = el.dataset.p;
        if (!p) return;
        const kind = el.dataset.kind || "auto";
        const items = (state.data?.items || (state.data?.roots || []).map((x) => ({ path: x, kind: "auto" }))).slice();
        if (!items.some((it) => it.path === p)) items.push({ path: p, kind });
        state.data = await api("/roots", { method: "POST", body: JSON.stringify({ items }) });
        toast(t("t_folder_added"));
        return load();
      }
      if (act === "folder-kind") {
        const p = el.dataset.p;
        const items = (state.data?.items || []).map((it) => ({ ...it }));
        const it = items.find((x) => x.path === p);
        if (!it) return;
        const order = ["auto", "series", "shorts"];
        it.kind = order[(order.indexOf(it.kind) + 1) % order.length];
        state.data = await api("/roots", { method: "POST", body: JSON.stringify({ items }) });
        toast(t("t_kind_changed"));
        return load();
      }
      if (act === "folder-remove") {
        const items = (state.data?.items || []).filter((it) => it.path !== el.dataset.p);
        state.data = await api("/roots", { method: "POST", body: JSON.stringify({ items }) });
        toast(t("t_folder_removed"));
        return load();
      }
      if (act === "cal-view") {
        state.calView = el.dataset.v || "day";
        try { localStorage.setItem("calView", state.calView); } catch (_) {}
        renderCalendar(state.data || {});
        return;
      }
      if (act === "cal-day") {
        state.calDate = el.dataset.d;
        state.calView = "day";
        try { localStorage.setItem("calView", "day"); } catch (_) {}
        renderCalendar(state.data || {});
        return;
      }
      if (act === "cal-shift") {
        const step = Number(el.dataset.n) || 1;
        const view = state.calView || "day";
        const cur = state.calDate || isoOf(new Date());
        if (view === "month") {
          const [y, m] = cur.split("-").map(Number);
          const nm = m + step;
          const dt = new Date(y + Math.floor((nm - 1) / 12), ((nm - 1) % 12 + 12) % 12, 1, 12);
          state.calDate = `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-01`;
        } else {
          state.calDate = addDaysIso(cur, view === "week" ? step * 7 : step);
        }
        renderCalendar(state.data || {});
        return;
      }
      if (act === "cal-today") {
        state.calDate = isoOf(new Date());
        renderCalendar(state.data || {});
        return;
      }
      if (act === "sched-count") {
        state.schedCount = state.schedCount || {};
        state.schedCount[el.dataset.p] = Number(el.dataset.n) || 1;
        renderSettings(state.data || {});
        return;
      }
      if (act === "sched-save") {
        const key = el.dataset.p;
        const root = el.closest(".panel");
        const daysOf = (kind) => Array.from(root.querySelectorAll(`[data-day="${key}|${kind}"]:checked`)).map((c) => c.value);
        const timeOf = (kind) => {
          const i = root.querySelector(`[data-time="${key}|${kind}"]`);
          return i ? i.value.trim() : "";
        };
        const block = {};
        const longDays = daysOf("long"), longTime = timeOf("long");
        if (longDays.length || longTime) block.long = {};
        if (longDays.length) block.long.days = longDays;
        if (longTime) block.long.time = longTime;
        const thTime = timeOf("thematic");
        if (thTime) block.thematic = { time: thTime };
        const saDays = daysOf("standalone");
        const saInput = root.querySelector(`[data-times="${key}|standalone"]`);
        const saFromInputs = Array.from(root.querySelectorAll(`[data-time-n^="${key}|standalone|"]`))
          .map((i) => (i.value || "").trim()).filter(Boolean);
        const saTimes = saFromInputs.length ? saFromInputs
          : (saInput ? saInput.value.split(",").map((x) => x.trim()).filter(Boolean) : []);
        if (saDays.length || saTimes.length) block.standalone = {};
        if (saDays.length) block.standalone.days = saDays;
        if (saTimes.length) block.standalone.times = saTimes;
        const limitInput = root.querySelector(`[data-limit="${key}"]`);
        if (limitInput && limitInput.value !== "") block.daily_limit = Number(limitInput.value);
        const settings = Object.assign({}, state.data?.settings || {});
        settings[key] = block;
        await api("/schedule_settings", { method: "POST", body: JSON.stringify({ settings }) });
        toast(t("sched_saved"));
        return load();
      }
      if (act === "sched-reset") {
        const key = el.dataset.p;
        const settings = Object.assign({}, state.data?.settings || {});
        delete settings[key];
        await api("/schedule_settings", { method: "POST", body: JSON.stringify({ settings }) });
        toast(t("sched_saved"));
        return load();
      }
      if (act === "group-add") {
        const name = (document.getElementById("group-name")?.value || "").trim();
        const plats = Array.from(document.querySelectorAll("[data-gplat]:checked")).map((c) => c.value);
        if (!name || !plats.length) return toast(t("error_prefix"));
        const groups = (state.data?.groups || []).concat([{ name, platforms: plats }]);
        await api("/groups", { method: "POST", body: JSON.stringify({ groups }) });
        toast(t("t_group_added"));
        return load();
      }
      if (act === "group-remove") {
        const groups = (state.data?.groups || []).filter((g) => g.name !== el.dataset.p);
        await api("/groups", { method: "POST", body: JSON.stringify({ groups }) });
        toast(t("t_group_removed"));
        return load();
      }
      if (act === "folder-scan") {
        busy(t("working"));
        const r = await api("/scan", { method: "POST", body: "{}" }).finally(() => unbusy());
        state.scan = r;
        const s = r.stats || {};
        toast(`${t("t_scan")}: long ${s.long || 0}, shorts ${s.shorts || 0}, standalone ${s.standalone || 0}`);
        return load();
      }
      if (act === "queue-cleanup-orphans") {
        const ask = t("confirm_cleanup_orphans");
        if (!(await confirmDialog(ask))) return;
        busy(t("working"));
        try {
          const r = await api("/queue/cleanup_orphans", { method: "POST", body: "{}" });
          unbusy();
          toast(`${t("cleaned")}: ${r.deleted || 0}`);
        } catch (e) { unbusy(); toastErr(e); }
        return load();
      }
      if (act === "queue-restore-all") {
        busy(t("working"));
        try {
          const r = await api("/queue/restore", { method: "POST", body: JSON.stringify({ all: true }) });
          unbusy();
          toast(`${t("restored")}: ${r.restored || 0}`);
        } catch (e) { unbusy(); toastErr(e); }
        return load();
      }
      if (act === "queue-remove-everywhere") {
        return openDeleteDialog({
          etype: el.dataset.et, eid: el.dataset.eid, platform: "",
          tg: el.dataset.tg === "1", title: el.dataset.title || "",
        });
      }
      if (act === "queue-remove-film-only") {
        return openDeleteDialog({
          etype: "long_video", eid: el.dataset.eid, platform: "",
          tg: el.dataset.tg === "1", title: el.dataset.title || "",
        });
      }
      if (act === "queue-edit") {
        state.queueEdit = { key: el.dataset.key };
        return render();
      }
      if (act === "queue-edit-cancel") {
        state.queueEdit = null;
        return render();
      }
      if (act === "queue-filter") {
        state.queueFilter = el.dataset.p || "all";
        try { localStorage.setItem("queueFilter", state.queueFilter); } catch (_) {}
        return render();
      }
      if (act === "queue-select") {
        state.queueSelect = !state.queueSelect;
        state.queueSelected = {};
        state.queueBulkTags = null;
        return render();
      }
      if (act === "queue-check") {
        const k = el.dataset.key || "";
        state.queueSelected = state.queueSelected || {};
        state.queueSelected[k] = !state.queueSelected[k];
        return render();
      }
      if (act === "queue-check-all") {
        const all = state.data?.items || [];
        const filter = state.queueFilter || "all";
        const visible = filter === "all" ? all : all.filter((it) => it.platform === filter);
        const cur = state.queueSelected || {};
        const keys = visible.map((it) => `${it.entity_type}|${it.entity_id}|${it.platform}`);
        const allOn = keys.length > 0 && keys.every((k) => cur[k]);
        state.queueSelected = {};
        if (!allOn) keys.forEach((k) => { state.queueSelected[k] = true; });
        return render();
      }
      if (act === "queue-bulk-tags") {
        state.queueBulkTags = "";
        return render();
      }
      if (act === "queue-bulk-tags-cancel") {
        state.queueBulkTags = null;
        return render();
      }
      if (act === "queue-bulk-tags-apply") {
        const val = (document.getElementById("qb-tags") || {}).value || "";
        return bulkEditTags(val.trim());
      }
      if (act === "queue-bulk-delete") {
        return bulkDelete();
      }
      if (act === "cover-pick") {
        const sel = document.getElementById("qe-cover");
        if (!sel) return;
        openCoverPicker({
          select: sel,
          startPath: el.dataset.video || "",
          entityType: el.dataset.et || "",
          entityId: el.dataset.eid || "",
        });
        return;
      }
      if (act === "queue-edit-save") {
        const val = (id) => {
          const n = document.getElementById(id);
          return n ? n.value : "";
        };
        busy(t("working"));
        let r;
        try {
          r = await api("/queue/edit", {
            method: "POST",
            body: JSON.stringify({
              entity_type: el.dataset.et,
              entity_id: Number(el.dataset.eid),
              platform: el.dataset.p,
              title: val("qe-title"),
              description: val("qe-desc"),
              hashtags: val("qe-tags"),
              date: val("qe-date"),
              time: val("qe-time"),
              cover: val("qe-cover"),
            }),
          });
        } catch (e) {
          toastErr(e);
          return;
        } finally {
          unbusy();  // P1-10: при ошибке оверлей не должен оставаться навсегда
        }
        state.queueEdit = null;
        toast(`${t("t_saved")}: ${r.updated || 0}/${r.recreated || 0}`);
        return load();
      }
      if (act === "queue-remove") {
        return openDeleteDialog({
          etype: el.dataset.et, eid: el.dataset.eid, platform: el.dataset.p || "",
          tg: el.dataset.tg === "1", title: el.dataset.title || "",
        });
      }
      if (act === "trash-select") {
        state.trashSelect = !state.trashSelect;
        state.trashSelected = {};
        return render();
      }
      if (act === "trash-check") {
        const k = el.dataset.key || "";
        state.trashSelected = state.trashSelected || {};
        state.trashSelected[k] = !state.trashSelected[k];
        return render();
      }
      if (act === "trash-check-all") {
        const items = state.data?.items || [];
        const cur = state.trashSelected || {};
        const ks = items.map((it) => it.key);
        const allOn = ks.length > 0 && ks.every((k) => cur[k]);
        state.trashSelected = {};
        if (!allOn) ks.forEach((k) => { state.trashSelected[k] = true; });
        return render();
      }
      if (act === "trash-restore" || act === "trash-restore-all") {
        const ids = act === "trash-restore-all" ? [] : Object.keys(state.trashSelected || {}).filter((k) => state.trashSelected[k]);
        if (act === "trash-restore" && !ids.length) return;
        busy(t("working"));
        try {
          const body = act === "trash-restore-all" ? { all: true } : { ids };
          const r = await api("/trash/restore", { method: "POST", body: JSON.stringify(body) });
          toast(`${t("restored")}: ${r.restored || 0}`);
        } catch (e) { toastErr(e); }
        finally { unbusy(); }
        state.trashSelected = {};
        return load();
      }
      if (act === "trash-purge") {
        const ids = Object.keys(state.trashSelected || {}).filter((k) => state.trashSelected[k]);
        if (!ids.length) return;
        if (!(await confirmDialog(t("confirm_purge") + "\n\n" + t("trash_hint")))) return;
        busy(t("working"));
        try {
          const r = await api("/trash/purge", { method: "POST", body: JSON.stringify({ ids }) });
          toast(`${t("trash_purge")}: ${r.purged || 0}`);
        } catch (e) { toastErr(e); }
        finally { unbusy(); }
        state.trashSelected = {};
        return load();
      }
      if (act === "toggle-mode") {
        const cur = (state.data?.sched?.mode === "auto") ? "auto" : "manual";
        await api("/scheduling_mode", { method: "POST", body: JSON.stringify({ mode: cur === "auto" ? "manual" : "auto" }) });
        return load();
      }
      if (act === "scan-restore") {
        busyJob(t("job_restore"));
        try {
          await api("/queue/restore", { method: "POST", body: JSON.stringify({ all: true }) });
          await api("/schedule", { method: "POST", body: JSON.stringify({ async: true }) });
        } catch (e) {
          stopJob();
          toastErr(e);
        }
        state.scan = null;
        return;
      }
      if (act === "job-cancel") {
        await api("/job/cancel", { method: "POST", body: "{}" });
        toast(t("job_cancelling"));
        return;
      }
      if (act === "settings-tab") {
        state.settingsTab = el.dataset.p || "sched";
        return render();
      }
      if (act === "scan-start" || act === "scan-start-dates") {
        const body = { async: true };
        if (act === "scan-start-dates") {
          const films = document.getElementById("scan-date-films");
          const shorts = document.getElementById("scan-date-shorts");
          if (films && films.value) body.start_date = films.value;
          if (shorts && shorts.value) body.shorts_start_date = shorts.value;
          if (!body.start_date && !body.shorts_start_date) return toast(t("t_error_date"));
        }
        busyJob(t("job_scheduling"));
        try {
          await api("/schedule", { method: "POST", body: JSON.stringify(body) });
        } catch (e) {
          stopJob();
          toastErr(e);
        }
        state.scan = null;
        return;
      }
      if (act === "backlog-answer") {
        // P1-11: кнопки «Распределить/Ждать/Не публиковать» не имели обработчика.
        const fromDate = ($("backlog-date") || {}).value || "";
        busy(t("working"));
        try {
          await api("/backlog/answer", {
            method: "POST",
            body: JSON.stringify({
              platform: el.dataset.p,
              answer: el.dataset.a,
              from_date: fromDate,
            }),
          });
        } catch (e) {
          toastErr(e);
          return;
        } finally {
          unbusy();
        }
        return load();
      }
      if (act === "pause-all") {
        await api("/pause", { method: "POST", body: "{}" });
        toast(t("t_paused"));
      } else if (act === "resume-all") {
        await api("/resume", { method: "POST", body: "{}" });
        toast(t("t_resumed"));
      } else if (act === "resume-one") {
        await api("/resume_platform", { method: "POST", body: JSON.stringify({ platform: el.dataset.p }) });
        toast(`${t("t_resume")} ${el.dataset.p}`);
      } else if (act === "tail-on") {
        await api("/series_end", { method: "POST", body: JSON.stringify({ platform: el.dataset.p, enable: true }) });
        toast(`${t("t_tail_on")} · ${el.dataset.p}`);
      } else if (act === "tail-off") {
        await api("/series_end", { method: "POST", body: JSON.stringify({ platform: el.dataset.p, enable: false }) });
        toast(`${t("t_tail_off")} · ${el.dataset.p}`);
      } else if (act === "test-schedule" || act === "test-dry") {
        const platform = ($("tp-p") || {}).value;
        const minutes = Number(($("tp-delay") || {}).value || 1);
        const sel = (($("tp-e") || {}).value || "").split(":");
        if (!platform || !sel[0] || !sel[1]) { toast(t("test_hint")); return; }
        const r = await api("/test/schedule", {
          method: "POST",
          body: JSON.stringify({
            platforms: [platform], platform, delay_minutes: minutes,
            entity_type: sel[0], entity_id: Number(sel[1]), dry_run: act === "test-dry",
          }),
        });
        toast(`${r.dry_run ? t("t_test_dry") : t("t_test_sched")} ${r.scheduled_for || ""}`);
      } else if (act === "test-cancel") {
        await api("/test/cancel", { method: "POST", body: JSON.stringify({ postiz_post_id: el.dataset.pid }) });
        toast(t("t_test_cancelled"));
      } else if (act === "distribute") {
        const r = await api("/distribute", { method: "POST", body: "{}" });
        toast(`${t("t_distributed")}: ${r.count ?? 0}`);
      } else if (act === "force-link") {
        const entity_id = Number($("fl-id").value);
        const platform = $("fl-p").value;
        const url = $("fl-url").value.trim();
        await api("/force_link", { method: "POST", body: JSON.stringify({ entity_id, platform, url }) });
        toast(t("t_saved"));
      }
      await load();
    } catch (e) {
      toastErr(e);
    }
  }

  function setRefreshLabel() {
    const el = $("btn-refresh");
    if (!el) return;
    el.setAttribute("aria-label", t("refresh"));
    el.setAttribute("title", t("refresh"));
  }

  function spinRefresh() {
    const el = $("btn-refresh");
    if (!el) return;
    el.classList.remove("spin-once");
    void el.offsetWidth;
    el.classList.add("spin-once");
    setTimeout(() => el.classList.remove("spin-once"), 700);
  }

  function bind() {
    $("nav").addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-view]");
      if (!btn) return;
      gotoView(btn.dataset.view);
    });
    const tb = $("tabbar");
    if (tb) {
      tb.addEventListener("click", (e) => {
        const btn = e.target.closest("button");
        if (!btn) return;
        haptic("select");
        if (btn.dataset.more) { openMoreSheet(); return; }
        if (btn.dataset.view) gotoView(btn.dataset.view);
      });
    }
    $("btn-refresh").addEventListener("click", () => { spinRefresh(); load(); });
    $("lang").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-lang]");
      if (b) setLang(b.dataset.lang);
    });
    content().addEventListener("input", (e) => {
      if (e.target && e.target.id === "folder-q") {
        state.folderSearch = state.folderSearch || { q: "", items: null };
        state.folderSearch.q = e.target.value;
      }
    });
    content().addEventListener("keydown", (e) => {
      if (e.target && e.target.id === "folder-q" && e.key === "Enter") runFolderSearch();
    });
    content().addEventListener("click", (e) => {
      const go = e.target.closest("[data-goto]");
      if (go) { haptic("select"); gotoView(go.dataset.goto); return; }
      const btn = e.target.closest("[data-act]");
      if (!btn) return;
      haptic(btn.classList.contains("danger") || btn.classList.contains("icon-btn") ? "medium" : "light");
      onAction(btn.dataset.act, btn);
    });
  }

  function boot() {
    if (tg) {
      try { if (typeof tg.ready === "function") tg.ready(); } catch (_) {}
      try { if (typeof tg.expand === "function") tg.expand(); } catch (_) {}
      if (tgOk("6.1")) {
        try { tg.setHeaderColor("secondary_bg_color"); } catch (_) {}
        try { tg.setBackgroundColor("bg_color"); } catch (_) {}
      }
    }

    document.documentElement.lang = state.lang;
    const langParam = new URLSearchParams(location.search).get("lang");
    if (langParam && I18N[langParam]) state.lang = langParam;

    // Полный экран + цвет зоны статус-бара iPhone: часы/батарея должны быть видны.
    // В fullscreen Telegram рисует СВОЮ кнопку закрытия в правом верхнем углу —
    // помечаем body классом tg-fs, чтобы зарезервировать этот угол в вёрстке.
    function applyFsClass() {
      applyTgInsets();
    }
    window.__fsRequested = false;
    try {
      if (tg) {
        if (tg.expand) tg.expand();
        if (tgOk("6.1") && tg.requestFullscreen) {
          try { tg.requestFullscreen(); window.__fsRequested = true; } catch (_) {}
        }
        if (tg.onEvent) {
          try { tg.onEvent("fullscreenChanged", applyFsClass); } catch (_) {}
          try { tg.onEvent("viewportChanged", () => { setTimeout(applyFsClass, 300); applyTgInsets(); }); } catch (_) {}
        }
        setTimeout(applyFsClass, 300);
        setTimeout(applyFsClass, 1200);
        // цвет зоны статус-бара = фактический токен темы из CSS, без «магических» hex
        let bg = "";
        try {
          bg = (getComputedStyle(document.documentElement).getPropertyValue("--bg") || "").trim();
        } catch (_) {}
        if (!bg) {
          const dark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
          bg = dark ? "#000000" : "#f2f2f7";
        }
        if (tgOk("6.1")) {
          try { tg.setHeaderColor(bg); } catch (_) {}
          try { tg.setBackgroundColor(bg); } catch (_) {}
        }
        if (tgOk("7.7") && tg.disableVerticalSwipes) {
          try { tg.disableVerticalSwipes(); } catch (_) {}
        }
      }
    } catch (_) {}
    // B2: тема/инсеты/цвет нижней панели + реакция на изменения
    applyTgTheme();
    applyTgInsets();
    try {
      if (tg && tg.onEvent) {
        tg.onEvent("themeChanged", () => { applyTgTheme(); applyTgInsets(); });
        tg.onEvent("safeAreaChanged", applyTgInsets);
        tg.onEvent("contentSafeAreaChanged", applyTgInsets);
      }
    } catch (_) {}
    try {
      if (tgOk("7.0") && tg.setBottomBarColor) {
        const card = getComputedStyle(document.documentElement).getPropertyValue("--card").trim();
        if (card) tg.setBottomBarColor(card);
      }
    } catch (_) {}

    function applyViewportHeight() {
      const h = (tg && (tg.viewportStableHeight || tg.viewportHeight)) || window.innerHeight;
      document.documentElement.style.setProperty("--wa-h", h + "px");
    }
    applyViewportHeight();
    try { if (tg && tg.onEvent) tg.onEvent("viewportChanged", applyViewportHeight); } catch (_) {}
    window.addEventListener("resize", applyViewportHeight);
    window.addEventListener("orientationchange", () => setTimeout(applyViewportHeight, 200));

    $("gate-msg").textContent = t("gate_msg");

    if (!state.initData) {
      const h = (location.hash || "").replace(/^#/, "");
      if (h) {
        const hd = new URLSearchParams(h).get("tgWebAppData");
        if (hd) state.initData = hd;
      }
    }

    const dev = new URLSearchParams(location.search).get("dev") === "1";
    if (!state.initData && !dev && !state.key) {
      try {
        fetch("/webapp/diag?u=" + encodeURIComponent(location.href) +
          "&tg=" + (tg ? 1 : 0) + "&k=" + (state.key ? 1 : 0), { cache: "no-store" });
      } catch (_) {}
      $("gate").hidden = false;
      $("app").hidden = true;
      return;
    }
    if (dev && !state.initData) state.initData = "dev";

    // B6: сначала локализуем навигацию/заголовки, потом показываем приложение (без FOUC)
    updateNavLabels();
    syncTabs();
    setRefreshLabel();
    $("title").textContent = titles()[state.view] || state.view;
    $("gate").hidden = true;
    $("app").hidden = false;
    if (state.user) {
      $("user-info").textContent =
        [state.user.first_name, state.user.username ? "@" + state.user.username : ""].filter(Boolean).join(" ");
    }
    api("/version").then((v) => { $("ver").textContent = "v" + (v.version || "?"); }).catch(() => {});

    $("lang").querySelectorAll("button").forEach((b) =>
      b.classList.toggle("active", b.dataset.lang === state.lang));

    const viewParam = new URLSearchParams(location.search).get("view");
    if (viewParam && titles()[viewParam]) {
      state.view = viewParam;
      $("nav").querySelectorAll("button").forEach((b) =>
        b.classList.toggle("active", b.dataset.view === viewParam));
    }
    bind();
    load();
  }

  boot();
})();
