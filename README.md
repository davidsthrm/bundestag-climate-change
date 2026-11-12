# Bundestag & Climate Change (2004–today)

Student project for a university NLP module.

## Research question
Does the Bundestag's attention to climate change follow the **physical climate signal** or
**public attention**? Extension: differences between parties, including the
**stance** of climate-related speech (pro climate action vs. sceptical/opposing).

## Hypotheses
Fixed before looking at results (#2).

**H1: Physical signal vs. public attention.** Short-term variation in parliamentary climate attention
follows public attention (Google Trends) more closely than the physical climate signal. Long-term trend
and seasonality are removed first.
- Attention, two measures: (a) share of climate-relevant sentences ("mentions"), (b) share of speeches with
  climate as main topic.
- Physical signal: global temperature anomaly (GISTEMP) and global climate-related disasters (EM-DAT:
  climatological, hydrological, meteorological; no geophysical events, #17). The German anomaly (DWD)
  goes into the robustness checks.
- Global, because climate change is a global phenomenon and the debate refers to global benchmarks
  (IPCC, COPs, 1.5 °C).

**H1b: Tone over time (exploratory).** The share of pro-climate-action stance windows follows public
attention / the physical signal. Attention alone cannot separate speaking *for* climate action from
speaking *against* it. Analysed overall and within parties, because party composition changes over time
(quarterly if party-months are too sparse). Only if the stance criteria below are met.

**H2: Local vs. distant signals.** Attention reacts more strongly to local signals than to global ones:
German vs. global temperature anomaly, German vs. non-German disasters (same EM-DAT data, no extra source).
German disasters are rare (most months 0), so this part may stay descriptive. A hand-picked event study
(~10 events) is optional and descriptive only.

**H3: Stance.** Stance on climate action (pro / neutral / contra) differs between parties and between
government and opposition. Tested with three methods: lexicon + TF-IDF, embeddings + classifier, LLM.

### Success criteria
- **Gold set:** Cohen's κ ≥ 0.6 between both annotators. If lower: revise the guideline once,
  re-annotate, report both values.
- **Stance:** best method macro-F1 ≥ 0.6 **and** above the lexicon baseline, with bootstrap confidence
  intervals (small test split). For H1b, pro and contra each need F1 ≥ 0.5.
- **H1 test:** monthly series detrended and deseasonalized; regression attention ~ Trends + temperature +
  disasters (with lags, standardized coefficients, Newey-West standard errors). Supported if the Trends
  coefficient is significant and larger than the physical-signal coefficients, the difference tested with
  a Wald test. A Granger test checks temporal order (does parliament precede searches?); it shows which
  comes first in time, not causation, because both can react to the same events.
- **Months without sittings** (e.g. August recess) have no attention value: they are left out of the
  regression, not set to 0. For the Granger test, lagged attention is also missing in the first month
  after each recess, so those rows are dropped too.
- **H2:** same model with German vs. global predictors.
- H1 / H2 count as supported only if the result holds in the robustness checks.

## Pipeline
| Step | Script | Output |
|------|--------|--------|
| 0 | `src/00_download.py`    | raw data into `data/raw/` (+ MANIFEST.csv) |
| 1a | `src/01a_wp21_to_policorp.py` | 21st Bundestag XML in PoliCorp format (`data/interim/wp21_policorp.json`) |
| 1 | `src/01_speeches.py`    | all speeches 2004–today, one row per sentence, with party and government/opposition (`config/governments.yaml`) (`data/interim/sentences.parquet`) |
| 2 | `src/02_relevance.py`   | climate-relevant sentences (keyword dictionary) + main-topic speeches |
| 3 | `src/03_stance.py`      | stance label per window (relevant sentence ± 2 sentences) |
| 4 | `src/04_temperature.py` | monthly temperature anomalies DE + global |
| 4b | `src/04b_disasters.py` | monthly climate-related disasters (EM-DAT), Germany + rest of world |
| 4c | `src/04c_heat_mortality.py` | heat-related deaths in Germany (RKI), monthly 2016–today, yearly 2004–today |
| 5 | `src/05_trends.py`      | monthly Google Trends index (DE) |
| 6 | `src/06_merge.py`       | one monthly panel in `data/processed/` |

## Data sources
| Data | Source | Coverage | How we get it |
|------|--------|----------|---------------|
| Plenary speeches WP15–20 | PoliCorp-GermaParl2-PLUS, Zenodo [10.5281/zenodo.21295610](https://doi.org/10.5281/zenodo.21295610), CC BY 4.0 | 1949 – 18 Mar 2025, sentence-level, with party | `src/00_download.py policorp` |
| Plenary speeches WP21 | Bundestag Open Data, plenary protocol XML (+ 3 WP20 sessions to validate the converter) | since 25 Mar 2025 | `src/00_download.py wp21` |
| MP master data | Bundestag Open Data, MdB-Stammdaten (dated parliamentary group memberships) | 1949 – today | `src/00_download.py wp21` |
| Temperature Germany | DWD Climate Data Center, regional averages, monthly mean air temperature (area mean Deutschland) | 1881 – last month | `src/00_download.py temperature` |
| Temperature global | NASA GISTEMP v4, global land-ocean index | 1880 – last month | `src/00_download.py temperature` |
| Public attention | Google Trends, region DE | 2004 – today, monthly | manual CSV export (below) |
| Climate disasters | EM-DAT (CRED, UCLouvain), free for academic use after registration, no redistribution | 2000 – today (our export), one row per event and country | manual export (below) |
| Heat-related deaths Germany | RKI weekly report on heat-related mortality (model estimate); before 2016 Winklmayr et al. 2022 ([10.3238/arztebl.m2022.0202](https://doi.org/10.3238/arztebl.m2022.0202)), eTable in `config/heat_deaths_paper.yaml` | weekly 2016 – today (summer weeks 15–40), yearly 1992–2021 | `src/00_download.py rki` |

All URLs are in `config/sources.yaml`. Raw data is **not** in git: each person runs the
download script locally. Every download is logged with URL, access time and SHA-256 in
`data/raw/MANIFEST.csv` (use it for the data section of the paper).

```bash
python src/00_download.py            # all scripted sources (~900 MB, mostly PoliCorp)
python src/01a_wp21_to_policorp.py   # -> data/interim/wp21_policorp.json (--validate: compare with PoliCorp)
python src/01_speeches.py            # -> data/interim/sentences.parquet
python src/04_temperature.py         # -> data/processed/temperature_monthly.csv
python src/04b_disasters.py          # -> data/processed/disasters_monthly.csv
python src/04c_heat_mortality.py     # -> data/processed/heat_mortality_monthly.csv + _yearly.csv
python src/05_trends.py              # -> data/processed/trends_monthly.csv
```

### Google Trends export (manual)
Google Trends has no official API and scrapers get rate-limited, so we export by hand.
Each file is **one entry requested alone**, so each has its own 0–100 scale.
Settings: trends.google.de → *Entdecken*, region **Deutschland**, custom range **01.01.2004 – last day of
the last complete month** (ranges > 5 years return monthly values), *Alle Kategorien*, *Websuche*.
Download via the ↓ icon of "Interesse im zeitlichen Verlauf".

| File in `data/raw/trends/` | Entry | Role |
|---|---|---|
| `A_term_klimawandel.csv`  | Klimawandel (Suchbegriff) | main variable: public attention to climate change |
| `B_topic_klimaschutz.csv` | Klimaschutz (Thema) | policy-driven attention |
| `B_topic_hitzewelle.csv`  | Hitzewelle (Thema)  | weather-driven attention |
| `B_topic_klima.csv`       | Klima (Thema)       | broad climate attention |

Note the export date in `data/raw/MANIFEST.csv`. Google samples the data, so a re-export on another
day can differ slightly; for robustness export A a second time on a different day
(`A_term_klimawandel_2.csv`) and check the correlation.

### EM-DAT export (manual)
EM-DAT needs a login, so the export is manual. public.emdat.be → register / log in → *Access Data*:
classification **Natural**, all countries, years **2000 – current year**, download the `.xlsx` into
`data/raw/disasters/` (exactly one file there). Log it in the manifest right away:

```bash
python -c "import importlib, pathlib, sys; sys.path.insert(0, 'src'); d = importlib.import_module('00_download'); [d.log_manifest(p.resolve(), d.SOURCES['emdat']['portal_url']) for p in pathlib.Path('data/raw/disasters').glob('*.xlsx')]"
```

`04b_disasters.py` keeps the subgroups climatological, hydrological, meteorological (`config/sources.yaml`),
counts each event once per region (ID without the country code), puts deaths and affected into the
start month and fills months without events with 0. Regions: Germany (`de`), rest of world (`row`) and
all countries (`global`). An event that hits Germany and other countries is a German event: it counts
in `de` (German deaths / affected) and in `global`, not in `row`. The licence forbids redistribution: never commit
the export or share it outside the team.

### Units of analysis
| Measure | Unit | Setting |
|---|---|---|
| Attention (a): mentions | sentence; share of climate-relevant sentences among all sentences per month | `attention_unit` |
| Attention (b): main topic | speech with ≥ 20 % relevant sentences and ≥ 2 relevant sentences (provisional) | `main_topic_threshold`, `main_topic_min_hits` |
| Stance | window: relevant sentence ± 2 sentences of the same speech, overlapping windows merged, split above 7 sentences into chunks of (nearly) equal length, larger first (9 → 5 + 4) | `stance_unit`, `stance_context_window`, `stance_max_window` |

Single sentences are too short for stance (many need the previous sentence to be labelled);
± 1 sentence was too little context. Interjections are not part of any unit.

### Known caveats
- PoliCorp transcripts are split into **sentences**, not paragraphs (`text_raw` = list of sentences
  with `type` speech / interjection / call to order). Interjections must be filtered out.
- PoliCorp ends with the 20th Bundestag (last session 18 Mar 2025); WP21 comes from the Bundestag XML,
  converted to PoliCorp's format by `01a`. Checked on 3 sessions of the 20th Bundestag that are in both
  sources: same contributions, identical text, sentence counts within 0.1%. Not available for WP21:
  topic, agenda type, NER.
- Party = parliamentary group on the speech date, from the official MP master data (CDU and CSU merged).
  The Linke group gap (6 Dec 2023 – 1 Feb 2024) gets the group the MPs joined afterwards (Linke or BSW).
  `config/party_overrides.yaml` covers ministers who are not MPs, state politicians, wrong IDs in
  PoliCorp and the PDS 2002–05. About 50 speeches (civil servants, commissioners) stay without party.
- GISTEMP anomalies are relative to 1951–1980; `04_temperature.py` re-baselines both series
  to 1991–2020 per calendar month.
- The climate-change topics ("Klimawandel", "Global warming") are 0 in Germany from 2017 to 2020,
  so the main variable is the *search term* Klimawandel.
- `B_topic_klima`: level jump ×3 in Nov 2016, when the climate-change topics drop to 0 (likely Google
  re-assigning searches between topics). Use a break marker from 2016-11.
- One-week spikes: Klimawandel 17–24 Apr 2022 (= 100), Klimaschutz Apr 2023 (= 100). Kept in the data;
  check results with and without these months.
- `B_topic_hitzewelle` is dominated by summer 2026 (= 100); values before 2018 are mostly 0–3.
- Google changed its data collection on 1 Jan 2011, 2016, 2017 and 2022 (marked "Hinweis" in Trends).
- EM-DAT heatwave deaths: missing for Germany before 2022, then 2–3 times the RKI estimates, and entered
  13–16 months late (the 2026 heatwave is missing). Use the RKI series for German heat deaths (#26);
  event counts rise only mildly (about +8 % from 2004–2014 to 2015–2025).
- EM-DAT adds events late: the last months of the export (2026) are incomplete.
- RKI heat deaths are model estimates (deaths with minus without heat), not counted deaths; the RKI
  revises them during the summer. Heat kills with a delay: about 40 % of the deaths of the June 2026 heat
  week fall into the following week, so monthly sums split heatwaves at month ends. Before 2016 only
  yearly values from an earlier model version exist (2016–2021: up to 500 deaths apart).

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
