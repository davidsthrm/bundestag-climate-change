"""Harmonise manually exported Google Trends CSVs (see README, "Google Trends export").

Input : data/raw/trends/*.csv  (each export = one entry requested alone, region DE)
        data/raw/trends/check/*.csv  (re-exports <name>_2.csv for the sampling check, #4; not in the output)
Output: data/processed/trends_monthly.csv  (month, term, index, file)
        results/2_data_understanding/tables/05_trends_reexport.csv  (only if check/ has files)

Notes
- Values are relative (0-100) *within one export*; only terms from the same file are
  directly comparable. Keep the file name in the output so this stays traceable.
- '<1' is coded as 0.5.
- Works with English and German UI exports ("Month"/"Monat"/"Time"/"Zeit").
"""
from __future__ import annotations

import io
import re
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "trends"
CHECK = RAW / "check"  # re-exports for the sampling check (#4); not part of the output
OUT = ROOT / "data" / "processed" / "trends_monthly.csv"
TABLES = ROOT / "results" / "2_data_understanding" / "tables"
SETTINGS = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
START, END = SETTINGS["start_date"][:7], (SETTINGS["end_date"] or "9999-12")[:7]

HEADER_RE = re.compile(r'^"?(month|monat|time|zeit|woche|week|tag|day)"?\s*,', re.I)


def read_export(path: Path) -> pd.DataFrame:
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if HEADER_RE.match(l.strip())), None)
    if start is None:
        raise ValueError(f"{path.name}: no header line (Month/Monat/Time...) found")
    df = pd.read_csv(io.StringIO("\n".join(lines[start:])), dtype=str)
    time_col = df.columns[0]
    long = df.melt(id_vars=time_col, var_name="term", value_name="index")
    # "Klimawandel: (Deutschland)" -> "Klimawandel"
    long["term"] = long["term"].str.replace(r":\s*\(.*\)\s*$", "", regex=True).str.strip()
    long["index"] = pd.to_numeric(long["index"].str.replace("<1", "0.5", regex=False), errors="coerce")
    dates = pd.to_datetime(long[time_col], errors="coerce")
    if dates.dt.day.nunique() > 1:
        raise ValueError(f"{path.name}: data is not monthly - export a range of > 5 years")
    long["month"] = dates.dt.strftime("%Y-%m")
    long["file"] = path.name
    return long[["month", "term", "index", "file"]]


def reexport_check() -> None:
    """Compare each re-export in check/ (<name>_2.csv) with the first export <name>.csv (#4)."""
    rows = []
    for f in sorted(CHECK.glob("*.csv")):
        first = RAW / (re.sub(r"_\d+$", "", f.stem) + ".csv")
        m = (read_export(first).merge(read_export(f), on=["month", "term"], suffixes=("_1", "_2"))
             .query("@START <= month <= @END").sort_values("month"))
        d = m[["index_1", "index_2"]].diff()
        rows.append({"file_1": first.name, "file_2": f.name, "months": len(m),
                     "r_levels": m.index_1.corr(m.index_2), "r_changes": d.index_1.corr(d.index_2),
                     "max_abs_diff": (m.index_1 - m.index_2).abs().max()})
    if rows:
        TABLES.mkdir(parents=True, exist_ok=True)
        res = pd.DataFrame(rows).round(3)
        res.to_csv(TABLES / "05_trends_reexport.csv", index=False)
        print("\nre-export check (#4)\n" + res.to_string(index=False))


def main() -> None:
    files = sorted(RAW.glob("*.csv"))
    if not files:
        raise SystemExit("No CSVs in data/raw/trends/ - do the manual export first (README).")
    out = pd.concat([read_export(f) for f in files], ignore_index=True).dropna(subset=["month"])
    out = out[out["month"].between(START, END)]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.sort_values(["file", "term", "month"]).to_csv(OUT, index=False)
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(out.groupby(["file", "term"])["month"].agg(["min", "max", "count"]).to_string())
    reexport_check()


if __name__ == "__main__":
    main()
