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

Views, by hypothesis: H1 signals (attention a and b, Trends, global temperature, global
disasters), H1 indexed overlay, H1 detrended and deseasonalized (display only; #12 fixes the method), all four Trends exports with the topic break and spike months,
H2 Germany vs world (temperature, disasters, attention around German disaster months, RKI heat deaths if present), H3 parties and
government vs opposition, stance units per party (monthly vs quarterly), corpus and join.

`viz/src/data/viz.json` is derived data and not committed.
