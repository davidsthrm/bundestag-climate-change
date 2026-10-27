"""Load PoliCorp speeches from start_date on, attach the party, write one row per sentence.

Input : data/raw/speeches/policorp/policorp_lp-*.json   (periods: config/sources.yaml)
        data/raw/speeches/policorp/parliamentarians.json
        config/party_overrides.yaml
Output: data/interim/sentences.parquet
        One row per sentence of type "speech" (interjections and calls to order are dropped),
        only speaker roles from config/settings.yaml (MPs, government, Bundesrat).

Party (parliamentary group label), first rule that applies wins:
1. config/party_overrides.yaml (party switchers, ministers who are not MPs, state politicians, wrong IDs)
2. group valid on the speech date, from parliamentarians.json via speaker_id
3. 20th Bundestag: MPs whose (only recorded) group is the Linke or BSW group were in the
   Linke group before that group started -> DIE LINKE
4. PoliCorp's own party label
CDU and CSU are merged into CDU/CSU. If nothing applies, party stays empty.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "raw" / "speeches" / "policorp"
OUT = ROOT / "data" / "interim" / "sentences.parquet"
SETTINGS = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
SOURCES = yaml.safe_load((ROOT / "config" / "sources.yaml").read_text(encoding="utf-8"))
OVERRIDES = yaml.safe_load((ROOT / "config" / "party_overrides.yaml").read_text(encoding="utf-8"))["overrides"]

# group names in parliamentarians.json -> label
GROUPS = {
    "Fraktion der Christlich Demokratischen Union/Christlich - Sozialen Union": "CDU/CSU",
    "Fraktion der Sozialdemokratischen Partei Deutschlands": "SPD",
    "Fraktion BÜNDNIS 90/DIE GRÜNEN": "GRÜNE",
    "Fraktion der Freien Demokratischen Partei": "FDP",
    "Fraktion DIE LINKE.": "DIE LINKE",
    "Gruppe Die Linke": "DIE LINKE",
    "Fraktion Alternative für Deutschland": "AfD",
    "Gruppe BSW - Bündnis Sahra Wagenknecht - Vernunft und Gerechtigkeit": "BSW",
    "Fraktionslos": "fraktionslos",
}
# PoliCorp party labels -> label ("not known", "non-party" etc. are not mapped)
LABELS = {"CDU": "CDU/CSU", "CSU": "CDU/CSU", "CDU/CSU": "CDU/CSU", "SPD": "SPD",
          "Bündnis 90/Die Grünen": "GRÜNE", "FDP": "FDP", "DIE LINKE": "DIE LINKE", "PDS": "DIE LINKE",
          "AfD": "AfD", "BSW": "BSW"}


def load_groups() -> dict[tuple[int, int], tuple[str, str]]:
    """(speaker_id, period) -> (group label, ISO start date of membership)."""
    groups = {}
    for p in json.loads((SRC / "parliamentarians.json").read_text(encoding="utf-8")):
        for e in p.get("WAHLPERIODEN") or []:
            if e.get("INSART_LANG") == "Fraktion/Gruppe" and e.get("INS_LANG") in GROUPS:
                start = pd.to_datetime(e.get("MDBINS_VON") or "01.01.1900", dayfirst=True).strftime("%Y-%m-%d")
                groups[(p["ID"], int(e["WP"]))] = (GROUPS[e["INS_LANG"]], start)
    return groups


def party_of(s: dict, name: str, groups: dict, overrides: dict) -> tuple[str | None, str]:
    date, lp = s["date"], s["legislativeperiod"]
    for o in overrides.get(s["speaker_id"], []):
        if date <= o.get("until", "9999-12-31") and o.get("name_contains", "") in name:
            return o["party"], "override"
    g = groups.get((s["speaker_id"], lp))
    if g and date >= g[1]:
        return g[0], "group_on_date"
    if g and lp == 20 and g[0] in ("DIE LINKE", "BSW"):
        return "DIE LINKE", "linke_rule"
    if s.get("party") in LABELS:
        return LABELS[s["party"]], "policorp_label"
    return None, "unknown"


def top_topic(topics: list | None) -> str | None:
    if not topics:
        return None
    return max(topics, key=lambda t: t.get("score") or 0)["label"]


def main() -> None:
    start, end = SETTINGS["start_date"], SETTINGS["end_date"] or "9999-12-31"
    roles = set(SETTINGS["speaker_roles"])
    groups = load_groups()
    overrides: dict[int, list] = {}
    for o in OVERRIDES:
        overrides.setdefault(o["speaker_id"], []).append(o)

    frames = []
    for lp in SOURCES["policorp"]["legislative_periods"]:
        data = json.loads((SRC / f"policorp_lp-{lp}.json").read_text(encoding="utf-8"))["data"]
        rows = []
        for s in data:
            if not (start <= s["date"] <= end) or s["role"] not in roles:
                continue
            name = " ".join((s["name"] or "").split())
            party, source = party_of(s, name, groups, overrides)
            meta = {
                "speech_id": s["speech_id"], "date": s["date"], "month": s["date"][:7], "lp": lp,
                "sessionno": s["sessionno"], "agenda_id": s["agenda_id"], "agenda_type": s["agenda_type"],
                "topic": top_topic(s["topic"]), "role": s["role"],
                "position": " ".join((s["position"] or "").split()) or None,
                "speaker_id": s["speaker_id"], "name": name, "party": party, "party_source": source,
            }
            rows += [{**meta, "seq_no": x["seq_no"], "text": x["text"]}
                     for x in s["text_raw"] if x["type"] == "speech"]
        del data
        frames.append(pd.DataFrame(rows))
        print(f"  LP {lp}: {len(rows):,} sentences")

    df = pd.concat(frames, ignore_index=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)

    speeches = df.drop_duplicates("speech_id")
    print(f"\nwrote {OUT.relative_to(ROOT)}: {len(df):,} sentences, {len(speeches):,} speeches, "
          f"{df.date.min()} .. {df.date.max()}")
    print(speeches.groupby("lp").agg(speeches=("speech_id", "size"),
                                     unknown_party_pct=("party", lambda p: round(p.isna().mean() * 100, 2))).to_string())
    print("\nparty:", speeches.party.fillna("<unknown>").value_counts().to_dict())
    print("party source:", speeches.party_source.value_counts().to_dict())


if __name__ == "__main__":
    main()
