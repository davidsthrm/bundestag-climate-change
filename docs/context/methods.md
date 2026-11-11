# Methods

Purpose: the conventions for relevance, stance and time-series analysis, with the issue where each is worked on.
Agreed thresholds and criteria: [decisions.md](decisions.md). Values: `config/settings.yaml`.
`#N` = issue or pull request N of this repository.

## Relevance (#5)
- Keyword dictionary `config/keywords_de.yaml`, matched case-insensitively; script `src/02_relevance.py` (stub).
- Groups: `core` (relevance filter), `energy` (weaker signal), `sceptic_markers` (for stance
  validation, not for filtering).
- Open: whether `energy` terms count only together with a `core` term.
- Output unit: sentence (attention a) and speech (main topic b), see decisions.md.
- Quality: precision/recall check of the dictionary.
- Main-topic threshold (20 %, ≥ 2 hits) is provisional and rechecked here.

## Stance (#6, #7, #9, #10, #11, #13)
- Labels: pro climate action / neutral / contra.
- Unit: window (hit sentence ± 2 sentences, same speech, overlaps merged, at most 7 sentences,
  longer ones split into nearly equal chunks); built by `src/03_stance.py` (stub).
- Labelling rules: [annotation/README.md](../../annotation/README.md) (whole window; speaker's own
  position decides).
- Gold set: both annotators label the same sample (~200–300 windows) independently (#6, #7);
  agreement reported as Cohen's κ; disagreements resolved; train/test split (#7).
- Three methods on the same task: lexicon + TF-IDF baseline (#9), sentence embeddings +
  classifier (#10), LLM zero-/few-shot (#11).
- Evaluation: macro-F1 on the test split with bootstrap confidence intervals, compared with the
  lexicon baseline; error analysis for all three methods (#13).
- Interjections are not part of any window.

## Time series (#8, #12, #14)
- Monthly panel from `src/06_merge.py` (stub, #8): attention (a) and (b), stance shares,
  temperature, Trends, disasters (#17).
- Detrend and deseasonalize all series before testing (shared upward trend 2004–2026 would
  otherwise produce a spurious correlation).
- Regression attention ~ Trends + temperature + disasters, with lags, standardized coefficients,
  Newey-West standard errors (#12).
- Wald test for the difference between the Trends coefficient and the physical-signal coefficients.
- Granger test = temporal order (which series moves first), not causation: both can react to the
  same events.
- Months without sittings are missing, not 0; for Granger the first month after each recess is
  dropped too.
- H2: same model with German vs. global predictors.
- Open: which disaster measure enters the main model (count, deaths or affected) (#17, #12).
- Robustness (#14): German anomaly instead of the global one; with and without the Trends spike
  months (Apr 2022, Apr 2023); break marker for the Klima topic from 2016-11.
