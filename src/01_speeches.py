"""Load PoliCorp speeches, keep 2005-10-18..today, attach party, split into paragraphs.
Output: data/interim/paragraphs.parquet  (speech_id, date, speaker, party, para_id, text)
"""
