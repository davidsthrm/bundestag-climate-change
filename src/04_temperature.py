"""Monthly temperature signal for Germany (DWD) and the globe (NASA GISTEMP v4).

Input  (via src/00_download.py temperature):
    data/raw/temperature/dwd/regional_averages_tm_01..12.txt
    data/raw/temperature/gistemp_GLB.Ts+dSST.csv
Output:
    data/processed/temperature_monthly.csv
    columns: month (YYYY-MM), temp_de, anomaly_de, anomaly_global
    Both anomalies are relative to the same baseline (config/sources.yaml,
    default 1991-2020), computed per calendar month (removes seasonality).
"""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "temperature"
OUT = ROOT / "data" / "processed" / "temperature_monthly.csv"
CFG = yaml.safe_load((ROOT / "config" / "sources.yaml").read_text(encoding="utf-8"))
SETTINGS = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))


def read_dwd_file(path: Path) -> pd.DataFrame:
    """One DWD file = one calendar month for all years. Header line starts with 'Jahr;'."""
    lines = path.read_text(encoding="latin-1").splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip().lower().startswith("jahr;"))
    df = pd.read_csv(io.StringIO("\n".join(lines[start:])), sep=";", dtype=str)
    df.columns = [c.strip() for c in df.columns]
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]
    df = df[pd.to_numeric(df["Jahr"], errors="coerce").notna()]
    return pd.DataFrame({
        "year": df["Jahr"].astype(int),
        "month_num": df["Monat"].astype(int),
        "temp_de": pd.to_numeric(df["Deutschland"].str.replace(",", "."), errors="coerce"),
    })


def read_dwd() -> pd.DataFrame:
    files = sorted((RAW / "dwd").glob("regional_averages_tm_*.txt"))
    if len(files) != 12:
        raise SystemExit(f"Expected 12 DWD files, found {len(files)}. Run: python src/00_download.py temperature")
    return pd.concat([read_dwd_file(f) for f in files], ignore_index=True)


def read_gistemp() -> pd.DataFrame:
    path = RAW / "gistemp_GLB.Ts+dSST.csv"
    if not path.exists():
        raise SystemExit("GISTEMP file missing. Run: python src/00_download.py temperature")
    df = pd.read_csv(path, skiprows=1, na_values=["***", "****"])
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    long = df.melt(id_vars="Year", value_vars=months, var_name="m", value_name="anomaly_global_5180")
    long["month_num"] = long["m"].map({m: i + 1 for i, m in enumerate(months)})
    long = long.rename(columns={"Year": "year"}).drop(columns="m")
    long["anomaly_global_5180"] = pd.to_numeric(long["anomaly_global_5180"], errors="coerce")
    return long


def anomaly(df: pd.DataFrame, col: str, base: tuple[int, int]) -> pd.Series:
    """Deviation from the per-calendar-month mean over the baseline years."""
    in_base = df["year"].between(*base)
    clim = df[in_base].groupby("month_num")[col].mean()
    return df[col] - df["month_num"].map(clim)


def main() -> None:
    base = tuple(CFG["temperature"]["baseline"])
    de, gl = read_dwd(), read_gistemp()
    df = de.merge(gl, on=["year", "month_num"], how="outer")
    df["anomaly_de"] = anomaly(df, "temp_de", base)
    df["anomaly_global"] = anomaly(df, "anomaly_global_5180", base)
    df["month"] = pd.to_datetime(dict(year=df.year, month=df.month_num, day=1)).dt.strftime("%Y-%m")

    start = pd.Timestamp(SETTINGS["start_date"]).to_period("M").strftime("%Y-%m")
    df = df[df["month"] >= start]
    df = df.dropna(subset=["temp_de", "anomaly_global"], how="all").sort_values("month")

    out = df[["month", "temp_de", "anomaly_de", "anomaly_global"]].round(3)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(out)} months, {out.month.min()} .. {out.month.max()} "
          f"(baseline {base[0]}-{base[1]}, analysis starts {start})")
    last = out.dropna().tail(3)
    print(last.to_string(index=False))


if __name__ == "__main__":
    main()
