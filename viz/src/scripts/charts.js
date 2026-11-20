import * as Plot from "@observablehq/plot";

const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const utc = (y, m = 1) => new Date(Date.UTC(y, m - 1, 1));
const toDate = (month) => utc(+month.slice(0, 4), +month.slice(5, 7));
const nextMonth = (month) => utc(+month.slice(0, 4), +month.slice(5, 7) + 1);
const fmt = (x, d = 2, unit = "") => (x == null ? "–" : `${x.toFixed(d)}${unit}`);
const int = (x) => (x == null ? "–" : Math.round(x).toLocaleString("en-US"));
const pct = (x) => (x == null ? null : x * 100);
const zscore = (rows, key) => {
  const v = rows.map((d) => d[key]).filter((x) => x != null);
  const mean = v.reduce((a, b) => a + b, 0) / v.length;
  const sd = Math.sqrt(v.reduce((a, b) => a + (b - mean) ** 2, 0) / v.length);
  return (x) => (x == null ? null : (x - mean) / sd);
};

export const PARTIES = ["CDU/CSU", "SPD", "GRÜNE", "FDP", "DIE LINKE", "AfD", "BSW"];
const PARTY_VAR = {
  "CDU/CSU": "--party-union", SPD: "--party-spd", "GRÜNE": "--party-gruene", FDP: "--party-fdp",
  "DIE LINKE": "--party-linke", AfD: "--party-afd", BSW: "--party-bsw",
};
// H1: one Bundestag series against public attention and the global physical signal
const SIGNALS = [
  { key: "share_a_12m", label: "Bundestag climate share", color: "--series-1" },
  { key: "trends_Klimawandel_12m", label: "Trends: Klimawandel", color: "--series-2" },
  { key: "anomaly_global_12m", label: "Temperature global", color: "--series-4" },
  { key: "events_global_12m", label: "Disasters global", color: "--series-3" },
];
// H1, as #12 sees them: linear trend and calendar-month means removed (07_data_understanding.detrend)
export const DETRENDED = [
  { key: "share_a", label: "Bundestag (a) climate share", color: "--series-1" },
  { key: "share_b", label: "Bundestag (b) main topic", color: "--series-1" },
  { key: "trends_Klimawandel", label: "Trends: Klimawandel", color: "--series-2" },
  { key: "anomaly_global", label: "Temperature global", color: "--series-4" },
  { key: "events_global", label: "Disasters global", color: "--series-3" },
];
const Z_MAX = 4; // detrended charts show ±4 SD; values beyond are clipped and labelled
// series shown in the join coverage strip, top to bottom
const COVERAGE = [
  ["sentences", "Bundestag sentences"], ["share_a", "attention (a)"], ["share_b", "attention (b)"],
  ["trends_Klimawandel", "Trends Klimawandel"], ["trends_Klima", "Trends Klima"],
  ["trends_Klimaschutz", "Trends Klimaschutz"], ["trends_Hitzewelle", "Trends Hitzewelle"],
  ["anomaly_de", "temperature DE"], ["anomaly_global", "temperature global"],
  ["events_de", "disasters DE"], ["events_row", "disasters rest of world"], ["heat_deaths_de", "heat deaths DE"],
];

export function render(data) {
  const c = {
    primary: css("--text-primary"), secondary: css("--text-secondary"), muted: css("--text-muted"),
    grid: css("--grid"), baseline: css("--baseline"), surface: css("--surface"),
    s1: css("--series-1"), s2: css("--series-2"), s3: css("--series-3"), s4: css("--series-4"),
    warm: css("--div-warm"), cool: css("--div-cool"),
  };
  const partyColor = (p) => (PARTY_VAR[p] ? css(PARTY_VAR[p]) : c.muted);

  const M = data.monthly.map((d) => ({
    ...d, date: toDate(d.month),
    aPct: pct(d.share_a), a12: pct(d.share_a_12m), bPct: pct(d.share_b), b12: pct(d.share_b_12m),
  }));
  const { first_month: first, last_month: last, emdat_complete_until: complete } = data.meta;
  const xDomain = [toDate(first), nextMonth(last)];
  const style = { background: "transparent", color: c.secondary, fontSize: "12px", fontFamily: "inherit", overflow: "visible" };

  const draw = (id, make) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.replaceChildren(make(Math.max(el.clientWidth, 260)));
  };
  const time = (width, height, y, marks, extra = {}) =>
    Plot.plot({
      width, height, style, marginLeft: 48, marginRight: 16, marginTop: 16,
      x: { domain: xDomain, label: null, ticks: width < 500 ? 5 : 10 },
      y: { grid: true, ...y }, marks, ...extra,
    });
  const crosshair = (rows, title, y) => [
    Plot.ruleX(rows, Plot.pointerX({ x: "date", stroke: c.muted, strokeWidth: 1 })),
    Plot.tip(rows, Plot.pointerX({ x: "date", y, title, fontSize: 12 })),
  ];
  // EM-DAT months after complete_until: late reporting, shaded so the drop is not read as a trend
  const incomplete = [
    Plot.rect([{ x1: nextMonth(complete), x2: nextMonth(last) }], { x1: "x1", x2: "x2", fill: c.muted, fillOpacity: 0.15 }),
    Plot.text([{ x: nextMonth(complete) }], { x: "x", text: () => "incomplete", frameAnchor: "top", dy: -12, textAnchor: "start", fill: c.muted }),
  ];
  // monthly values as faint bars, rolling mean as solid line
  const barsLine = (id, y, y12, color, yOpt, title, { height = 200, extra = [] } = {}) =>
    draw(id, (w) => time(w, height, yOpt, [
      ...extra,
      Plot.rectY(M, { x: "date", y, interval: "month", fill: color, fillOpacity: 0.3, inset: 0.3 }),
      Plot.lineY(M, { x: "date", y: y12, stroke: color, strokeWidth: 2 }),
      Plot.ruleY([0], { stroke: c.baseline }),
      ...crosshair(M, title, y),
    ]));
  const anomalyAxis = { label: "°C vs 1991–2020", tickFormat: (d) => (d > 0 ? "+" : "") + d };
  const pctAxis = { label: "%", tickFormat: (d) => d + " %" };
  const noSitting = (d) => `${d.month}\nno plenary sitting`;

  // ---------------------------------------------------------------- H1: signals
  const top = M.filter((d) => d.aPct != null && d.sentences >= 2000).sort((a, b) => b.aPct - a.aPct).slice(0, 5);
  // label the five strongest months directly on the chart (replaces the old top-months table)
  draw("chart-share-a", (w) => time(w, 240, pctAxis, [
    Plot.rectY(M, { x: "date", y: "aPct", interval: "month", fill: c.s1, fillOpacity: 0.3, inset: 0.3 }),
    Plot.lineY(M, { x: "date", y: "a12", stroke: c.s1, strokeWidth: 2 }),
    Plot.ruleY([0], { stroke: c.baseline }),
    Plot.dot(top, { x: (d) => new Date(+d.date + 15 * 864e5), y: "aPct", r: 3.5, fill: c.s1, stroke: c.surface, strokeWidth: 2 }),
    Plot.text(top, { x: (d) => new Date(+d.date + 15 * 864e5), y: "aPct", text: "month", dy: -10, fill: c.primary, fontWeight: 600 }),
    ...crosshair(M, (d) => d.sitting
      ? `${d.month}\n(a) ${fmt(d.aPct, 2, " %")} of sentences\n12-month ${fmt(d.a12, 2, " %")}\n${int(d.relevant)} of ${int(d.sentences)} sentences`
      : noSitting(d), "aPct"),
  ], { marginTop: 24 }));
  barsLine("chart-share-b", "bPct", "b12", c.s1, pctAxis, (d) => d.sitting
    ? `${d.month}\n(b) ${fmt(d.bPct, 2, " %")} of speeches\n12-month ${fmt(d.b12, 2, " %")}\n${int(d.main_topic)} of ${int(d.speeches)} speeches`
    : noSitting(d));
  barsLine("chart-trends-main", "trends_Klimawandel", "trends_Klimawandel_12m", c.s2,
    { label: "index 0–100", domain: [0, 100] },
    (d) => `${d.month}\nKlimawandel ${fmt(d.trends_Klimawandel, 0)}\n12-month ${fmt(d.trends_Klimawandel_12m, 1)}`);
  barsLine("chart-temp-global-main", "anomaly_global", "anomaly_global_12m", c.s4, anomalyAxis,
    (d) => `${d.month}\nglobal anomaly ${fmt(d.anomaly_global, 2, " °C")}\n12-month ${fmt(d.anomaly_global_12m, 2, " °C")}`);
  barsLine("chart-events-global", "events_global", "events_global_12m", c.s3, { label: "events per month" },
    (d) => `${d.month}\n${int(d.events_global)} events worldwide\n${int(d.deaths_global)} deaths\n12-month ${fmt(d.events_global_12m, 1)} events`,
    { extra: incomplete });

  // ---------------------------------------------------------------- H1: indexed overlay
  const zs = Object.fromEntries(SIGNALS.map((s) => [s.key, zscore(M, s.key)]));
  const Z = M.map((d) => ({ date: d.date, month: d.month, ...Object.fromEntries(SIGNALS.map((s) => [s.key, zs[s.key](d[s.key])])) }));
  const Zlong = SIGNALS.flatMap((s) => Z.map((d) => ({ date: d.date, series: s.label, z: d[s.key] })));
  draw("chart-indexed", (w) => {
    const labels = w >= 640;
    return time(w, 320, { label: "standard deviations from mean" }, [
      ...incomplete,
      Plot.ruleY([0], { stroke: c.baseline }),
      Plot.lineY(Zlong, { x: "date", y: "z", z: "series", stroke: "series", strokeWidth: 2 }),
      labels ? Plot.text(Zlong.filter((d) => d.z != null), Plot.selectLast({
        x: "date", y: "z", z: "series", text: "series", dx: 6, textAnchor: "start", fill: c.secondary,
      })) : null,
      Plot.ruleX(Z, Plot.pointerX({ x: "date", stroke: c.muted })),
      Plot.tip(Z, Plot.pointerX({
        x: "date", y: () => 2.5, fontSize: 12,
        title: (d) => [d.month, ...SIGNALS.map((s) => `${s.label}: ${fmt(d[s.key], 2)}`)].join("\n"),
      })),
    ], {
      marginRight: labels ? 160 : 16, marginTop: 24,
      color: { domain: SIGNALS.map((s) => s.label), range: SIGNALS.map((s) => css(s.color)) },
    });
  });

  // ---------------------------------------------------------------- H1: detrended and deseasonalized
  for (const s of DETRENDED) {
    const key = `${s.key}_detr_z`;
    const out = M.filter((d) => d[key] != null && Math.abs(d[key]) > Z_MAX);
    draw(`chart-detr-${s.key}`, (w) => time(w, 130, { label: null, ticks: 3, domain: [-Z_MAX, Z_MAX] }, [
      s.key.startsWith("events") ? incomplete[0] : null,
      Plot.ruleY([0], { stroke: c.baseline }),
      Plot.lineY(M, { x: "date", y: key, stroke: css(s.color), strokeWidth: 1.5, clip: true }),
      Plot.text(out, { x: "date", y: (d) => Math.sign(d[key]) * Z_MAX, text: (d) => `${d.month}: ${fmt(d[key], 1)} SD ↑`,
        dx: 6, textAnchor: "start", fill: c.primary, fontWeight: 600 }),
      ...crosshair(M, (d) => (d[key] == null ? `${d.month}\nno value` : `${d.month}\n${s.label}: ${fmt(d[key], 2)} SD`), key),
    ], { marginTop: 8 }));
  }

  // ---------------------------------------------------------------- H1: Google Trends, all exports
  const brk = [{ date: toDate(data.meta.trends_break) }];
  for (const term of data.meta.trend_terms) {
    const key = `trends_${term}`;
    const spikes = data.trends_spikes.filter((d) => d.term === term).map((d) => ({ ...d, date: toDate(d.month) }));
    draw(`chart-trend-${term}`, (w) => time(w, 170, { label: null, domain: [0, 100], ticks: 3 }, [
      Plot.ruleX(brk, { x: "date", stroke: c.secondary, strokeDasharray: "3,3" }),
      Plot.lineY(M, { x: "date", y: key, stroke: c.s2, strokeOpacity: 0.45, strokeWidth: 1 }),
      Plot.lineY(M, { x: "date", y: `${key}_12m`, stroke: c.s2, strokeWidth: 2 }),
      Plot.dot(spikes, { x: "date", y: "index", r: 4, fill: c.s2, stroke: c.surface, strokeWidth: 2 }),
      Plot.text(spikes.slice(0, 1), { x: "date", y: "index", text: (d) => `${d.month} ×${fmt(d.ratio, 0)}`,
        dx: -8, textAnchor: "end", fill: c.primary, fontWeight: 600 }),
      Plot.ruleY([0], { stroke: c.baseline }),
      ...crosshair(M, (d) => `${d.month}\n${term} ${fmt(d[key], 0)}\n12-month ${fmt(d[`${key}_12m`], 1)}`, key),
    ], { marginLeft: 32, x: { domain: xDomain, label: null, ticks: 4 } }));
  }

  // ---------------------------------------------------------------- H2: Germany vs world
  const tempBars = (id, key, label) => draw(id, (w) => time(w, 220, anomalyAxis, [
    Plot.rectY(M, { x: "date", y: key, interval: "month", fill: (d) => (d[key] >= 0 ? c.warm : c.cool), inset: 0.3 }),
    Plot.lineY(M, { x: "date", y: `${key}_12m`, stroke: c.primary, strokeWidth: 2 }),
    Plot.ruleY([0], { stroke: c.baseline }),
    ...crosshair(M, (d) => `${d.month}\n${label} ${fmt(d[key], 2, " °C")}\n12-month ${fmt(d[`${key}_12m`], 2, " °C")}`, key),
  ]));
  tempBars("chart-temp-de", "anomaly_de", "Germany");
  tempBars("chart-temp-global", "anomaly_global", "global");

  const DE = M.filter((d) => d.events_de > 0);
  draw("chart-events-de", (w) => time(w, 180, { label: "events", ticks: 3 }, [
    ...incomplete,
    Plot.ruleX(DE, { x: "date", y: "events_de", stroke: c.primary, strokeWidth: 2 }),
    Plot.dot(DE, { x: "date", y: "events_de", r: 4, fill: c.primary, stroke: c.surface, strokeWidth: 2 }),
    Plot.ruleY([0], { stroke: c.baseline }),
    Plot.tip(DE, Plot.pointerX({ x: "date", y: "events_de", fontSize: 12,
      title: (d) => `${d.month}\n${d.events_de} German event(s)\n${int(d.deaths_de)} deaths in Germany` })),
  ], { marginTop: 24 }));
  barsLine("chart-events-row", "events_row", "events_row_12m", c.s3, { label: "events per month" },
    (d) => `${d.month}\n${int(d.events_row)} events, rest of world\n${int(d.deaths_row)} deaths\n12-month ${fmt(d.events_row_12m, 1)}`,
    { extra: incomplete });
  if (data.meta.has_heat) {
    draw("chart-heat", (w) => time(w, 180, { label: "deaths" }, [
      Plot.rectY(M, { x: "date", y: "heat_deaths_de", interval: "month", fill: c.warm, inset: 0.3 }),
      Plot.ruleY([0], { stroke: c.baseline }),
      ...crosshair(M, (d) => `${d.month}\n${int(d.heat_deaths_de)} heat-related deaths`, "heat_deaths_de"),
    ]));
  }

  const EV = M.filter((d) => d.events_de > 0);
  draw("chart-events-attention", (w) => time(w, 240, pctAxis, [
    Plot.ruleX(EV, { x: "date", stroke: c.primary, strokeOpacity: 0.35, strokeWidth: 1 }),
    Plot.rectY(M, { x: "date", y: "aPct", interval: "month", fill: c.s1, fillOpacity: 0.45, inset: 0.3 }),
    Plot.ruleY([0], { stroke: c.baseline }),
    ...crosshair(M, (d) => [
      d.month,
      d.sitting ? `(a) ${fmt(d.aPct, 2, " %")} of sentences` : "no plenary sitting",
      d.events_de > 0 ? `German event(s): ${d.events_de}, ${int(d.deaths_de)} deaths` : null,
    ].filter(Boolean).join("\n"), "aPct"),
  ]));

  // event study: mean deviation from the all-month mean per offset (bars), each event as a dot
  const OFF = { "-1": "t−1", 0: "t", 1: "t+1", 2: "t+2" };
  const jitter = (i) => ((i * 0.618034) % 1 - 0.5) * 0.36; // deterministic spread of the event dots
  const ES = data.event_study;
  const ESdots = data.events_de.flatMap((e, i) => [-1, 0, 1, 2].map((k) => {
    const v = e[`share_a_t${k >= 0 ? "+" : "-"}${Math.abs(k)}`];
    return v == null ? null : { month: e.month, deaths: e.deaths_de, k, x: k + jitter(i), diff: (v - e.share_a_mean_all) * 100 };
  }).filter(Boolean));
  draw("chart-event-study", (w) => Plot.plot({
    width: w, height: 280, style, marginLeft: 56, marginTop: 20,
    x: { domain: [-1.5, 2.5], ticks: [-1, 0, 1, 2], tickFormat: (k) => OFF[k], label: "months relative to a German disaster month" },
    y: { label: "percentage points vs. average month", grid: true, tickFormat: (d) => (d > 0 ? "+" : "") + d },
    marks: [
      Plot.dot(ESdots, { x: "x", y: "diff", r: 2.5, fill: c.muted, fillOpacity: 0.6 }),
      Plot.rectY(ES, { x1: (d) => d.offset - 0.28, x2: (d) => d.offset + 0.28, y: "diff_pp", fill: c.s1, fillOpacity: 0.85, rx: 4 }),
      ...[[(d) => d.diff_pp >= 0, -10], [(d) => d.diff_pp < 0, 12]].map(([keep, dy]) =>
        Plot.text(ES.filter(keep), { x: "offset", y: "diff_pp", text: (d) => `${d.diff_pp > 0 ? "+" : ""}${fmt(d.diff_pp, 2)} pp`,
          dy, fill: c.primary, fontWeight: 600 })),
      Plot.ruleY([0], { stroke: c.baseline }),
      Plot.tip(ESdots, Plot.pointer({ x: "x", y: "diff", fontSize: 12,
        title: (d) => `event month ${d.month} (${int(d.deaths)} deaths)\n${OFF[d.k]}: ${fmt(d.diff, 2)} pp vs average` })),
    ],
  }));

  // ---------------------------------------------------------------- H3: parties
  const PY = data.party_year.map((d) => ({ ...d, sharePct: d.share * 100 }));
  if (PY.length) {
    const yMax = Math.max(...PY.map((d) => d.sharePct)) * 1.05;
    const years = Array.from({ length: +last.slice(0, 4) - 2003 }, (_, i) => 2004 + i);
    // one row per party and year, null where a party has no data, so lines break (e.g. FDP 2014-2017)
    const PYfull = PARTIES.flatMap((p) => years.map((year) =>
      PY.find((d) => d.party === p && d.year === year) ?? { party: p, year, sharePct: null }));
    for (const party of PARTIES) {
      const own = PY.filter((d) => d.party === party);
      draw(`chart-party-${party}`, (w) => Plot.plot({
        width: w, height: 170, style, marginLeft: 36, marginTop: 12,
        x: { domain: [2004, years.at(-1)], label: null, tickFormat: "d", ticks: 4 },
        y: { domain: [0, yMax], label: null, grid: true, ticks: 3, tickFormat: (d) => d + " %" },
        marks: [
          Plot.lineY(PYfull.filter((d) => d.party !== party), { x: "year", y: "sharePct", z: "party", stroke: c.grid, strokeWidth: 1 }),
          Plot.lineY(PYfull.filter((d) => d.party === party), { x: "year", y: "sharePct", stroke: partyColor(party), strokeWidth: 2 }),
          Plot.dot(own, { x: "year", y: "sharePct", r: 3, fill: partyColor(party), stroke: c.surface, strokeWidth: 1.5 }),
          Plot.ruleY([0], { stroke: c.baseline }),
          Plot.tip(own, Plot.pointerX({ x: "year", y: "sharePct", fontSize: 12,
            title: (d) => `${party} ${d.year}\nclimate share ${fmt(d.sharePct, 2, " %")}\n${int(d.relevant)} of ${int(d.sentences)} sentences` })),
        ],
      }));
    }
  }

  const GY = data.gov_year.map((d) => ({ ...d, sharePct: d.share * 100 }));
  draw("chart-gov", (w) => Plot.plot({
    width: w, height: 260, style, marginLeft: 48, marginRight: w >= 640 ? 110 : 16, marginTop: 16,
    x: { label: null, tickFormat: "d" }, y: { label: "% of sentences", grid: true, tickFormat: (d) => d + " %" },
    color: { domain: ["government", "opposition"], range: [c.s1, c.s2] },
    marks: [
      Plot.ruleY([0], { stroke: c.baseline }),
      Plot.lineY(GY, { x: "year", y: "sharePct", stroke: "side", strokeWidth: 2 }),
      Plot.dot(GY, { x: "year", y: "sharePct", fill: "side", r: 3, stroke: c.surface, strokeWidth: 1.5 }),
      w >= 640 ? Plot.text(GY, Plot.selectLast({ x: "year", y: "sharePct", z: "side", text: "side", dx: 8, textAnchor: "start", fill: c.secondary })) : null,
      Plot.tip(GY, Plot.pointer({ x: "year", y: "sharePct", fontSize: 12,
        title: (d) => `${d.side} ${d.year}\nclimate share ${fmt(d.sharePct, 2, " %")}\n${int(d.relevant)} of ${int(d.sentences)} sentences` })),
    ],
  }));

  // ---------------------------------------------------------------- stance units: median per party, month vs quarter
  const U = data.stance_units.filter((d) => PARTIES.includes(d.party));
  const uOrder = PARTIES.filter((p) => U.some((d) => d.party === p));
  const uWide = uOrder.map((p) => ({
    party: p, m: U.find((d) => d.party === p && d.grain === "month")?.median,
    q: U.find((d) => d.party === p && d.grain === "quarter")?.median,
  }));
  draw("chart-units", (w) => Plot.plot({
    width: w, height: uOrder.length * 34 + 50, style, marginLeft: 80, marginRight: 40,
    x: { type: "symlog", label: "median climate-relevant sentences per period (log scale)", grid: true },
    y: { domain: uOrder, label: null },
    color: { domain: ["per month", "per quarter"], range: [c.s1, c.s2] },
    marks: [
      Plot.ruleY(uWide, { y: "party", x1: "m", x2: "q", stroke: c.baseline, strokeWidth: 2 }),
      Plot.dot(uWide, { y: "party", x: "m", r: 6, fill: c.s1, stroke: c.surface, strokeWidth: 2 }),
      Plot.dot(uWide, { y: "party", x: "q", r: 6, fill: c.s2, stroke: c.surface, strokeWidth: 2 }),
      Plot.text(uWide, { y: "party", x: "m", text: (d) => fmt(d.m, 0), dx: -12, textAnchor: "end", fill: c.secondary }),
      Plot.text(uWide, { y: "party", x: "q", text: (d) => fmt(d.q, 0), dx: 12, textAnchor: "start", fill: c.secondary }),
      Plot.tip(U, Plot.pointer({ y: "party", x: "median", fontSize: 12,
        title: (d) => `${d.party} per ${d.grain}\nmedian ${fmt(d.median, 0)}, p10 ${fmt(d.p10, 0)}\n${d.zero} of ${d.periods} ${d.grain}s with 0` })),
    ],
  }));

  // ---------------------------------------------------------------- corpus: who speaks vs who speaks about climate
  const CP = data.corpus_party;
  const groups = [["all speech", "share_of_sentences"], ["climate speech", "relevant"]];
  const relTotal = CP.reduce((a, d) => a + (d.relevant ?? 0), 0);
  const comp = groups.flatMap(([g, key]) => {
    const rows = PARTIES.map((p) => {
      const d = CP.find((r) => r.party === p);
      const v = d == null ? 0 : key === "relevant" ? (d.relevant ?? 0) / (relTotal || 1) : d.share_of_sentences;
      return { group: g, party: p, share: v * 100 };
    });
    const other = 100 - rows.reduce((a, d) => a + d.share, 0);
    return [...rows, { group: g, party: "other / unknown", share: Math.max(other, 0) }];
  }).filter((d) => d.share > 0 && (d.group === "all speech" || relTotal > 0));
  const compParties = [...PARTIES, "other / unknown"];
  draw("chart-composition", (w) => Plot.plot({
    width: w, height: 150, style, marginLeft: 100, marginRight: 16,
    x: { domain: [0, 100], label: null, tickFormat: (d) => d + " %" },
    y: { domain: groups.map(([g]) => g), label: null },
    color: { domain: compParties, range: compParties.map(partyColor), legend: true },
    marks: [
      Plot.barX(comp, Plot.stackX({ x: "share", y: "group", fill: "party", order: compParties, insetRight: 2, rx: 3 })),
      Plot.text(comp.filter((d) => d.share >= 6), Plot.stackX({ x: "share", y: "group", z: "party", order: compParties,
        text: (d) => `${d.party.replace("other / unknown", "other")} ${fmt(d.share, 0)} %`,
        fill: c.primary, stroke: c.surface, strokeWidth: 3, fontSize: 11 })),
      Plot.tip(comp, Plot.pointer(Plot.stackX({ x: "share", y: "group", order: compParties, fontSize: 12,
        title: (d) => `${d.party}\n${fmt(d.share, 1)} % of ${d.group}` }))),
    ],
  }));

  // ---------------------------------------------------------------- corpus: speech length per period
  const LPr = data.corpus_lp.map((d) => ({ ...d, label: `${d.lp}.` }));
  draw("chart-lp", (w) => Plot.plot({
    width: w, height: 220, style, marginLeft: 44, marginTop: 20,
    x: { label: "legislative period", domain: LPr.map((d) => d.label) },
    y: { label: "sentences per speech", grid: true },
    marks: [
      Plot.barY(LPr, { x: "label", y: "mean_sentences_per_speech", fill: c.muted, rx: 4, insetLeft: 8, insetRight: 8 }),
      Plot.dot(LPr, { x: "label", y: "median_sentences_per_speech", r: 4, fill: c.primary }),
      Plot.text(LPr, { x: "label", y: "mean_sentences_per_speech", text: (d) => fmt(d.mean_sentences_per_speech, 1), dy: -10, fill: c.primary }),
      Plot.ruleY([0], { stroke: c.baseline }),
      Plot.tip(LPr, Plot.pointerX({ x: "label", y: "mean_sentences_per_speech", fontSize: 12,
        title: (d) => `${d.lp}. Bundestag (${d.first_month} – ${d.last_month})\n${int(d.speeches)} speeches, ${int(d.sentences)} sentences\nmean ${fmt(d.mean_sentences_per_speech, 1)}, median ${fmt(d.median_sentences_per_speech, 0)} sentences per speech` })),
    ],
  }));

  // ---------------------------------------------------------------- join: coverage strip
  const rows = COVERAGE.filter(([k]) => k in M[0]);
  const cov = rows.flatMap(([k, label]) => M.map((d) => ({
    date: d.date, month: d.month, series: label,
    status: d[k] == null ? "missing" : k.startsWith("events") && d.month > complete ? "incomplete" : "present",
  }))).filter((d) => d.status !== "missing");
  draw("chart-coverage", (w) => time(w, rows.length * 18 + 40, null, [
    Plot.barX(cov, { x1: "date", x2: (d) => nextMonth(d.month), y: "series",
      fill: (d) => (d.status === "present" ? c.s1 : c.muted), fillOpacity: (d) => (d.status === "present" ? 0.75 : 0.5), inset: 0 }),
    Plot.tip(cov, Plot.pointer({ x: "date", y: "series", fontSize: 12, title: (d) => `${d.series}\n${d.month}: ${d.status}` })),
  ], { marginLeft: 150, y: { domain: rows.map(([, l]) => l), label: null, grid: false } }));

  // ---------------------------------------------------------------- corpus volume
  const LP = data.corpus_lp.map((d) => ({ ...d, date: toDate(d.first_month) }));
  draw("chart-volume", (w) => time(w, 230, { label: null, tickFormat: "s" }, [
    Plot.rectY(M, { x: "date", y: "sentences", interval: "month", fill: c.muted, fillOpacity: 0.6, inset: 0.3 }),
    Plot.ruleX(LP.slice(1), { x: "date", stroke: c.secondary, strokeDasharray: "3,3" }),
    Plot.text(LP.slice(1), { x: "date", text: (d) => `LP ${d.lp}`, frameAnchor: "top", dx: 4, dy: -14, textAnchor: "start", fill: c.secondary }),
    Plot.ruleY([0], { stroke: c.baseline }),
    ...crosshair(M, (d) => (d.sitting ? `${d.month}\n${int(d.sentences)} sentences\n${int(d.speeches)} speeches` : noSitting(d)), "sentences"),
  ], { marginTop: 28 }));
}
