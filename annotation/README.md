# Manual annotation
Both annotators label the same random sample (~200–300 stance windows) independently:
`pro` / `neutral` / `contra`. A window is a climate-relevant sentence ± 2 sentences of the same speech
(overlaps merged, at most 7 sentences, see `config/settings.yaml`).
- The label is the stance of the **whole window** toward climate action: a neutral hit sentence with
  clearly contra context is `contra`.
- If a window contains both positions (e.g. the speaker quotes the other side and rejects it),
  the **speaker's own position** decides. Compute inter-annotator agreement (Cohen's kappa),
resolve disagreements, then use the result as gold standard to evaluate step 3.
