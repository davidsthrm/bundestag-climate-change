import * as Plot from "@observablehq/plot";

const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const utc = (y, m = 1) => new Date(Date.UTC(y, m - 1, 1));
const toDate = (month) => utc(+month.slice(0, 4), +month.slice(5, 7));
const fmt = (x, d = 2, unit = "") => (x == null ? "–" : `${x.toFixed(d)}${unit}`);
const int = (x) => (x == null ? "–" : x.toLocaleString("en-US"));
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

export function render(data) {
  const c = {
    primary: css("--text-primary"), secondary: css("--text-secondary"), muted: css("--text-muted"),
    grid: css("--grid"), baseline: css("--baseline"), surface: css("--surface"),
    s1: css("--series-1"), s2: css("--series-2"), s3: css("--series-3"), s4: css("--series-4"),
    warm: css("--div-warm"), cool: css("--div-cool"),
  };
  const partyColor = (p) => css(PARTY_VAR[p]);

  const M = data.monthly.map((d) => ({
    ...d, date: toDate(d.month),
    aPct: pct(d.share_a), a12: pct(d.share_a_12m), bPct: pct(d.share_b), b12: pct(d.share_b_12m),
  }));
  const last = data.meta.last_month;
  const xDomain = [toDate(data.meta.first_month), utc(+last.slice(0, 4), +last.slice(5) + 1)];
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
  // monthly values as faint bars, rolling mean as solid line
  const barsLine = (id, y, y12, color, yOpt, title, height = 200) =>
    draw(id, (w) => time(w, height, yOpt, [
      Plot.rectY(M, { x: "date", y, interval: "month", fill: color, fillOpacity: 0.3, inset: 0.3 }),
      Plot.lineY(M, { x: "date", y: y12, stroke: color, strokeWidth: 2 }),
      Plot.ruleY([0], { stroke: c.baseline }),
      ...crosshair(M, title, y),
    ]));
  const anomalyAxis = { label: "°C vs 1991–2020", tickFormat: (d) => (d > 0 ? "+" : "") + d };
  const pctAxis = { label: "%", tickFormat: (d) => d + " %" };
  const noSitting = (d) => `${d.month}\nno plenary sitting`;

  // ---------------------------------------------------------------- H1: signals
  barsLine("chart-share-a", "aPct", "a12", c.s1, pctAxis, (d) => d.sitting
    ? `${d.month}\n(a) ${fmt(d.aPct, 2, " %")} of sentences\n12-month ${fmt(d.a12, 2, " %")}\n${int(d.relevant)} of ${int(d.sentences)} sentences`
    : noSitting(d), 220);
  barsLine("chart-share-b", "bPct", "b12", c.s1, pctAxis, (d) => d.sitting
    ? `${d.month}\n(b) ${fmt(d.bPct, 2, " %")} of speeches\n12-month ${fmt(d.b12, 2, " %")}\n${int(d.main_topic)} of ${int(d.speeches)} speeches`
    : noSitting(d));
  barsLine("chart-trends-main", "trends_Klimawandel", "trends_Klimawandel_12m", c.s2,
    { label: "index 0–100", domain: [0, 100] },
    (d) => `${d.month}\nKlimawandel ${fmt(d.trends_Klimawandel, 0)}\n12-month ${fmt(d.trends_Klimawandel_12m, 1)}`);
  barsLine("chart-temp-global-main", "anomaly_global", "anomaly_global_12m", c.s4, anomalyAxis,
    (d) => `${d.month}\nglobal anomaly ${fmt(d.anomaly_global, 2, " °C")}\n12-month ${fmt(d.anomaly_global_12m, 2, " °C")}`);
  barsLine("chart-events-global", "events_global", "events_global_12m", c.s3, { label: "events per month" },
    (d) => `${d.month}\n${int(d.events_global)} events worldwide\n${int(d.deaths_global)} deaths\n12-month ${fmt(d.events_global_12m, 1)} events`);

  // ---------------------------------------------------------------- H1: indexed overlay
  const zs = Object.fromEntries(SIGNALS.map((s) => [s.key, zscore(M, s.key)]));
  const Z = M.map((d) => ({ date: d.date, month: d.month, ...Object.fromEntries(SIGNALS.map((s) => [s.key, zs[s.key](d[s.key])])) }));
  const Zlong = SIGNALS.flatMap((s) => Z.map((d) => ({ date: d.date, series: s.label, z: d[s.key] })));
  draw("chart-indexed", (w) => {
    const labels = w >= 640;
    return time(w, 320, { label: "standard deviations from mean" }, [
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
      marginRight: labels ? 160 : 16,
      color: { domain: SIGNALS.map((s) => s.label), range: SIGNALS.map((s) => css(s.color)) },
    });
  });

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
    Plot.ruleX(DE, { x: "date", y: "events_de", stroke: c.primary, strokeWidth: 2 }),
    Plot.dot(DE, { x: "date", y: "events_de", r: 4, fill: c.primary, stroke: c.surface, strokeWidth: 2 }),
    Plot.ruleY([0], { stroke: c.baseline }),
    Plot.tip(DE, Plot.pointerX({ x: "date", y: "events_de", fontSize: 12,
      title: (d) => `${d.month}\n${d.events_de} German event(s)\n${int(d.deaths_de)} deaths in Germany` })),
  ]));
  barsLine("chart-events-row", "events_row", "events_row_12m", c.s3, { label: "events per month" },
    (d) => `${d.month}\n${int(d.events_row)} events, rest of world\n${int(d.deaths_row)} deaths\n12-month ${fmt(d.events_row_12m, 1)}`);
  if (data.meta.has_heat) {
    draw("chart-heat", (w) => time(w, 180, { label: "deaths" }, [
      Plot.rectY(M, { x: "date", y: "heat_deaths_de", interval: "month", fill: c.warm, inset: 0.3 }),
      Plot.ruleY([0], { stroke: c.baseline }),
      ...crosshair(M, (d) => `${d.month}\n${int(d.heat_deaths_de == null ? null : Math.round(d.heat_deaths_de))} heat-related deaths`, "heat_deaths_de"),
    ]));
  }

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
