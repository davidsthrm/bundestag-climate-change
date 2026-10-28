import * as Plot from "@observablehq/plot";

const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const utc = (y, m = 1) => new Date(Date.UTC(y, m - 1, 1));
const toDate = (month) => utc(+month.slice(0, 4), +month.slice(5, 7));
const fmt = (x, d = 2, unit = "") => (x == null ? "–" : `${x.toFixed(d)}${unit}`);
const int = (x) => (x == null ? "–" : x.toLocaleString("en-US"));
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
const SIGNALS = [
  { key: "share_12m", label: "Bundestag climate share", color: "--series-1" },
  { key: "Klimawandel_12m", label: "Trends: Klimawandel", color: "--series-2" },
  { key: "anomaly_de_12m", label: "Temperature DE", color: "--series-3" },
  { key: "anomaly_global_12m", label: "Temperature global", color: "--series-4" },
];

export function render(data) {
  const c = {
    primary: css("--text-primary"), secondary: css("--text-secondary"), muted: css("--text-muted"),
    grid: css("--grid"), baseline: css("--baseline"),
    s1: css("--series-1"), s2: css("--series-2"), s3: css("--series-3"), s4: css("--series-4"),
    warm: css("--div-warm"), cool: css("--div-cool"), seqLow: css("--seq-low"), seqHigh: css("--seq-high"),
  };
  const partyColor = (p) => css(PARTY_VAR[p]);

  const M = data.monthly.map((d) => ({
    ...d,
    date: toDate(d.month),
    sharePct: d.share == null ? null : d.share * 100,
    share12: d.share_12m == null ? null : d.share_12m * 100,
    speechPct: d.speech_share == null ? null : d.speech_share * 100,
  }));
  const xDomain = [toDate(data.meta.first_month), utc(+data.meta.last_month.slice(0, 4), +data.meta.last_month.slice(5) + 1)];
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
  const crosshair = (data, title, y) => [
    Plot.ruleX(data, Plot.pointerX({ x: "date", stroke: c.muted, strokeWidth: 1 })),
    Plot.tip(data, Plot.pointerX({ x: "date", y, title, fontSize: 12 })),
  ];

  // ---------------------------------------------------------------- three signals
  draw("chart-share", (w) =>
    time(w, 220, { label: "% of sentences", tickFormat: (d) => d + " %" }, [
      Plot.rectY(M, { x: "date", y: "sharePct", interval: "month", fill: c.s1, fillOpacity: 0.3, inset: 0.3 }),
      Plot.lineY(M, { x: "date", y: "share12", stroke: c.s1, strokeWidth: 2 }),
      Plot.ruleY([0], { stroke: c.baseline }),
      ...crosshair(M, (d) =>
        d.sentences == null
          ? `${d.month}\nno plenary session`
          : `${d.month}\nclimate share ${fmt(d.sharePct, 2, " %")}\n12-month ${fmt(d.share12, 2, " %")}\n${int(d.climate)} of ${int(d.sentences)} sentences`,
        "sharePct"),
    ]));

  draw("chart-trends-main", (w) =>
    time(w, 200, { label: "Google Trends index", domain: [0, 100] }, [
      Plot.lineY(M, { x: "date", y: "Klimawandel", stroke: c.s2, strokeOpacity: 0.45, strokeWidth: 1 }),
      Plot.lineY(M, { x: "date", y: "Klimawandel_12m", stroke: c.s2, strokeWidth: 2 }),
      Plot.ruleY([0], { stroke: c.baseline }),
      ...crosshair(M, (d) => `${d.month}\nKlimawandel ${fmt(d.Klimawandel, 0)}\n12-month ${fmt(d.Klimawandel_12m, 1)}`, "Klimawandel"),
    ]));

  draw("chart-temp-main", (w) =>
    time(w, 200, { label: "°C vs 1991–2020", tickFormat: (d) => (d > 0 ? "+" : "") + d }, [
      Plot.rectY(M, { x: "date", y: "anomaly_de", interval: "month", fill: c.s3, fillOpacity: 0.3, inset: 0.3 }),
      Plot.lineY(M, { x: "date", y: "anomaly_de_12m", stroke: c.s3, strokeWidth: 2 }),
      Plot.ruleY([0], { stroke: c.baseline }),
      ...crosshair(M, (d) => `${d.month}\nGermany ${fmt(d.temp_de, 1, " °C")}\nanomaly ${fmt(d.anomaly_de, 2, " °C")}\n12-month ${fmt(d.anomaly_de_12m, 2, " °C")}`, "anomaly_de"),
    ]));

  // ---------------------------------------------------------------- indexed overlay
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

  // ---------------------------------------------------------------- scatter plots
  const scatter = (id, x, xLabel, unit) =>
    draw(id, (w) => Plot.plot({
      width: w, height: 260, style, marginLeft: 44, marginTop: 16,
      x: { label: xLabel, grid: true }, y: { label: "% climate sentences", grid: true },
      marks: [
        Plot.dot(M, { x, y: "sharePct", r: 3.5, fill: c.s1, fillOpacity: 0.45 }),
        Plot.linearRegressionY(M, { x, y: "sharePct", stroke: c.primary, strokeWidth: 1.5 }),
        Plot.tip(M, Plot.pointer({ x, y: "sharePct", fontSize: 12,
          title: (d) => `${d.month}\nclimate share ${fmt(d.sharePct, 2, " %")}\n${xLabel}: ${fmt(d[x], 2, unit)}` })),
      ],
    }));
  scatter("chart-scatter-trends", "Klimawandel", "Trends: Klimawandel", "");
  scatter("chart-scatter-de", "anomaly_de", "Anomaly DE (°C)", " °C");
  scatter("chart-scatter-global", "anomaly_global", "Anomaly global (°C)", " °C");

  // ---------------------------------------------------------------- Google Trends small multiples
  for (const term of data.meta.trend_terms) {
    draw(`chart-trend-${term}`, (w) => time(w, 170, { label: null, domain: [0, 100], ticks: 3 }, [
      Plot.lineY(M, { x: "date", y: term, stroke: c.s2, strokeOpacity: 0.45, strokeWidth: 1 }),
      Plot.lineY(M, { x: "date", y: `${term}_12m`, stroke: c.s2, strokeWidth: 2 }),
      Plot.ruleY([0], { stroke: c.baseline }),
      ...crosshair(M, (d) => `${d.month}\n${term} ${fmt(d[term], 0)}\n12-month ${fmt(d[`${term}_12m`], 1)}`, term),
    ], { marginLeft: 32, x: { domain: xDomain, label: null, ticks: 4 } }));
  }

  // ---------------------------------------------------------------- temperature
  draw("chart-temp-de", (w) => time(w, 240, { label: "°C vs 1991–2020", tickFormat: (d) => (d > 0 ? "+" : "") + d }, [
    Plot.rectY(M, { x: "date", y: "anomaly_de", interval: "month", fill: (d) => (d.anomaly_de >= 0 ? c.warm : c.cool), inset: 0.3 }),
    Plot.lineY(M, { x: "date", y: "anomaly_de_12m", stroke: c.primary, strokeWidth: 2 }),
    Plot.ruleY([0], { stroke: c.baseline }),
    ...crosshair(M, (d) => `${d.month}\nGermany ${fmt(d.temp_de, 1, " °C")}\nanomaly ${fmt(d.anomaly_de, 2, " °C")}\n12-month ${fmt(d.anomaly_de_12m, 2, " °C")}`, "anomaly_de"),
  ]));
  draw("chart-temp-global", (w) => time(w, 200, { label: "°C vs 1991–2020", tickFormat: (d) => (d > 0 ? "+" : "") + d }, [
    Plot.rectY(M, { x: "date", y: "anomaly_global", interval: "month", fill: (d) => (d.anomaly_global >= 0 ? c.warm : c.cool), inset: 0.3 }),
    Plot.lineY(M, { x: "date", y: "anomaly_global_12m", stroke: c.primary, strokeWidth: 2 }),
    Plot.ruleY([0], { stroke: c.baseline }),
    ...crosshair(M, (d) => `${d.month}\nglobal anomaly ${fmt(d.anomaly_global, 2, " °C")}\n12-month ${fmt(d.anomaly_global_12m, 2, " °C")}`, "anomaly_global"),
  ]));

  // ---------------------------------------------------------------- parties
  const PY = data.party_year.map((d) => ({ ...d, sharePct: d.share * 100 }));
  const yMax = Math.max(...PY.map((d) => d.sharePct)) * 1.05;
  // one row per party and year, null where a party has no data, so lines break (e.g. FDP 2014-2017)
  const years = Array.from({ length: 23 }, (_, i) => 2004 + i);
  const PYfull = PARTIES.flatMap((p) => years.map((year) =>
    PY.find((d) => d.party === p && d.year === year) ?? { party: p, year, sharePct: null }));
  for (const party of PARTIES) {
    const own = PY.filter((d) => d.party === party);
    draw(`chart-party-${party}`, (w) => Plot.plot({
      width: w, height: 170, style, marginLeft: 36, marginTop: 12,
      x: { domain: [2004, 2026], label: null, tickFormat: "d", ticks: 4 },
      y: { domain: [0, yMax], label: null, grid: true, ticks: 3, tickFormat: (d) => d + " %" },
      marks: [
        Plot.lineY(PYfull.filter((d) => d.party !== party), { x: "year", y: "sharePct", z: "party", stroke: c.grid, strokeWidth: 1 }),
        Plot.lineY(PYfull.filter((d) => d.party === party), { x: "year", y: "sharePct", stroke: partyColor(party), strokeWidth: 2 }),
        Plot.dot(own, { x: "year", y: "sharePct", r: 3, fill: partyColor(party), stroke: css("--surface"), strokeWidth: 1.5 }),
        Plot.ruleY([0], { stroke: c.baseline }),
        Plot.tip(own, Plot.pointerX({ x: "year", y: "sharePct", fontSize: 12,
          title: (d) => `${party} ${d.year}\nclimate share ${fmt(d.sharePct, 2, " %")}\n${int(d.climate)} of ${int(d.sentences)} sentences` })),
      ],
    }));
  }

  const PT = data.party_total.map((d) => ({ ...d, sharePct: d.share * 100 }));
  draw("chart-party-total", (w) => Plot.plot({
    width: w, height: 240, style, marginLeft: 80, marginRight: 56,
    x: { label: "% of all sentences that are climate-related", grid: true },
    y: { label: null, domain: [...PT].sort((a, b) => b.share - a.share).map((d) => d.party) },
    marks: [
      Plot.barX(PT, { x: "sharePct", y: "party", fill: (d) => partyColor(d.party), rx: 4, insetTop: 3, insetBottom: 3 }),
      Plot.text(PT, { x: "sharePct", y: "party", text: (d) => fmt(d.sharePct, 2, " %"), dx: 6, textAnchor: "start", fill: c.secondary }),
      Plot.ruleX([0], { stroke: c.baseline }),
      Plot.tip(PT, Plot.pointerY({ x: "sharePct", y: "party", fontSize: 12,
        title: (d) => `${d.party}\n${int(d.climate)} climate sentences of ${int(d.sentences)}\n${int(d.speeches)} speeches` })),
    ],
  }));

  // ---------------------------------------------------------------- government vs opposition
  const GY = data.gov_year.map((d) => ({ ...d, sharePct: d.share * 100 }));
  draw("chart-gov", (w) => Plot.plot({
    width: w, height: 260, style, marginLeft: 48, marginRight: w >= 640 ? 140 : 16, marginTop: 16,
    x: { label: null, tickFormat: "d" }, y: { label: "% of sentences", grid: true, tickFormat: (d) => d + " %" },
    color: { domain: ["Government parties", "Opposition"], range: [c.s1, c.s2] },
    marks: [
      Plot.ruleY([0], { stroke: c.baseline }),
      Plot.lineY(GY, { x: "year", y: "sharePct", stroke: "side", strokeWidth: 2 }),
      Plot.dot(GY, { x: "year", y: "sharePct", fill: "side", r: 3, stroke: css("--surface"), strokeWidth: 1.5 }),
      w >= 640 ? Plot.text(GY, Plot.selectLast({ x: "year", y: "sharePct", z: "side", text: "side", dx: 8, textAnchor: "start", fill: c.secondary })) : null,
      Plot.tip(GY, Plot.pointer({ x: "year", y: "sharePct", fontSize: 12,
        title: (d) => `${d.side} ${d.year}\nclimate share ${fmt(d.sharePct, 2, " %")}\n${int(d.climate)} of ${int(d.sentences)} sentences` })),
    ],
  }));

  // ---------------------------------------------------------------- keywords heatmap
  const terms = ["core", "energy", "sceptic_markers"].flatMap((g) => data.meta.keywords[g]);
  draw("chart-keywords", (w) => Plot.plot({
    width: w, height: terms.length * 20 + 50, style, marginLeft: 150, marginTop: 8,
    padding: 0.06,
    x: { label: null, tickFormat: "d", ticks: w < 600 ? 6 : 12, type: "band" },
    y: { label: null, domain: terms },
    color: { type: "log", range: [c.seqLow, c.seqHigh], interpolate: "lab", legend: true, label: "sentences per year (log scale)" },
    marks: [
      Plot.cell(data.keywords_year, { x: "year", y: "term", fill: "n", rx: 2 }),
      Plot.tip(data.keywords_year, Plot.pointer({ x: "year", y: "term", fontSize: 12,
        title: (d) => `„${d.term}“ (${d.group})\n${d.year}: ${int(d.n)} sentences` })),
    ],
  }));

  // ---------------------------------------------------------------- sceptic markers
  const SK = data.keywords_year.filter((d) => d.group === "sceptic_markers");
  const skYears = Object.values(SK.reduce((acc, d) => {
    acc[d.year] ??= { year: d.year, n: 0 };
    acc[d.year].n += d.n;
    return acc;
  }, {}));
  draw("chart-sceptic-year", (w) => Plot.plot({
    width: w, height: 220, style, marginLeft: 40, marginTop: 16,
    x: { label: null, tickFormat: "d", domain: [2004, 2026] }, y: { label: "sentences", grid: true },
    marks: [
      Plot.rectY(skYears, { x: "year", y: "n", interval: 1, fill: c.s1, rx: 3, inset: 2 }),
      Plot.ruleY([0], { stroke: c.baseline }),
      Plot.tip(skYears, Plot.pointerX({ x: "year", y: "n", fontSize: 12, title: (d) => `${d.year}: ${d.n} sentences with a sceptic marker` })),
    ],
  }));
  draw("chart-sceptic-party", (w) => Plot.plot({
    width: w, height: 220, style, marginLeft: 80, marginRight: 40,
    x: { label: "sentences with a sceptic marker", grid: true },
    y: { label: null, domain: [...PT].sort((a, b) => b.sceptic - a.sceptic).map((d) => d.party) },
    marks: [
      Plot.barX(PT, { x: "sceptic", y: "party", fill: (d) => partyColor(d.party), rx: 4, insetTop: 3, insetBottom: 3 }),
      Plot.text(PT, { x: "sceptic", y: "party", text: (d) => int(d.sceptic), dx: 6, textAnchor: "start", fill: c.secondary }),
      Plot.ruleX([0], { stroke: c.baseline }),
    ],
  }));

  // ---------------------------------------------------------------- debate volume
  const LP = data.lp.map((d) => ({ ...d, date: toDate(d.first) }));
  draw("chart-volume", (w) => time(w, 230, { label: null, tickFormat: "s" }, [
    Plot.rectY(M, { x: "date", y: "sentences", interval: "month", fill: c.muted, fillOpacity: 0.6, inset: 0.3 }),
    Plot.ruleX(LP.slice(1), { x: "date", stroke: c.secondary, strokeDasharray: "3,3" }),
    Plot.text(LP.slice(1), { x: "date", text: (d) => `LP ${d.lp}`, frameAnchor: "top", dx: 4, dy: -14, textAnchor: "start", fill: c.secondary }),
    Plot.ruleY([0], { stroke: c.baseline }),
    ...crosshair(M, (d) => (d.sentences == null ? `${d.month}\nno plenary session` : `${d.month}\n${int(d.sentences)} sentences\n${int(d.speeches)} speeches`), "sentences"),
  ], { marginTop: 28 }));
}
