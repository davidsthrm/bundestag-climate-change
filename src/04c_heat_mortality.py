"""Heat-related deaths in Germany (RKI model estimates), monthly 2016-today and yearly 2004-today (#26).

Input (via src/00_download.py rki):
    data/raw/heat/rki_hitzemortalitaet_weekly.csv   RKI weekly report, summer weeks 15-40 since 2016:
                                                    deaths modelled with and without heat
    data/raw/heat/rki_hitzemortalitaet_yearly.csv   RKI yearly estimates since 2016 (same report)
    config/heat_deaths_paper.yaml                   Winklmayr et al. 2022, eTable 2004-2021
Output:
    data/processed/heat_mortality_monthly.csv   month, heat_deaths_de, weeks_modelled  (2016-01 .. end_date)
    data/processed/heat_mortality_yearly.csv    year, heat_deaths_de, lower, upper, source  (start_date .. )
    results/3_data_preparation/tables/04c_heat_yearly_check.csv  weekly sums vs. RKI yearly vs. paper

Rules
- Weekly heat deaths = "Modell mit Hitze" - "Modell ohne Hitze" (point estimates). All modelled weeks
  count, also the few slightly negative ones: the RKI yearly values are these sums (rounded).
- A week goes to the month of its Thursday (ISO week).
- Months without a modelled week (winter half-year) are 0: the model has no heat effect there.
  weeks_modelled shows how many weeks a month has; it is lower where the report stopped (2026: week 37).
- Yearly: RKI report for 2016 onwards; the paper's eTable (earlier model version) before 2016.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "heat"
OUT_M = ROOT / "data" / "processed" / "heat_mortality_monthly.csv"
OUT_Y = ROOT / "data" / "processed" / "heat_mortality_yearly.csv"
TABLES = ROOT / "results" / "3_data_preparation" / "tables"
SETTINGS = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))

def need(path: Path) -> Path:
    if not path.exists():
        raise SystemExit(f"{path.relative_to(ROOT)} missing. Run: python src/00_download.py rki")
    return path


def read_weekly() -> pd.DataFrame:
    w = pd.read_csv(need(RAW / "rki_hitzemortalitaet_weekly.csv"), sep=";", decimal=",", na_values="NA")
    w = w.dropna(subset=["Modell_Punktschätzer"])
    p = w.pivot_table(index=["Jahr", "Woche"], columns="Modell", values="Modell_Punktschätzer").reset_index()
    p["heat_deaths"] = p["Modell mit Hitze"] - p["Modell ohne Hitze"]
    p["month"] = [date.fromisocalendar(y, wk, 4).strftime("%Y-%m") for y, wk in zip(p["Jahr"], p["Woche"])]
    print(f"weekly: {len(p)} modelled weeks, {p['Jahr'].min()}-{p['Jahr'].max()}, "
          f"report date {w['Berichtsdatum'].iloc[0]}")
    return p


def read_yearly_report() -> pd.DataFrame:
    y = pd.read_csv(need(RAW / "rki_hitzemortalitaet_yearly.csv"), sep=";", dtype=str)
    num = lambda c: y[c].str.replace(".", "", regex=False).astype(int)
    return pd.DataFrame({"year": y["Jahr"].astype(int), "heat_deaths_de": num("Modell_Punktschätzer"),
                         "lower": num("Modell_untere_PG"), "upper": num("Modell_obere_PG"),
                         "source": "RKI report " + y["Berichtsdatum"]})


def read_paper() -> pd.DataFrame:
    """eTable of Winklmayr et al. 2022 (config/heat_deaths_paper.yaml): year -> [estimate, lower, upper]."""
    years = yaml.safe_load((ROOT / "config" / "heat_deaths_paper.yaml").read_text(encoding="utf-8"))["years"]
    t = pd.DataFrame([(y, *v) for y, v in years.items()], columns=["year", "heat_deaths_de", "lower", "upper"])
    t["source"] = "Winklmayr et al. 2022, eTable"
    return t


def main() -> None:
    weeks = read_weekly()
    start, end = SETTINGS["start_date"][:7], (SETTINGS["end_date"] or weeks["month"].max())[:7]
    report, paper = read_yearly_report(), read_paper()

    first = f"{weeks['Jahr'].min()}-01"
    months = pd.period_range(first, end, freq="M").strftime("%Y-%m")
    monthly = (weeks.groupby("month").agg(heat_deaths_de=("heat_deaths", "sum"), weeks_modelled=("Woche", "size"))
               .reindex(months).fillna(0).round().astype("int64"))
    monthly.index.name = "month"

    yearly = pd.concat([paper[paper["year"] < report["year"].min()], report], ignore_index=True)
    yearly = yearly[yearly["year"] >= int(start[:4])].sort_values("year")

    check = (weeks.groupby("Jahr")["heat_deaths"].sum().round().astype("int64").rename("weekly_sum").to_frame()
             .join(report.set_index("year")["heat_deaths_de"].rename("rki_report"))
             .join(paper.set_index("year")["heat_deaths_de"].rename("winklmayr2022")))
    check.index.name = "year"

    for path, df in ((OUT_M, monthly), (OUT_Y, yearly.set_index("year"))):
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path)
        print(f"wrote {path.relative_to(ROOT)}: {len(df)} rows, {df.index.min()} .. {df.index.max()}")
    TABLES.mkdir(parents=True, exist_ok=True)
    check.to_csv(TABLES / "04c_heat_yearly_check.csv")

    print("\nyearly check: weekly sums vs. RKI yearly (should match up to rounding) vs. paper (older model)")
    print(check.to_string())
    dev = (check["weekly_sum"] - check["rki_report"]).abs()
    print(f"max |weekly sum - RKI yearly|: {dev.max()} ({dev.idxmax()})")
    print("\nmonths with most heat deaths")
    print(monthly.sort_values("heat_deaths_de", ascending=False).head(6).to_string())
    print("\nlast 6 months (weeks_modelled < usual = report stopped)")
    print(monthly.tail(6).to_string())


if __name__ == "__main__":
    main()
