"""Aggregate the pipeline outputs into one small JSON file for the visualisation app (viz/).

Input : data/interim/sentences.parquet           (src/01_speeches.py)
        data/processed/temperature_monthly.csv   (src/04_temperature.py)
        data/processed/trends_monthly.csv        (src/05_trends.py)
        config/keywords_de.yaml
Output: viz/src/data/viz.json  (not committed, like all derived data)

Climate relevance here is a PROVISIONAL stand-in for step 2: a sentence counts as climate-related
if it contains a term from the "core" list (case-insensitive substring match, "CO 2" read as "co2"). Replace with the
output of src/02_relevance.py once that exists.

Usage (from repo root): python viz/export_data.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
SENTENCES = ROOT / "data" / "interim" / "sentences.parquet"
TEMP = ROOT / "data" / "processed" / "temperature_monthly.csv"
TRENDS = ROOT / "data" / "processed" / "trends_monthly.csv"
OUT = ROOT / "viz" / "src" / "data" / "viz.json"
KEYWORDS = yaml.safe_load((ROOT / "config" / "keywords_de.yaml").read_text(encoding="utf-8"))
SETTINGS = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
PARTIES = ["CDU/CSU", "SPD", "GRÜNE", "FDP", "DIE LINKE", "AfD", "BSW"]


def pattern(terms: list[str]) -> str:
    return "|".join(re.escape(t.lower()) for t in terms)


def r(x: float | None, nd: int = 4) -> float | None:
    return None if x is None or pd.isna(x) else round(float(x), nd)


def records(df: pd.DataFrame, nd: int = 4) -> list[dict]:
    return [{k: (r(v, nd) if isinstance(v, (float, np.floating)) else v) for k, v in row.items()}
            for row in df.to_dict("records")]


def main() -> None:
    cols = ["speech_id", "month", "lp", "role", "party", "party_in_government", "text"]
    df = pd.read_parquet(SENTENCES, columns=cols)
    df["year"] = df["month"].str[:4].astype(int)
    # many protocols render the subscript in CO₂ as "CO 2" (e.g. all of 2009), which "co2" would miss
    low = df["text"].str.lower().str.replace("co 2", "co2", regex=False)
    df["climate"] = low.str.contains(pattern(KEYWORDS["core"]), regex=True)
    df["energy"] = low.str.contains(pattern(KEYWORDS["energy"]), regex=True)
    df["sceptic"] = low.str.contains(pattern(KEYWORDS["sceptic_markers"]), regex=True)
    print(f"{len(df):,} sentences, {df.climate.sum():,} climate (core), {df.energy.sum():,} energy, "
          f"{df.sceptic.sum():,} sceptic markers")

    # keyword hits per year (sentence counts; one sentence can contain several terms)
    kw_rows = []
    for group in ("core", "energy", "sceptic_markers"):
        for term in KEYWORDS[group]:
            hits = low.str.contains(term.lower(), regex=False)
            for year, n in df.loc[hits, "year"].value_counts().sort_index().items():
                kw_rows.append({"term": term, "group": group, "year": int(year), "n": int(n)})
    del low

    # ---- monthly Bundestag series
    start, end = SETTINGS["start_date"][:7], (SETTINGS["end_date"] or "9999-12")[:7]
    months = pd.period_range(start, end, freq="M").strftime("%Y-%m")
    m = df.groupby("month").agg(sentences=("climate", "size"), climate=("climate", "sum"),
                                energy=("energy", "sum"), sceptic=("sceptic", "sum"),
                                speeches=("speech_id", "nunique"))
    sp = df.groupby(["month", "speech_id"])["climate"].any().groupby("month").sum().rename("climate_speeches")
    m = m.join(sp).reindex(months)
    m["share"] = m.climate / m.sentences
    m["speech_share"] = m.climate_speeches / m.speeches
    # 12-month rolling share = climate sentences / all sentences over the window (recess months count as 0/0)
    roll = m[["climate", "sentences"]].fillna(0).rolling(12, min_periods=6).sum()
    m["share_12m"] = roll.climate / roll.sentences.replace(0, np.nan)

    temp = pd.read_csv(TEMP).set_index("month").reindex(months)
    trends = pd.read_csv(TRENDS).pivot_table(index="month", columns="term", values="index").reindex(months)
    for c in ["anomaly_de", "anomaly_global"]:
        temp[c + "_12m"] = temp[c].rolling(12, min_periods=6).mean()
    for c in trends.columns:
        trends[c + "_12m"] = trends[c].rolling(12, min_periods=6).mean()

    monthly = pd.concat([m, temp, trends], axis=1).reset_index().rename(columns={"index": "month"})
    for c in ["sentences", "climate", "energy", "sceptic", "speeches", "climate_speeches"]:
        monthly[c] = monthly[c].astype("Int64")

    # ---- correlations (monthly values, session months only)
    sig = monthly.set_index("month")
    targets = {"Climate sentence share": "share", "Climate speech share": "speech_share"}
    drivers = {"Trends: Klimawandel": "Klimawandel", "Trends: Klimaschutz": "Klimaschutz",
               "Trends: Klima": "Klima", "Trends: Hitzewelle": "Hitzewelle",
               "Temp. anomaly DE": "anomaly_de", "Temp. anomaly global": "anomaly_global"}
    corr = []
    for tname, t in targets.items():
        for dname, d in drivers.items():
            row = {"target": tname, "driver": dname}
            for lag in (0, 1, 3, 12):
                row[f"lag{lag}"] = r(sig[t].astype(float).corr(sig[d].shift(lag)), 3)
            # smoothed series: rolling windows overlap, so this r looks stronger than it is
            row["lag0_12m"] = r(sig["share_12m"].corr(sig[d + "_12m"]), 3) if t == "share" else None
            corr.append(row)

    # ---- parties, government/opposition, roles (per year)
    pdf = df[df.party.isin(PARTIES)]
    party_year = (pdf.groupby(["party", "year"]).agg(sentences=("climate", "size"), climate=("climate", "sum"),
                                                     sceptic=("sceptic", "sum"))
                  .reset_index())
    party_year["share"] = party_year.climate / party_year.sentences
    party_year = party_year[party_year.sentences >= 2000]  # drop tiny party-years (e.g. BSW 2024)
    party_total = (pdf.groupby("party").agg(sentences=("climate", "size"), climate=("climate", "sum"),
                                            sceptic=("sceptic", "sum"), speeches=("speech_id", "nunique"))
                   .reindex(PARTIES).reset_index())
    party_total["share"] = party_total.climate / party_total.sentences
    party_total["sceptic_per_1000_climate"] = 1000 * party_total.sceptic / party_total.climate

    gov = df.dropna(subset=["party_in_government"]).copy()
    gov["side"] = np.where(gov.party_in_government.astype(bool), "Government parties", "Opposition")
    gov_year = gov.groupby(["side", "year"]).agg(sentences=("climate", "size"), climate=("climate", "sum")).reset_index()
    gov_year["share"] = gov_year.climate / gov_year.sentences

    lp = df.groupby("lp").agg(sentences=("climate", "size"), climate=("climate", "sum"),
                              speeches=("speech_id", "nunique"), first=("month", "min"), last=("month", "max")).reset_index()
    lp["share"] = lp.climate / lp.sentences

    role = df.groupby("role").agg(sentences=("climate", "size"), climate=("climate", "sum")).reset_index()
    role["share"] = role.climate / role.sentences

    out = {
        "meta": {
            "sentences": int(len(df)), "speeches": int(df.speech_id.nunique()),
            "climate_sentences": int(df.climate.sum()), "energy_sentences": int(df.energy.sum()),
            "sceptic_sentences": int(df.sceptic.sum()),
            "first_month": start, "last_month": end, "n_months": len(months),
            "session_months": int(m.sentences.notna().sum()),
            "keywords": {k: KEYWORDS[k] for k in ("core", "energy", "sceptic_markers")},
            "trend_terms": [c for c in trends.columns if not c.endswith("_12m")],
        },
        "monthly": records(monthly, 5),
        "correlations": corr,
        "party_year": records(party_year, 5),
        "party_total": records(party_total, 5),
        "gov_year": records(gov_year, 5),
        "lp": records(lp, 5),
        "role": records(role, 5),
        "keywords_year": kw_rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, default=lambda v: None if pd.isna(v) else int(v)),
                   encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1e3:,.0f} kB)")


if __name__ == "__main__":
    main()
