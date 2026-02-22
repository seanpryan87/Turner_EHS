# Safety Observations vs Incidents Analyzer (SharePoint MVP)

This MVP analyzes safety **incident** and **observation** data by location and month, then generates:

- `reports/location_summary.xlsx`
- `reports/location_summary.csv`
- `reports/report.html` (single-file HTML dashboard)

It runs immediately with sample local files and includes a SharePoint Graph data-source abstraction for enterprise rollout.

## Quick start (non-coder friendly)

1. Install Python 3.11+.
2. Open terminal in this folder.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run:
   ```bash
   python -m src.main
   ```
5. Open `reports/report.html` in your browser.

## Configuration

Edit `config.yaml`.

### Local mode (default)
- `mode: local`
- Uses `sample_data/incidents.csv`, `sample_data/observations.csv`, `sample_data/exposure.csv`.

### SharePoint Graph mode
- Set `mode: graph`
- Fill in tenant/client/site/drive settings under `sharepoint`.
- Uses Device Code Flow (no hardcoded credentials).

Supported SharePoint source types:
- Document library files (`source_type: document_library`)
- SharePoint lists (`source_type: list`)

## Column mapping and data variability

`config.yaml` includes column mapping dictionaries to map inconsistent source headers to canonical fields.

Canonical incident fields:
- `incident_id`, `date`, `location`, `severity`, `category`

Canonical observation fields:
- `observation_id`, `date`, `location`, `category`, `observation_type`
- quality proxy helpers if present (comments, corrective action, closure date, etc.)

## What analytics are included

- Monthly counts by location for incidents and observations
- Severity index and serious-potential counts
- Incident rate per 200k hours (if exposure provided)
- Correlation + lagged correlations (0/1/2 month) between observations and incidents
- Leading indicator score (composite quality proxy)
- Mismatch flags:
  - high observations + non-improving incidents = potential quality/coaching issue
  - low observations + high incidents = potential coverage issue
- Guidance generation with action, rationale, and KPI

## Project structure

- `src/data_sources.py` - Data source abstraction and implementations
- `src/preprocess.py` - Standardization and mapping
- `src/analysis.py` - Metrics, effectiveness, mismatch heuristics, guidance
- `src/reporting.py` - HTML and Excel/CSV output
- `src/main.py` - one-command entrypoint
- `sample_data/` - runnable sample datasets
- `reports/` - output artifacts

## Critical questions to finalize your environment setup

Please share these to wire to your real SharePoint data:
1. SharePoint source type: **Document Library files** or **SharePoint Lists**?
2. Exact file names (or list names) and folder paths.
3. Column names for **location** and **date** in each dataset.
4. Exposure data availability (hours worked/headcount): **yes/no**.
