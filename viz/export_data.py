"""Pack the data-understanding tables into one JSON file for the visualisation app (viz/).
No computation here: every number comes from src/07_data_understanding.py (#22), so the app and
the paper show the same values.

Input : results/2_data_understanding/tables/07_*.csv
        config/sources.yaml (Trends topic break)
Output: viz/src/data/viz.json  (not committed, like all derived data)

Usage (from repo root): python src/07_data_understanding.py && python viz/export_data.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "results" / "2_data_understanding" / "tables"
OUT = ROOT / "viz" / "src" / "data" / "viz.json"
SOURCES = yaml.safe_load((ROOT / "config" / "sources.yaml").read_text(encoding="utf-8"))


def records(name: str) -> list[dict]:
    path = TABLES / f"07_{name}.csv"
    if not path.exists():
        return []
    df = pd.read_csv(path)
    return json.loads(df.to_json(orient="records", double_precision=6))


def main() -> None:
    monthly = records("monthly")
    summary = {r["key"]: r["value"] for r in records("summary")}
    out = {
        "meta": {
            **summary,
            "first_month": monthly[0]["month"], "last_month": monthly[-1]["month"],
            "has_relevance": "share_a" in monthly[0],
            "has_heat": "heat_deaths_de" in monthly[0],
            "trend_terms": [k.removeprefix("trends_") for k in monthly[0]
                            if k.startswith("trends_") and not k.endswith("_12m")],
            "trends_break": SOURCES["trends"]["topic_break"],
        },
        "monthly": monthly,
        **{name: records(name) for name in ("corpus_lp", "corpus_party", "party_year", "gov_year",
                                            "stance_units", "trends_spikes", "events_de", "missing")},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1e3:,.0f} kB)")


if __name__ == "__main__":
    main()
