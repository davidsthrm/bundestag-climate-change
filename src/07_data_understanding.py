"""Data understanding (#22): describe every series the hypotheses need, on one monthly axis.
Descriptive only: no hypothesis tests (H1/H2 are tested in #12).

Input : data/interim/sentences_relevant.parquet  (src/02_relevance.py; if missing, sentences.parquet
                                                 and the attention columns stay empty)
        data/processed/temperature_monthly.csv   (src/04_temperature.py)
        data/processed/disasters_monthly.csv     (src/04b_disasters.py)
        data/processed/heat_mortality_monthly.csv (src/04c_heat_mortality.py, optional)
        data/processed/trends_monthly.csv        (src/05_trends.py)
Output: results/2_data_understanding/tables/07_*.csv   (read by the viz app via viz/export_data.py)
        results/2_data_understanding/figures/07_*.png  (for the paper)

Tables
  07_profile         rows, columns, months per input file
  07_monthly         all series on one monthly axis (the join), incl. 12-month rolling means and
                     detrended z-scores (*_detr_z, see detrend())
  07_missing         months without a value per series
  07_corpus_lp       speeches, sentences, speech length per legislative period
  07_corpus_party    speeches, sentences, relevant sentences, main-topic speeches per party
  07_party_year      climate share per party and year (H3, descriptive)
  07_gov_year        climate share government vs. opposition per year (H3, descriptive)
  07_stance_units    relevant sentences per party-month and party-quarter (H1b/H3: monthly or quarterly?)
  07_trends_spikes   per Trends term the 3 months with the largest jump over their neighbours
  07_events_de       months with a German EM-DAT event and attention (a) from 1 month before to 2 after (H2)
  07_event_study     mean attention (a) at each offset around German event months vs. the mean of all months
  07_summary         key numbers for results/2_data_understanding/README.md

python src/07_data_understanding.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "results" / "2_data_understanding"
SETTINGS = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
EMDAT_COMPLETE = yaml.safe_load((ROOT / "config" / "sources.yaml").read_text(encoding="utf-8"))["emdat"]["complete_until"]
START, END = SETTINGS["start_date"][:7], (SETTINGS["end_date"] or "9999-12")[:7]
MONTHS = pd.period_range(START, END, freq="M").strftime("%Y-%m")

RELEVANT = INTERIM / "sentences_relevant.parquet"
SENTENCES = INTERIM / "sentences.parquet"
HEAT = PROCESSED / "heat_mortality_monthly.csv"
SENT_COLS = ["speech_id", "month", "lp", "party", "party_in_government"]
REL_COLS = ["relevant", "sceptic", "main_topic"]
ROLL = 12  # months in the rolling mean (display only)
DETREND = ["share_a", "share_b", "trends_Klimawandel", "anomaly_global", "events_global"]

# colours of the viz app (viz/src/styles/global.css, light theme), so paper and app match
INK, MUTED, GRID = "#0b0b0b", "#898781", "#e1e0d9"
BUNDESTAG, TRENDS, DISASTERS, GLOBAL = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"


def read_sentences() -> tuple[pd.DataFrame, bool]:
    if RELEVANT.exists():
        return pd.read_parquet(RELEVANT, columns=SENT_COLS + REL_COLS), True
    print(f"{RELEVANT.relative_to(ROOT)} missing: attention columns stay empty (run src/02_relevance.py)")
    return pd.read_parquet(SENTENCES, columns=SENT_COLS), False


def profile(files: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return pd.DataFrame([{"file": name, "rows": len(df), "columns": df.shape[1],
                          "first_month": df["month"].min(), "last_month": df["month"].max(),
                          "column_names": ";".join(df.columns)} for name, df in files.items()])


def monthly(sent: pd.DataFrame, has_rel: bool, temp, dis, trends, heat) -> pd.DataFrame:
    speeches = sent.drop_duplicates("speech_id")
    m = pd.DataFrame({"sentences": sent.groupby("month").size(),
                      "speeches": speeches.groupby("month").size()})
    if has_rel:
        m["relevant"] = sent.groupby("month")["relevant"].sum()
        m["main_topic"] = speeches.groupby("month")["main_topic"].sum()
        m["share_a"] = m["relevant"] / m["sentences"]
        m["share_b"] = m["main_topic"] / m["speeches"]
    m = m.reindex(MONTHS)
    m["sitting"] = m["sentences"].notna()  # months without sittings stay empty, not 0 (PR #19)

    tr = trends.pivot_table(index="month", columns="term", values="index").add_prefix("trends_")
    dis = dis.set_index("month")[[f"{v}_{r}" for v in ("events", "deaths") for r in ("de", "row", "global")]]
    parts = [m, temp.set_index("month")[["anomaly_de", "anomaly_global"]], dis, tr]
    if heat is not None:
        parts.append(heat.set_index("month")[["heat_deaths_de"]])
    df = pd.concat(parts, axis=1).reindex(MONTHS)
    df.index.name = "month"

    roll_cols = ["anomaly_de", "anomaly_global", "events_de", "events_row", "events_global", *tr.columns]
    for c in roll_cols:
        df[f"{c}_12m"] = df[c].rolling(ROLL, min_periods=ROLL // 2).mean()
    if has_rel:  # ratio of sums over the window, so recess months count as 0/0, not as 0 %
        s = df[["relevant", "sentences", "main_topic", "speeches"]].fillna(0).rolling(ROLL, min_periods=ROLL // 2).sum()
        df["share_a_12m"] = s["relevant"] / s["sentences"].replace(0, np.nan)
        df["share_b_12m"] = s["main_topic"] / s["speeches"].replace(0, np.nan)
    return detrend(df.reset_index())


def detrend(df: pd.DataFrame) -> pd.DataFrame:
    """Display only, NOT the method of #12: residuals of a linear trend + calendar-month dummies,
    as z-scores. Months without a value (no sittings) are left out of the fit and stay empty."""
    t = np.arange(len(df))
    dummies = pd.get_dummies(pd.to_datetime(df["month"]).dt.month, drop_first=True).to_numpy(float)
    X = np.column_stack([np.ones(len(df)), t, dummies])
    for c in [c for c in DETREND if c in df]:
        y = df[c].to_numpy(float)
        ok = ~np.isnan(y)
        beta, *_ = np.linalg.lstsq(X[ok], y[ok], rcond=None)
        resid = np.where(ok, y - X @ beta, np.nan)
        df[f"{c}_detr_z"] = resid / np.nanstd(resid)
    return df


def events_de(df: pd.DataFrame) -> pd.DataFrame:
    """Months with a German disaster and attention (a) around them; descriptive event view for H2."""
    out = df.loc[df["events_de"] > 0, ["month", "events_de", "deaths_de"]].copy()
    if "share_a" in df:
        for k in (-1, 0, 1, 2):
            out[f"share_a_t{k:+d}"] = df["share_a"].shift(-k).loc[out.index].round(5)
        out["share_a_mean_all"] = round(df["share_a"].mean(), 5)
    return out


def event_study(ev: pd.DataFrame) -> pd.DataFrame:
    """Mean over German event months per offset; months without sittings are left out."""
    rows = []
    for k in (-1, 0, 1, 2):
        v = ev[f"share_a_t{k:+d}"].dropna()
        rows.append({"offset": k, "events": len(v), "mean_share_a": round(v.mean(), 5),
                     "diff_pp": round((v.mean() - ev["share_a_mean_all"].iloc[0]) * 100, 3)})
    return pd.DataFrame(rows)


def missing(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in df.columns if c not in ("month", "sitting") and not c.endswith(("_12m", "_detr_z"))]
    return pd.DataFrame([{"series": c, "months": len(df), "missing": int(df[c].isna().sum()),
                          "first_month": df.loc[df[c].notna(), "month"].min(),
                          "last_month": df.loc[df[c].notna(), "month"].max()} for c in cols])


def corpus_lp(sent: pd.DataFrame) -> pd.DataFrame:
    per_speech = sent.groupby(["lp", "speech_id"]).size().rename("n").reset_index()
    out = per_speech.groupby("lp")["n"].agg(speeches="size", sentences="sum",
                                            mean_sentences_per_speech="mean",
                                            median_sentences_per_speech="median")
    out = out.join(sent.groupby("lp")["month"].agg(first_month="min", last_month="max"))
    return out.round(2).reset_index()


def corpus_party(sent: pd.DataFrame, has_rel: bool) -> pd.DataFrame:
    party = sent["party"].fillna("(unknown)")
    g = sent.assign(party=party).groupby("party")
    out = pd.DataFrame({"speeches": g["speech_id"].nunique(), "sentences": g.size()})
    out["share_of_sentences"] = out["sentences"] / out["sentences"].sum()
    if has_rel:
        out["relevant"] = g["relevant"].sum()
        out["share_relevant"] = out["relevant"] / out["sentences"]
        out["sceptic"] = g["sceptic"].sum()
        out["main_topic_speeches"] = (sent.assign(party=party).drop_duplicates("speech_id")
                                      .groupby("party")["main_topic"].sum())
    return out.sort_values("sentences", ascending=False).round(5).reset_index()


def share_by(sent: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    out = sent.groupby(keys).agg(sentences=("relevant", "size"), relevant=("relevant", "sum"))
    out["share"] = (out["relevant"] / out["sentences"]).round(5)
    return out.reset_index()


def stance_units(sent: pd.DataFrame) -> pd.DataFrame:
    """Relevant sentences per party and period; only periods with sittings, 0 if a party was silent."""
    rel = sent.dropna(subset=["party"]).assign(quarter=lambda d: pd.PeriodIndex(d["month"], freq="M")
                                                 .asfreq("Q").astype(str))
    rows = []
    for grain, col in (("month", "month"), ("quarter", "quarter")):
        n = rel.groupby(["party", col])["relevant"].sum().unstack(fill_value=0)
        active = rel.groupby(["party", col]).size().unstack().notna()  # party spoke in that period
        for party in n.index:
            v = n.loc[party][active.loc[party]]
            rows.append({"party": party, "grain": grain, "periods": len(v), "zero": int((v == 0).sum()),
                         "p10": v.quantile(0.1), "p25": v.quantile(0.25), "median": v.median(),
                         "total": int(v.sum())})
    return pd.DataFrame(rows).sort_values(["grain", "total"], ascending=[True, False]).round(1)


def trends_spikes(df: pd.DataFrame) -> pd.DataFrame:
    """Jump = value / median of the 6 months before and after (the month itself excluded)."""
    rows = []
    for c in [c for c in df.columns if c.startswith("trends_") and not c.endswith(("_12m", "_detr_z"))]:
        s = df.set_index("month")[c]
        around = pd.concat([s.shift(k) for k in [*range(-6, 0), *range(1, 7)]], axis=1).median(axis=1)
        ratio = (s / around.replace(0, np.nan)).nlargest(3)
        rows += [{"term": c.removeprefix("trends_"), "month": mo, "index": s[mo],
                  "median_around": around[mo], "ratio": round(r, 2)} for mo, r in ratio.items()]
    return pd.DataFrame(rows)


def summary(df: pd.DataFrame, sent: pd.DataFrame, has_rel: bool, units: pd.DataFrame) -> pd.DataFrame:
    rows = [
        ("months", len(df), "months in the window"),
        ("months_with_sittings", int(df["sitting"].sum()), "months with at least one speech sentence"),
        ("speeches", int(sent["speech_id"].nunique()), "speeches"),
        ("sentences", len(sent), "speech sentences"),
        ("share_unknown_party", round(sent["party"].isna().mean(), 5), "share of sentences without party"),
        ("months_zero_events_de", int((df["events_de"] == 0).sum()), "months with 0 German EM-DAT events"),
    ]
    if has_rel:
        rows += [
            ("relevant_sentences", int(sent["relevant"].sum()), "climate-relevant sentences"),
            ("main_topic_speeches", int(sent.drop_duplicates("speech_id")["main_topic"].sum()),
             "speeches with climate as main topic"),
            ("share_a_mean", round(df["share_a"].mean(), 5), "mean monthly share of relevant sentences"),
            ("share_b_mean", round(df["share_b"].mean(), 5), "mean monthly share of main-topic speeches"),
        ]
        for grain in ("month", "quarter"):
            u = units[units["grain"] == grain]
            rows.append((f"min_party_median_per_{grain}", u["median"].min(),
                         f"smallest party median of relevant sentences per {grain}"))
    return pd.DataFrame(rows, columns=["key", "value", "meaning"])


def _axis(ax, title: str, unit: str) -> None:
    ax.set_title(title, loc="left", fontsize=10, color=INK)
    ax.set_ylabel(unit, fontsize=8, color=MUTED)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8)


def _panel(ax, x, monthly_vals, rolled, color, title, unit) -> None:
    ax.bar(x, monthly_vals, width=25, color=color, alpha=0.3, linewidth=0)
    ax.plot(x, rolled, color=color, linewidth=2)
    ax.axhline(0, color=MUTED, linewidth=0.6)
    _axis(ax, title, unit)


def _incomplete(ax, df: pd.DataFrame) -> None:
    """Shade EM-DAT months after complete_until (late reporting)."""
    start = pd.Period(EMDAT_COMPLETE, freq="M") + 1
    ax.axvspan(start.to_timestamp(), pd.to_datetime(df["month"].iloc[-1]) + pd.offsets.MonthEnd(),
               color=MUTED, alpha=0.15, linewidth=0)
    ax.text(start.to_timestamp(), ax.get_ylim()[1], " incomplete", fontsize=7, color=MUTED, va="top")


def fig_h1(df: pd.DataFrame, has_rel: bool, path: Path) -> None:
    x = pd.to_datetime(df["month"])
    fig, axes = plt.subplots(4, 1, figsize=(8, 8.5), sharex=True)
    if has_rel:
        _panel(axes[0], x, df["share_a"] * 100, df["share_a_12m"] * 100, BUNDESTAG,
               "Bundestag: share of climate-relevant sentences (a)", "%")
    else:
        _axis(axes[0], "Bundestag attention: run src/02_relevance.py first", "%")
    _panel(axes[1], x, df["trends_Klimawandel"], df["trends_Klimawandel_12m"], TRENDS,
           "Public attention: Google Trends “Klimawandel” (DE)", "index 0–100")
    _panel(axes[2], x, df["anomaly_global"], df["anomaly_global_12m"], GLOBAL,
           "Physical signal: global temperature anomaly (GISTEMP)", "°C vs 1991–2020")
    _panel(axes[3], x, df["events_global"], df["events_global_12m"], DISASTERS,
           "Physical signal: climate-related disasters worldwide (EM-DAT)", "events per month")
    _incomplete(axes[3], df)
    fig.text(0.01, 0.005, f"Bars: monthly values. Line: {ROLL}-month rolling mean. "
             "Empty Bundestag months: no sittings.", fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(path, dpi=200)
    plt.close(fig)


def fig_h2(df: pd.DataFrame, path: Path) -> None:
    x = pd.to_datetime(df["month"])
    fig, axes = plt.subplots(2, 1, figsize=(8, 5.5), sharex=True)
    for col, color, label in (("anomaly_de", INK, "Germany (DWD)"), ("anomaly_global", GLOBAL, "global (GISTEMP)")):
        axes[0].plot(x, df[f"{col}_12m"], color=color, linewidth=2, label=label)
    axes[0].axhline(0, color=MUTED, linewidth=0.6)
    _axis(axes[0], f"Temperature anomaly, {ROLL}-month rolling mean", "°C vs 1991–2020")
    axes[0].legend(frameon=False, fontsize=8)
    axes[1].bar(x, df["events_de"], width=25, color=INK, linewidth=0, label="Germany")
    axes[1].plot(x, df["events_row_12m"], color=DISASTERS, linewidth=2, label=f"rest of world ({ROLL}-month mean)")
    axes[1].set_yscale("symlog", linthresh=1)
    _axis(axes[1], "Climate-related disasters (EM-DAT): Germany vs. rest of world", "events per month (log)")
    axes[1].legend(frameon=False, fontsize=8)
    _incomplete(axes[1], df)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def fig_volume(df: pd.DataFrame, lp: pd.DataFrame, path: Path) -> None:
    x = pd.to_datetime(df["month"])
    fig, ax = plt.subplots(figsize=(8, 2.8))
    ax.bar(x, df["sentences"] / 1000, width=25, color=MUTED, linewidth=0)
    for _, row in lp.iloc[1:].iterrows():
        d = pd.to_datetime(row["first_month"])
        ax.axvline(d, color=INK, linewidth=0.6, linestyle=":")
        ax.text(d, ax.get_ylim()[1], f" LP {row['lp']}", fontsize=7, color=MUTED, va="top")
    _axis(ax, "Speech sentences per month (gaps: no sittings)", "thousand sentences")
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main() -> None:
    sent, has_rel = read_sentences()
    sent = sent[sent["month"].between(START, END)]
    temp = pd.read_csv(PROCESSED / "temperature_monthly.csv")
    dis = pd.read_csv(PROCESSED / "disasters_monthly.csv")
    trends = pd.read_csv(PROCESSED / "trends_monthly.csv")
    heat = pd.read_csv(HEAT) if HEAT.exists() else None

    files = {(RELEVANT if has_rel else SENTENCES).name: sent, "temperature_monthly.csv": temp,
             "disasters_monthly.csv": dis, "trends_monthly.csv": trends}
    if heat is not None:
        files[HEAT.name] = heat

    df = monthly(sent, has_rel, temp, dis, trends, heat)
    lp = corpus_lp(sent)
    tables = {"07_profile": profile(files), "07_monthly": df, "07_missing": missing(df),
              "07_corpus_lp": lp, "07_corpus_party": corpus_party(sent, has_rel),
              "07_trends_spikes": trends_spikes(df), "07_events_de": events_de(df)}
    if has_rel:
        sent["year"] = sent["month"].str[:4].astype(int)
        gov = sent.dropna(subset=["party_in_government"]).assign(
            side=lambda d: np.where(d["party_in_government"].astype(bool), "government", "opposition"))
        tables["07_party_year"] = share_by(sent.dropna(subset=["party"]), ["party", "year"])
        tables["07_gov_year"] = share_by(gov, ["side", "year"])
        tables["07_stance_units"] = stance_units(sent)
        tables["07_event_study"] = event_study(tables["07_events_de"])
    tables["07_summary"] = summary(df, sent, has_rel, tables.get("07_stance_units"))

    (OUT / "tables").mkdir(parents=True, exist_ok=True)
    (OUT / "figures").mkdir(parents=True, exist_ok=True)
    for name, t in tables.items():
        t.to_csv(OUT / "tables" / f"{name}.csv", index=False)
    fig_h1(df, has_rel, OUT / "figures" / "07_h1_signals.png")
    fig_h2(df, OUT / "figures" / "07_h2_germany_vs_world.png")
    fig_volume(df, lp, OUT / "figures" / "07_corpus_volume.png")

    print(tables["07_summary"].to_string(index=False))
    print(f"wrote {len(tables)} tables and 3 figures to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
