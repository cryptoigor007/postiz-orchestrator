// GUI-проверка панели: грузим реальную страницу в jsdom, кликаем по кнопкам,
// ловим JS-ошибки и проверяем ключевые потоки (очередь, обложка, удаление, папки).
// Запуск: node tests/gui/check.mjs <URL-страницы>
import { JSDOM, VirtualConsole } from "jsdom";

const url = process.argv[2];
if (!url) {
  console.error("usage: node check.mjs <page-url>");
  process.exit(2);
}
const html = await (await fetch(url)).text();
if (!html.includes("id=\"content\"")) {
  console.error("страница не похожа на панель (нет #content)");
  process.exit(2);
}

const calls = [];
const bodies = [];
const jsErrors = [];
const fail = (msg) => { console.error("❌ " + msg); process.exitCode = 1; };
const ok = (msg) => console.log("✓ " + msg);

// Реальные ответы API берём с живого сервера (кроме опасных POST)
const parsed = new URL(url);
const key = process.env.WEBAPP_ACCESS_KEY
  || ((parsed.pathname.match(/\/webapp\/k\/([^/]+)/) || [])[1] || "");
const apiBase = `${parsed.origin}/webapp/api`;
const realFixtures = {};
const GET_ENDPOINTS = ["version", "status", "roots", "browse", "calendar", "queue",
  "platforms", "schedule_settings", "failed", "tail", "backlog", "metrics", "trash",
  "manual/plan", "manual/uploads"];
for (const ep of GET_ENDPOINTS) {
  try {
    const r = await fetch(`${apiBase}/${ep}?key=${encodeURIComponent(key)}`,
                          { headers: { "X-Webapp-Key": key } });
    if (r.ok) realFixtures[ep] = await r.json();
  } catch { /* оставим заглушку */ }
}

const fixtures = {
  version: { version: "test", build: "test" },
  status: { counts: { ready: 1, scheduled: 2 }, platforms: [
    { name: "youtube", enabled: true, daily_limit: 7, paused: false },
    { name: "telegram", enabled: true, daily_limit: 5, paused: false }] },
  roots: { roots: ["/mnt/video"], items: [{ path: "/mnt/video", kind: "auto" }],
           browse_roots: ["/mnt/video"] },
  browse: { path: "/mnt/video", parent: null, root: "/mnt/video", roots: ["/mnt/video"],
            roots_meta: [{ path: "/mnt/video", available: true, note: "" }],
            warning: "", dirs: [{ name: "ssd_backup", path: "/mnt/video/ssd_backup" }],
            selected: true },
  calendar: { days: [{ date: "2026-09-22", items: [] }] },
  queue: { items: [
    { entity_type: "short", entity_id: 1, platform: "youtube", status: "scheduled",
      postiz_scheduled_for: "2026-09-21T09:00:00+00:00", date: "2026-09-21", time: "12:00",
      title: "Шортс: Тест", title_text: "Тест", description_text: "d", hashtags_text: "#t",
      cover_path: "", covers: [], has_tg: true, video_path: "/mnt/video/x.mp4" },
    { entity_type: "short", entity_id: 1, platform: "telegram", status: "ready",
      postiz_scheduled_for: "2026-09-21T09:15:00+00:00", date: "2026-09-21", time: "12:15",
      title: "Шортс: Тест", title_text: "Тест", description_text: "d", hashtags_text: "#t",
      cover_path: "/mnt/video/c.jpg", covers: [], has_tg: true, video_path: "/mnt/video/x.mp4" },
  ]},
  platforms: { items: [{ name: "youtube", enabled: true, daily_limit: 7, paused: false }] },
  schedule_settings: { settings: {}, groups: [], platforms: ["youtube", "telegram"],
    mode: "manual", effective: {} },
  failed: { items: [] },
  tail: { items: [] },
  backlog: { items: [] },
  metrics: {},
  trash: { items: [
    { key: "short|1|youtube", entity_type: "short", entity_id: 1, platform: "youtube",
      title: "Тестовый шортс", deleted_at: "2026-09-21T09:00:00+00:00",
      deleted_reason: "platform", cascade_from: "", scheduled_for: null, parent_id: null }],
    total: 1 },
  "manual/plan": { total: 0, by_status: {}, by_platform: {}, platforms: [], last_scan: null },
  "manual/uploads": { items: [] },
  "browse/search": { q: "готов", items: [
    { name: "готовые", path: "/mnt/video/ssd_backup/готовые", root: "/mnt/video" }] },
  "cover/frames": { ok: true, duration: 40.0,
    frames: [{ name: "frame_01.jpg", path: "/mnt/video/.covers/f1.jpg", at: 4.8 },
             { name: "frame_02.jpg", path: "/mnt/video/.covers/f2.jpg", at: 12.0 }] },
  "cover/list": { path: "/mnt/video", parent: null, roots: ["/mnt/video"],
    dirs: [{ name: "sub", path: "/mnt/video/sub" }],
    images: [{ name: "c.jpg", path: "/mnt/video/c.jpg", size: 10 }], warning: "" },
  "queue/remove": { ok: true, removed: 1, blocked: [] },
  roots_post: { ok: true, items: [{ path: "/mnt/video", kind: "auto" }], roots: ["/mnt/video"] },
};

// если живая очередь пуста — проверяем на синтетических строках
if (realFixtures.queue && !(realFixtures.queue.items || []).length) {
  realFixtures.queue = fixtures.queue;
}

// Календарь: синтетический пост на 5 платформ (регрессия «иконки вылезали из ячейки месяца»).
// Дата — локальная «сегодня», как её считает сам app.js.
const _d0 = new Date();
const CAL_DATE = `${_d0.getFullYear()}-${String(_d0.getMonth() + 1).padStart(2, "0")}-${String(_d0.getDate()).padStart(2, "0")}`;
realFixtures.calendar = { days: [{ date: CAL_DATE, count: 5,
  items: ["youtube", "telegram", "instagram", "tiktok", "facebook"].map((p) => ({
    scheduled_for: "", date: CAL_DATE, time: "09:00", platform: p,
    title: "Шортс: проверка ячейки месяца", status: "scheduled", source: "db",
    entity_type: "short", entity_id: 1, project: "" })) }], total: 5 };

// Проекты: >= 2 → в полосе календаря появляются чипы фильтра проектов (регрессия S2)
realFixtures.projects = { items: [{ id: "p1", title: "Точка наблюдения" },
                                  { id: "p2", title: "Проект 2" }] };

function response(data) {
  return Promise.resolve({ ok: true, status: 200,
    json: () => Promise.resolve(data), text: () => Promise.resolve(JSON.stringify(data)) });
}

const vc = new VirtualConsole();
vc.on("jsdomError", (e) => jsErrors.push(String(e.message)));
vc.on("log", () => {}); vc.on("warn", () => {}); vc.on("info", () => {}); vc.on("debug", () => {});

const dom = new JSDOM(html, {
  runScripts: "dangerously",
  url: new URL(url).toString(),
  pretendToBeVisual: true,
  virtualConsole: vc,
  beforeParse(window) {
    window.confirm = () => true;
    window.Telegram = undefined;
    window.fetch = (u, opts = {}) => {
      const s = String(u);
      const path = s.split("?")[0].replace(/^https?:\/\/[^/]+/, "");
      const m = (opts.method || "GET") + " " + path;
      calls.push(m);
      if (opts && opts.body) bodies.push(String(opts.body));
      const ep = path.replace(/^\/webapp\/api\//, "");
      if (ep === "roots" && opts.method === "POST") return response(fixtures.roots_post);
      if (ep.startsWith("queue/remove")) {
        if (opts.body && String(opts.body).includes("plan_only")) {
          let req = {};
          try { req = JSON.parse(String(opts.body)); } catch (_) { /* ignore */ }
          const plat = req.platform || "youtube";
          const plats = plat === "youtube" ? ["youtube", "telegram"] : [plat];
          return response({ ok: true, plan_only: true, blocked: [], count: plats.length,
            targets: plats.map((p) => ({ entity_type: req.entity_type || "short",
              entity_id: req.entity_id || 1, platform: p, status: "scheduled" })) });
        }
        return response(fixtures["queue/remove"]);
      }
      if (realFixtures[ep] !== undefined) return response(realFixtures[ep]);
      if (fixtures[ep]) return response(fixtures[ep]);
      return response({});
    };
  },
});

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const doc = dom.window.document;
await wait(400);

// 1. Все экраны открываются без JS-ошибок
const views = [...doc.querySelectorAll("#nav button[data-view]")].map((b) => b.dataset.view);
let viewFails = 0;
for (const v of views) {
  const btn = doc.querySelector(`#nav button[data-view="${v}"]`);
  if (!btn) { console.log(`  (нет кнопки экрана ${v})`); continue; }
  const before = jsErrors.length;
  btn.click();
  await wait(250);
  const text = (doc.getElementById("content").textContent || "").trim();
  const err = /^(Ошибка|Error)/.test(text) || !text;
  if (err || jsErrors.length > before) {
    fail(`экран ${v}: ${err ? "пусто/ошибка" : "JS-ошибка: " + jsErrors.slice(before).join("; ")}`);
    viewFails++;
  }
}
if (!viewFails) ok(`все ${views.length} экранов открываются без ошибок`);

// 1b. Шторка «Ещё»: failed / help / trash — каждый в свой экран (не «Настройки»)
for (const v of ["failed", "help", "trash"]) {
  const mb = doc.getElementById("tab-more");
  if (mb) { mb.click(); await wait(150); }
  const sheet = doc.getElementById("more-sheet");
  const b = sheet && sheet.querySelector(`button[data-view="${v}"]`);
  if (!b) { fail(`шторка: нет пункта ${v}`); continue; }
  b.click();
  await wait(220);
  const text = (doc.getElementById("content").textContent || "").trim();
  if (text) ok(`шторка: ${v} — свой экран, непустой`);
  else fail(`шторка: экран ${v} пуст`);
}

// 1c. Календарь: месяц — иконки платформ не вылезают за ячейку (регрессия S1)
doc.querySelector('#nav button[data-view="calendar"]').click();
await wait(250);
const mBtn = doc.querySelector('[data-act="cal-view"][data-v="month"]');
if (!mBtn) fail("календарь: нет переключателя «Месяц»");
else {
  mBtn.click();
  await wait(250);
  const cells = doc.querySelectorAll(".cal-cell");
  const hasDay = doc.querySelectorAll(".cal-cell.has").length;
  const dots = doc.querySelectorAll(".cal-cell .cal-dot");
  let maxIco = 0;
  dots.forEach((d) => { maxIco = Math.max(maxIco, d.querySelectorAll(".pico").length); });
  if (cells.length >= 28 && hasDay >= 1 && dots.length >= 1) {
    ok(`календарь (месяц): ячеек ${cells.length}, дней с постами ${hasDay}`);
  } else {
    fail(`календарь (месяц): ячеек ${cells.length}, с постами ${hasDay}, точек ${dots.length}`);
  }
  if (maxIco <= 2) ok(`календарь (месяц): иконок в посте не больше 2 (макс ${maxIco})`);
  else fail(`календарь (месяц): иконок в посте ${maxIco} — вылезут за границы ячейки`);
  // S2: полоса фильтров не должна растягивать сегмент «День|Неделя|Месяц» по высоте чипов
  const bar = doc.querySelector(".cal-bar");
  const seg = bar && bar.querySelector(".seg");
  const chips = bar && bar.querySelector(".chips");
  if (seg && chips) ok(`календарь: полоса фильтров — сегмент + ${chips.querySelectorAll(".chip").length} чипов проектов`);
  else fail(`календарь: полоса фильтров без чипов проектов (seg=${!!seg}, chips=${!!chips})`);
  const al = bar && dom.window.getComputedStyle(bar).alignItems;
  if (al === "center") ok("календарь: полоса не растягивает сегмент (align-items: center)");
  else fail(`календарь: align-items=${al} — сегмент растянется по высоте чипов`);
  const firstCell = doc.querySelector(".cal-cell");
  const ov = firstCell && dom.window.getComputedStyle(firstCell).overflow;
  if (ov === "hidden") ok("календарь (месяц): ячейка обрезает переполнение");
  else fail(`календарь (месяц): у ячейки overflow=${ov} — содержимое может вылезти`);
  // 1d. v8.4.48: ‹ › и «Сегодня» есть во всех трёх видах, дата — подписью без дубля заголовка
  for (const v of ["day", "week", "month"]) {
    const vb = doc.querySelector(`[data-act="cal-view"][data-v="${v}"]`);
    if (!vb) { fail(`календарь: нет переключателя вида ${v}`); continue; }
    vb.click();
    await wait(220);
    const steps = doc.querySelectorAll('[data-act="cal-shift"]');
    const labels = [...steps].map((b) => b.getAttribute("aria-label") || "");
    const period = doc.querySelector(".cal-period");
    const h3 = [...doc.querySelectorAll("#content h3")].map((h) => h.textContent.trim());
    if (steps.length === 2 && labels.every((l) => l.length > 0)) {
      ok(`календарь (${v}): стрелки ‹ › на месте, подпись периода «${period ? period.textContent.trim() : "—"}»`);
    } else {
      fail(`календарь (${v}): стрелок ${steps.length}, aria-label=${JSON.stringify(labels)}`);
    }
    if (h3.includes(period ? period.textContent.trim() : "\u0000")) {
      fail(`календарь (${v}): заголовок дублирует подпись периода (${h3.join("/")})`);
    }
    const today = doc.querySelector('[data-act="cal-today"]');
    if (today) ok(`календарь (${v}): «Сегодня» доступна (${today.textContent.trim()})`);
    else fail(`календарь (${v}): нет кнопки «Сегодня»`);
  }
  // стрелка перелистывает период, «Сегодня» возвращает
  const beforeShift = (doc.querySelector(".cal-period") || {}).textContent;
  doc.querySelector('[data-act="cal-shift"][data-n="1"]').click();
  await wait(220);
  const afterShift = (doc.querySelector(".cal-period") || {}).textContent;
  if (afterShift !== beforeShift) ok(`календарь: стрелка › перелистывает период («${afterShift}»)`);
  else fail("календарь: стрелка › не перелистывает период");
  doc.querySelector('[data-act="cal-today"]').click();
  await wait(220);
  if ((doc.querySelector(".cal-period") || {}).textContent === beforeShift) {
    ok("календарь: «Сегодня» возвращает к текущему периоду");
  } else {
    fail("календарь: «Сегодня» не вернула текущий период");
  }
  // месяцу нужен свежий клик «Месяц» — внутри месяца остаёмся на сегодняшнем дне
  doc.querySelector('[data-act="cal-view"][data-v="month"]').click();
  await wait(220);
  if (doc.querySelector(".cal-cell.today")) ok("календарь (месяц): сегодняшняя ячейка помечена");
  else fail("календарь (месяц): нет ячейки .today");
}

// 2. Очередь: редактирование → выбор обложки
doc.querySelector('#nav button[data-view="queue"]').click();
await wait(250);
const rows = doc.querySelectorAll(".q-item").length;
const delBtns = doc.querySelectorAll('[data-act="queue-remove"]').length;
if (rows >= 2 && delBtns >= 1) ok(`очередь: строк ${rows}, кнопок удаления ${delBtns}`);
else fail(`очередь не отрисовалась (rows=${rows}, del=${delBtns})`);

doc.querySelector('[data-act="queue-edit"]').click();
await wait(80);
if (doc.querySelector('[data-act="queue-remove-everywhere"]')) ok("редактирование: кнопка «Удалить везде» есть");
else fail("нет кнопки «Удалить везде»");
const pickBtn = doc.querySelector('[data-act="cover-pick"]');
if (pickBtn) ok("редактирование: кнопка «Выбрать обложку…» есть");
else fail("нет кнопки «Выбрать обложку…»");
if (pickBtn) {
  pickBtn.click();
  await wait(200);
  const picker = doc.getElementById("coverPicker");
  if (picker && picker.querySelectorAll(".cp-thumb").length >= 1) ok("выбор обложки: окно и картинки есть");
  else fail("выбор обложки не открылся/нет картинок");
  const tabs = picker ? picker.querySelectorAll(".cp-tab").length : 0;
  if (tabs >= 4) ok("выбор обложки: 4 источника (сервер/устройство/ссылка/кадры)");
  else fail(`выбор обложки: вкладок ${tabs}, ожидалось 4`);
  const framesTab = picker && picker.querySelector('[data-tab="frames"]');
  if (framesTab) {
    framesTab.click();
    await wait(200);
    const thumbs = picker.querySelectorAll(".cp-thumb").length;
    if (thumbs >= 1) ok("выбор обложки: кадры из видео показываются");
    else fail("вкладка «Из видео» не показала кадры");
  } else fail("нет вкладки «Из видео»");
  if (picker && picker.querySelector('[data-cp="close"]')) picker.querySelector('[data-cp="close"]').click();
  await wait(50);
  if (!doc.getElementById("coverPicker")) ok("выбор обложки: окно закрывается");
  else fail("окно выбора обложки не закрылось");
}

// 2.5 Фильтры-чипы и мультивыбор
const chips = doc.querySelectorAll('[data-act="queue-filter"]');
if (chips.length >= 2) ok(`фильтры: чипов ${chips.length}`);
else fail(`фильтры: чипов ${chips.length}, ожидалось >= 2 (Все + платформы)`);
const tgChip = doc.querySelector('[data-act="queue-filter"][data-p="telegram"]');
if (tgChip) {
  tgChip.click();
  await wait(150);
  const n = doc.querySelectorAll(".q-item").length;
  if (n >= 1) ok(`фильтр telegram: строк ${n}`);
  else fail("фильтр telegram: строк нет");
  const back = doc.querySelector('[data-act="queue-filter"][data-p="all"]');
  if (back) { back.click(); await wait(150); }
}
const daySeps = doc.querySelectorAll(".day-sep").length;
if (daySeps >= 1) ok(`разделители по дням: ${daySeps}`);
else fail("нет разделителей по дням");
const selBtn = doc.querySelector('[data-act="queue-select"]');
if (selBtn) {
  selBtn.click();
  await wait(150);
  const checks = doc.querySelectorAll('[data-act="queue-check"]');
  if (checks.length) {
    ok(`мультивыбор: чекбоксов ${checks.length}`);
    checks[0].click();
    await wait(150);
    if (doc.querySelector(".bulk-bar")) ok("мультивыбор: панель действий появилась");
    else fail("мультивыбор: нет панели действий");
    if (doc.querySelector('[data-act="queue-bulk-delete"]')) ok("мультивыбор: кнопка удаления есть");
    else fail("мультивыбор: нет кнопки удаления");
    if (doc.querySelector('[data-act="queue-bulk-tags"]')) ok("мультивыбор: массовые хештеги есть");
    else fail("мультивыбор: нет кнопки хештегов");
  } else fail("мультивыбор: чекбоксы не появились");
  const done = doc.querySelector('[data-act="queue-select"]');
  if (done) { done.click(); await wait(150); }
} else fail("нет кнопки «Выбрать»");

// 3. Удаление: интерактивное окно (план) → подтверждение → запрос, список обновился
const qBefore = calls.filter((c) => c === "GET /webapp/api/queue").length;
doc.querySelector('[data-act="queue-remove"]').click();
await wait(300);
const dl = doc.getElementById("delDialog");
if (dl) ok("удаление: интерактивное окно открылось");
else fail("удаление: окно удаления не открылось");
if (calls.some((c) => c === "POST /webapp/api/queue/remove")) ok("удаление: план запрошен (plan_only)");
else fail("удаление: план НЕ запрошен");
// F9: фокус внутри окна и Escape закрывает
if (dl && doc.activeElement && dl.contains(doc.activeElement)) ok("удаление: фокус перенесён в окно");
else fail("удаление: фокус не перенесён в окно");
if (dl) {
  doc.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
  await wait(180);
}
if (!doc.getElementById("delDialog")) ok("удаление: Escape закрывает окно");
else fail("удаление: Escape не закрывает окно");
// переоткрываем и подтверждаем
doc.querySelector('[data-act="queue-remove"]').click();
await wait(300);
const dl2 = doc.getElementById("delDialog");
const okBtn = dl2 && dl2.querySelector('[data-dd="ok"]');
if (okBtn) { okBtn.click(); await wait(400); }
else fail("удаление: нет кнопки подтверждения");
const qAfter = calls.filter((c) => c === "GET /webapp/api/queue").length;
const busy = doc.getElementById("busy");
const delBody = bodies.filter((b) => b.includes("entity_type")).slice(-1)[0] || "";
if (delBody.includes("platform")) ok("удаление: платформенное (platform в запросе)");
else fail(`удаление: платформа НЕ передана (body=${delBody.slice(0, 80)})`);
if (qAfter > qBefore) ok("удаление: очередь перезагрузилась");
else fail("удаление: очередь не перезагрузилась");
if (busy && busy.style.display === "none") ok("удаление: спиннер погас (unbusy)");
else fail("удаление: спиннер не погас — GUI зависнет");

// 3.5 Экран «Действия»: кнопка восстановления удалённых постов
doc.querySelector('#nav button[data-view="actions"]').click();
await wait(250);
if (doc.querySelector('[data-act="queue-restore-all"]')) ok("действия: кнопка «Вернуть удалённые посты» есть");
else fail("нет кнопки восстановления постов");

// 4. Папки: список корней и «добавить папку» шлёт корректный payload
doc.querySelector('#nav button[data-view="folders"]').click();
await wait(250);
const addBtn = doc.querySelector('[data-act="folder-add"]');
if (addBtn) {
  const before = calls.length;
  addBtn.click();
  await wait(250);
  const post = calls.slice(before).find((c) => c === "POST /webapp/api/roots");
  if (post) ok("папки: «добавить» сохраняет корень (POST /roots)");
  else fail("папки: кнопка «добавить» не отправила POST /roots");
} else {
  fail("папки: нет кнопки «добавить папку»");
}
const qInput = doc.getElementById("folder-q");
const qBtn = doc.querySelector('[data-act="folder-search"]');
if (qInput && qBtn) {
  qInput.value = "готов";
  qInput.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
  qBtn.click();
  await wait(250);
  const found = calls.some((c) => c.includes("/browse/search"));
  const results = doc.querySelectorAll(".search-list .row").length;
  if (found && results >= 1) ok(`поиск папок: работает (${results} результат)`);
  else fail(`поиск папок: запрос=${found}, результатов=${results}`);
} else {
  fail("поиск папок: нет поля ввода");
}

// 5. Итог по JS-ошибкам
if (jsErrors.length) fail("JS-ошибки: " + jsErrors.join(" | "));
else ok("JS-ошибок нет");

console.log(process.exitCode ? "GUI-ПРОВЕРКА ПРОВАЛЕНА" : "GUI-ПРОВЕРКА ПРОЙДЕНА");
