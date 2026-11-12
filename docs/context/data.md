# Data

Purpose: per source, where it comes from, where it lies, what the columns are and what to watch out for.
Sources table, download commands and Trends export steps: [README.md, "Data sources"](../../README.md#data-sources).
URLs: `config/sources.yaml`. `data/` is not in git; each person builds it locally.
Columns below were read from the real files on 11 Nov 2026, unless marked otherwise.
`#N` = issue or pull request N of this repository.

## General
- Period: 2004-01 to 2026-09, monthly, 273 months (`start_date`, `end_date` in `config/settings.yaml`).
- `data/raw/MANIFEST.csv`: one row per downloaded file, 127 rows (incl. the EM-DAT export);
  columns `file`, `url`, `accessed_utc`, `bytes`, `sha256`. Written by `src/00_download.py`
  (manual exports: command in the README).
- Month key in all processed files: `month` as `YYYY-MM`.

## Speeches, 15th–20th Bundestag (PoliCorp-GermaParl2-PLUS)
- Origin: Zenodo, DOI 10.5281/zenodo.21295610, CC BY 4.0; `src/00_download.py policorp`.
- Raw: `data/raw/speeches/policorp/`: `policorp_lp-15.json` .. `policorp_lp-20.json`,
  `party_mapping.json` (list with `party`, `party_name`, `party_id`, `wiki`, `link`),
  `parliamentarians.json`, metadata PDF, zip.
- Period: corpus 1949 – 18 Mar 2025; used from 2004-01 (15th Bundestag covers 2004).
- Unit: one speech (contribution) per entry; `text_raw` = list of sentences with `type`
  speech / interjection / call to order.
- Caveats: ends with the 20th Bundestag (last session 18 Mar 2025); some wrong or empty parties,
  fixed via `config/party_overrides.yaml`.

## Speeches, 21st Bundestag (Bundestag Open Data XML)
- Origin: Bundestag Open Data, plenary protocol XML; `src/00_download.py wp21`.
- Raw: `data/raw/speeches/bundestag_wp21/` (103 XML files, `21001.xml` ..);
  `data/raw/speeches/bundestag_wp20_validation/` (session XML of the 20th Bundestag, to validate
  the converter); `data/raw/speeches/MdB-Stammdaten.zip` (MP master data, dated group memberships).
- Interim: `data/interim/wp21_policorp.json`, written by `src/01a_wp21_to_policorp.py`: object with
  `note` and `data` (list of 40,284 speeches).
- Fields per speech: `agenda_id`, `legislativeperiod`, `sessionno`, `date`, `source_file`,
  `agenda_type`, `agenda_nr`, `speech_id`, `speechno`, `speaker_id`, `name`, `role`, `position`,
  `party`, `party_id`, `topic`, `text_raw`, `source`.
- Period: since 25 Mar 2025.
- Caveats: `topic`, `agenda_type` and NER are not available (null); calls to order are not marked
  in the XML; government members have no party in the XML (filled in step 1); converter checked
  on 3 sessions of the 20th Bundestag (same contributions, identical text, sentence counts
  within 0.1 %); speeches are on average shorter than in earlier periods (PR #1).

## All speeches, sentence level
- File: `data/interim/sentences.parquet`, written by `src/01_speeches.py`.
- **From code, not verified on data:** one sentence per row; columns `speech_id`, `date`, `month`,
  `lp`, `sessionno`, `agenda_id`, `agenda_type`, `topic`, `role`, `position`, `speaker_id`, `name`,
  `party`, `party_source`, `party_in_government`, `seq_no`, `text`.
- Size according to #3: 5.14 M sentences in 206,915 speeches.
- Only sentences of type speech: interjections and calls to order are excluded.
- Only roles in `speaker_roles` (`config/settings.yaml`): mp, government, federal_council.
- Party = parliamentary group on the speech date; rules and exceptions (CDU/CSU merged, Linke
  group gap, overrides, ~50 speeches without party): [README.md, "Known caveats"](../../README.md#known-caveats).
- `party_in_government`: party is a coalition party on the speech date (`config/governments.yaml`);
  government dates before Nov 2024 still to verify (#4).
- Months without sittings (e.g. August recess) have no sentences, so no attention value.

## Temperature
- Origin: DWD Climate Data Center (area mean Germany, monthly mean air temperature) and NASA
  GISTEMP v4 (global land-ocean index); `src/00_download.py temperature`.
- Raw: `data/raw/temperature/dwd/regional_averages_tm_01.txt` .. `_12.txt` (one file per calendar
  month); `data/raw/temperature/gistemp_GLB.Ts+dSST.csv` (one row per year, columns `Jan`..`Dec`,
  `J-D`, `D-N`, `DJF`, `MAM`, `JJA`, `SON`, missing value `***`).
- Processed: `data/processed/temperature_monthly.csv`, written by `src/04_temperature.py`:
  273 rows, 2004-01..2026-09; columns `month`, `temp_de`, `anomaly_de`, `anomaly_global`.
- Unit: °C; anomalies relative to 1991–2020 per calendar month.
- Caveat: GISTEMP raw anomalies are relative to 1951–1980; step 4 re-baselines them.

## Google Trends
- Origin: manual CSV export from Google Trends, region DE, each entry requested alone
  (steps in the README).
- Raw: `data/raw/trends/*.csv`: `A_term_klimawandel.csv`, `B_topic_klimaschutz.csv`,
  `B_topic_hitzewelle.csv`, `B_topic_klima.csv`; two columns `Time`, `<term>`, monthly,
  values 0..100.
- Processed: `data/processed/trends_monthly.csv`, written by `src/05_trends.py`: 1092 rows
  (4 terms × 273 months), 2004-01..2026-09; columns `month`, `term`, `index`, `file`.
- Terms: Klimawandel (main series, file `A_term_klimawandel.csv`), Klima, Klimaschutz, Hitzewelle
  (files `B_topic_*.csv`).
- Unit: index 0–100 within one export; values from different files are not on the same scale.
- Caveats (details in [README.md, "Known caveats"](../../README.md#known-caveats)):
  - Topic break 2016-11: `B_topic_klima` jumps ×3 when the climate-change topics drop to 0; use
    a break marker from 2016-11.
  - One-week spikes: Klimawandel Apr 2022 (= 100), Klimaschutz Apr 2023 (= 100); kept in the
    data, check results with and without these months.
  - Hitzewelle is dominated by summer 2026; values before 2018 are mostly 0–3.
  - Google samples the data and changed its collection on 1 Jan 2011, 2016, 2017 and 2022;
    second export of the main series for a correlation check is open (#4).

## Disasters (EM-DAT)
- Origin: EM-DAT (CRED, UCLouvain), public.emdat.be, free for academic use after registration;
  licence does not allow redistribution. Manual export (login), steps in the README.
- Raw: `data/raw/disasters/public_emdat_custom_request.xlsx` (one file), sheets `EM-DAT Data`
  (10,949 rows, 47 columns) and `EM-DAT Info`. Export settings: classification Natural, all countries,
  start years 2000–2026. One row per event and country; `DisNo.` = `YYYY-NNNN-ISO`.
  Columns used: `DisNo.`, `Disaster Subgroup`, `ISO`, `Start Year`, `Start Month`, `Total Deaths`,
  `Total Affected`.
- Processed: `data/processed/disasters_monthly.csv`, written by `src/04b_disasters.py`: 273 rows,
  2004-01..2026-09; columns `month` and `events_*`, `deaths_*`, `affected_*` for `de` (Germany,
  ISO DEU), `row` (rest of world: events that did not hit Germany) and `global` (all countries);
  months without events = 0.
- Rules (#17): subgroups climatological, hydrological, meteorological (`config/sources.yaml`);
  events counted once per region by `DisNo.` without the country code; deaths and affected summed
  over rows; everything in the start month; blank deaths / affected = 0; events without start month
  dropped (45 rows with start year 2004–2026, 10 deaths).
- Caveats:
  - Germany: 55 events in 50 of 273 months; 47 of them also hit other countries (mostly European storms,
    floods, heatwaves). They are German events: in `de` with the German deaths / affected; their rows
    for the other countries (182,105 deaths, 2.3 M affected) count only in `global`, not in `row` (#17,
    PR #24). So deaths / affected of `de` + `row` are lower than `global`; events add up except in
    18 months where a German event starts in another month elsewhere.
  - Because the large European heatwaves 2022–2024 also hit Germany, `deaths_row` 2022–2024 is
    13–25 k per year, while `deaths_global` is 72–79 k.
  - 107 events start in different months in different countries and count in each of those months.
  - Heatwave deaths are not a usable German heat signal. EM-DAT enters European heatwaves a median
    of 13–16 months after they start (2022–2025), with deaths from later excess-mortality studies.
    The 2026 heatwave is not in the export (12 Nov 2026). Before 2022, German heatwave deaths are
    almost missing (2018: none, 2019: 4; RKI estimates 9,000 and 7,400), and from 2022 they are
    2–3 times the RKI estimates (DE: 8,173 in 2022-05, 6,376 in 2023-07, 6,282 in 2024-06, 2,445 in
    2025-07). German heat deaths come from the RKI instead (#26).
  - Event counts: 227–334 events per year worldwide (2004–2025), about +8 % from 2004–2014
    (mean 260.5) to 2015–2025 (mean 281.6): a mild rise, no strong reporting trend.
  - Late reporting: 2026 has ~15 events per month worldwide vs. ~24–25 in 2023–2025, so the
    last months are incomplete.
  - Some events have a start month after the export date (2026-11, 2026-12); outside the window.
  - Per-year counts (unique events per year): `results/3_data_preparation/tables/04b_disasters_per_year.csv`.

## Planned outputs (scripts are stubs)
- `data/interim/sentences_relevant.parquet` (`src/02_relevance.py`, #5).
- `data/interim/windows_stance.parquet` (`src/03_stance.py`).
- `data/processed/panel_monthly.csv` (`src/06_merge.py`, #8).
