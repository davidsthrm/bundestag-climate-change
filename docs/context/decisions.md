# Decisions

Purpose: every agreed decision, one bullet each, with the issue or PR where it was agreed.
`#N` = issue or pull request N of this repository (`gh issue view N` / `gh pr view N`).
New entries only after both team members agreed in an issue or PR (see `CLAUDE.md`).

## Research question and hypotheses
Full text: [README.md, "Research question" and "Hypotheses"](../../README.md#research-question).
The README is the single source; the bullets below are a short form.

- Hypotheses H1, H1b, H2, H3 and the success criteria are fixed before looking at results (#2, PR #19).
- Research question asks whether attention follows the physical climate signal or public
  attention; the German signal is not named there, H2 tests it (PR #19).
- Extension: party comparison incl. stance (pro climate action / neutral / contra) (#2).
- Physical signal = global temperature anomaly (GISTEMP) + global EM-DAT climate disasters.
  German anomaly (DWD) only in H2 and the robustness checks (#2).
- H1: short-term parliamentary attention follows public attention (Google Trends) more closely
  than the physical signal; trend and seasonality removed first; two attention measures,
  (a) mentions and (b) main topic (#2).
- H1b (tone over time) is exploratory; only if the stance criteria are met; overall and within
  parties, quarterly if party-months are too sparse (#2, PR #19).
- H2: German vs. global temperature anomaly, German vs. non-German disasters from the same EM-DAT
  data, no extra source; may stay descriptive (most months have 0 German events); hand-picked
  event study (~10 events) optional and descriptive only (#2, PR #19).
- H3: stance differs between parties and between government and opposition; tested with three
  methods (#2).

## Success criteria
Full text: [README.md, "Success criteria"](../../README.md#success-criteria).

- Gold set: Cohen's κ ≥ 0.6 between both annotators; if lower, revise the guideline once,
  re-annotate, report both values (#2).
- Stance: best method macro-F1 ≥ 0.6 and above the lexicon baseline, with bootstrap confidence
  intervals; for H1b, pro and contra each need F1 ≥ 0.5 (#2).
- H1 test: series detrended and deseasonalized; regression attention ~ Trends + temperature +
  disasters with lags, standardized coefficients, Newey-West standard errors; supported if the
  Trends coefficient is significant and larger than the physical-signal coefficients (#2), the
  difference tested with a Wald test (PR #19).
- Granger test checks temporal order only, not causation (PR #19).
- Months without sittings are left out of the regression, not set to 0; for the Granger test the
  first month after each recess is dropped too (PR #19).
- H2: same model with German vs. global predictors (#2).
- H1 / H2 count as supported only if the result holds in the robustness checks (#2, #14).

## Data
- Period: 2004-01 (start of Google Trends) to today, monthly; `start_date` / `end_date` in
  `config/settings.yaml` (PR #1).
- Speeches: PoliCorp-GermaParl2-PLUS (15th–20th Bundestag, ends 18 Mar 2025) is the main corpus,
  incl. its party mapping (PR #1).
- Speeches of the 21st Bundestag come from the official Bundestag Open Data XML and are converted
  into PoliCorp's format (same fields, sentence-level `text_raw`, party names mapped to PoliCorp
  labels), then merged. The converter is validated on 20th-Bundestag sessions present in both
  sources (PR #1). Check for overlap/gaps at the boundary (no link, predates the rule).
- Interjections are excluded from the analysis (PR #1, #3).
- Temperature anomalies are relative to 1991–2020, per calendar month, both DE and global (PR #1).
- Public attention: main series is the Google Trends *search term* Klimawandel, because the
  climate-change topics are 0 in Germany from 2017 to 2020 (PR #1).
- EM-DAT disasters: subgroups climatological, hydrological, meteorological; no geophysical
  events (#2, #17).
- The lecturer confirmed that additional structured sources are welcome (e.g. Trends,
  temperature, social-media or news statistics) (PR #20).

## Units of analysis
Table: [README.md, "Units of analysis"](../../README.md#units-of-analysis). Values in
`config/settings.yaml`.

- Attention (a) = sentence: share of climate-relevant sentences among all sentences per month
  (`attention_unit`) (#3).
- Main topic (b) = speech with ≥ 20 % relevant sentences (`main_topic_threshold`, #3) and ≥ 2
  relevant sentences (`main_topic_min_hits`, PR #18); provisional, recheck in #5.
- Stance = window: hit sentence ± 2 sentences, same speech, overlaps merged (`stance_unit`,
  `stance_context_window`) (#3).
- Windows longer than 7 sentences (`stance_max_window`) are split into chunks of (nearly) equal
  length, larger first (9 → 5 + 4, not 7 + 2) (PR #18).
- The window is labelled as a whole: a neutral hit sentence with clearly contra context is
  contra (#3).
- If a window contains both positions, the speaker's own position decides (PR #18).
- Stance windows are also the unit for H1b (#3).
