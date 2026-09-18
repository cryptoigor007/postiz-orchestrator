(() => {
  const tg = window.Telegram?.WebApp;
  const state = {
    view: "status",
    initData: tg?.initData || "",
    user: tg?.initDataUnsafe?.user || null,
    data: {},
  };

  const $ = (id) => document.getElementById(id);
  const content = () => $("content");

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
    else if (["scheduled", "updating"].includes(s)) cls += " info";
    else if (["failed", "error"].includes(s)) cls += " err";
    else if (["paused", "skipped"].includes(s)) cls += " warn";
    return `<span class="${cls}">${status || "—"}</span>`;
  }

  const titles = {
    status: "Статус",
    calendar: "Календарь",
    queue: "Очередь",
    platforms: "Платформы",
    tail: "Режим хвоста",
    failed: "Ошибки",
    actions: "Действия",
    metrics: "Метрики",
  };

  async function load() {
    const v = state.view;
    content().innerHTML = `<div class="empty">Загрузка…</div>`;
    try {
      if (v === "status") state.data = await api("/status");
      else if (v === "calendar") state.data = await api("/calendar");
      else if (v === "queue") state.data = await api("/queue");
      else if (v === "platforms") state.data = await api("/platforms");
      else if (v === "tail") state.data = await api("/tail");
      else if (v === "failed") state.data = await api("/failed");
      else if (v === "actions") state.data = await api("/status");
      else if (v === "metrics") state.data = await api("/metrics");
      render();
    } catch (e) {
      content().innerHTML = `<div class="empty">Ошибка: ${e.message}</div>`;
    }
  }

  function renderStatus(d) {
    const counts = d.counts || {};
    const cards = Object.entries(counts)
      .map(
        ([k, v]) =>
          `<div class="card"><div class="label">${k}</div><div class="value">${v}</div></div>`
      )
      .join("");
    const plats = (d.platforms || [])
      .map(
        (p) =>
          `<div class="row"><div class="title">${p.name}</div>${
            p.paused ? pill("paused") : pill("ok")
          }<span class="meta">limit ${p.daily_limit}</span></div>`
      )
      .join("");
    content().innerHTML = `<div class="view-enter">
      <div class="grid">${cards || '<div class="empty">Нет данных</div>'}</div>
      <div class="panel">
        <div class="panel-header">Платформы</div>
        ${plats || '<div class="empty">Нет платформ</div>'}
      </div>`;
  }

  function renderCalendar(d) {
    const days = d.days || [];
    if (!days.length) {
      content().innerHTML = `<div class="panel"><div class="empty">Календарь пуст</div></div>`;
      return;
    }
    content().innerHTML = days
      .map((day) => {
        const rows = (day.items || [])
          .map(
            (it) =>
              `<div class="row"><span class="mono">${it.time || ""}</span>
               <div class="title">${it.platform} · ${it.entity_type}#${it.entity_id}</div>
               ${pill(it.status)}</div>`
          )
          .join("");
        return `<div class="panel"><div class="panel-header">${day.date}</div>${rows}</div>`;
      })
      .join("");
  }

  function renderQueue(d) {
    const rows = (d.items || [])
      .map(
        (it) =>
          `<div class="row">
            <div class="title">${it.entity_type}#${it.entity_id}</div>
            <span class="meta">${it.platform}</span>
            ${pill(it.status)}
            <span class="mono meta">${it.postiz_scheduled_for || ""}</span>
          </div>`
      )
      .join("");
    content().innerHTML = `<div class="panel"><div class="panel-header">Очередь</div>${
      rows || '<div class="empty">Пусто</div>'
    }</div>`;
  }

  function renderPlatforms(d) {
    const rows = (d.platforms || [])
      .map(
        (p) => `
      <div class="row">
        <div class="title">${p.name}</div>
        ${p.enabled ? pill("ok") : pill("off")}
        ${p.paused ? pill("paused") : ""}
        <span class="meta">limit ${p.daily_limit}</span>
        <button class="btn secondary" data-act="resume-one" data-p="${p.name}">Resume</button>
      </div>`
      )
      .join("");
    content().innerHTML = `
      <div class="panel">
        <div class="panel-header">
          Платформы
          <span>
            <button class="btn danger" data-act="pause-all">Pause all</button>
            <button class="btn success" data-act="resume-all">Resume all</button>
          </span>
        </div>
        ${rows || '<div class="empty">Нет</div>'}
      </div>`;
  }

  function renderTail(d) {
    const rows = (d.items || [])
      .map(
        (t) => `
      <div class="row">
        <div class="title">${t.platform}</div>
        ${t.tail ? pill("tail ON") : pill("off")}
        <button class="btn primary" data-act="tail-on" data-p="${t.platform}">Включить</button>
        <button class="btn secondary" data-act="tail-off" data-p="${t.platform}">Выключить</button>
      </div>`
      )
      .join("");
    content().innerHTML = `<div class="panel"><div class="panel-header">Хвост серии</div>${
      rows || '<div class="empty">Нет данных</div>'
    }</div>`;
  }

  function renderFailed(d) {
    const rows = (d.items || [])
      .map(
        (it) =>
          `<div class="row">
            <div class="title">${it.entity_type}#${it.entity_id} · ${it.platform}</div>
            <span class="meta">${it.last_error || ""}</span>
            ${pill(it.status)}
          </div>`
      )
      .join("");
    content().innerHTML = `<div class="panel"><div class="panel-header">Ошибки</div>${
      rows || '<div class="empty">Ошибок нет</div>'
    }</div>`;
  }

  function renderActions() {
    content().innerHTML = `
      <div class="panel">
        <div class="panel-header">Быстрые действия</div>
        <div class="form-row">
          <button class="btn primary" data-act="distribute">Distribute long</button>
          <button class="btn secondary" data-act="refresh">Обновить данные</button>
        </div>
      </div>
      <div class="panel">
        <div class="panel-header">Force link update</div>
        <div class="form-row">
          <input id="fl-id" type="number" placeholder="entity_id" style="width:100px" />
          <select id="fl-p">
            <option>youtube</option><option>instagram</option>
            <option>tiktok</option><option>facebook</option>
          </select>
          <input id="fl-url" type="url" placeholder="https://..." style="flex:1;min-width:140px" />
          <button class="btn primary" data-act="force-link">Сохранить</button>
        </div>
      </div>`;
  }


  function renderMetrics(d) {
    const entries = Object.entries(d || {}).filter(([k]) => k !== "note");
    const cards = entries
      .map(([k, v]) => {
        const val = typeof v === "object" ? JSON.stringify(v) : v;
        return `<div class="card"><div class="label">${k}</div><div class="value" style="font-size:18px">${val ?? "—"}</div></div>`;
      })
      .join("");
    content().innerHTML = `<div class="grid">${cards || '<div class="empty">Нет метрик</div>'}</div>
      <div class="panel"><div class="panel-header">Raw</div>
      <div class="row"><span class="mono">${JSON.stringify(d || {}, null, 0)}</span></div></div>`;
  }

  function render() {
    $("title").textContent = titles[state.view] || state.view;
    const d = state.data;
    if (state.view === "status") renderStatus(d);
    else if (state.view === "calendar") renderCalendar(d);
    else if (state.view === "queue") renderQueue(d);
    else if (state.view === "platforms") renderPlatforms(d);
    else if (state.view === "tail") renderTail(d);
    else if (state.view === "failed") renderFailed(d);
    else if (state.view === "actions") renderActions();
    else if (state.view === "metrics") renderMetrics(d);
    // Emil: enter from scale>=0.95 + opacity; stagger list rows
    const root = content();
    root.classList.remove("view-enter");
    void root.offsetWidth;
    root.classList.add("view-enter");
    root.querySelectorAll(".row").forEach((el) => el.classList.add("stagger"));
  }

  async function onAction(act, el) {
    try {
      if (act === "refresh") return load();
      if (act === "pause-all") {
        await api("/pause", { method: "POST", body: "{}" });
        toast("Все платформы на паузе");
      } else if (act === "resume-all") {
        await api("/resume", { method: "POST", body: "{}" });
        toast("Все платформы возобновлены");
      } else if (act === "resume-one") {
        await api("/resume_platform", {
          method: "POST",
          body: JSON.stringify({ platform: el.dataset.p }),
        });
        toast(`Resume ${el.dataset.p}`);
      } else if (act === "tail-on") {
        await api("/series_end", {
          method: "POST",
          body: JSON.stringify({ platform: el.dataset.p, enable: true }),
        });
        toast(`Хвост ON · ${el.dataset.p}`);
      } else if (act === "tail-off") {
        await api("/series_end", {
          method: "POST",
          body: JSON.stringify({ platform: el.dataset.p, enable: false }),
        });
        toast(`Хвост OFF · ${el.dataset.p}`);
      } else if (act === "distribute") {
        const r = await api("/distribute", { method: "POST", body: "{}" });
        toast(`Distributed: ${r.count ?? 0}`);
      } else if (act === "force-link") {
        const entity_id = Number($("fl-id").value);
        const platform = $("fl-p").value;
        const url = $("fl-url").value.trim();
        await api("/force_link", {
          method: "POST",
          body: JSON.stringify({ entity_id, platform, url }),
        });
        toast("Ссылка сохранена");
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
    content().addEventListener("click", (e) => {
      const btn = e.target.closest("[data-act]");
      if (!btn) return;
      onAction(btn.dataset.act, btn);
    });
  }

  function boot() {
    if (tg) {
      tg.ready();
      tg.expand();
      try {
        tg.setHeaderColor("secondary_bg_color");
        tg.setBackgroundColor("bg_color");
      } catch (_) {}
    }

    // Dev fallback: allow ?dev=1 without Telegram
    const dev = new URLSearchParams(location.search).get("dev") === "1";
    if (!state.initData && !dev) {
      $("gate").hidden = false;
      $("app").hidden = true;
      return;
    }
    if (dev && !state.initData) state.initData = "dev";

    $("gate").hidden = true;
    $("app").hidden = false;
    if (state.user) {
      $("user-info").textContent =
        [state.user.first_name, state.user.username ? "@" + state.user.username : ""]
          .filter(Boolean)
          .join(" ");
    }
    api("/version")
      .then((v) => {
        $("ver").textContent = "v" + (v.version || "?");
      })
      .catch(() => {});
    bind();
    load();
  }

  boot();
})();
