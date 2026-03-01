from __future__ import annotations

from src.analysis import build_guidance, location_effectiveness, mismatch_flags, monthly_location_metrics, top_categories
from src.config import load_config
from src.data_sources import GraphSharePointDataSource, LocalFileDataSource
from src.preprocess import standardize_exposure, standardize_incidents, standardize_observations
from src.reporting import build_html_report, export_summary_excel


def get_data_source(config: dict):
    if config.get("mode", "local") == "graph":
        return GraphSharePointDataSource(config["sharepoint"])
    return LocalFileDataSource(config["local"])


def run(config_path: str = "config.yaml") -> None:
    config = load_config(config_path)
    analysis_cfg = config.get("analysis", {})
    data_source = get_data_source(config)

    incidents_raw = data_source.load_incidents()
    observations_raw = data_source.load_observations()
    exposure_raw = data_source.load_exposure()

    incidents = standardize_incidents(incidents_raw, config["column_mapping"]["incidents"])
    observations = standardize_observations(observations_raw, config["column_mapping"]["observations"])
    exposure = standardize_exposure(exposure_raw, config["column_mapping"]["exposure"])

    monthly = monthly_location_metrics(incidents, observations, exposure)
    effectiveness = location_effectiveness(
        monthly,
        analysis_cfg.get("lag_months", [0, 1, 2]),
        leading_weights=analysis_cfg.get("leading_indicator_weights"),
    )
    effectiveness = mismatch_flags(
        effectiveness,
        high_incident_threshold_quantile=analysis_cfg.get("high_incident_threshold_quantile", 0.7),
        low_observation_threshold_quantile=analysis_cfg.get("low_observation_threshold_quantile", 0.3),
    )
    categories = top_categories(incidents, observations)
    guidance = build_guidance(effectiveness, categories)

    export_summary_excel(monthly, effectiveness, guidance, categories)
    build_html_report(monthly, effectiveness, guidance)
    print("Generated reports/location_summary.xlsx and reports/report.html")


if __name__ == "__main__":
    run()
