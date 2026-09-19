(() => {
  const tg = window.Telegram?.WebApp;

  const I18N = {
    ru: {
      nav_status: "Статус", nav_folders: "Папки", nav_calendar: "Календарь", nav_queue: "Очередь",
      nav_platforms: "Платформы", nav_tail: "Остаток", nav_failed: "Ошибки", nav_metrics: "Метрики",
      nav_actions: "Действия", nav_help: "Справка",
      title_status: "Статус", title_folders: "Папки с видео", title_calendar: "Календарь",
      title_queue: "Очередь", title_platforms: "Платформы", title_tail: "Остаток шортсов серии",
      title_failed: "Ошибки", title_actions: "Действия", title_metrics: "Метрики", title_help: "Справка",
      loading: "Загрузка…", error_prefix: "Ошибка", refresh: "Обновить", no_data: "Нет данных",
      platforms: "Платформы", no_platforms: "Нет платформ", limit: "лимит",
      remove: "Убрать", open: "Открыть", up: "↑ Вверх", add_folder: "Добавить эту папку",
      scan: "Сканировать", no_subfolders: "Нет подпапок", folders_to_scan: "Папки для сканирования",
      folders_none: "Папки не выбраны", browse: "Обзор папок",
      net_root: "Сеть · /mnt/video", local_root: "Локально · /",
      backlog_unposted: "Не опубликовано шортсов", backlog_awaiting: "Ждём ответа до",
      backlog_distribute: "Распределить остаток", backlog_wait: "Ждать ещё",
      backlog_skip: "Не публиковать", backlog_from: "Распределять с даты (необязательно)", backlog_on: "распределение вкл", backlog_off: "распределение выкл",
      calendar_empty: "Календарь пуст", calendar_explain: "Показаны запланированные и опубликованные посты (из оркестратора и Postiz), сгруппированные по дням. Пометка справа — статус поста.", queue_empty: "Пусто",
      resume: "Возобновить", pause_all: "Пауза всем", resume_all: "Возобновить все", none: "Нет",
      tail_title: "Остаток шортсов серии", tail_explain: "Шортсы уже нарезаны для серии, но ещё не опубликованы. Когда новых серий больше нет, система распределяет остаток по слотам (в слот основной серии — обычные шортсы, в 20:30 — шортсы к другим сериям), и только после этого запускается следующая серия. Перед запуском она спросит подтверждение.", enable: "Включить", disable: "Выключить",
      tail_on: "хвост вкл", tail_off: "выкл", no_errors: "Ошибок нет",
      quick_actions: "Быстрые действия", act_sync: "Обновить статусы",
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
      st_updating: "обновляется", st_queue: "в очереди", st_ready: "готово",
      st_draft: "черновик", st_failed: "ошибка", st_error: "ошибка", st_paused: "пауза",
      st_skipped: "пропущено", st_on: "включено", st_off: "выключено",
      st_manual: "ручная", st_postiz: "из Postiz", st_suggested: "предложено",
      st_unmatched: "не найдено", st_confirmed: "подтверждено", st_rejected: "отклонено",
      st_ignored: "проигнорировано", st_claimed: "клейм", st_none: "нет",
      nav_manual: "Ручные", title_manual: "Ручные загрузки",
      mu_scan_all: "Сканировать всё", mu_scan: "Сканировать", mu_total: "Всего",
      mu_manual: "Ручных", mu_postiz: "От Postiz", mu_suggested: "Предложено",
      mu_confirmed: "Подтверждено", mu_none: "Ничего не найдено", mu_confirm: "Подтвердить",
      mu_reject: "Не моё", mu_ignore: "Игнорировать", mu_candidates: "Кандидаты",
      mu_confidence: "уверенность", mu_claim: "клейм", mu_claim_title: "Обнаружен клейм",
      mu_claim_delete: "Удалить видео", mu_claim_keep: "Оставить", mu_last_scan: "Последний скан",
      mu_from: "источник",
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
      help_st_off: "Выключено.",
    },
    en: {
      nav_status: "Status", nav_folders: "Folders", nav_calendar: "Calendar", nav_queue: "Queue",
      nav_platforms: "Platforms", nav_tail: "Backlog", nav_failed: "Errors", nav_metrics: "Metrics",
      nav_actions: "Actions", nav_help: "Help",
      title_status: "Status", title_folders: "Video folders", title_calendar: "Calendar",
      title_queue: "Queue", title_platforms: "Platforms", title_tail: "Unposted series shorts",
      title_failed: "Errors", title_actions: "Actions", title_metrics: "Metrics", title_help: "Help",
      loading: "Loading…", error_prefix: "Error", refresh: "Refresh", no_data: "No data",
      platforms: "Platforms", no_platforms: "No platforms", limit: "limit",
      remove: "Remove", open: "Open", up: "↑ Up", add_folder: "Add this folder",
      scan: "Scan", no_subfolders: "No subfolders", folders_to_scan: "Folders to scan",
      folders_none: "No folders selected", browse: "Browse",
      net_root: "Network · /mnt/video", local_root: "Local · /",
      backlog_unposted: "Unposted shorts", backlog_awaiting: "Awaiting answer until",
      backlog_distribute: "Distribute backlog", backlog_wait: "Wait more",
      backlog_skip: "Do not publish", backlog_from: "Distribute from date (optional)", backlog_on: "distribution on", backlog_off: "distribution off",
      calendar_empty: "Calendar is empty", calendar_explain: "Scheduled and published posts (from the orchestrator and Postiz), grouped by day. The badge shows the post status.", queue_empty: "Empty",
      resume: "Resume", pause_all: "Pause all", resume_all: "Resume all", none: "None",
      tail_title: "Unposted series shorts", tail_explain: "Shorts already cut for the series but not published yet. When no new episodes appear, the system distributes the backlog into slots (standard shorts in the main-series slot, other series' shorts at 20:30) and only then starts the next series. It asks for confirmation first.", enable: "Enable", disable: "Disable",
      tail_on: "tail ON", tail_off: "off", no_errors: "No errors",
      quick_actions: "Quick actions", act_sync: "Sync now",
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
      st_updating: "updating", st_queue: "queued", st_ready: "ready",
      st_draft: "draft", st_failed: "failed", st_error: "error", st_paused: "paused",
      st_skipped: "skipped", st_on: "on", st_off: "off",
      st_manual: "manual", st_postiz: "from Postiz", st_suggested: "suggested",
      st_unmatched: "not found", st_confirmed: "confirmed", st_rejected: "rejected",
      st_ignored: "ignored", st_claimed: "claim", st_none: "none",
      nav_manual: "Manual", title_manual: "Manual uploads",
      mu_scan_all: "Scan all", mu_scan: "Scan", mu_total: "Total",
      mu_manual: "Manual", mu_postiz: "From Postiz", mu_suggested: "Suggested",
      mu_confirmed: "Confirmed", mu_none: "Nothing found", mu_confirm: "Confirm",
      mu_reject: "Not mine", mu_ignore: "Ignore", mu_candidates: "Candidates",
      mu_confidence: "confidence", mu_claim: "claim", mu_claim_title: "Claim detected",
      mu_claim_delete: "Delete video", mu_claim_keep: "Keep", mu_last_scan: "Last scan",
      mu_from: "source",
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
      help_st_off: "Disabled.",
    },
  };

  const state = {
    view: "status",
    lang: localStorage.getItem("lang") || "ru",
    initData: tg?.initData || "",
    key: window.__WEBAPP_KEY__ || readKey() || "",
    user: tg?.initDataUnsafe?.user || null,
    data: {},
  };

  const $ = (id) => document.getElementById(id);
  const content = () => $("content");
  const t = (k) => (I18N[state.lang] && I18N[state.lang][k]) || I18N.ru[k] || k;

  function readKey() {
    const q = new URLSearchParams(location.search).get("key");
    if (q) return q;
    const m = location.pathname.match(/\/webapp\/k\/([^/]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function toast(msg) {
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
    return fetch(`/webapp/api${path}`, { ...opts, headers }).then(async (r) => {
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.error || r.statusText || "error");
      return data;
    });
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
    help: t("title_help"), manual: t("title_manual"),
  });

  async function load() {
    const v = state.view;
    content().innerHTML = `<div class="empty">${t("loading")}</div>`;
    try {
      if (v === "status") state.data = await api("/status");
      else if (v === "folders") {
        state.data = await api("/roots");
        if (!state.browse) state.browse = await api("/browse");
      }
      else if (v === "calendar") state.data = await api("/calendar");
      else if (v === "queue") state.data = await api("/queue");
      else if (v === "platforms") state.data = await api("/platforms");
      else if (v === "tail") {
        const tail = await api("/tail");
        const backlog = await api("/backlog");
        state.data = { items: tail.items || [], backlog: backlog.platforms || [] };
      }
      else if (v === "failed") state.data = await api("/failed");
      else if (v === "actions") state.data = await api("/status");
      else if (v === "metrics") state.data = await api("/metrics");
      else if (v === "manual") {
        const plan = await api("/manual/plan");
        const uploads = await api("/manual/uploads");
        state.data = { plan, items: uploads.items || [] };
      }
      render();
    } catch (e) {
      content().innerHTML = `<div class="empty">${t("error_prefix")}: ${e.message}</div>`;
    }
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
      .map((p) => `<div class="row"><div class="title">${p.name}</div>${
        p.paused ? pill("paused") : pill("ok")
      }<span class="meta">${t("limit")} ${p.daily_limit}</span></div>`)
      .join("");
    content().innerHTML = `<div class="view-enter">
      <div class="grid">${cards || `<div class="empty">${t("no_data")}</div>`}</div>
      <div class="panel"><div class="panel-header">${t("platforms")}</div>
        ${plats || `<div class="empty">${t("no_platforms")}</div>`}
      </div>`;
  }

  function renderFolders(d) {
    const roots = (d.roots || [])
      .map((r) => `<div class="row"><div class="title mono" style="flex:1;word-break:break-all">${r}</div>
        <button class="btn danger" data-act="folder-remove" data-p="${r}">${t("remove")}</button></div>`)
      .join("");
    const b = state.browse || { path: "", parent: null, dirs: [], root: "", roots: [] };
    const rootLabel = (r) => (r === "/mnt/video" ? t("net_root") : r === "/" ? t("local_root") : r);
    const rsel = (b.roots || []).length > 1
      ? `<div class="form-row">${(b.roots || []).map((r) =>
          `<button class="btn ${r === b.root ? "primary" : "secondary"}" data-act="folder-open" data-p="${r}">${rootLabel(r)}</button>`).join("")}</div>`
      : "";
    const dirs = (b.dirs || [])
      .map((x) => `<div class="row"><div class="title">📁 ${x.name}</div>
        <button class="btn secondary" data-act="folder-open" data-p="${x.path}">${t("open")}</button></div>`)
      .join("");
    content().innerHTML = `
      <div class="panel"><div class="panel-header">${t("folders_to_scan")}</div>
        ${roots || `<div class="empty">${t("folders_none")}</div>`}
      </div>
      <div class="panel">
        <div class="panel-header">${t("browse")} · <span class="mono" style="font-size:12px">${b.path || ""}</span></div>
        ${rsel}
        <div class="row"><div class="title mono" style="font-size:12px;word-break:break-all">${b.path || ""}</div></div>
        <div class="form-row">
          <button class="btn secondary" data-act="folder-up" data-p="${b.parent || ""}" ${b.parent ? "" : "disabled"}>${t("up")}</button>
          <button class="btn primary" data-act="folder-add" data-p="${b.path || ""}">${t("add_folder")}</button>
          <button class="btn success" data-act="folder-scan">${t("scan")}</button>
        </div>
        ${dirs || `<div class="empty">${t("no_subfolders")}</div>`}
      </div>`;
  }

  async function browseTo(path) {
    const q = path ? `?path=${encodeURIComponent(path)}` : "";
    state.browse = await api("/browse" + q);
    renderFolders(state.data || {});
  }

  function renderCalendar(d) {
    const legend = `<div class="panel"><div class="panel-header">${t("title_calendar")}</div>
      <div class="row"><span class="meta">${t("calendar_explain")}</span></div></div>`;
    const days = d.days || [];
    if (!days.length) {
      content().innerHTML = legend + `<div class="panel"><div class="empty">${t("calendar_empty")}</div></div>`;
      return;
    }
    content().innerHTML = legend + days.map((day) => {
      const rows = (day.items || []).map((it) => {
        const title = it.title || it.platform || "";
        const link = it.url ? ` <a href="${it.url}" target="_blank" rel="noopener">↗</a>` : "";
        return `<div class="row"><span class="mono">${it.time || ""}</span>
          <div class="title">${title}${link}</div>
          <span class="meta">${it.platform || ""}</span>${pill(it.status)}</div>`;
      }).join("");
      return `<div class="panel"><div class="panel-header">${day.date} <span class="meta">${day.count || 0}</span></div>${rows}</div>`;
    }).join("");
  }

  function renderQueue(d) {
    const rows = (d.items || []).map((it) =>
      `<div class="row"><div class="title">${it.entity_type}#${it.entity_id}</div>
       <span class="meta">${it.platform}</span>${pill(it.status)}
       <span class="mono meta">${it.postiz_scheduled_for || ""}</span></div>`).join("");
    content().innerHTML = `<div class="panel"><div class="panel-header">${t("nav_queue")}</div>${
      rows || `<div class="empty">${t("queue_empty")}</div>`}</div>`;
  }

  function renderPlatforms(d) {
    const rows = (d.platforms || []).map((p) => `
      <div class="row"><div class="title">${p.name}</div>
        ${p.enabled ? pill("ok") : pill("off")}${p.paused ? pill("paused") : ""}
        <span class="meta">${t("limit")} ${p.daily_limit}</span>
        <button class="btn secondary" data-act="resume-one" data-p="${p.name}">${t("resume")}</button>
        <button class="btn danger" data-act="pause-one" data-p="${p.name}">${t("pa_pause")}</button>
      </div>`).join("");
    content().innerHTML = `
      <div class="panel">
        <div class="panel-header">${t("platforms")}
          <span class="panel-actions">
            <button class="btn danger" data-act="pause-all">${t("pause_all")}</button>
            <button class="btn success" data-act="resume-all">${t("resume_all")}</button>
          </span>
        </div>
        ${rows || `<div class="empty">${t("none")}</div>`}
      </div>`;
  }

  function renderTail(d) {
    const dateRow = `<div class="form-row"><label class="meta">${t("backlog_from")}
        <input id="backlog-date" type="date" /></label></div>`;
    const rows = (d.backlog || []).map((p) => {
      const state = p.awaiting
        ? pill(t("backlog_awaiting"))
        : (p.tail_mode ? pill(t("backlog_on")) : pill(t("backlog_off")));
      const slot = p.slot ? `<span class="mono meta">${String(p.slot).slice(0, 16).replace("T", " ")}</span>` : "";
      return `<div class="row"><div class="title">${p.platform}</div>
          <span class="meta">${t("backlog_unposted")}: ${p.count}</span>
          ${state}${slot}</div>
        <div class="form-row">
          <button class="btn primary" data-act="backlog-answer" data-p="${p.platform}" data-a="distribute">${t("backlog_distribute")}</button>
          <button class="btn secondary" data-act="backlog-answer" data-p="${p.platform}" data-a="wait">${t("backlog_wait")}</button>
          <button class="btn danger" data-act="backlog-answer" data-p="${p.platform}" data-a="skip">${t("backlog_skip")}</button>
        </div>`;
    }).join("");
    content().innerHTML = `<div class="panel"><div class="panel-header">${t("tail_title")}</div>
      <div class="row"><span class="meta">${t("tail_explain")}</span></div>
      ${rows || `<div class="empty">${t("no_data")}</div>`}</div>`;
  }

  function renderFailed(d) {
    const rows = (d.items || []).map((it) =>
      `<div class="row"><div class="title">${it.entity_type}#${it.entity_id} · ${it.platform}</div>
       <span class="meta">${it.last_error || ""}</span>${pill(it.status)}</div>`).join("");
    content().innerHTML = `<div class="panel"><div class="panel-header">${t("nav_failed")}</div>${
      rows || `<div class="empty">${t("no_errors")}</div>`}</div>`;
  }

  function renderActions(d) {
    const opts = ((d && d.platforms) || [])
      .map((p) => `<option>${p.name}</option>`).join("")
      || `<option>youtube</option>`;
    content().innerHTML = `
      <div class="panel"><div class="panel-header">${t("quick_actions")}</div>
        <div class="form-row">
          <button class="btn primary" data-act="distribute">${t("distribute")}</button>
          <button class="btn secondary" data-act="schedule">${t("act_schedule")}</button>
        </div>
        <div class="form-row">
          <button class="btn secondary" data-act="sync">${t("act_sync")}</button>
          <button class="btn secondary" data-act="reconcile">${t("act_reconcile")}</button>
          <button class="btn secondary" data-act="backup">${t("act_backup")}</button>
          <button class="btn secondary" data-act="refresh">${t("refresh_data")}</button>
        </div>
      </div>
      <div class="panel"><div class="panel-header">${t("force_link_title")}</div>
        <div class="row"><span class="meta">${t("fl_hint")}</span></div>
        <div class="form-row">
          <input id="fl-id" type="number" placeholder="${t("fl_id_ph")}" style="width:120px" />
          <select id="fl-p">${opts}</select>
          <input id="fl-url" type="url" placeholder="https://..." style="flex:1;min-width:140px" />
          <button class="btn primary" data-act="force-link">${t("save")}</button>
        </div>
      </div>`;
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
      ? `<div class="row"><span class="pill err">${t("m_err_pill")}</span><span class="title">${d.last_error}</span></div>`
      : `<div class="row"><span class="pill ok">ОК</span><span class="title">${t("m_no_err")}</span></div>`;
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
      `<div class="row"><div class="title">${t(nameKey)}</div><span class="meta" style="flex:2;text-align:right">${t(descKey)}</span></div>`
    ).join("");
    return `<div class="panel"><div class="panel-header">${t(titleKey)}</div>${rows}</div>`;
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
             data-id="${it.id}" data-et="${c.entity_type}" data-eid="${c.entity_id}">${c.title} · ${Math.round((c.score || 0) * 100)}%</button>`
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
        <div class="panel-header">${it.title || it.platform_video_id} ${pill(it.origin === "postiz" ? "postiz" : "manual")} ${pill(it.match_status)}</div>
        <div class="row"><div class="title">${it.platform} · ${it.published_at || ""}</div>
          ${it.url ? `<a href="${it.url}" target="_blank" rel="noopener">↗</a>` : ""}${claimMark}</div>
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

  function renderHelp() {
    content().innerHTML = [
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
    const d = state.data;
    if (state.view === "status") renderStatus(d);
    else if (state.view === "folders") renderFolders(d);
    else if (state.view === "calendar") renderCalendar(d);
    else if (state.view === "queue") renderQueue(d);
    else if (state.view === "platforms") renderPlatforms(d);
    else if (state.view === "tail") renderTail(d);
    else if (state.view === "failed") renderFailed(d);
    else if (state.view === "actions") renderActions(d);
    else if (state.view === "metrics") renderMetrics(d);
    else if (state.view === "manual") renderManual(d);
    else if (state.view === "help") renderHelp();
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
    $("btn-refresh").textContent = t("refresh");
    $("gate-msg").textContent = t("gate_msg");
    $("lang").querySelectorAll("button").forEach((b) =>
      b.classList.toggle("active", b.dataset.lang === l));
    load();
  }

  function updateNavLabels() {
    $("nav").querySelectorAll("button[data-view]").forEach((b) => {
      const span = b.querySelector(".label");
      if (span) span.textContent = t("nav_" + b.dataset.view);
    });
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
      if (act === "folder-up") return browseTo(el.dataset.p || "/");
      if (act === "folder-add") {
        const p = el.dataset.p;
        if (!p) return;
        const roots = (state.data?.roots || []).slice();
        if (!roots.includes(p)) roots.push(p);
        state.data = await api("/roots", { method: "POST", body: JSON.stringify({ roots }) });
        toast(t("t_folder_added"));
        return load();
      }
      if (act === "folder-remove") {
        const roots = (state.data?.roots || []).filter((r) => r !== el.dataset.p);
        state.data = await api("/roots", { method: "POST", body: JSON.stringify({ roots }) });
        toast(t("t_folder_removed"));
        return load();
      }
      if (act === "folder-scan") {
        const r = await api("/scan", { method: "POST", body: "{}" });
        const s = r.stats || {};
        toast(`${t("t_scan")}: long ${s.long || 0}, shorts ${s.shorts || 0}, standalone ${s.standalone || 0}`);
        return;
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
      toast(e.message);
    }
  }

  function bind() {
    $("nav").addEventListener("click", (e) => {
      const btn = e.target.closest("button[data-view]");
      if (!btn) return;
      state.view = btn.dataset.view;
      $("nav").querySelectorAll("button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      load();
    });
    $("btn-refresh").addEventListener("click", () => load());
    $("lang").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-lang]");
      if (b) setLang(b.dataset.lang);
    });
    content().addEventListener("click", (e) => {
      const btn = e.target.closest("[data-act]");
      if (!btn) return;
      onAction(btn.dataset.act, btn);
    });
  }

  function boot() {
    if (tg) {
      try { tg.ready(); } catch (_) {}
      try { tg.expand(); } catch (_) {}
      try {
        tg.setHeaderColor("secondary_bg_color");
        tg.setBackgroundColor("bg_color");
      } catch (_) {}
    }

    document.documentElement.lang = state.lang;
    const langParam = new URLSearchParams(location.search).get("lang");
    if (langParam && I18N[langParam]) state.lang = langParam;

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

    $("gate").hidden = true;
    $("app").hidden = false;
    if (state.user) {
      $("user-info").textContent =
        [state.user.first_name, state.user.username ? "@" + state.user.username : ""].filter(Boolean).join(" ");
    }
    api("/version").then((v) => { $("ver").textContent = "v" + (v.version || "?"); }).catch(() => {});

    updateNavLabels();
    $("btn-refresh").textContent = t("refresh");
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
