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

// ---- Operations panel (display only). Read live from GitHub: the local runner's heartbeat (pushed every 5 minutes to
// the `runner-heartbeat` branch: each job's latest log and what it says, and the installed runner's SHA-256), main's
// runner.py (installed = main?) and the open alert issues. GitHub caches raw files for up to 5 minutes.
const REPO = "andreaskoul/test_trading_agent", RAW = `https://raw.githubusercontent.com/${REPO}`;
const JOBS = { archive: "News archive", weekly: "Weekly AI desks (Wednesday)", reconcile: "Broker reconcile and scoring", report: "Daily message to the owner",
  lifecycle: "Live fund session (decides and trades before the close)", prices: "Live price marks for the pages", r5: "Thesis-tree forecasts (research)",
  qshadow: "31-name research books (weekly)", spx: "S&P 500 AI books (weekly decision)", spxmark: "S&P 500 AI books (daily mark and booking)" };
const DAYN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const daysTxt = s => s === "0123456" ? "daily" : s === "01234" ? "Mon–Fri" : s === "12345" ? "Tue–Sat" : [...(s || "")].map(c => DAYN[+c]).join(", ");
async function sha256hex(buf) { const h = await crypto.subtle.digest("SHA-256", buf); return [...new Uint8Array(h)].map(b => b.toString(16).padStart(2, "0")).join(""); }
function jobState(e, now) {                       // [css class, text]
  const slot = e.slot, started = e.started;
  if (slot && (!started || started < slot))         // the latest slot has no log yet
    return (now - new Date(slot)) / 6e4 > e.late_min ? ["bad", "did not run (Mac asleep or off?)"] : ["", "due"];
  return { ok: ["ok", "ok"], "nothing to do": ["ok", "ok, nothing to do"], running: ["run", "running"], failed: ["bad", "failed (an issue was opened)"],
    "no result": ["bad", "no result: stopped without an end line"], unreadable: ["warn", "log unreadable"] }[e.status] || ["warn", e.status || "no log"];
}
function opsPanel(el) {
  const box = document.getElementById(el), now = new Date();
  const get = (u, kind) => fetch(u, { cache: "no-store" }).then(r => r.ok ? r[kind]() : null).catch(() => null);
  Promise.all([get(`${RAW}/runner-heartbeat/heartbeat.json`, "json"), get(`${RAW}/main/fund/local/runner.py`, "arrayBuffer"),
               get(`https://api.github.com/repos/${REPO}/issues?state=open&per_page=50`, "json")]).then(async ([hb, src, iss]) => {
    const parts = [], probs = [];
    if (!hb) { parts.push(`<span class="dot warn"></span>runner heartbeat unavailable`); probs.push(1); }
    else {
      const age = (now - new Date(hb.at)) / 6e4, cls = age > 60 ? "bad" : age > 20 ? "warn" : "ok";
      if (cls !== "ok" || !hb.enabled) probs.push(1);
      parts.push(`<span class="dot ${hb.enabled ? cls : "warn"}"></span>runner ${hb.enabled ? "" : "<b>disabled</b>, "}last heard ${age < 1 ? "just now" : Math.round(age) + " min ago"}`);
      if (hb.runner_sha256 && src) {
        const same = hb.runner_sha256 === await sha256hex(src);
        if (!same) probs.push(1);
        parts.push(same ? `<span class="dot ok"></span>installed runner = main` : `<span class="dot bad"></span><b>installed runner differs from main: re-run fund/local/install.sh</b>`);
      }
    }
    const J = hb && hb.jobs ? Object.entries(hb.jobs) : [];
    if (J.length) {
      const st = J.map(([k, e]) => [k, e, jobState(e, now)]), bad = st.filter(x => ["bad", "warn"].includes(x[2][0]));
      probs.push(...bad);
      parts.push(bad.length ? `<span class="dot bad"></span><b>${bad.map(x => esc(JOBS[x[0]] || x[0]) + ": " + x[2][1]).join("; ")}</b>` : `<span class="dot ok"></span>all ${J.length} scheduled jobs fine`);
    }
    if (Array.isArray(iss)) { const n = iss.filter(i => !i.pull_request).length;
      parts.push(`<span class="dot ${n ? "warn" : "ok"}"></span><a href="https://github.com/${REPO}/issues">${n} open alert${n === 1 ? "" : "s"}</a>`); }
    box.innerHTML = `<summary><b>Operations</b> · ${parts.join(" · ")} <span class="muted">(click for each job)</span></summary><div class="scroll" id="${el}-jobs"></div><div id="${el}-iss"></div>`;
    if (probs.length && store.get("fold:" + location.pathname + ":" + el) == null) box.open = true;     // a problem opens it, unless you chose
    box.addEventListener("toggle", () => store.set("fold:" + location.pathname + ":" + el, box.open ? "1" : "0"));
    if (J.length) table(`${el}-jobs`, [["Job", x => `<b>${esc(JOBS[x[0]] || x[0])}</b>`], ["Schedule (UTC)", x => `${daysTxt(x[1].days)} ${x[1].at}${x[1].every ? `–${x[1].until}, every ${x[1].every} min` : ""}`],
      ["Latest slot", x => (x[1].slot || "").replace("T", " ").slice(0, 16)], ["Latest run started", x => (x[1].started || "").replace("T", " ").slice(0, 16)],
      ["Result", x => `<span class="dot ${x[2][0]}"></span>${x[2][1]}`]], J.map(([k, e]) => [k, e, jobState(e, now)]));
    else document.getElementById(`${el}-jobs`).innerHTML = '<div class="empty">The installed runner does not report its jobs yet (re-run fund/local/install.sh after the merge that adds it).</div>';
    if (Array.isArray(iss) && iss.length) table(`${el}-iss`, [["Open alert", i => `<a href="${i.html_url}">${esc(i.title)}</a>`, "wrap"], ["Opened", i => i.created_at.slice(0, 10)]],
      iss.filter(i => !i.pull_request));
  });
}
