"""Load all speeches from start_date on, attach the party, write one row per sentence.

Input : data/raw/speeches/policorp/policorp_lp-*.json   (periods: config/sources.yaml)
        data/interim/wp21_policorp.json                 (21st Bundestag, from src/01a_wp21_to_policorp.py)
        data/raw/speeches/MdB-Stammdaten.zip            (official MP master data, group memberships)
        config/party_overrides.yaml
        config/governments.yaml                         (coalition parties per date)
Output: data/interim/sentences.parquet
        One row per sentence of type "speech" (interjections and calls to order are dropped),
        only speaker roles from config/settings.yaml (MPs, government, Bundesrat).

Party (parliamentary group label), first rule that applies wins:
1. config/party_overrides.yaml (ministers who are not MPs, state politicians, wrong IDs, PDS 2002-05)
2. group membership valid on the speech date, from the MP master data via speaker_id.
   Exception: the Linke group dissolved on 6 Dec 2023 and its MPs were non-attached until the
   Linke and BSW groups started on 2 Feb 2024; that gap gets the group they joined afterwards.
3. the party label in the speech data (PoliCorp, or <fraktion> in the XML)
CDU and CSU are merged into CDU/CSU. If nothing applies, party stays empty.

party_in_government: True if the speaker's party is a federal coalition party on the speech date
(config/governments.yaml), False otherwise (also fraktionslos/parteilos), empty if the party is unknown.
This is about the party, not the person: role == "government" marks members of the government.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "raw" / "speeches" / "policorp"
WP21 = ROOT / "data" / "interim" / "wp21_policorp.json"
MDB = ROOT / "data" / "raw" / "speeches" / "MdB-Stammdaten.zip"
OUT = ROOT / "data" / "interim" / "sentences.parquet"
SETTINGS = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
SOURCES = yaml.safe_load((ROOT / "config" / "sources.yaml").read_text(encoding="utf-8"))
OVERRIDES = yaml.safe_load((ROOT / "config" / "party_overrides.yaml").read_text(encoding="utf-8"))["overrides"]
GOVERNMENTS = yaml.safe_load((ROOT / "config" / "governments.yaml").read_text(encoding="utf-8"))["governments"]

# group names in the MP master data -> label
GROUPS = {
    "Fraktion der Christlich Demokratischen Union/Christlich - Sozialen Union": "CDU/CSU",
    "Fraktion der Sozialdemokratischen Partei Deutschlands": "SPD",
    "Fraktion BÜNDNIS 90/DIE GRÜNEN": "GRÜNE",
    "Fraktion der Freien Demokratischen Partei": "FDP",
    "Fraktion DIE LINKE.": "DIE LINKE",
    "Gruppe Die Linke": "DIE LINKE",
    "Fraktion Die Linke": "DIE LINKE",
    "Fraktion Alternative für Deutschland": "AfD",
    "Gruppe BSW - Bündnis Sahra Wagenknecht - Vernunft und Gerechtigkeit": "BSW",
    "Fraktionslos": "fraktionslos",
}
# party labels in the speech data -> label ("not known", "non-party" etc. are not mapped)
LABELS = {"CDU": "CDU/CSU", "CSU": "CDU/CSU", "CDU/CSU": "CDU/CSU", "SPD": "SPD",
          "Bündnis 90/Die Grünen": "GRÜNE", "FDP": "FDP", "DIE LINKE": "DIE LINKE", "PDS": "DIE LINKE",
          "AfD": "AfD", "BSW": "BSW", "fraktionslos": "fraktionslos"}
LINKE_GAP = ("2023-12-06", "2024-02-01")  # Linke group dissolved .. Linke and BSW groups start


def load_groups() -> dict[int, list[tuple[str, str, str]]]:
    """speaker_id -> [(group label, ISO start, ISO end)], from the official MP master data."""
    iso = lambda d: pd.to_datetime(d, dayfirst=True).strftime("%Y-%m-%d") if d else None
    with zipfile.ZipFile(MDB) as z:
        root = ET.fromstring(z.read("MDB_STAMMDATEN.XML"))
    groups: dict[int, list] = {}
    for mdb in root.iter("MDB"):
        for wp in mdb.iter("WAHLPERIODE"):
            for ins in wp.iter("INSTITUTION"):
                if ins.findtext("INSART_LANG") == "Fraktion/Gruppe" and ins.findtext("INS_LANG") in GROUPS:
                    start = iso(ins.findtext("MDBINS_VON")) or iso(wp.findtext("MDBWP_VON"))
                    end = iso(ins.findtext("MDBINS_BIS")) or iso(wp.findtext("MDBWP_BIS")) or "9999-12-31"
                    groups.setdefault(int(mdb.findtext("ID")), []).append((GROUPS[ins.findtext("INS_LANG")], start, end))
    return groups


def group_on(groups: dict, speaker_id: int, date: str) -> str | None:
    hits = [g for g in groups.get(speaker_id, []) if g[1] <= date <= g[2]]
    return max(hits, key=lambda g: g[1])[0] if hits else None  # latest start wins on a switch day


def party_of(s: dict, name: str, groups: dict, overrides: dict) -> tuple[str | None, str]:
    date, sid = s["date"], s["speaker_id"]
    for o in overrides.get(sid, []):
        if date <= o.get("until", "9999-12-31") and o.get("name_contains", "") in name:
            return o["party"], "override"
    g = group_on(groups, sid, date)
    if g == "fraktionslos" and LINKE_GAP[0] <= date <= LINKE_GAP[1]:
        after = group_on(groups, sid, "2024-02-02")
        if after in ("DIE LINKE", "BSW"):
            return after, "linke_gap"
    if g:
        return g, "group_on_date"
    if s.get("party") in LABELS:
        return LABELS[s["party"]], "speech_label"
    return None, "unknown"


def in_government(party: str | None, date: str) -> bool | None:
    if party is None:
        return None
    current = [g for g in GOVERNMENTS if g["from"] <= date]
    return party in max(current, key=lambda g: g["from"])["parties"]


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

    files = [(lp, SRC / f"policorp_lp-{lp}.json") for lp in SOURCES["policorp"]["legislative_periods"]]
    files.append((SOURCES["bundestag_wp21"]["wahlperiode"], WP21))
    frames = []
    for lp, path in files:
        data = json.loads(path.read_text(encoding="utf-8"))["data"]
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
                "party_in_government": in_government(party, s["date"]),
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
    print("\nshare of speeches by coalition parties, per government start:")
    starts = pd.Series([g["from"] for g in GOVERNMENTS])
    gov_start = starts.searchsorted(speeches.date, side="right") - 1
    in_gov = speeches.party_in_government.astype("boolean")
    print(in_gov.groupby(starts[gov_start].values).agg(["size", "mean"]).round(3).to_string())


if __name__ == "__main__":
    main()
