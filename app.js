/* Daily Stoic — static, no framework. */
(() => {
  "use strict";

  const MONTHS = ["January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December"];
  const KEY_SAVED = "ds.saved";   // ["10-24", ...]
  const KEY_NOTES = "ds.notes";   // {"10-24": "text", ...}
  const main = document.getElementById("main");
  const toastEl = document.querySelector(".toast");

  let DATA = null;       // {version, months:[{month,name,theme,intro,entries:[...]}]}
  let ALL = [];          // flat, Jan 1 .. Dec 31 including Feb 29
  let BY_ID = new Map();
  let lastIndex = null;

  // ------------------------------------------------------------ utilities
  const pad = (n) => String(n).padStart(2, "0");
  const idOf = (m, d) => `${pad(m)}-${pad(d)}`;
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function roman(n) {
    const map = [[1000, "M"], [900, "CM"], [500, "D"], [400, "CD"], [100, "C"], [90, "XC"],
      [50, "L"], [40, "XL"], [10, "X"], [9, "IX"], [5, "V"], [4, "IV"], [1, "I"]];
    let out = "";
    for (const [v, s] of map) { while (n >= v) { out += s; n -= v; } }
    return out;
  }

  function todayId() {
    const t = new Date();               // local date, not UTC
    return idOf(t.getMonth() + 1, t.getDate());
  }

  function readJSON(key, fallback) {
    try { const v = JSON.parse(localStorage.getItem(key)); return v ?? fallback; } catch { return fallback; }
  }
  function writeJSON(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch { toast("Couldn't save on this device"); return false; }
  }
  const getSaved = () => new Set(readJSON(KEY_SAVED, []));
  const getNotes = () => readJSON(KEY_NOTES, {});

  let toastTimer;
  function toast(msg) {
    toastEl.textContent = msg;
    toastEl.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toastEl.hidden = true; }, 2200);
  }

  const ICON = {
    save: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3.5h12v17l-6-4.2-6 4.2z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>',
    saved: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3.5h12v17l-6-4.2-6 4.2z" fill="currentColor" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>',
    share: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 15V3.5M7.5 8 12 3.5 16.5 8M5 12.5v6.5a1.5 1.5 0 0 0 1.5 1.5h11a1.5 1.5 0 0 0 1.5-1.5v-6.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  };

  function setNav(which) {
    document.querySelectorAll("[data-nav]").forEach((a) => {
      if (a.dataset.nav === which) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
  }

  function dateLabel(e) { return `${MONTHS[e.month - 1]} ${e.day}`; }

  // ------------------------------------------------------------ views
  function renderDay(id, dir) {
    const e = BY_ID.get(id);
    if (!e) { location.replace("#/"); return; }
    const i = ALL.indexOf(e);
    const prev = ALL[(i - 1 + ALL.length) % ALL.length];
    const next = ALL[(i + 1) % ALL.length];
    const isToday = id === todayId();
    const saved = getSaved().has(id);
    const note = getNotes()[id] || "";
    const mo = DATA.months[e.month - 1];
    setNav(isToday ? "today" : "");
    document.title = `${e.title} · Daily Stoic`;

    main.innerHTML = `
      <article class="day enter ${dir ? (dir > 0 ? "from-right" : "from-left") : ""}" aria-labelledby="day-title">
        <span class="numeral" aria-hidden="true">${roman(e.day)}</span>
        <p class="dateline">
          <span>${isToday ? "Today, " : ""}${dateLabel(e)}</span><span class="sep" aria-hidden="true">&middot;</span>
          <a href="#/month/${e.month}">${esc(mo.theme)}</a>
        </p>
        <h1 id="day-title">${esc(e.title)}</h1>
        <blockquote class="quote">
          <p>${esc(e.quote)}</p>
          <footer>&mdash; ${esc(e.cite)}</footer>
        </blockquote>
        <p class="reflection">${esc(e.reflection)}</p>
        <section class="practice" aria-label="Practice for today">
          <span class="practice-label">For today</span>
          <p>${esc(e.practice)}</p>
        </section>
        <div class="actions">
          <button class="btn" type="button" data-act="save" aria-pressed="${saved}">${saved ? ICON.saved : ICON.save}<span>${saved ? "Saved" : "Save"}</span></button>
          <button class="btn" type="button" data-act="share">${ICON.share}<span>Share</span></button>
        </div>
        <div class="notes">
          <label for="note">Your notes <span class="status" aria-live="polite"></span></label>
          <textarea id="note" placeholder="What does this ask of you today?" spellcheck="true">${esc(note)}</textarea>
        </div>
        <nav class="pager" aria-label="Other days">
          <a class="prev" href="#/day/${prev.id}" rel="prev"><small>&larr; ${dateLabel(prev)}</small>${esc(prev.title)}</a>
          ${isToday ? "<span></span>" : `<a class="today" href="#/">Today</a>`}
          <a class="next" href="#/day/${next.id}" rel="next"><small>${dateLabel(next)} &rarr;</small>${esc(next.title)}</a>
        </nav>
      </article>`;

    lastIndex = i;
    wireDay(e);
  }

  function wireDay(e) {
    const saveBtn = main.querySelector('[data-act="save"]');
    saveBtn.addEventListener("click", () => {
      const s = getSaved();
      const on = !s.has(e.id);
      on ? s.add(e.id) : s.delete(e.id);
      writeJSON(KEY_SAVED, [...s].sort());
      saveBtn.setAttribute("aria-pressed", String(on));
      saveBtn.innerHTML = `${on ? ICON.saved : ICON.save}<span>${on ? "Saved" : "Save"}</span>`;
      toast(on ? "Saved" : "Removed from saved");
    });

    main.querySelector('[data-act="share"]').addEventListener("click", () => share(e));

    const ta = main.querySelector("#note");
    const status = main.querySelector(".notes .status");
    let t;
    ta.addEventListener("input", () => {
      status.textContent = "";
      clearTimeout(t);
      t = setTimeout(() => {
        const notes = getNotes();
        const v = ta.value;
        if (v.trim()) notes[e.id] = v; else delete notes[e.id];
        if (writeJSON(KEY_NOTES, notes)) status.textContent = "Saved";
      }, 500);
    });
  }

  async function share(e) {
    const url = `${location.origin}${location.pathname}#/day/${e.id}`;
    const text = `“${e.quote}”\n— ${e.cite}`;
    if (navigator.share) {
      try { await navigator.share({ title: `${e.title} · Daily Stoic`, text, url }); return; }
      catch (err) { if (err && err.name === "AbortError") return; }
    }
    try {
      await navigator.clipboard.writeText(`${text}\n${url}`);
      toast("Copied to clipboard");
    } catch {
      const ta = document.createElement("textarea");
      ta.value = `${text}\n${url}`; document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); toast("Copied to clipboard"); } catch { toast("Couldn't copy"); }
      ta.remove();
    }
  }

  function renderMonths() {
    setNav("months");
    document.title = "Months · Daily Stoic";
    const cur = new Date().getMonth() + 1;
    main.innerHTML = `
      <section class="months">
        <h1 class="page-title">The year</h1>
        <p class="lede">Twelve themes, one for each month. Every day pairs a passage from Marcus Aurelius, Epictetus or Seneca with a short reflection and something to practise.</p>
        <ol class="month-list">
          ${DATA.months.map((m) => `
            <li><a href="#/month/${m.month}" class="${m.month === cur ? "current" : ""}">
              <span class="mn" aria-hidden="true">${roman(m.month)}</span>
              <span class="name">${m.name}</span>
              <span class="theme">${esc(m.theme)}</span>
            </a></li>`).join("")}
        </ol>
        <p class="colophon">Quotations from George Long&rsquo;s translations of Marcus Aurelius and Epictetus and Richard M. Gummere&rsquo;s translation of Seneca, all in the public domain. <a href="#/about">About this book</a></p>
      </section>`;
  }

  function renderMonth(m) {
    const mo = DATA.months[m - 1];
    if (!mo) { location.replace("#/months"); return; }
    setNav("months");
    document.title = `${mo.name} · Daily Stoic`;
    const saved = getSaved();
    const tid = todayId();
    main.innerHTML = `
      <section class="month-head">
        <span class="numeral" aria-hidden="true">${roman(m)}</span>
        <h1 class="page-title">${mo.name}: ${esc(mo.theme)}</h1>
        <p class="intro">${esc(mo.intro)}</p>
        <ol class="day-list">
          ${mo.entries.map((e) => `
            <li><a href="#/day/${e.id}" class="${e.id === tid ? "is-today" : ""}" ${e.id === tid ? 'aria-current="date"' : ""}>
              <span class="dn">${e.day}</span>
              <span class="t">${esc(e.title)}${saved.has(e.id) ? '<span class="mark" aria-label="saved">&#9670;</span>' : ""}</span>
            </a></li>`).join("")}
        </ol>
        <nav class="pager" aria-label="Other months" style="margin-top:2rem">
          <a class="prev" href="#/month/${m === 1 ? 12 : m - 1}"><small>&larr; Previous</small>${MONTHS[(m + 10) % 12]}</a>
          <a class="today" href="#/months">All months</a>
          <a class="next" href="#/month/${m === 12 ? 1 : m + 1}"><small>Next &rarr;</small>${MONTHS[m % 12]}</a>
        </nav>
      </section>`;
  }

  function renderSaved() {
    setNav("saved");
    document.title = "Saved · Daily Stoic";
    const saved = [...getSaved()].filter((id) => BY_ID.has(id));
    const notes = getNotes();
    const noted = Object.keys(notes).filter((id) => BY_ID.has(id) && !saved.includes(id));
    const item = (id) => {
      const e = BY_ID.get(id);
      return `<li><a href="#/day/${id}"><span class="when">${dateLabel(e)}${notes[id] ? " &middot; has notes" : ""}</span>
        <span class="t">${esc(e.title)}</span><span class="q">${esc(e.quote)}</span></a></li>`;
    };
    main.innerHTML = `
      <section>
        <h1 class="page-title">Saved</h1>
        ${saved.length ? `<ol class="saved-list">${saved.map(item).join("")}</ol>`
          : `<p class="empty">Nothing saved yet. Tap Save on any day to keep it here.</p>`}
        ${noted.length ? `<h2 class="page-title" style="font-size:1.4rem;margin-top:2.2rem">Days with notes</h2>
          <ol class="saved-list">${noted.sort().map(item).join("")}</ol>` : ""}
        <div class="data-tools">
          <h2>Your notes and saved days</h2>
          <p>They live only on this device. Export a copy to back them up or move them to another phone.</p>
          <div class="row">
            <button class="btn" type="button" data-act="export">Export notes</button>
            <button class="btn" type="button" data-act="import">Import notes</button>
            <input type="file" accept="application/json,.json" hidden>
          </div>
        </div>
      </section>`;
    main.querySelector('[data-act="export"]').addEventListener("click", exportNotes);
    const file = main.querySelector('input[type="file"]');
    main.querySelector('[data-act="import"]').addEventListener("click", () => file.click());
    file.addEventListener("change", () => importNotes(file.files[0]));
  }

  function exportNotes() {
    const payload = { app: "daily-stoic", exported: new Date().toISOString(), saved: [...getSaved()], notes: getNotes() };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `daily-stoic-notes-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    toast("Notes exported");
  }

  async function importNotes(f) {
    if (!f) return;
    try {
      const data = JSON.parse(await f.text());
      if (!data || typeof data !== "object" || (!data.notes && !data.saved)) throw new Error("bad file");
      const notes = getNotes();
      let added = 0;
      for (const [id, text] of Object.entries(data.notes || {})) {
        if (!BY_ID.has(id) || typeof text !== "string" || !text.trim()) continue;
        if (!notes[id]) { notes[id] = text; added++; }
        else if (notes[id] !== text && !notes[id].includes(text)) { notes[id] = `${notes[id]}\n\n${text}`; added++; }
      }
      const s = getSaved();
      (data.saved || []).forEach((id) => BY_ID.has(id) && s.add(id));
      writeJSON(KEY_NOTES, notes);
      writeJSON(KEY_SAVED, [...s].sort());
      toast(`Imported ${added} note${added === 1 ? "" : "s"}`);
      renderSaved();
    } catch {
      toast("That file isn't a Daily Stoic export");
    }
  }

  function renderAbout() {
    setNav("");
    document.title = "About · Daily Stoic";
    main.innerHTML = `
      <section class="about">
        <h1 class="page-title">About this book</h1>
        <p>Daily Stoic gives you one short passage for each day of the year, including February 29. The passages come from three Roman Stoics:</p>
        <ul>
          <li>Marcus Aurelius, <em>Meditations</em>, translated by George Long</li>
          <li>Epictetus, <em>Discourses</em> (selection) and <em>Enchiridion</em>, translated by George Long</li>
          <li>Seneca, <em>Moral Letters to Lucilius</em>, translated by Richard M. Gummere</li>
        </ul>
        <p>Every quotation was pulled from those public-domain texts by script, word for word. The titles, reflections and practices are original. This app is not affiliated with any other book of a similar name.</p>
        <p>It works without a connection once opened. To keep it on your phone, use your browser&rsquo;s <em>Add to Home Screen</em>. Notes and saved days stay on your device.</p>
        <p class="colophon">Edition ${esc(DATA.version)}</p>
      </section>`;
  }

  // ------------------------------------------------------------ routing
  function route() {
    const h = location.hash.replace(/^#\/?/, "");
    const [a, b] = h.split("/");
    let dir = 0;
    if (a === "day" && b) {
      const e = BY_ID.get(b);
      if (e && lastIndex !== null) {
        const i = ALL.indexOf(e);
        dir = (i === lastIndex + 1 || (lastIndex === ALL.length - 1 && i === 0)) ? 1
          : (i === lastIndex - 1 || (lastIndex === 0 && i === ALL.length - 1)) ? -1 : 0;
      }
      renderDay(b, dir);
    } else if (a === "months") renderMonths();
    else if (a === "month" && b) renderMonth(parseInt(b, 10));
    else if (a === "saved") renderSaved();
    else if (a === "about") renderAbout();
    else renderDay(todayId(), 0);
    if (dir === 0) window.scrollTo(0, 0); else window.scrollTo({ top: 0 });
  }

  function step(delta) {
    const cur = currentDay();
    if (!cur) return;
    const i = ALL.indexOf(cur);
    const n = ALL[(i + delta + ALL.length) % ALL.length];
    location.hash = `#/day/${n.id}`;
  }

  function currentDay() {
    const h = location.hash.replace(/^#\/?/, "");
    const [a, b] = h.split("/");
    if (a === "day") return BY_ID.get(b);
    if (!a) return BY_ID.get(todayId());
    return null;
  }

  // keyboard
  document.addEventListener("keydown", (ev) => {
    if (ev.target.closest("textarea, input")) return;
    if (ev.altKey || ev.ctrlKey || ev.metaKey) return;
    if (ev.key === "ArrowRight") step(1);
    else if (ev.key === "ArrowLeft") step(-1);
    else if (ev.key === "t" || ev.key === "T") location.hash = "#/";
  });

  // swipe left / right on the day view
  let sx = 0, sy = 0, st = 0;
  main.addEventListener("touchstart", (ev) => {
    if (ev.touches.length !== 1 || ev.target.closest("textarea")) { st = 0; return; }
    sx = ev.touches[0].clientX; sy = ev.touches[0].clientY; st = Date.now();
  }, { passive: true });
  main.addEventListener("touchend", (ev) => {
    if (!st || !currentDay()) return;
    const dx = ev.changedTouches[0].clientX - sx;
    const dy = ev.changedTouches[0].clientY - sy;
    if (Date.now() - st < 700 && Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.6) step(dx < 0 ? 1 : -1);
    st = 0;
  }, { passive: true });

  // ------------------------------------------------------------ boot
  async function boot() {
    try {
      const res = await fetch("data/entries.json", { cache: "no-cache" });
      DATA = await res.json();
    } catch {
      main.innerHTML = '<p class="loading">Couldn&rsquo;t open the book. Check your connection and reload.</p>';
      return;
    }
    ALL = DATA.months.flatMap((m) => m.entries);
    BY_ID = new Map(ALL.map((e) => [e.id, e]));
    window.addEventListener("hashchange", route);
    route();
  }

  if ("serviceWorker" in navigator && location.protocol !== "file:") {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("sw.js").catch(() => {});
    });
  }

  boot();
})();
