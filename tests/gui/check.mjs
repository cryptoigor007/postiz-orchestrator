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
const jsErrors = [];
const fail = (msg) => { console.error("❌ " + msg); process.exitCode = 1; };
const ok = (msg) => console.log("✓ " + msg);

// Реальные ответы API берём с живого сервера (кроме опасных POST)
const parsed = new URL(url);
const key = (parsed.pathname.match(/\/webapp\/k\/([^/]+)/) || [])[1] || "";
const apiBase = `${parsed.origin}/webapp/api`;
const realFixtures = {};
const GET_ENDPOINTS = ["version", "status", "roots", "browse", "calendar", "queue",
  "platforms", "schedule_settings", "failed", "tail", "backlog", "metrics",
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
  schedule_settings: { settings: {}, groups: {}, platforms: ["youtube", "telegram"],
    mode: "manual", effective: {} },
  failed: { items: [] },
  tail: { items: [] },
  backlog: { items: [] },
  metrics: {},
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
      const ep = path.replace(/^\/webapp\/api\//, "");
      if (ep === "roots" && opts.method === "POST") return response(fixtures.roots_post);
      if (ep.startsWith("queue/remove")) return response(fixtures["queue/remove"]);
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

// 2. Очередь: редактирование → выбор обложки
doc.querySelector('#nav button[data-view="queue"]').click();
await wait(250);
const rows = doc.querySelectorAll(".row").length;
const delBtns = doc.querySelectorAll('[data-act="queue-remove"]').length;
if (rows >= 2 && delBtns >= 1) ok(`очередь: строк ${rows}, кнопок удаления ${delBtns}`);
else fail(`очередь не отрисовалась (rows=${rows}, del=${delBtns})`);

doc.querySelector('[data-act="queue-edit"]').click();
await wait(80);
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
  const n = doc.querySelectorAll(".q-row").length;
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

// 3. Удаление: запрос ушёл, список обновился, оверлей погас
const qBefore = calls.filter((c) => c === "GET /webapp/api/queue").length;
doc.querySelector('[data-act="queue-remove"]').click();
await wait(350);
const qAfter = calls.filter((c) => c === "GET /webapp/api/queue").length;
const busy = doc.getElementById("busy");
if (calls.some((c) => c === "POST /webapp/api/queue/remove")) ok("удаление: запрос отправлен");
else fail("удаление: запрос НЕ отправлен");
if (qAfter > qBefore) ok("удаление: очередь перезагрузилась");
else fail("удаление: очередь не перезагрузилась");
if (busy && busy.style.display === "none") ok("удаление: спиннер погас (unbusy)");
else fail("удаление: спиннер не погас — GUI зависнет");

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
