"""Load PoliCorp speeches, keep start_date (config/settings.yaml)..today, attach party, split into paragraphs.
Output: data/interim/paragraphs.parquet  (speech_id, date, speaker, party, para_id, text)
"""
