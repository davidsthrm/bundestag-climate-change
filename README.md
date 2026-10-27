# Bundestag & Climate Change (2005–today)

Student project for a university NLP module.

## Research question
Does the Bundestag's attention to climate change follow the **physical climate
signal** (temperatures in Germany and globally) or **public attention**
(Google Trends)? Extension: differences between parties, including the
**stance** of climate-related speech (pro climate action vs. sceptical/opposing).

## Pipeline
| Step | Script | Output |
|------|--------|--------|
| 1 | `src/01_speeches.py`    | speeches filtered to 2005–today, with party |
| 2 | `src/02_relevance.py`   | climate-relevant paragraphs (keyword dictionary) |
| 3 | `src/03_stance.py`      | stance label per relevant paragraph |
| 4 | `src/04_temperature.py` | monthly temperature anomalies DE + global |
| 5 | `src/05_trends.py`      | monthly Google Trends index (DE) |
| 6 | `src/06_merge.py`       | one monthly panel in `data/processed/` |

## Data sources
| Data | Source | Notes |
|------|--------|-------|
| Plenary speeches | PoliCorp (incl. party mapping) | not committed – see `data/raw/speeches/` |
| Temperature Germany | DWD Climate Data Center, regional averages, monthly air temperature | area mean for Germany |
| Temperature global | NASA GISTEMP v4 (global mean anomaly) | |
| Public attention | Google Trends, region DE, 2005–today | manual CSV export, terms requested together |

Raw data is **not** in git. Each person downloads it locally into `data/raw/`.

## Setup
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Workflow
- `main` stays runnable. Work on a branch per task (`feat/trends-download`), merge via pull request.
- Tasks live in GitHub Issues; assign yourself before starting.
- Config (time window, keywords) lives in `config/`, not hard-coded in scripts.
