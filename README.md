# Safety Observations vs Incidents Analyzer (SharePoint MVP)

This MVP analyzes safety **incident** and **observation** data by location/month (project-level using `project number`), then generates:

- `reports/location_summary.xlsx`
- `reports/location_summary.csv`
- `reports/report.html` (single-file HTML dashboard)

## Quick start

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

## Run modes

### 1) Local mode (default)
- `mode: local` in `config.yaml`
- Reads from `sample_data/` so you can validate the end-to-end flow without SharePoint access.

### 2) SharePoint Graph mode (enterprise)
- Set `mode: graph`
- Uses **Device Code Flow** (no hard-coded credentials)
- Supports SharePoint **Document Library files** and **SharePoint Lists**.

For this project, `config.yaml` is pre-filled for document library files:
- Weekly Claims Report.xlsx (incidents)
- Observation Export - Safety Inspection.xlsx (observations)
- Safety_Metrics.xlsx (exposure)

You can provide files by either:
- `*_file_url` (direct SharePoint link), or
- `document_library_drive_id` + `*_file_path`.

## Data mapping

`config.yaml` contains configurable mapping dictionaries so inconsistent source column names are mapped to canonical fields.

This repo is pre-configured for your stated keys:
- Join/location key: `project number`
- Incident date: `loss date`
- Observation date: `Observation date`
- Exposure date: `Valuation Date`
- Exposure source: `Safety_Metrics.xlsx`

## Analytics included

- Monthly incident counts and severity index by location/project
- Observation volume and quality proxies
- Incident rate per 200k hours (when exposure exists)
- Observation-vs-incident correlation and lagged correlation (0/1/2 month)
- Leading indicator score (weighted composite; weights configurable)
- Mismatch detection:
  - high observations + flat/worse incidents → quality/coaching issue
  - low observations + high incidents → coverage/resource issue
- Auto-generated guidance (action + rationale + KPI)

## Project structure

- `src/data_sources.py` - data-source abstraction (local + graph)
- `src/preprocess.py` - schema mapping and standardization
- `src/analysis.py` - metrics, heuristics, and guidance
- `src/reporting.py` - Excel/CSV + HTML report generation
- `src/main.py` - entrypoint
- `sample_data/` - demo data
- `reports/` - generated outputs

## Notes for Azure app registration

For graph mode, ensure your app registration allows delegated permissions:
- `Files.Read.All`
- `Sites.Read.All`

Then grant admin consent according to your tenant policy.
