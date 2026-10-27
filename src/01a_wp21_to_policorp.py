"""Convert Bundestag plenary protocols (XML, schema from the 19th Bundestag on) into PoliCorp's JSON format.

Input : data/raw/speeches/bundestag_wp21/21*.xml        (src/00_download.py wp21)
Output: data/interim/wp21_policorp.json  {"note": ..., "data": [contribution, ...]}
        Same fields as data/raw/speeches/policorp/policorp_lp-*.json, so src/01_speeches.py reads it
        like a PoliCorp period.

How the XML is mapped
- One agenda per <tagesordnungspunkt> (and <sitzungsbeginn>), own IDs ("xml_<session>_<n>").
- Each <rede> is split at every change of speaker: <p klasse="redner"> starts a contribution of that
  speaker, <name> (session chair) starts a contribution with role "presidency". Speaker blocks
  outside a <rede> (e.g. at the start of a sitting) are read the same way; agenda headings are skipped.
- role: "government" if the speaker has a <rolle> (position = rolle_lang), else "mp".
- party: the speaker's <fraktion> as a PoliCorp label. Government members have no <fraktion>;
  their party is filled in step 1 from the MP master data / config/party_overrides.yaml.
- text_raw: each <p> is split into sentences (type "speech"); each <kommentar> is one entry
  (type "interjection"). Calls to order are not marked in the XML.
- Not available from the XML and set to null: topic, agenda_type, ner, legal_ner.
  Every contribution has source = "bundestag_xml".

Check against PoliCorp on 3 sessions of the 20th Bundestag (in both sources):
    python src/01a_wp21_to_policorp.py --validate
"""
from __future__ import annotations

import csv
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEECHES = ROOT / "data" / "raw" / "speeches"
OUT = ROOT / "data" / "interim" / "wp21_policorp.json"

# <fraktion> in the XML -> PoliCorp party label (and party_id from party_mapping.json)
FRAKTION = {"CDU/CSU": "CDU/CSU", "SPD": "SPD", "BÜNDNIS 90/DIE GRÜNEN": "Bündnis 90/Die Grünen",
            "Die Linke": "DIE LINKE", "DIE LINKE": "DIE LINKE", "AfD": "AfD", "FDP": "FDP", "BSW": "BSW",
            "fraktionslos": "fraktionslos", "Fraktionslos": "fraktionslos"}
PARTY_ID = {"AfD": 0, "CDU/CSU": 27, "DIE LINKE": 4, "SPD": 14, "Bündnis 90/Die Grünen": 16, "FDP": 10, "BSW": 26}

# Sentence splitting: end mark (+ closing quote/bracket), whitespace, then an upper-case start.
BOUNDARY = re.compile(r'([.!?…]["“”»)]*)\s+(?=["„»(]?[A-ZÄÖÜ])')
# ... but not after an abbreviation, a day/ordinal number ("am 3. Oktober") or an initial ("Hans J. Meier").
ABBREV = (r"Dr|Prof|Nr|Abs|Art|Abg|Drs|Kap|Ziff|bzw|ca|vgl|ggf|usw|etc|Mio|Mrd|Tsd|St|Std|inkl|zzgl|evtl|sog"
          r"|z\. ?B|d\. ?h|u\. ?a|i\. ?d\. ?R|v\. ?a|o\. ?ä|s\. ?o")
NO_SPLIT = re.compile(r"(?:\b(?:" + ABBREV + r")|\b\d{1,2}|\b[A-ZÄÖÜ])\.$")


def split_sentences(text: str) -> list[str]:
    text = " ".join(text.split())
    out, start = [], 0
    for m in BOUNDARY.finditer(text):
        piece = text[start:m.end(1)]
        if NO_SPLIT.search(piece):
            continue
        out.append(piece)
        start = m.end()
    out.append(text[start:])
    return [s for s in out if s]


def undouble(s: str | None) -> str | None:
    """'SvenjaSvenja' -> 'Svenja' (one XML speaker entry has every value twice)."""
    if s and len(s) % 2 == 0 and s[: len(s) // 2] == s[len(s) // 2:]:
        return s[: len(s) // 2]
    return s


def text_of(el: ET.Element) -> str:
    return " ".join("".join(el.itertext()).split())


def speaker_from(p: ET.Element) -> dict:
    r = p.find("redner")
    n = r.find("name")
    get = lambda tag: undouble(" ".join((n.findtext(tag) or "").split()) or None)
    name = " ".join(x for x in (get("titel"), get("vorname"), get("namenszusatz"), get("nachname")) if x)
    rolle = n.find("rolle")
    fraktion = get("fraktion")
    fraktion = fraktion.replace("\xa0", " ") if fraktion else None
    party = FRAKTION.get(fraktion) if fraktion else None
    if fraktion and party is None:
        raise ValueError(f"unknown <fraktion> {fraktion!r} - add it to FRAKTION")
    position = " ".join((rolle.findtext("rolle_lang") or "").split()) if rolle is not None else None
    role = "mp" if rolle is None else "government"
    if position and "des Deutschen Bundestages" in position:  # e.g. Wehrbeauftragte, as in PoliCorp
        role = "parliamentary_commissioner"
    return {
        "speaker_id": int(r.get("id").split()[0]) if r.get("id") else None,
        "name": name,
        "role": role,
        "position": position,
        "party": party,
        "party_id": PARTY_ID.get(party),
    }


def chair_from(el: ET.Element) -> dict:
    title, _, name = text_of(el).rstrip(":").partition(" ")
    return {"speaker_id": None, "name": name, "role": "presidency", "position": title, "party": None, "party_id": None}


def convert_file(path: Path, source_url: str | None) -> list[dict]:
    root = ET.parse(path).getroot()
    wp, sess = int(root.get("wahlperiode")), int(root.get("sitzung-nr"))
    d, m, y = root.get("sitzung-datum").split(".")
    date = f"{y}-{m}-{d}"
    contributions = []
    agendas = [a for a in root.find("sitzungsverlauf") if a.tag in ("sitzungsbeginn", "tagesordnungspunkt")]
    for agenda_nr, agenda in enumerate(agendas):
        agenda_id = f"xml_{wp}{sess:03d}_{agenda_nr}"
        speechno, current = 0, None
        for block in agenda:
            # speaker blocks are usually inside <rede>, but some (e.g. at the start of a sitting) are not
            if block.tag == "rede":
                current = None
            for el in (block if block.tag == "rede" else [block]):
                if el.tag == "p" and el.get("klasse") == "redner":
                    current = speaker_from(el)
                elif el.tag == "name":
                    current = chair_from(el)
                elif el.tag in ("p", "kommentar"):
                    if current is None or (el.get("klasse") or "").startswith("T_"):  # T_*: agenda headings
                        continue
                    if "text_raw" not in current:  # first text of this speaker -> new contribution
                        current = {
                            "agenda_id": agenda_id, "legislativeperiod": wp, "sessionno": sess, "date": date,
                            "source_file": source_url, "agenda_type": None, "agenda_nr": agenda_nr,
                            "speech_id": f"{agenda_id}_{speechno}", "speechno": speechno, **current,
                            "topic": None, "text_raw": [], "source": "bundestag_xml",
                        }
                        contributions.append(current)
                        speechno += 1
                    if el.tag == "kommentar":
                        parts = [(text_of(el), "interjection")]
                    else:
                        parts = [(s, "speech") for s in split_sentences(text_of(el))]
                    for text, typ in parts:
                        current["text_raw"].append({"seq_no": len(current["text_raw"]), "text": text,
                                                    "type": typ, "ner": None, "legal_ner": None})
            if block.tag == "rede":
                current = None
    return contributions


def manifest_urls() -> dict[str, str]:
    with (ROOT / "data" / "raw" / "MANIFEST.csv").open(encoding="utf-8") as f:
        return {Path(r["file"]).name: r["url"] for r in csv.DictReader(f)}


def main() -> None:
    urls = manifest_urls()
    files = sorted((SPEECHES / "bundestag_wp21").glob("21*.xml"))
    data = []
    for f in files:
        data += convert_file(f, urls.get(f.name))
    note = ("21st Bundestag converted from Bundestag Open Data XML by src/01a_wp21_to_policorp.py. "
            "Not available, set to null: topic, agenda_type, ner, legal_ner; party of government members.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"note": note, "data": data}, ensure_ascii=False), encoding="utf-8")
    n_sent = sum(x["type"] == "speech" for c in data for x in c["text_raw"])
    roles = {r: sum(c["role"] == r for c in data) for r in ("mp", "government", "presidency")}
    print(f"wrote {OUT.relative_to(ROOT)}: {len(files)} sessions, {data[0]['date']} .. {data[-1]['date']}, "
          f"{len(data):,} contributions {roles}, {n_sent:,} speech sentences")


def validate() -> None:
    """Convert the WP20 validation sessions and compare them with PoliCorp."""
    files = sorted((SPEECHES / "bundestag_wp20_validation").glob("20*.xml"))
    if not files:
        raise SystemExit("No validation files. Run: python src/00_download.py wp21")
    pc = json.loads((SPEECHES / "policorp" / "policorp_lp-20.json").read_text(encoding="utf-8"))["data"]
    norm = lambda s: re.sub(r"\s+", "", s)
    for f in files:
        ours = [c for c in convert_file(f, None) if c["role"] != "presidency"]
        sess = ours[0]["sessionno"]
        theirs = [c for c in pc if c["sessionno"] == sess and c["role"] != "presidency"]
        speech = lambda c: [x["text"] for x in c["text_raw"] if x["type"] == "speech"]
        key = lambda c: norm(" ".join(speech(c)))
        # PoliCorp orders contributions differently, so match them by identical speech text
        ours_by_text: dict[str, list] = {}
        for c in ours:
            ours_by_text.setdefault(key(c), []).append(c)
        pairs = [(ours_by_text[key(b)].pop(), b) for b in theirs if ours_by_text.get(key(b))]
        same_id = sum(a["speaker_id"] == b["speaker_id"] for a, b in pairs)
        chars = lambda cs: sum(len(key(c)) for c in cs)
        sent_o, sent_t = sum(len(speech(c)) for c in ours), sum(len(speech(c)) for c in theirs)
        party_pairs = [(a["party"], b["party"]) for a, b in pairs
                       if a["role"] == "mp" and b["party"] not in ("not known", "non-party", None)]
        party_same = sum(a == b or (a == "CDU/CSU" and b in ("CDU", "CSU")) for a, b in party_pairs)
        print(f"session {sess}: contributions {len(ours)} vs {len(theirs)} | found with identical text "
              f"{len(pairs) / max(len(theirs), 1):.1%} | same speaker_id {same_id}/{len(pairs)} "
              f"| speech chars {chars(ours):,} vs {chars(theirs):,} | sentences {sent_o:,} vs {sent_t:,} "
              f"({sent_o / max(sent_t, 1) - 1:+.1%}) | party same {party_same}/{len(party_pairs)}")


if __name__ == "__main__":
    validate() if "--validate" in sys.argv else main()
