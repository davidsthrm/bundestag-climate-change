"""Download all raw data into data/raw/ (not committed to git).

Usage (from repo root):
    python src/00_download.py               # everything
    python src/00_download.py temperature   # only DWD + GISTEMP (small, ~1 MB)
    python src/00_download.py policorp      # PoliCorp zip (~880 MB) + extract LP 15-20
    python src/00_download.py wp21          # 21st Bundestag XML protocols

Already downloaded files are skipped (delete them to refresh).
Every download is logged with URL, access time and SHA-256 in data/raw/MANIFEST.csv
-> use that for the data section of the paper.
Google Trends is a manual export, see README.
"""
from __future__ import annotations

import csv
import hashlib
import re
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
MANIFEST = RAW / "MANIFEST.csv"
SOURCES = yaml.safe_load((ROOT / "config" / "sources.yaml").read_text(encoding="utf-8"))

HEADERS = {"User-Agent": "Mozilla/5.0 (student research project; bundestag-climate-change)"}


# --------------------------------------------------------------------------- helpers
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def log_manifest(path: Path, url: str) -> None:
    new = not MANIFEST.exists()
    with MANIFEST.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["file", "url", "accessed_utc", "bytes", "sha256"])
        w.writerow([
            path.relative_to(ROOT).as_posix(), url,
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            path.stat().st_size, sha256(path),
        ])


def download(url: str, dest: Path, session: requests.Session | None = None) -> Path:
    """Stream url to dest (atomic via .part file). Skips if dest exists."""
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  skip (exists) {dest.relative_to(ROOT)}")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    s = session or requests
    for attempt in range(1, 4):
        try:
            with s.get(url, headers=HEADERS, stream=True, timeout=60) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                done = 0
                with tmp.open("wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        f.write(chunk)
                        done += len(chunk)
                        if total > 5_000_000:
                            print(f"\r  {dest.name}: {done/1e6:,.0f} / {total/1e6:,.0f} MB", end="", flush=True)
                if total > 5_000_000:
                    print()
            tmp.replace(dest)
            log_manifest(dest, url)
            print(f"  ok   {dest.relative_to(ROOT)}  ({dest.stat().st_size/1e3:,.0f} kB)")
            return dest
        except requests.RequestException as e:
            print(f"  attempt {attempt} failed for {url}: {e}")
            time.sleep(3 * attempt)
    raise SystemExit(f"Download failed: {url}")


# --------------------------------------------------------------------------- sources
def get_temperature() -> None:
    print("DWD regional averages (Germany, monthly mean air temperature)")
    cfg = SOURCES["dwd"]
    for m in range(1, 13):
        name = cfg["file_pattern"].format(month=m)
        download(cfg["base_url"] + name, RAW / "temperature" / "dwd" / name)

    print("NASA GISTEMP v4 global")
    download(SOURCES["gistemp"]["url"], RAW / "temperature" / "gistemp_GLB.Ts+dSST.csv")


def get_policorp() -> None:
    print("PoliCorp-GermaParl2-PLUS (Zenodo)")
    cfg = SOURCES["policorp"]
    out = RAW / "speeches" / "policorp"
    zpath = download(cfg["zip_url"], out / "germaparl2-plus_lp_subsets.zip")
    download(cfg["doc_url"], out / "PoliCorp-GermaParl2-PLUS_metadata_description.pdf")

    wanted_lp = {str(lp) for lp in cfg["legislative_periods"]}
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
        print(f"  zip contains {len(names)} entries")
        for n in names:
            base = Path(n).name
            if not base:
                continue
            m = re.search(r"lp[-_]?(\d+)", base, flags=re.I)
            keep = (m and m.group(1) in wanted_lp) or base in {"parliamentarians.json", "party_mapping.json"}
            if not keep:
                continue
            target = out / base
            if target.exists():
                print(f"  skip (extracted) {base}")
                continue
            with z.open(n) as src, target.open("wb") as dst:
                while chunk := src.read(1 << 20):
                    dst.write(chunk)
            print(f"  extracted {base} ({target.stat().st_size/1e6:,.0f} MB)")
        unmatched = [Path(n).name for n in names if Path(n).name and not (out / Path(n).name).exists()]
        if unmatched:
            print(f"  not extracted (other legislative periods etc.): {len(unmatched)} files, e.g. {unmatched[:3]}")


def get_wp21() -> None:
    """21st Bundestag plenary protocols from bundestag.de open data.

    The open data page loads its file lists via AJAX ("data-dataloader-url").
    We find those endpoints, page through them and keep links to 21xxx XML files.
    """
    print("Bundestag Open Data, 21. Wahlperiode (XML)")
    cfg = SOURCES["bundestag_wp21"]
    wp = str(cfg["wahlperiode"])
    out = RAW / "speeches" / f"bundestag_wp{wp}"
    s = requests.Session()
    page = s.get(cfg["opendata_page"], headers=HEADERS, timeout=60)
    page.raise_for_status()
    loaders = sorted(set(re.findall(r'/ajax/filterlist/[^"&\s]+', page.text)))
    if not loaders:
        raise SystemExit("No AJAX file lists found on the open data page - layout changed? "
                         "Download the WP21 XMLs manually into " + str(out))
    pat = re.compile(r'href="([^"]*?/' + wp + r'\d{3}(?:-data)?\.xml)"')
    links: dict[str, str] = {}
    for loader in loaders:
        offset, found_here = 0, 0
        while True:
            url = urljoin(cfg["opendata_page"], loader)
            r = s.get(url, params={"limit": 10, "noFilterSet": "true", "offset": offset},
                      headers=HEADERS, timeout=60)
            if r.status_code != 200:
                break
            batch = {Path(h).name: urljoin(cfg["opendata_page"], h) for h in pat.findall(r.text)}
            new = {k: v for k, v in batch.items() if k not in links}
            if not new:
                break
            links.update(new)
            found_here += len(new)
            offset += 10
            time.sleep(0.5)
        if found_here:
            print(f"  {loader}: {found_here} protocol files")
    if not links:
        raise SystemExit("Found no WP21 XML links. Check https://www.bundestag.de/services/opendata manually.")
    for name, url in sorted(links.items()):
        download(url, out / name, session=s)
        time.sleep(0.3)
    print(f"  {len(links)} WP{wp} protocols in {out.relative_to(ROOT)}")


TASKS = {"temperature": get_temperature, "policorp": get_policorp, "wp21": get_wp21}

if __name__ == "__main__":
    chosen = sys.argv[1:] or list(TASKS)
    for t in chosen:
        if t not in TASKS:
            raise SystemExit(f"unknown task {t!r}; choose from {list(TASKS)}")
    RAW.mkdir(parents=True, exist_ok=True)
    for t in chosen:
        TASKS[t]()
    print("\nDone. Google Trends still needs the manual export (see README).")
