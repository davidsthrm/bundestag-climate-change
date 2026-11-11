"""Build stance windows (relevant sentence ± stance_context_window, same speech, overlaps merged,
split above stance_max_window) and classify their stance (pro climate action / neutral / contra).
Windows longer than stance_max_window are split into chunks of (nearly) equal length, larger chunks
first (9 -> 5 + 4, not 7 + 2), so there is no short tail chunk without a hit sentence.
Validate against a hand-annotated sample in annotation/.
Output: data/interim/windows_stance.parquet
"""
