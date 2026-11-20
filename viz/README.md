# Visualisation app

Helper for data understanding (#21, #22), not the deployment (#23). Runs locally, no hosting.
Every number comes from `results/2_data_understanding/tables/07_*.csv` (written by
`src/07_data_understanding.py`), so the app and the paper show the same values.
`viz/export_data.py` only packs those tables into one JSON file.

```bash
python src/02_relevance.py            # from repo root; needs steps 1, 4, 4b, 5 (4c optional)
python src/07_data_understanding.py   # tables + paper figures
python viz/export_data.py             # -> viz/src/data/viz.json
cd viz
npm install
npm run dev                           # http://localhost:4321
```

Layout for storytelling: "The story in one minute" at the top collects the one-line takeaway of
every section (computed from the tables). Part A shows each source on its own (speeches, attention,
Google Trends, temperature incl. warming stripes, EM-DAT disasters, RKI heat deaths); Part B shows
the join and the hypotheses (H1 overlay, detrended series, lag correlations; H2 event study; H3
party heatmap, who speaks about climate; stance units). Each section has one main chart; more
charts and tables are folded under "More charts". Every chart has a PNG button (2x, with its title)
for slides. EM-DAT months after `complete_until` (`config/sources.yaml`) are shaded as incomplete.

`viz/src/data/viz.json` is derived data and not committed.
