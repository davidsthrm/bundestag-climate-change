# Data

Purpose: per source, where it comes from, where it lies, what the columns are and what to watch out for.
Sources table, download commands and Trends export steps: [README.md, "Data sources"](../../README.md#data-sources).
URLs: `config/sources.yaml`. `data/` is not in git; each person builds it locally.
Columns below were read from the real files on 11 Nov 2026, unless marked otherwise.
`#N` = issue or pull request N of this repository.

## General
- Period: 2004-01 to 2026-09, monthly, 273 months (`start_date`, `end_date` in `config/settings.yaml`).
- `data/raw/MANIFEST.csv`: one row per downloaded file, 126 rows; columns `file`, `url`,
  `accessed_utc`, `bytes`, `sha256`. Written by `src/00_download.py`.
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
  dates checked against the Bundestag Datenhandbuch, chapter 6, on 12 Nov 2026 (#4); the minority
  phase from 7 Nov 2024 is not a separate cabinet there but follows from the FDP dismissals (ch. 6.12).
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
  values 0..100. `data/raw/trends/check/A_term_klimawandel_2.csv`: second export of the main series
  on another day, same settings; not merged, only compared (#4).
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
  - Google samples the data and changed its collection on 1 Jan 2011, 2016, 2017 and 2022.
    Second export of the main series vs. the first: r = TODO (levels), r = TODO (month-to-month
    changes), max. difference TODO index points (`results/2_data_understanding/tables/05_trends_reexport.csv`, #4).

## Disasters (EM-DAT), planned
- Not in the repo yet: #17 (`src/04b_disasters.py`).
- Planned: manual export (login needed) into `data/raw/disasters/`; processed
  `data/processed/disasters_monthly.csv`, monthly, Germany and rest of world.
- Subgroups climatological, hydrological, meteorological; no geophysical events.
- Licence does not allow redistribution.

## Planned outputs (scripts are stubs)
- `data/interim/sentences_relevant.parquet` (`src/02_relevance.py`, #5).
- `data/interim/windows_stance.parquet` (`src/03_stance.py`).
- `data/processed/panel_monthly.csv` (`src/06_merge.py`, #8).
