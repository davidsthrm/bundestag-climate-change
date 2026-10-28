# Visualisation app

Exploratory Astro page over the pipeline outputs (speeches, temperature, Google Trends).
The climate filter here is a provisional keyword match, not step 2.

```bash
python viz/export_data.py   # from repo root, needs steps 1, 4, 5; writes viz/src/data/viz.json (~3 min)
cd viz
npm install
npm run dev                 # http://localhost:4321
```

`viz/src/data/viz.json` is derived data and not committed.
