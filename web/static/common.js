// Shared helpers: top bar, theme, API access, formatting, party colours, a small SVG line chart.

const PAGES = [
  ["index.html", "Overview"],
  ["explorer.html", "Data & speeches"],
  ["results.html", "Results"],
  ["board.html", "Board"],
  ["slides.html", "Slides"],
];

function topbar() {
  const here = location.pathname.split("/").pop() || "index.html";
  const bar = document.createElement("header");
  bar.className = "topbar";
  bar.innerHTML = `<div class="in">
    <a class="brand" href="index.html">Heat Without Debate?</a>
    <nav>${PAGES.map(([h, t]) => `<a href="${h}" class="${h === here ? "on" : ""}">${t}</a>`).join("")}</nav>
    <button class="btn" id="theme-btn" title="Toggle light / dark">◐</button></div>`;
  document.body.prepend(bar);
  bar.querySelector("#theme-btn").onclick = () => {
    const dark = document.documentElement.dataset.theme
      ? document.documentElement.dataset.theme === "dark"
      : matchMedia("(prefers-color-scheme: dark)").matches;
    const next = dark ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("theme", next); } catch (e) {}
    window.dispatchEvent(new Event("themechange"));
  };
}
try { const t = localStorage.getItem("theme"); if (t) document.documentElement.dataset.theme = t; } catch (e) {}
document.addEventListener("DOMContentLoaded", topbar);

// API: retries while the server is still loading the corpus (HTTP 503 + loading)
async function api(name, params = {}, onWait) {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v != null));
  for (;;) {
    const r = await fetch(`/api/${name}?${qs}`);
    const d = await r.json();
    if (r.status === 503 && d.loading) { onWait && onWait(); await new Promise(s => setTimeout(s, 2000)); continue; }
    if (d.error) throw new Error(d.error);
    return d;
  }
}

const fmt = {
  int: v => v == null ? "–" : Math.round(v).toLocaleString("en-US"),
  pct: (v, d = 2) => v == null ? "–" : (v * 100).toFixed(d) + " %",
  num: (v, d = 2) => v == null ? "–" : (+v).toFixed(d),
  month: m => { const [y, mo] = m.split("-"); return new Date(+y, +mo - 1, 1).toLocaleString("en-GB", { month: "short", year: "numeric" }); },
};
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// Fixed party -> colour mapping (colour follows the entity, never its rank).
// CDU/CSU uses the primary ink (its conventional black); others use palette slots.
const PARTY_VAR = {
  "CDU/CSU": "--ink", "SPD": "--s8", "GRÜNE": "--s6", "FDP": "--s4", "AfD": "--s1",
  "DIE LINKE": "--s5", "BSW": "--s7", "fraktionslos": "--s3", "parteilos": "--ink-2", "": "--ink-2",
};
const PARTY_ORDER = ["CDU/CSU", "SPD", "GRÜNE", "FDP", "AfD", "DIE LINKE", "BSW", "fraktionslos", "parteilos"];
const cssVar = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const partyColor = p => `var(${PARTY_VAR[p] || "--ink-2"})`;
const partyTag = p => `<span class="tag party" style="--c:${partyColor(p)}">${esc(p || "no party")}</span>`;

function rolling(values, w = 12) {
  // trailing mean over the last w months, ignoring missing months; needs >= w/2 values
  return values.map((_, i) => {
    const win = values.slice(Math.max(0, i - w + 1), i + 1).filter(v => v != null);
    return win.length >= w / 2 ? win.reduce((a, b) => a + b, 0) / win.length : null;
  });
}

// ---------------------------------------------------------------- line chart
// lineChart(el, {x: [months], series: [{name, values, color, width, dash}], yFmt, height,
//               onClick(month), group}) -> {update(opts)}
const chartGroups = {};
function lineChart(el, opts) {
  el.classList.add("chart");
  el.innerHTML = "";
  const svgNS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNS, "svg");
  const tip = document.createElement("div");
  tip.className = "tip";
  el.append(svg, tip);
  let o = opts, W = 0, xs, ys, M;
  const H = () => o.height || 180;
  const pad = { l: 46, r: 12, t: 8, b: 22 };

  function niceTicks(lo, hi, n = 4) {
    const span = hi - lo || 1, step0 = span / n, mag = 10 ** Math.floor(Math.log10(step0));
    const step = [1, 2, 2.5, 5, 10].map(s => s * mag).find(s => span / s <= n) || mag * 10;
    const t = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-12; v += step) t.push(+v.toFixed(10));
    return t;
  }

  function draw() {
    W = el.clientWidth;
    if (!W) return;
    const h = H(), x = o.x, n = x.length;
    const vis = o.series.filter(s => !s.hidden);
    const all = vis.flatMap(s => s.values).filter(v => v != null);
    let lo = Math.min(...all), hi = Math.max(...all);
    if (o.zero !== false && lo > 0) lo = 0;
    if (!all.length) { lo = 0; hi = 1; }
    const yt = niceTicks(lo, hi);
    lo = Math.min(lo, yt[0]); hi = Math.max(hi, yt[yt.length - 1]);
    xs = i => pad.l + (i / Math.max(n - 1, 1)) * (W - pad.l - pad.r);
    ys = v => pad.t + (1 - (v - lo) / (hi - lo || 1)) * (h - pad.t - pad.b);
    M = { n };
    svg.setAttribute("viewBox", `0 0 ${W} ${h}`);
    svg.setAttribute("height", h);
    const yf = o.yFmt || (v => v);
    let s = "";
    for (const v of yt) {
      s += `<line x1="${pad.l}" x2="${W - pad.r}" y1="${ys(v)}" y2="${ys(v)}" stroke="var(--grid)" stroke-width="1"/>`;
      s += `<g class="tick"><text x="${pad.l - 6}" y="${ys(v) + 4}" text-anchor="end">${yf(v)}</text></g>`;
    }
    if (lo < 0 && hi > 0) s += `<line x1="${pad.l}" x2="${W - pad.r}" y1="${ys(0)}" y2="${ys(0)}" stroke="var(--axis)"/>`;
    // year ticks
    const every = W < 500 ? 4 : W < 900 ? 2 : 1;
    x.forEach((m, i) => {
      if (m.endsWith("-01")) {
        const yr = +m.slice(0, 4);
        if (yr % every) return;
        s += `<g class="tick"><line x1="${xs(i)}" x2="${xs(i)}" y1="${h - pad.b}" y2="${h - pad.b + 4}" stroke="var(--axis)"/>
              <text x="${xs(i)}" y="${h - 6}" text-anchor="middle">${W < 500 ? "’" + String(yr).slice(2) : yr}</text></g>`;
      }
    });
    s += `<line x1="${pad.l}" x2="${W - pad.r}" y1="${h - pad.b}" y2="${h - pad.b}" stroke="var(--axis)"/>`;
    for (const se of vis) {
      let d = "", pen = false;
      se.values.forEach((v, i) => {
        if (v == null) { pen = false; return; }
        d += `${pen ? "L" : "M"}${xs(i).toFixed(1)},${ys(v).toFixed(1)}`;
        pen = true;
      });
      s += `<path d="${d}" fill="none" stroke="${se.color}" stroke-width="${se.width || 2}" stroke-linejoin="round"
            stroke-linecap="round" ${se.dash ? `stroke-dasharray="${se.dash}"` : ""} opacity="${se.faint ? 0.35 : 1}"/>`;
    }
    for (const b of o.marks || []) {   // vertical event marks: {month, label}
      const i = x.indexOf(b.month);
      if (i < 0) continue;
      s += `<line x1="${xs(i)}" x2="${xs(i)}" y1="${pad.t}" y2="${h - pad.b}" stroke="var(--ink-2)" stroke-dasharray="2 3"/>
            <text x="${xs(i) + 4}" y="${pad.t + 10}" font-size="11" fill="var(--ink-2)">${esc(b.label)}</text>`;
    }
    s += `<g class="hover" style="display:none"><line class="cx" y1="${pad.t}" y2="${h - pad.b}" stroke="var(--ink-2)" stroke-width="1"/>
          ${vis.map(se => `<circle r="4" fill="${se.color}" stroke="var(--surface)" stroke-width="2"/>`).join("")}</g>`;
    s += `<rect class="hit" x="${pad.l}" y="0" width="${W - pad.l - pad.r}" height="${h}" fill="transparent"
          style="cursor:${o.onClick ? "pointer" : "default"}"/>`;
    svg.innerHTML = s;
  }

  function show(i) {
    const g = svg.querySelector(".hover");
    if (!g) return;
    if (i == null) { g.style.display = "none"; tip.style.display = "none"; return; }
    const vis = o.series.filter(s => !s.hidden);
    g.style.display = "";
    g.querySelector(".cx").setAttribute("x1", xs(i));
    g.querySelector(".cx").setAttribute("x2", xs(i));
    g.querySelectorAll("circle").forEach((c, k) => {
      const v = vis[k].values[i];
      c.style.display = v == null ? "none" : "";
      if (v != null) { c.setAttribute("cx", xs(i)); c.setAttribute("cy", ys(v)); }
    });
    const yf = o.tipFmt || o.yFmt || (v => v);
    tip.innerHTML = `<div class="muted">${fmt.month(o.x[i])}</div>` + vis.map(se =>
      `<div class="row"><span class="sw" style="background:${se.color}"></span>${esc(se.name)}<b>${se.values[i] == null ? "no sitting" : yf(se.values[i])}</b></div>`
    ).join("") + (o.onClick ? `<div class="muted small">click: speeches of this month</div>` : "");
    tip.style.display = "block";
    const tx = xs(i) + 12, tw = tip.offsetWidth;
    tip.style.left = (tx + tw > W ? xs(i) - tw - 12 : tx) + "px";
    tip.style.top = "4px";
  }

  const idxAt = ev => {
    const r = svg.getBoundingClientRect();
    const px = (ev.clientX - r.left) * (W / r.width);
    return Math.max(0, Math.min(M.n - 1, Math.round((px - pad.l) / (W - pad.l - pad.r) * (M.n - 1))));
  };
  const peers = () => (o.group ? chartGroups[o.group] : [api_]);
  svg.addEventListener("mousemove", ev => { const i = idxAt(ev); peers().forEach(c => c._show(i)); });
  svg.addEventListener("mouseleave", () => peers().forEach(c => c._show(null)));
  svg.addEventListener("click", ev => o.onClick && o.onClick(o.x[idxAt(ev)]));

  const api_ = { update(n) { o = { ...o, ...n }; draw(); }, _show: show };
  if (o.group) (chartGroups[o.group] ||= []).push(api_);
  new ResizeObserver(draw).observe(el);
  window.addEventListener("themechange", draw);
  draw();
  return api_;
}

// sortable table from columns + rows
function renderTable(el, columns, rows) {
  let sortCol = -1, asc = true;
  const isNum = c => rows.every(r => r[c] == null || typeof r[c] === "number");
  const draw = () => {
    const rs = sortCol < 0 ? rows : [...rows].sort((a, b) => {
      const x = a[sortCol], y = b[sortCol];
      if (x == null) return 1; if (y == null) return -1;
      return (x > y ? 1 : x < y ? -1 : 0) * (asc ? 1 : -1);
    });
    el.innerHTML = `<div class="tbl-wrap"><table><thead><tr>${columns.map((c, i) =>
      `<th data-i="${i}">${esc(c)}${i === sortCol ? (asc ? " ▲" : " ▼") : ""}</th>`).join("")}</tr></thead>
      <tbody>${rs.map(r => `<tr>${r.map((v, i) => `<td class="${isNum(i) ? "n" : ""}">${esc(v)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    el.querySelectorAll("th").forEach(th => th.onclick = () => {
      const i = +th.dataset.i; asc = i === sortCol ? !asc : true; sortCol = i; draw();
    });
  };
  draw();
}
