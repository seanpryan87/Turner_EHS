from __future__ import annotations

import argparse

from src.analysis import (
    build_guidance,
    emerging_risk_dashboard,
    location_effectiveness,
    mismatch_flags,
    monthly_location_metrics,
    top_categories,
)
from src.config import load_config
from src.data_sources import GraphSharePointDataSource, LocalFileDataSource
from src.preprocess import resolve_dimensions, standardize_exposure, standardize_incidents, standardize_observations
from src.reporting import build_html_report, export_summary_excel


def get_data_source(config: dict, overrides: dict | None = None):
    if config.get("mode", "local") == "graph":
        return GraphSharePointDataSource(config["sharepoint"])
    local_cfg = {**config["local"], **(overrides or {})}
    return LocalFileDataSource(local_cfg)


def run(config_path: str = "config.yaml", local_overrides: dict | None = None) -> None:
    config = load_config(config_path)
    analysis_cfg = config.get("analysis", {})
    data_source = get_data_source(config, local_overrides)

    incidents_raw = data_source.load_incidents()
    observations_raw = data_source.load_observations()
    exposure_raw = data_source.load_exposure()

    incidents = standardize_incidents(incidents_raw, config["column_mapping"]["incidents"])
    observations = standardize_observations(observations_raw, config["column_mapping"]["observations"])
    exposure = standardize_exposure(exposure_raw, config["column_mapping"]["exposure"])
    hierarchy_map, incidents, observations, exposure = resolve_dimensions(incidents, observations, exposure)

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
    emerging_risk, user_risk, subcontractor_risk = emerging_risk_dashboard(monthly, incidents, observations)

    export_summary_excel(
        monthly,
        effectiveness,
        guidance,
        categories,
        hierarchy_map,
        emerging_risk,
        user_risk,
        subcontractor_risk,
    )
    build_html_report(monthly, effectiveness, guidance, hierarchy_map, emerging_risk, user_risk, subcontractor_risk)
    print("Generated reports/location_summary.xlsx and reports/report.html")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build emerging risk dashboard from EHS data.")
    parser.add_argument("--config", default="config.yaml", help="Path to config YAML.")
    parser.add_argument("--incidents", help="Override incidents file path (CSV/XLSX).")
    parser.add_argument("--observations", help="Override observations file path (CSV/XLSX).")
    parser.add_argument("--exposure", help="Override exposure file path (CSV/XLSX).")
    args = parser.parse_args()
    overrides = {}
    if args.incidents:
        overrides["incident_path"] = args.incidents
    if args.observations:
        overrides["observation_path"] = args.observations
    if args.exposure:
        overrides["exposure_path"] = args.exposure
    run(args.config, local_overrides=overrides)
