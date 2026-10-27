# Bundestag & Climate Change (2004–today)

Student project for a university NLP module.

## Research question
Does the Bundestag's attention to climate change follow the **physical climate
signal** (temperatures in Germany and globally) or **public attention**
(Google Trends)? Extension: differences between parties, including the
**stance** of climate-related speech (pro climate action vs. sceptical/opposing).

## Pipeline
| Step | Script | Output |
|------|--------|--------|
| 0 | `src/00_download.py`    | raw data into `data/raw/` (+ MANIFEST.csv) |
| 1 | `src/01_speeches.py`    | speeches filtered to 2004–today, with party |
| 2 | `src/02_relevance.py`   | climate-relevant paragraphs (keyword dictionary) |
| 3 | `src/03_stance.py`      | stance label per relevant paragraph |
| 4 | `src/04_temperature.py` | monthly temperature anomalies DE + global |
| 5 | `src/05_trends.py`      | monthly Google Trends index (DE) |
| 6 | `src/06_merge.py`       | one monthly panel in `data/processed/` |

## Data sources
| Data | Source | Coverage | How we get it |
|------|--------|----------|---------------|
| Plenary speeches WP15–20 | PoliCorp-GermaParl2-PLUS, Zenodo [10.5281/zenodo.21295610](https://doi.org/10.5281/zenodo.21295610), CC BY 4.0 | 1949 – Feb 2025, sentence-level, with party | `src/00_download.py policorp` |
| Plenary speeches WP21 | Bundestag Open Data, plenary protocol XML | since 25 Mar 2025 | `src/00_download.py wp21` |
| Temperature Germany | DWD Climate Data Center, regional averages, monthly mean air temperature (area mean Deutschland) | 1881 – last month | `src/00_download.py temperature` |
| Temperature global | NASA GISTEMP v4, global land-ocean index | 1880 – last month | `src/00_download.py temperature` |
| Public attention | Google Trends, region DE | 2004 – today, monthly | manual CSV export (below) |

All URLs are in `config/sources.yaml`. Raw data is **not** in git: each person runs the
download script locally. Every download is logged with URL, access time and SHA-256 in
`data/raw/MANIFEST.csv` (use it for the data section of the paper).

```bash
python src/00_download.py            # all scripted sources (~900 MB, mostly PoliCorp)
python src/04_temperature.py         # -> data/processed/temperature_monthly.csv
python src/05_trends.py              # -> data/processed/trends_monthly.csv
```

### Google Trends export (manual)
Google Trends has no official API and scrapers get rate-limited, so we export by hand.
1. Open trends.google.de → *Explore*. Region **Deutschland**, time range **custom: 01.01.2004 – today**
   (ranges > 5 years return **monthly** values), category *All*, *Web search*.
2. **Export A** – one entry: the *topic* “Klimawandel” (pick the suggestion labelled *Thema*/*Topic*,
   not the search term). Save as `data/raw/trends/A_topic_klimawandel.csv`.
3. **Export B** – search terms requested together: `Klimawandel`, `Klimaschutz`, `Klimakrise`,
   `Erderwärmung`, `Hitzewelle`. Save as `data/raw/trends/B_terms.csv`.
4. Note the export date in the file name or in `data/raw/MANIFEST.csv`.

Values are relative (0–100) *within one export* only. Google samples the data, so a re-export
on another day can differ slightly; for robustness export B a second time on a different day
(`B_terms_2.csv`) and check the correlation.

### Known caveats
- PoliCorp transcripts are split into **sentences**, not paragraphs (`text_raw` = list of sentences
  with `type` speech / interjection / call to order). Interjections must be filtered out.
- PoliCorp ends with the 20th Bundestag (Feb 2025); WP21 comes from the Bundestag XML and needs
  its own parser and party mapping (fraction names) in step 1.
- GISTEMP anomalies are relative to 1951–1980; `04_temperature.py` re-baselines both series
  to 1991–2020 per calendar month.

## Setup
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Workflow
- `main` stays runnable. Work on a branch per task (`feat/trends-download`), merge via pull request.
- Tasks live in GitHub Issues; assign yourself before starting.
- Config (time window, keywords) lives in `config/`, not hard-coded in scripts.
