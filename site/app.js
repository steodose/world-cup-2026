"use strict";

const STAGES = [
  { key: "round_of_32", label: "R32" },
  { key: "round_of_16", label: "R16" },
  { key: "quarter_finals", label: "QF" },
  { key: "semi_finals", label: "SF" },
  { key: "final", label: "Final" },
  { key: "champion", label: "Champion" },
];

function pct(p) {
  const v = p * 100;
  if (v <= 0) return { text: "—", zero: true };
  if (v < 0.1) return { text: "<0.1%", zero: false };
  if (v >= 10) return { text: v.toFixed(0) + "%", zero: false };
  return { text: v.toFixed(1) + "%", zero: false };
}

// Simulations table: always one decimal, regardless of magnitude.
function pct1(p) {
  const v = p * 100;
  if (v <= 0) return { text: "—", zero: true };
  if (v < 0.1) return { text: "<0.1%", zero: false };
  return { text: v.toFixed(1) + "%", zero: false };
}

// Heatmap background for a probability cell (white -> amber).
function heat(p) {
  const a = Math.pow(Math.min(p, 1), 0.7) * 0.9; // perceptual boost for small p
  return `rgba(217, 119, 6, ${a.toFixed(3)})`;
}

function el(tag, cls, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html != null) e.innerHTML = html;
  return e;
}

function flag(team) {
  const img = el("img", "flag");
  img.crossOrigin = "anonymous";   // ESPN CDN sends ACAO:* -> canvas-safe for PNG export
  img.src = team.logo;
  img.alt = team.name;
  img.onerror = () => { img.style.visibility = "hidden"; };
  return img;
}

/* ---------------- Group phase ---------------- */
function renderGroups(groups) {
  const grid = document.getElementById("group-grid");
  grid.innerHTML = "";
  for (const g of groups) {
    const card = el("div", "group-card");
    card.appendChild(el("h3", null, "Group " + g.letter));
    for (const t of g.teams) {
      const row = el("div", "team-row");
      row.appendChild(flag(t));

      const info = el("div");
      info.appendChild(el("div", "team-name", t.name));
      info.appendChild(el("div", "team-sub",
        `Rank ${t.rank} · ${t.proj_points.toFixed(1)} xPts · Win Group: ${pct(t.win_group).text}`));
      row.appendChild(info);

      const cell = el("div", "advance-cell");
      const bar = el("div", "bar");
      const span = el("span");
      span.style.width = (t.advance * 100).toFixed(1) + "%";
      bar.appendChild(span);
      bar.appendChild(el("i", null, pct(t.advance).text));
      cell.appendChild(bar);
      row.appendChild(cell);

      card.appendChild(row);
    }
    grid.appendChild(card);
  }
}

/* ---------------- Knockout table ---------------- */
let TEAMS = [];
let sortKey = "champion";
let sortDir = -1;

function renderKnockout() {
  const table = document.getElementById("ko-table");
  const thead = table.querySelector("thead");
  const tbody = table.querySelector("tbody");

  const cols = [
    { key: "rank", label: "#", sort: false },
    { key: "name", label: "Team", sort: true },
    { key: "group", label: "Grp", sort: true },
    { key: "rating", label: "Rating", sort: true },
    ...STAGES.map((s) => ({ key: s.key, label: s.label, sort: true })),
  ];

  // header
  const tr = el("tr");
  for (const c of cols) {
    const th = el("th", c.key === sortKey ? "sorted" : null);
    th.textContent = c.label;
    if (c.key === sortKey) {
      th.appendChild(el("span", "arrow", sortDir < 0 ? "▼" : "▲"));
    }
    if (c.sort) {
      th.onclick = () => {
        if (sortKey === c.key) sortDir = -sortDir;
        else { sortKey = c.key; sortDir = c.key === "name" || c.key === "group" ? 1 : -1; }
        renderKnockout();
      };
    } else {
      th.style.cursor = "default";
    }
    tr.appendChild(th);
  }
  thead.innerHTML = "";
  thead.appendChild(tr);

  // sort
  const sorted = [...TEAMS].sort((a, b) => {
    let av = a[sortKey], bv = b[sortKey];
    if (typeof av === "string") return av.localeCompare(bv) * sortDir;
    return (av - bv) * sortDir;
  });

  // body
  tbody.innerHTML = "";
  sorted.forEach((t, i) => {
    const row = el("tr");

    const rk = el("td"); rk.appendChild(el("span", "cell-rank", String(i + 1)));
    row.appendChild(rk);

    const tdTeam = el("td");
    const wrap = el("div", "cell-team");
    wrap.appendChild(flag(t));
    wrap.appendChild(el("span", "nm", t.name));
    tdTeam.appendChild(wrap);
    row.appendChild(tdTeam);

    row.appendChild(el("td", "cell-group", t.group));
    row.appendChild(el("td", "cell-rating", String(t.rating)));

    for (const s of STAGES) {
      const p = t[s.key];
      const info = pct1(p);
      const td = el("td");
      const div = el("div", "prob" + (info.zero ? " zero" : ""), info.text);
      if (!info.zero) div.style.background = heat(p);
      td.appendChild(div);
      row.appendChild(td);
    }
    tbody.appendChild(row);
  });
}

/* ---------------- Matches ---------------- */
let MATCHES = [];

function fmtDate(iso) {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-US",
    { weekday: "short", month: "short", day: "numeric" });
}

function stackedBar(m) {
  const bar = el("div", "m-bar");
  const segs = [["seg-a", m.p_a], ["seg-d", m.p_draw], ["seg-b", m.p_b]];
  for (const [cls, p] of segs) {
    const s = el("div", "seg " + cls);
    s.style.width = (p * 100).toFixed(1) + "%";
    if (p >= 0.08) s.textContent = Math.round(p * 100) + "%";
    s.title = Math.round(p * 100) + "%";
    bar.appendChild(s);
  }
  return bar;
}

function matchCard(m) {
  const aWin = m.played && m.score_a > m.score_b;
  const bWin = m.played && m.score_b > m.score_a;

  const row = el("div", "match");

  const teamA = el("div", "m-team m-team-a" + (aWin ? " win" : ""));
  const aInfo = el("div", "m-name-wrap");
  aInfo.appendChild(el("span", "m-name", m.team_a.name));
  aInfo.appendChild(el("span", "m-xg", m.xg_a.toFixed(1) + " xG"));
  teamA.appendChild(aInfo);
  teamA.appendChild(flag(m.team_a));
  row.appendChild(teamA);

  if (m.played) {
    row.appendChild(el("div", "m-score", `${m.score_a}–${m.score_b}`));
  } else {
    row.appendChild(stackedBar(m));
  }

  const teamB = el("div", "m-team m-team-b" + (bWin ? " win" : ""));
  teamB.appendChild(flag(m.team_b));
  const bInfo = el("div", "m-name-wrap");
  bInfo.appendChild(el("span", "m-name", m.team_b.name));
  bInfo.appendChild(el("span", "m-xg", m.xg_b.toFixed(1) + " xG"));
  teamB.appendChild(bInfo);
  row.appendChild(teamB);

  const card = el("div", "match-card" + (m.played ? " is-played" : ""));
  card.appendChild(row);
  const tag = m.played ? "FT" : "Group " + m.group;
  card.appendChild(el("div", "m-meta", `${m.venue} · ${tag}`));
  return card;
}

function renderMatches(matches) {
  const wrap = document.getElementById("match-list");
  if (!wrap) return;
  wrap.innerHTML = "";
  let curDate = null;
  for (const m of matches) {
    if (m.date !== curDate) {
      curDate = m.date;
      wrap.appendChild(el("div", "match-date", fmtDate(m.date)));
    }
    wrap.appendChild(matchCard(m));
  }
}

/* ---------------- Tabs + boot ---------------- */
function activateTab(name) {
  const tabs = document.querySelectorAll(".tab");
  let matched = false;
  tabs.forEach((t) => {
    const on = t.dataset.tab === name;
    t.classList.toggle("is-active", on);
    matched = matched || on;
  });
  if (!matched) return;
  document.querySelectorAll(".panel").forEach((p) =>
    p.classList.toggle("is-active", p.id === name));
}

function setupTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.onclick = () => {
      history.replaceState(null, "", "#" + tab.dataset.tab);
      activateTab(tab.dataset.tab);
    };
  });
  if (location.hash) activateTab(location.hash.slice(1));
  window.addEventListener("hashchange", () => activateTab(location.hash.slice(1)));
}

/* ---------------- Downloads (PNG / CSV) ---------------- */
let DATE_STR = "";

function triggerBlobDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function capturePng(node, filename, btn, pad) {
  if (typeof html2canvas === "undefined") {
    alert("PNG export needs the rendering library, which didn't load.\n" +
          "Check your internet connection and reload.");
    return;
  }
  const label = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Rendering…";
  try {
    const canvas = await html2canvas(node, {
      scale: 3,                 // high-resolution for print/blog
      backgroundColor: "#ffffff",
      useCORS: true,
      logging: false,
      onclone: (doc) => {
        if (!pad) return;
        const clone = doc.getElementById(node.id);
        if (clone) clone.style.padding = "20px";
      },
    });
    await new Promise((resolve) =>
      canvas.toBlob((blob) => {
        if (blob) triggerBlobDownload(blob, filename);
        resolve();
      }, "image/png"));
  } catch (e) {
    alert("Couldn't render the image. PNG export works best when the page is " +
          "served over http (run `python -m http.server` in the site folder) " +
          "rather than opened directly as a file.\n\n" + e);
  } finally {
    btn.disabled = false;
    btn.textContent = label;
  }
}

function downloadSimsCsv() {
  const cols = [
    ["name", "Team"], ["group", "Group"], ["rating", "Rating"], ["rank", "Rank"],
    ["win_group", "WinGroup"], ["round_of_32", "ReachR32"],
    ["round_of_16", "ReachR16"], ["quarter_finals", "ReachQF"],
    ["semi_finals", "ReachSF"], ["final", "ReachFinal"], ["champion", "WinCup"],
  ];
  const esc = (v) => {
    const s = String(v);
    return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  };
  const sorted = [...TEAMS].sort((a, b) => b.champion - a.champion);
  const lines = [cols.map((c) => c[1]).join(",")];
  for (const t of sorted) {
    lines.push(cols.map(([key]) => {
      const v = t[key];
      // probability columns -> 4-decimal fractions; rating/rank/text as-is
      return (typeof v === "number" && v <= 1 && key !== "rating" && key !== "rank")
        ? esc(v.toFixed(4)) : esc(v);
    }).join(","));
  }
  const blob = new Blob([lines.join("\n") + "\n"], { type: "text/csv;charset=utf-8" });
  triggerBlobDownload(blob, `wc2026-simulations-${DATE_STR}.csv`);
}

function downloadMatchesCsv() {
  const cols = [
    ["match_no", "Match"], ["date", "Date"], ["venue", "Venue"],
    ["group", "Group"], ["a", "TeamA"], ["b", "TeamB"],
    ["p_a", "WinA"], ["p_draw", "Draw"], ["p_b", "WinB"],
    ["played", "Played"], ["sa", "ScoreA"], ["sb", "ScoreB"],
  ];
  const esc = (v) => {
    const s = String(v);
    return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  };
  const lines = [cols.map((c) => c[1]).join(",")];
  for (const m of MATCHES) {
    const flat = {
      match_no: m.match_no, date: m.date, venue: m.venue, group: m.group,
      a: m.team_a.name, b: m.team_b.name,
      p_a: m.p_a.toFixed(4), p_draw: m.p_draw.toFixed(4), p_b: m.p_b.toFixed(4),
      played: m.played ? 1 : 0,
      sa: m.played ? m.score_a : "", sb: m.played ? m.score_b : "",
    };
    lines.push(cols.map(([k]) => esc(flat[k])).join(","));
  }
  const blob = new Blob([lines.join("\n") + "\n"], { type: "text/csv;charset=utf-8" });
  triggerBlobDownload(blob, `wc2026-match-predictions-${DATE_STR}.csv`);
}

function setupDownloads() {
  const groupsBtn = document.getElementById("dl-groups-png");
  const simsPngBtn = document.getElementById("dl-sims-png");
  const simsCsvBtn = document.getElementById("dl-sims-csv");
  const matchesCsvBtn = document.getElementById("dl-matches-csv");
  if (matchesCsvBtn) matchesCsvBtn.onclick = downloadMatchesCsv;
  if (groupsBtn) groupsBtn.onclick = () =>
    capturePng(document.getElementById("group-grid"),
               `wc2026-group-stage-${DATE_STR}.png`, groupsBtn, true);
  if (simsPngBtn) simsPngBtn.onclick = () =>
    capturePng(document.getElementById("sims-table-wrap"),
               `wc2026-simulations-${DATE_STR}.png`, simsPngBtn, false);
  if (simsCsvBtn) simsCsvBtn.onclick = downloadSimsCsv;
}

async function boot() {
  setupTabs();
  let data = window.WC_DATA;   // present when data.js loaded (works from file://)
  if (!data) {
    try {
      const resp = await fetch("data.json", { cache: "no-store" });
      data = await resp.json();
    } catch (e) {
      document.getElementById("meta").textContent =
        "Could not load data — run `python run.py` to generate site/data.js.";
      return;
    }
  }

  const m = data.meta;
  const lockNote = (m.locked_group_matches || m.locked_ko_matches)
    ? ` · <b>${m.locked_group_matches + m.locked_ko_matches}</b> result(s) locked in`
    : "";
  document.getElementById("meta").innerHTML =
    `Last updated · ${m.generated}` + lockNote;
  const nsimsEl = document.getElementById("how-nsims");
  if (nsimsEl) nsimsEl.textContent = m.n_sims.toLocaleString();

  DATE_STR = (m.generated || "").split(" ")[0] ||
             new Date().toISOString().slice(0, 10);
  TEAMS = data.teams;
  MATCHES = data.matches || [];
  renderGroups(data.groups);
  renderMatches(MATCHES);
  renderKnockout();
  setupDownloads();
}

boot();
