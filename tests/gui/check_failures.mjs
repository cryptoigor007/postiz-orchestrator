// Проверка отказоустойчивости панели: все API отвечают 500 → UI не зависает,
// показывает ошибку, затем после восстановления API — снова рендерится.
// Запуск: node tests/gui/check_failures.mjs <URL-страницы>
import { JSDOM, VirtualConsole } from "jsdom";

const url = process.argv[2];
if (!url) {
  console.error("usage: node check_failures.mjs <page-url>");
  process.exit(2);
}
const html = await (await fetch(url)).text();
if (!html.includes('id="content"')) {
  console.error("страница не похожа на панель");
  process.exit(2);
}
const parsed = new URL(url);
const key = process.env.WEBAPP_ACCESS_KEY
  || ((parsed.pathname.match(/\/webapp\/k\/([^/]+)/) || [])[1] || "");
const apiBase = `${parsed.origin}/webapp/api`;

// заранее тянем реальные ответы (для фазы «восстановление»)
const real = {};
let failing = true;
for (const ep of ["version", "status", "queue", "roots", "browse", "calendar", "platforms",
                  "schedule_settings", "failed", "tail", "backlog", "metrics",
                  "manual/plan", "manual/uploads"]) {
  try {
    const r = await fetch(`${apiBase}/${ep}?key=${encodeURIComponent(key)}`,
                          { headers: { "X-Webapp-Key": key } });
    if (r.ok) real[ep] = await r.json();
  } catch { /* skip */ }
}

const jsErrors = [];
const fail = (m) => { console.error("❌ " + m); process.exitCode = 1; };
const ok = (m) => console.log("✓ " + m);
const vc = new VirtualConsole();
vc.on("jsdomError", (e) => jsErrors.push(String(e.message)));
for (const ev of ["log", "warn", "info", "debug"]) vc.on(ev, () => {});

const dom = new JSDOM(html, {
  runScripts: "dangerously",
  url: new URL(url).toString(),
  pretendToBeVisual: true,
  virtualConsole: vc,
  beforeParse(window) {
    window.confirm = () => true;
    window.fetch = (u, opts = {}) => {
      const s = String(u);
      const path = s.split("?")[0].replace(/^https?:\/\/[^/]+/, "");
      const ep = path.replace(/^\/webapp\/api\//, "");
      if (failing) {
        return Promise.resolve({ ok: false, status: 500,
          json: () => Promise.resolve({ error: "simulated 500" }),
          text: () => Promise.resolve('{"error":"simulated 500"}') });
      }
      if (real[ep] !== undefined) {
        return Promise.resolve({ ok: true, status: 200,
          json: () => Promise.resolve(real[ep]),
          text: () => Promise.resolve(JSON.stringify(real[ep])) });
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}),
                               text: () => Promise.resolve("{}") });
    };
  },
});

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const doc = dom.window.document;
await wait(500);

// Фаза 1: все API падают — экран должен показать ошибку, спиннер не завис
let viewsWithError = 0;
const views = [...doc.querySelectorAll("#nav button[data-view]")].map((b) => b.dataset.view);
for (const v of views) {
  const btn = doc.querySelector(`#nav button[data-view="${v}"]`);
  if (!btn) continue;
  btn.click();
  await wait(300);
  const text = (doc.getElementById("content").textContent || "").trim();
  if (/Ошибка|Error|500/.test(text)) viewsWithError++;
}
if (viewsWithError >= Math.min(5, views.length)) ok(`при сбое API экраны показывают ошибку (${viewsWithError}/${views.length})`);
else fail(`экраны не показали ошибку: ${viewsWithError}/${views.length}`);
const busy1 = doc.getElementById("busy");
if (!busy1 || busy1.style.display === "none") ok("спиннер не завис при сбое API");
else fail("спиннер завис (busy overlay виден) при сбое API");

// Фаза 2: API восстановились — клик «Обновить» возвращает данные
failing = false;
doc.querySelector('#nav button[data-view="queue"]').click();
await wait(200);
const refresh = doc.getElementById("btn-refresh");
if (refresh) refresh.click();
await wait(600);
const rows = doc.querySelectorAll(".q-row").length;
const text2 = (doc.getElementById("content").textContent || "").trim();
if (rows >= 1 || !/Ошибка|Error/.test(text2)) ok(`восстановление API: UI ожил (строк=${rows})`);
else fail(`после восстановления API UI не отрисовался: «${text2.slice(0, 60)}»`);

if (jsErrors.length) fail("JS-ошибки: " + jsErrors.join(" | "));
else ok("необработанных JS-ошибок нет");

console.log(process.exitCode ? "ПРОВЕРКА ОТКАЗОУСТОЙЧИВОСТИ ПРОВАЛЕНА" : "ПРОВЕРКА ОТКАЗОУСТОЙЧИВОСТИ ПРОЙДЕНА");
