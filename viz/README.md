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

Each section opens with a one-line takeaway computed from the tables, then charts; the full tables
are folded away under "Show ...". Sections: H1 signals, indexed, detrended (display only; #12 fixes
the method), Google Trends exports; H2 Germany vs world and attention around German disaster months
(event study); H3 who speaks vs who speaks about climate, parties, government vs opposition; stance
units per party; corpus and join (coverage of every series). EM-DAT months after `complete_until`
(`config/sources.yaml`) are shaded as incomplete.

`viz/src/data/viz.json` is derived data and not committed.
