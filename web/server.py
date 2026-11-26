"""Local project hub: slides, results, issue board and a speech explorer.

Run from the repository root:  python web/server.py   (then open http://localhost:8000)

Reads the pipeline outputs in data/ and results/ (never writes there). On first start it
writes a cache of the sentence texts with small row groups to web/.cache/ (gitignored), so a
single speech can be read without loading all 5 M sentences into memory.
Only the Python standard library plus pandas / pyarrow (already in requirements.txt).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(__file__).resolve().parent / "static"
CACHE = Path(__file__).resolve().parent / ".cache"
SENTENCES = ROOT / "data/interim/sentences_relevant.parquet"
PROCESSED = ROOT / "data/processed"
RG = 65536  # rows per row group in the text cache (smaller groups made the full-text scan ~15x slower)

META_COLS = ["speech_id", "date", "month", "lp", "sessionno", "agenda_type", "topic", "role",
             "name", "party", "party_in_government", "speech_n", "speech_hits", "speech_share",
             "main_topic"]
TEXT_COLS = ["seq_no", "text", "relevant", "energy", "sceptic", "matched"]
# files that may be served raw (read-only)
SERVABLE = ("results/", "annotation/", "slides/", "README.md", "docs/context/")


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


# ---------------------------------------------------------------- data loading
class Corpus:
    """Speech table in memory, sentence texts read on demand from the cache file."""

    def __init__(self) -> None:
        self.ready = False
        self.error: str | None = None
        self.speeches: pd.DataFrame | None = None
        self.monthly: list[dict] = []
        self.party_monthly: list[dict] = []
        self.cache_file = CACHE / "texts.parquet"
        self.rg_months: list[tuple[str, str]] = []

    def load(self) -> None:
        try:
            if not SENTENCES.exists():
                raise FileNotFoundError(f"{SENTENCES.relative_to(ROOT)} missing: run src/02_relevance.py")
            self._load_meta()
            self._build_cache()
            self.ready = True
            log("corpus ready")
        except Exception as e:  # shown in the UI instead of crashing the server
            self.error = f"{type(e).__name__}: {e}"
            log("corpus failed: " + self.error)

    def _load_meta(self) -> None:
        log("reading speech metadata ...")
        f = pq.ParquetFile(SENTENCES)
        firsts, month_rows, offset = [], [], 0
        prev_id = None
        for i in range(f.num_row_groups):
            t = f.read_row_group(i, columns=META_COLS + ["relevant"])
            ids = t["speech_id"]
            # sentences of one speech are contiguous: a speech starts where the id changes
            shifted = pa.concat_arrays([pa.array([prev_id], pa.large_string()),
                                        ids.combine_chunks().slice(0, len(ids) - 1)])
            starts = pc.indices_nonzero(pc.fill_null(pc.not_equal(ids, shifted), True))
            first = t.take(starts).drop_columns(["relevant"]).to_pandas()
            first["row_start"] = starts.to_numpy() + offset
            firsts.append(first)
            prev_id = ids[-1].as_py()
            g = (t.select(["month", "party", "relevant"]).group_by(["month", "party"], use_threads=False)
                 .aggregate([("relevant", "count"), ("relevant", "sum")]).to_pandas())
            month_rows.append(g)
            offset += t.num_rows
        sp = pd.concat(firsts, ignore_index=True)
        sp["row_end"] = sp["row_start"].shift(-1, fill_value=offset).astype("int64")
        sp["party"] = sp["party"].fillna("")
        sp["topic"] = sp["topic"].fillna("")
        sp["agenda_type"] = sp["agenda_type"].fillna("")
        sp["name_l"] = sp["name"].fillna("").str.lower()
        sp["topic_l"] = sp["topic"].str.lower()
        self.speeches = sp
        self.n_sentences = offset

        mp = pd.concat(month_rows).groupby(["month", "party"], dropna=False, as_index=False).sum()
        mp.columns = ["month", "party", "sentences", "relevant"]
        mp["party"] = mp["party"].fillna("")
        # speeches and main-topic speeches per month (and party)
        spm = sp.groupby(["month", "party"], as_index=False).agg(
            speeches=("speech_id", "size"), main_topic=("main_topic", "sum"))
        mp = mp.merge(spm, on=["month", "party"], how="left")
        self.party_monthly = mp.to_dict("records")
        tot = mp.groupby("month", as_index=False)[["sentences", "relevant", "speeches", "main_topic"]].sum()
        self.monthly = self._join_signals(tot)
        log(f"{len(sp):,} speeches, {offset:,} sentences")

    @staticmethod
    def _join_signals(tot: pd.DataFrame) -> list[dict]:
        """Monthly Bundestag counts joined with whatever processed series exist."""
        df = tot.copy()
        months = pd.period_range(df["month"].min(), df["month"].max(), freq="M").astype(str)
        df = pd.DataFrame({"month": months}).merge(df, on="month", how="left")
        temp = PROCESSED / "temperature_monthly.csv"
        if temp.exists():
            df = df.merge(pd.read_csv(temp), on="month", how="left")
        trends = PROCESSED / "trends_monthly.csv"
        if trends.exists():
            tr = pd.read_csv(trends).pivot(index="month", columns="term", values="index")
            tr.columns = [f"trends_{c}" for c in tr.columns]
            df = df.merge(tr.reset_index(), on="month", how="left")
        dis = PROCESSED / "disasters_monthly.csv"
        if dis.exists():
            df = df.merge(pd.read_csv(dis), on="month", how="left")
        heat = PROCESSED / "heat_mortality_monthly.csv"
        if heat.exists():
            df = df.merge(pd.read_csv(heat), on="month", how="left")
        df["share"] = df["relevant"] / df["sentences"]
        df["main_share"] = df["main_topic"] / df["speeches"]
        df = df.astype(object).where(df.notna(), None)
        return df.to_dict("records")

    def _build_cache(self) -> None:
        CACHE.mkdir(exist_ok=True)
        stamp = CACHE / "texts.source"
        src_id = f"{SENTENCES.stat().st_size}:{SENTENCES.stat().st_mtime_ns}:{RG}"
        if not (self.cache_file.exists() and stamp.exists() and stamp.read_text() == src_id):
            log("writing text cache (first start only, ~1 min) ...")
            f = pq.ParquetFile(SENTENCES)
            tmp = self.cache_file.with_suffix(".tmp")
            with pq.ParquetWriter(tmp, f.schema_arrow.empty_table().select(TEXT_COLS).schema,
                                  compression="zstd") as w:
                for i in range(f.num_row_groups):
                    w.write_table(f.read_row_group(i, columns=TEXT_COLS), row_group_size=RG)
            tmp.replace(self.cache_file)
            stamp.write_text(src_id)
        self.cache = pq.ParquetFile(self.cache_file)
        # month range per cache row group, so date filters can skip whole groups
        starts = self.speeches["row_start"].to_numpy()
        months = self.speeches["month"].to_numpy()
        for g in range(self.cache.num_row_groups):
            a = max(starts.searchsorted(g * RG, "right") - 1, 0)
            b = max(starts.searchsorted(min((g + 1) * RG, self.n_sentences) - 1, "right") - 1, 0)
            seg = months[a:b + 1]
            self.rg_months.append((min(seg), max(seg)))
        self._lock = threading.Lock()

    def rows(self, start: int, end: int) -> pa.Table:
        groups = list(range(start // RG, (end - 1) // RG + 1))
        with self._lock:
            t = self.cache.read_row_groups(groups)
        return t.slice(start - groups[0] * RG, end - start)


CORPUS = Corpus()


# ---------------------------------------------------------------- API helpers
def speech_dict(r) -> dict:
    return {"id": r.speech_id, "date": r.date, "lp": int(r.lp), "session": int(r.sessionno),
            "name": r.name, "party": r.party, "role": r.role, "gov": bool(r.party_in_government),
            "topic": r.topic, "agenda_type": r.agenda_type, "n": int(r.speech_n),
            "hits": int(r.speech_hits), "share": round(float(r.speech_share), 4),
            "main": bool(r.main_topic)}


def filter_speeches(q: dict) -> pd.DataFrame:
    sp = CORPUS.speeches
    m = pd.Series(True, index=sp.index)
    if q.get("party"):
        m &= sp["party"] == q["party"]
    if q.get("from"):
        m &= sp["month"] >= q["from"]
    if q.get("to"):
        m &= sp["month"] <= q["to"]
    if q.get("month"):
        m &= sp["month"] == q["month"]
    if q.get("lp"):
        m &= sp["lp"] == int(q["lp"])
    if q.get("gov") in ("1", "0"):
        m &= sp["party_in_government"] == (q["gov"] == "1")
    if q.get("climate") == "relevant":
        m &= sp["speech_hits"] > 0
    elif q.get("climate") == "main":
        m &= sp["main_topic"]
    if q.get("speaker"):
        m &= sp["name_l"].str.contains(q["speaker"].lower(), regex=False)
    if q.get("topic"):
        m &= sp["topic_l"].str.contains(q["topic"].lower(), regex=False)
    return sp[m]


def api_speeches(q: dict) -> dict:
    df = filter_speeches(q)
    sort = q.get("sort", "date_desc")
    key, asc = {"date_desc": ("row_start", False), "date_asc": ("row_start", True),
                "hits": ("speech_hits", False), "share": ("speech_share", False)}.get(sort, ("row_start", False))
    df = df.sort_values(key, ascending=asc, kind="stable")
    off, lim = int(q.get("offset", 0)), min(int(q.get("limit", 50)), 200)
    return {"total": int(len(df)), "offset": off,
            "items": [speech_dict(r) for r in df.iloc[off:off + lim].itertuples()]}


def api_speech(q: dict) -> dict:
    sp = CORPUS.speeches
    hit = sp.index[sp["speech_id"] == q.get("id", "")]
    if len(hit) == 0:
        return {"error": "unknown speech id"}
    i = hit[0]
    r = sp.loc[i]
    t = CORPUS.rows(int(r.row_start), int(r.row_end)).to_pylist()
    out = speech_dict(next(sp.loc[[i]].itertuples()))
    out["position"] = None
    out["sentences"] = [{"seq": s["seq_no"], "text": s["text"], "relevant": s["relevant"],
                         "energy": s["energy"], "sceptic": s["sceptic"], "matched": s["matched"]}
                        for s in t]
    # neighbours in the same session, for prev/next navigation
    out["prev"] = sp.at[i - 1, "speech_id"] if i > 0 else None
    out["next"] = sp.at[i + 1, "speech_id"] if i + 1 < len(sp) else None
    return out


def api_search(q: dict) -> dict:
    """Substring search over all sentence texts (case-insensitive), newest first."""
    needle = (q.get("q") or "").strip()
    if len(needle) < 3:
        return {"error": "type at least 3 characters"}
    lim = min(int(q.get("limit", 100)), 500)
    lo = max(q.get("from") or "0000", q.get("month") or "0000")
    hi = min(q.get("to") or "9999", q.get("month") or "9999")
    only_rel = q.get("climate") in ("relevant", "main")
    sp = CORPUS.speeches
    allowed = filter_speeches({k: v for k, v in q.items() if k != "q"})
    allowed_starts = set(allowed["row_start"].tolist()) if len(allowed) < len(sp) else None
    starts = sp["row_start"].to_numpy()
    hits, scanned, t0 = [], 0, time.time()
    for g in reversed(range(CORPUS.cache.num_row_groups)):
        gmin, gmax = CORPUS.rg_months[g]
        if gmax < lo or gmin > hi:
            continue
        with CORPUS._lock:
            t = CORPUS.cache.read_row_group(g, columns=["text", "relevant", "seq_no"])
        mask = pc.match_substring(t["text"], needle, ignore_case=True)
        if only_rel:
            mask = pc.and_(mask, t["relevant"])
        idx = pc.indices_nonzero(mask).to_numpy()
        scanned += t.num_rows
        for j in idx[::-1]:
            row = g * RG + int(j)
            si = int(starts.searchsorted(row, "right") - 1)
            r = sp.iloc[si]
            if allowed_starts is not None and int(r["row_start"]) not in allowed_starts:
                continue
            hits.append({"speech": r["speech_id"], "date": r["date"], "name": r["name"], "party": r["party"],
                         "seq": int(t["seq_no"][int(j)].as_py()), "text": t["text"][int(j)].as_py(),
                         "relevant": bool(t["relevant"][int(j)].as_py())})
            if len(hits) >= lim:
                break
        if len(hits) >= lim:
            break
    return {"items": hits, "truncated": len(hits) >= lim, "scanned": scanned,
            "seconds": round(time.time() - t0, 2)}


def api_overview(_q: dict) -> dict:
    out = {"ready": CORPUS.ready, "error": CORPUS.error,
           "files": {p: (ROOT / p).exists() for p in [
               "data/interim/sentences.parquet", "data/interim/sentences_relevant.parquet",
               "data/interim/windows_stance.parquet", "data/processed/temperature_monthly.csv",
               "data/processed/trends_monthly.csv", "data/processed/disasters_monthly.csv",
               "data/processed/heat_mortality_monthly.csv", "data/processed/panel_monthly.csv"]},
           "branch": run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).strip(),
           "commit": run(["git", "log", "-1", "--format=%h %s (%cr)"]).strip()}
    if CORPUS.ready:
        sp = CORPUS.speeches
        out.update({"speeches": int(len(sp)), "sentences": int(CORPUS.n_sentences),
                    "relevant": int(sp["speech_hits"].sum()), "main_topic": int(sp["main_topic"].sum()),
                    "first_month": sp["month"].min(), "last_month": sp["month"].max(),
                    "parties": sorted(p for p in sp["party"].unique() if p)})
    return out


def api_monthly(_q: dict) -> dict:
    return {"monthly": CORPUS.monthly, "party_monthly": CORPUS.party_monthly}


def parse_md_tables(text: str) -> list[dict]:
    """Markdown tables under '##' headings -> [{heading, header, rows}]."""
    out, heading, lines = [], "", text.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("#"):
            heading = ln.lstrip("#").strip()
        if ln.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            header = [c.strip() for c in ln.strip().strip("|").split("|")]
            rows, i = [], i + 2
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            out.append({"heading": heading, "header": header, "rows": rows})
            continue
        i += 1
    return out


def api_results(_q: dict) -> dict:
    phases = []
    for d in sorted((ROOT / "results").iterdir()):
        if not d.is_dir():
            continue
        readme = d / "README.md"
        text = readme.read_text(encoding="utf-8") if readme.exists() else ""
        intro = next((p.strip() for p in text.split("\n\n")[1:2]), "")
        files = sorted(str(p.relative_to(ROOT)) for sub in ("tables", "figures")
                       for p in (d / sub).glob("*") if p.is_file() and p.name != ".gitkeep")
        phases.append({"phase": d.name, "intro": intro, "tables": parse_md_tables(text), "files": files})
    extra = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "annotation").glob("*.csv"))
    return {"phases": phases, "annotation": extra}


def api_csv(q: dict) -> dict:
    p = safe_path(q.get("path", ""))
    if p is None or p.suffix != ".csv":
        return {"error": "not allowed"}
    df = pd.read_csv(p)
    return {"columns": list(df.columns), "rows": df.astype(object).where(df.notna(), None).values.tolist()}


def api_slides(_q: dict) -> dict:
    return {"decks": sorted(str(p.relative_to(ROOT)) for p in (ROOT / "slides").glob("*.md"))}


_gh_cache: dict = {}


def api_board(q: dict) -> dict:
    """Open + recently closed issues and PRs from GitHub (gh CLI), cached for 2 minutes."""
    if _gh_cache and time.time() - _gh_cache["t"] < 120 and q.get("refresh") != "1":
        return _gh_cache["data"]
    try:
        issues = json.loads(run(["gh", "issue", "list", "--state", "all", "--limit", "200", "--json",
                                 "number,title,state,labels,assignees,url,updatedAt,closedAt,createdAt,body,author"],
                                check=True))
        prs = json.loads(run(["gh", "pr", "list", "--state", "all", "--limit", "100", "--json",
                              "number,title,state,isDraft,url,author,body,updatedAt,reviewDecision,headRefName,"
                              "closingIssuesReferences"], check=True))
        repo = json.loads(run(["gh", "repo", "view", "--json", "url"], check=True))["url"]
    except Exception as e:
        return {"error": f"gh failed: {e}"}
    for pr in prs:
        refs = {r["number"] for r in pr.get("closingIssuesReferences") or []}
        # issues a PR works on: GitHub's closing references plus "(#N)" in the title
        refs |= {int(n) for n in re.findall(r"#(\d+)", pr["title"] or "")}
        pr["refs"] = sorted(refs - {pr["number"]})
        pr.pop("body", None)
        pr.pop("closingIssuesReferences", None)
    data = {"issues": issues, "prs": prs, "repo": repo, "fetched": time.strftime("%H:%M:%S")}
    _gh_cache.update(t=time.time(), data=data)
    return data


def run(cmd: list[str], check: bool = False) -> str:
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=30)
    if check and r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:300])
    return r.stdout


def safe_path(rel: str) -> Path | None:
    rel = rel.lstrip("/")
    p = (ROOT / rel).resolve()
    if ROOT not in p.parents or not p.is_file():
        return None
    if not any(str(p.relative_to(ROOT)).startswith(s) for s in SERVABLE):
        return None
    return p


API = {"overview": api_overview, "monthly": api_monthly, "speeches": api_speeches,
       "speech": api_speech, "search": api_search, "results": api_results, "csv": api_csv,
       "slides": api_slides, "board": api_board}
NEEDS_CORPUS = {"monthly", "speeches", "speech", "search"}


# ---------------------------------------------------------------- HTTP
class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(STATIC), **kw)

    def log_message(self, fmt, *args):  # quieter console
        if args and "/api/" in str(args[0]):
            log(" ".join(str(a) for a in args[:2]))

    def send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path.startswith("/api/"):
            name = u.path[5:]
            if name not in API:
                return self.send_json({"error": "unknown endpoint"}, 404)
            if name in NEEDS_CORPUS and not CORPUS.ready:
                return self.send_json({"error": CORPUS.error or "loading", "loading": CORPUS.error is None}, 503)
            try:
                return self.send_json(API[name](q))
            except Exception as e:
                return self.send_json({"error": f"{type(e).__name__}: {e}"}, 500)
        if u.path.startswith("/repo/"):  # raw files from results/, slides/, annotation/ ...
            p = safe_path(u.path[len("/repo/"):])
            if p is None:
                return self.send_error(404)
            ctype = self.guess_type(str(p))
            if p.suffix in (".md", ".csv", ".txt"):
                ctype += "; charset=utf-8"
            data = p.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return
        return super().do_GET()

    def end_headers(self):
        if not self.path.startswith("/repo/"):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    threading.Thread(target=CORPUS.load, daemon=True).start()
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    log(f"serving on http://{a.host}:{a.port}  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
