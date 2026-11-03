"""Build stance windows (relevant sentence ± stance_context_window, same speech, overlaps merged,
split above stance_max_window) and classify their stance (pro climate action / neutral / contra).
Validate against a hand-annotated sample in annotation/.
Output: data/interim/windows_stance.parquet
"""
