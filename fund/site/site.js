// Shared formatting and layout helpers for every page of the fund site (display only: nothing here changes data).
const fmt = (v, d = 2) => v == null ? "" : Number(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const pct = v => v == null ? "" : `<span class="${v >= 0 ? "pos" : "neg"}">${(v * 100).toFixed(2)}%</span>`;
const usd = v => v == null ? "" : `<span class="${v >= 0 ? "pos" : "neg"}">${v < 0 ? "−" : ""}$${fmt(Math.abs(v), 0)}</span>`;
const wt = v => v == null ? "" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${(Math.abs(v) * 100).toFixed(2)}%`;
const esc = s => (s ?? "").toString().replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
const clamp = t => t ? `<div class="clamp" title="${t.replace(/"/g, "&quot;")}">${t}</div>` : "";   // t is already esc()-ed
const store = { get: k => { try { return localStorage.getItem(k); } catch (e) { return null; } },
                set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} } };
const PAL = ["#2c5aa0", "#c0392b", "#1a7f4b", "#8e44ad", "#d35400", "#16a085", "#7f8c8d", "#b8860b", "#e84393", "#00a8ff", "#6c5ce7"];

// dates are ISO strings (YYYY-MM-DD); arithmetic at noon UTC so no time zone moves a day
const addDays = (d0, n) => { const t = new Date(d0 + "T12:00:00Z"); t.setUTCDate(t.getUTCDate() + n); return t.toISOString().slice(0, 10); };
const daysBetween = (a, b) => Math.round((new Date(b + "T12:00:00Z") - new Date(a + "T12:00:00Z")) / 864e5);
const today = () => new Date().toISOString().slice(0, 10);
const dlong = d => d ? new Date(d + "T12:00:00Z").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }) : "";
const weekday = x => ![0, 6].includes(new Date(x + "T12:00:00Z").getUTCDay());

function table(el, cols, rows, rowAttr, empty = "None.") {
  const box = typeof el === "string" ? document.getElementById(el) : el;
  if (!rows.length) { box.innerHTML = `<div class="empty">${empty}</div>`; return; }
  box.innerHTML = `<table><thead><tr>${cols.map(c => `<th>${c[0]}</th>`).join("")}</tr></thead><tbody>${
    rows.map(r => `<tr ${rowAttr ? rowAttr(r) : ""}>${cols.map(c => `<td class="${c[2] || ""}">${c[1](r)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}

// Progress to a decision: the bar is filled from start to today; a tick marks each registered check.
function prog(start, end, ticks = []) {
  const span = daysBetween(start, end), f = x => Math.max(0, Math.min(1, daysBetween(start, x) / span)) * 100;
  return `<div class="prog" title="${dlong(start)} → ${dlong(end)}"><i style="width:${f(today()).toFixed(1)}%"></i>${
    ticks.map(t => `<b style="left:calc(${f(t).toFixed(1)}% - 1px)" title="${dlong(t)}"></b>`).join("")}</div>`;
}

// The scorer's gate report is markdown: render its paragraphs and pipe tables as written (escaped; bold kept).
function mdLite(src) {
  const inline = s => esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`(.+?)`/g, "<code>$1</code>");
  const out = [], L = src.split("\n");
  for (let i = 0; i < L.length; i++) {
    const s = L[i].trim();
    if (!s || /^#/.test(s)) continue;                   // the page gives its own heading
    if (s.startsWith("|")) {
      const rows = [];
      for (; i < L.length && L[i].trim().startsWith("|"); i++) rows.push(L[i].trim().replace(/^\||\|$/g, "").split("|").map(c => c.trim()));
      i--;
      const body = rows.filter((r, j) => j > 0 && !r.every(c => /^:?-+:?$/.test(c)));
      out.push(`<div class="scroll"><table><thead><tr>${rows[0].map(c => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>${
        body.map(r => `<tr>${r.map((c, j) => `<td class="${j ? "n" : "wrap"}">${inline(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`);
    } else out.push(`<p>${inline(s)}</p>`);
  }
  return out.join("");
}

const lineOpts = (dp = 2) => ({ maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
  plugins: { legend: { position: "bottom", labels: { boxWidth: 10, padding: 6, font: { size: 10 } } },
    tooltip: { itemSort: (a, b) => b.parsed.y - a.parsed.y, callbacks: { label: c => `${c.dataset.label}: ${(c.parsed.y * 100).toFixed(dp)}%` } } },
  scales: { x: { ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } }, y: { ticks: { callback: v => (v * 100).toFixed(1) + "%" } } } });

// Collapsible tables: each <details class="fold"> remembers whether you left it open, and its heading shows how
// many rows its table has. Call once after the page's sections exist.
function folds() {
  document.querySelectorAll("details.fold").forEach(d => {
    const key = "fold:" + location.pathname + ":" + d.id;
    const v = store.get(key); if (v != null) d.open = v === "1";
    d.addEventListener("toggle", () => store.set(key, d.open ? "1" : "0"));
    const cnt = d.querySelector(":scope > summary .cnt");
    if (!cnt) return;
    const upd = () => { const n = d.querySelectorAll("tbody tr").length, s = n ? `(${n} row${n === 1 ? "" : "s"})` : "";
      if (cnt.textContent !== s) cnt.textContent = s; };                // only on change: no observer loop
    new MutationObserver(upd).observe(d, { childList: true, subtree: true });
    upd();
  });
}
