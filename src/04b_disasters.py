"""Monthly climate-related disasters for Germany and the rest of the world (EM-DAT).

Input : data/raw/disasters/*.xlsx  (one manual EM-DAT export, see README "EM-DAT export (manual)")
Output: data/processed/disasters_monthly.csv
        columns: month (YYYY-MM), events_/deaths_/affected_ x de, row, global
        (de = Germany, row = rest of world without German events, global = all countries)
        results/3_data_preparation/tables/04b_disasters_per_year.csv (data check: reporting bias)

Rules (#17)
- Only the subgroups in config/sources.yaml (climatological, hydrological, meteorological).
- EM-DAT has one row per event and country (DisNo. "2021-0359-DEU"). Events are counted once per
  region by the ID without the country code; deaths and affected are summed over the rows.
- An event that hits Germany and other countries is a German event: it counts in de only, with
  the German deaths / affected. Its rows for the other countries count only in global.
  So events_de + events_row = events_global, but deaths / affected of de + row can be lower
  than global.
- Everything goes to the start month. Events without a start month are dropped (and reported).
- Blank deaths / affected = not reported, counted as 0.
- Every month from start_date to end_date is present; months without events are 0.
- Raw counts only: log transform and detrending happen in the modelling step (#12).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "disasters"
OUT = ROOT / "data" / "processed" / "disasters_monthly.csv"
TABLES = ROOT / "results" / "3_data_preparation" / "tables"
CFG = yaml.safe_load((ROOT / "config" / "sources.yaml").read_text(encoding="utf-8"))["emdat"]
SETTINGS = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))

COLS = ["DisNo.", "Disaster Subgroup", "ISO", "Start Year", "Start Month", "Total Deaths", "Total Affected"]
MEASURES = ["events", "deaths", "affected"]
REGIONS = ["de", "row", "global"]


def read_export() -> pd.DataFrame:
    files = sorted(RAW.glob("*.xlsx"))
    if len(files) != 1:
        raise SystemExit(f"Expected one EM-DAT .xlsx in data/raw/disasters/, found {len(files)}. "
                         "Do the manual export first (README).")
    df = pd.read_excel(files[0])
    missing = [c for c in COLS if c not in df.columns]
    if missing:
        raise SystemExit(f"{files[0].name}: columns {missing} not found. Columns: {list(df.columns)}")
    print(f"read {files[0].name}: {len(df)} rows")
    return df[COLS]


def checks(df: pd.DataFrame, out: pd.DataFrame) -> None:
    """Print the data checks from #17: reporting bias, heavy tails, zero months, late reporting."""
    print("\nevents per year (reporting bias: more events recorded in later years?)")
    by_year = (df.assign(year=df["month"].str[:4]).groupby(["year", "region"])
               .agg(events=("event_id", "nunique"), deaths=("Total Deaths", "sum")).unstack("region"))
    by_year.columns = [f"{m}_{r}" for m, r in by_year.columns]
    by_year = by_year.reindex(columns=[f"{m}_{r}" for r in REGIONS for m in ("events", "deaths")]).fillna(0).astype("int64")
    print(by_year.to_string())
    TABLES.mkdir(parents=True, exist_ok=True)
    by_year.to_csv(TABLES / "04b_disasters_per_year.csv")

    print("\nheavy tails (per month)")
    cols = [f"{m}_{r}" for r in REGIONS for m in ("deaths", "affected")]
    tails = out[cols].describe(percentiles=[0.5, 0.9, 0.99]).T[["50%", "90%", "99%", "max"]]
    tails["skew"] = out[cols].skew()
    tails["skew_log1p"] = np.log1p(out[cols]).skew()
    print(tails.round(1).to_string())

    zero_de = (out["events_de"] == 0).sum()
    print(f"\nmonths without a German event: {zero_de} of {len(out)}")
    split = df[df["region"] == "global"].groupby("event_id")["month"].nunique().gt(1).sum()
    print(f"events with different start months per country (counted in each month): {split}")
    print("\nlast 6 months (EM-DAT adds events late: low values may be incomplete)")
    print(out.tail(6).to_string())


def main() -> None:
    df = read_export()
    start = SETTINGS["start_date"][:7]
    if df["Start Year"].min() > int(start[:4]):
        raise SystemExit(f"Export starts in {df['Start Year'].min()}, analysis starts {start}: export more years.")

    found = set(df["Disaster Subgroup"])
    unknown = set(CFG["subgroups"]) - found
    if unknown:
        raise SystemExit(f"Subgroups {sorted(unknown)} not in the export. Found: {sorted(found)}")
    print("rows per subgroup (kept: " + ", ".join(CFG["subgroups"]) + ")")
    print(df["Disaster Subgroup"].value_counts().to_string())
    df = df[df["Disaster Subgroup"].isin(CFG["subgroups"])]

    end = (SETTINGS["end_date"] or f"{df['Start Year'].max()}-12")[:7]
    in_window = df["Start Year"].between(int(start[:4]), int(end[:4]))
    no_month = df["Start Month"].isna() & in_window
    print(f"\ndropped (no start month, {start[:4]}-{end[:4]}): {no_month.sum()} rows, "
          f"{df.loc[no_month, 'Total Deaths'].sum():.0f} of {df.loc[in_window, 'Total Deaths'].sum():.0f} deaths")
    df = df[df["Start Month"].notna()].copy()

    df["month"] = (df["Start Year"].astype(int).astype(str) + "-"
                   + df["Start Month"].astype(int).astype(str).str.zfill(2))
    if df["month"].max() < end:
        raise SystemExit(f"Export ends {df['month'].max()}, end_date is {end}: export again.")
    df = df[df["month"].between(start, end)].copy()
    df["event_id"] = df["DisNo."].str.rsplit("-", n=1).str[0]
    is_de = df["ISO"] == CFG["country_iso"]
    german = df["event_id"].isin(df.loc[is_de, "event_id"])
    shared = df[german & ~is_de]
    print(f"German events also in other countries: {shared['event_id'].nunique()} of "
          f"{df.loc[is_de, 'event_id'].nunique()} (counted as German; other-country rows only in global: "
          f"{shared['Total Deaths'].sum():.0f} deaths, {shared['Total Affected'].sum():.0f} affected)")
    df = pd.concat([df[is_de].assign(region="de"), df[~german].assign(region="row"),
                    df.assign(region="global")], ignore_index=True)

    agg = df.groupby(["month", "region"]).agg(events=("event_id", "nunique"),
                                             deaths=("Total Deaths", "sum"),
                                             affected=("Total Affected", "sum")).unstack("region")
    agg.columns = [f"{m}_{r}" for m, r in agg.columns]
    months = pd.period_range(start, end, freq="M").strftime("%Y-%m")
    cols = [f"{m}_{r}" for r in REGIONS for m in MEASURES]
    out = agg.reindex(index=months, columns=cols).fillna(0).astype("int64")
    out.index.name = "month"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT)
    print(f"\nwrote {OUT.relative_to(ROOT)}: {len(out)} months, {out.index.min()} .. {out.index.max()}")
    checks(df, out)


if __name__ == "__main__":
    main()
