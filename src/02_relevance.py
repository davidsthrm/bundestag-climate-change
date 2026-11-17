"""Flag climate-relevant sentences with config/keywords_de.yaml (attention_unit in settings.yaml).
Also flags speeches with climate as main topic (main_topic_threshold, main_topic_min_hits).

Matching: text lowercased, "co 2" / "co₂" -> "co2", then substring match of the core terms, so
compounds match (klimaschutz -> Klimaschutzgesetz). The standalone word "Klima"/"Klimas" and
"Klima- und ..." also count, unless the sentence has a phrase from klima_plain.exclude.
Energy terms and sceptic markers are flags only, not relevant on their own.

Input : data/interim/sentences.parquet
Output: data/interim/sentences_relevant.parquet  (all sentences + flags + speech-level columns)
        results/3_data_preparation/tables/02_counts_month_party.csv
        results/3_data_preparation/tables/02_keyword_hits.csv
        annotation/02_relevance_check.csv          (sample to mark by hand, column is_climate = 1/0)

python src/02_relevance.py              # flag, write tables and the check sample
python src/02_relevance.py --summarise  # precision/recall from the marked check sample
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
IN = ROOT / "data" / "interim" / "sentences.parquet"
OUT = ROOT / "data" / "interim" / "sentences_relevant.parquet"
TABLES = ROOT / "results" / "3_data_preparation" / "tables"
CHECK = ROOT / "annotation" / "02_relevance_check.csv"
SETTINGS = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
KEYWORDS = yaml.safe_load((ROOT / "config" / "keywords_de.yaml").read_text(encoding="utf-8"))

KLIMA_PLAIN = re.compile(r"\bklimas?\b|\bklima-\s")


def any_of(terms: list[str]) -> re.Pattern:
    return re.compile("|".join(re.escape(t) for t in terms))


def normalise(text: pd.Series) -> pd.Series:
    return text.str.lower().str.replace(r"\bco\s?[2₂]", "co2", regex=True)


def flag(df: pd.DataFrame) -> pd.DataFrame:
    norm = normalise(df["text"])
    core = norm.str.contains(any_of(KEYWORDS["core"]))
    plain = (norm.str.contains(KLIMA_PLAIN)
             & ~norm.str.contains(any_of(KEYWORDS["klima_plain"]["exclude"])))
    df["relevant"] = core | plain
    df["hit_klima_plain"] = plain & ~core
    df["energy"] = norm.str.contains(any_of(KEYWORDS["energy"]))
    df["sceptic"] = norm.str.contains(any_of(KEYWORDS["sceptic_markers"]))
    df["matched"] = None
    df.loc[core, "matched"] = (norm[core].str.findall(any_of(KEYWORDS["core"]))
                               .map(lambda m: ";".join(sorted(set(m)))))
    df.loc[df["hit_klima_plain"], "matched"] = "klima"

    speech = df.groupby("speech_id")["relevant"].agg(speech_n="size", speech_hits="sum")
    speech["speech_share"] = speech["speech_hits"] / speech["speech_n"]
    speech["main_topic"] = ((speech["speech_share"] >= SETTINGS["main_topic_threshold"])
                            & (speech["speech_hits"] >= SETTINGS["main_topic_min_hits"]))
    return df.join(speech, on="speech_id"), norm


def tables(df: pd.DataFrame, norm: pd.Series) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    speeches = df.drop_duplicates("speech_id")
    counts = df.groupby(["month", "party"], dropna=False).agg(
        n_sentences=("relevant", "size"), n_relevant=("relevant", "sum"))
    counts["share"] = (counts["n_relevant"] / counts["n_sentences"]).round(5)
    counts = counts.join(speeches.groupby(["month", "party"], dropna=False).agg(
        n_speeches=("speech_id", "size"), n_main_topic=("main_topic", "sum")))
    counts.reset_index().to_csv(TABLES / "02_counts_month_party.csv", index=False)

    rows = [{"group": g, "term": t, "n_sentences": int(norm.str.contains(t, regex=False).sum())}
            for g in ("core", "energy", "sceptic_markers") for t in KEYWORDS[g]]
    rows.append({"group": "klima_plain", "term": "klima", "n_sentences": int(df["hit_klima_plain"].sum())})
    pd.DataFrame(rows).to_csv(TABLES / "02_keyword_hits.csv", index=False)


def check_sample(df: pd.DataFrame, norm: pd.Series) -> None:
    seed, n_hits = SETTINGS["relevance_sample_seed"], SETTINGS["relevance_sample_hits"]
    core_hits = df[df["relevant"] & ~df["hit_klima_plain"]]
    per_lp = -(-n_hits // core_hits["lp"].nunique())  # ceil, trimmed to n_hits below
    hits = (core_hits.groupby("lp").sample(per_lp, random_state=seed)
            .sample(frac=1, random_state=seed).head(n_hits).assign(kind="hit"))
    plain = df[df["hit_klima_plain"]].sample(SETTINGS["relevance_sample_klima_plain"],
                                             random_state=seed).assign(kind="klima_plain")
    nonhits = df[~df["relevant"] & norm.str.contains("klima", regex=False)].sample(
        SETTINGS["relevance_sample_nonhits"], random_state=seed).assign(kind="nonhit")
    sample = pd.concat([hits, plain, nonhits]).sample(frac=1, random_state=seed)  # mixed, so kind is not obvious
    sample["id"] = sample["speech_id"].astype(str) + "_" + sample["seq_no"].astype(str)
    sample["is_climate"] = ""
    CHECK.parent.mkdir(parents=True, exist_ok=True)
    sample[["id", "lp", "kind", "matched", "text", "is_climate"]].to_csv(CHECK, index=False)


def summarise() -> None:
    s = pd.read_csv(CHECK)
    if s["is_climate"].isna().any():
        sys.exit(f"{s['is_climate'].isna().sum()} rows in {CHECK.relative_to(ROOT)} are not marked yet (1/0)")
    flagged = s[s["kind"] != "nonhit"]
    out = pd.concat([
        s.groupby("kind")["is_climate"].agg(n="size", climate_share="mean"),
        flagged.groupby("lp")["is_climate"].agg(n="size", climate_share="mean").rename(lambda lp: f"lp {lp}"),
        pd.DataFrame({"n": [len(flagged)], "climate_share": [flagged["is_climate"].mean()]}, index=["all flagged"]),
    ]).round(3)
    out.index.name = "subset"
    out.to_csv(TABLES / "02_relevance_check_summary.csv")
    print(out.to_string())
    print("\nprecision = climate_share of hit / klima_plain / all flagged; "
          "for nonhit, climate_share = missed climate sentences among unflagged 'klima' sentences")


def main() -> None:
    if "--summarise" in sys.argv:
        return summarise()
    df = pd.read_parquet(IN)
    df, norm = flag(df)
    df.to_parquet(OUT, index=False)
    tables(df, norm)
    check_sample(df, norm)

    speeches = df.drop_duplicates("speech_id")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(df):,} sentences, {df['relevant'].sum():,} relevant "
          f"({df['relevant'].mean():.2%}), of these {df['hit_klima_plain'].sum():,} only via 'klima'")
    print(f"main-topic speeches: {speeches['main_topic'].sum():,} of {len(speeches):,}")
    print("relevant share per term:", df.groupby("lp")["relevant"].mean().round(4).to_dict())
    months = df.groupby("month")["relevant"].sum()
    print("months without hits:", list(months[months == 0].index))
    print(f"check sample: {CHECK.relative_to(ROOT)} (mark is_climate 1/0, then run --summarise)")


if __name__ == "__main__":
    main()
