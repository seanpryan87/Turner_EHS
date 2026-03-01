from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def export_summary_excel(
    monthly: pd.DataFrame,
    effectiveness: pd.DataFrame,
    guidance: pd.DataFrame,
    categories: pd.DataFrame,
    output_path: str = "reports/location_summary.xlsx",
) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path) as writer:
        monthly.to_excel(writer, sheet_name="monthly_metrics", index=False)
        effectiveness.to_excel(writer, sheet_name="effectiveness", index=False)
        guidance.to_excel(writer, sheet_name="guidance", index=False)
        categories.to_excel(writer, sheet_name="categories", index=False)

    monthly.to_csv("reports/location_summary.csv", index=False)


def build_html_report(
    monthly: pd.DataFrame,
    effectiveness: pd.DataFrame,
    guidance: pd.DataFrame,
    output_path: str = "reports/report.html",
) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    trend_img = _plot_incident_observation_trends(monthly)
    eff_table = effectiveness.round(3).to_html(index=False)
    monthly_table = monthly.sort_values(["location", "month"]).to_html(index=False)
    guidance_table = guidance.to_html(index=False)

    html = f"""
    <html><head><title>Safety Observations vs Incidents Analyzer</title>
    <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; font-size: 13px; }}
    th {{ background-color: #f2f2f2; }}
    h1, h2 {{ color: #1f3b4d; }}
    </style></head><body>
    <h1>Safety Observations vs Incidents Analyzer</h1>
    <h2>Location dashboard (monthly)</h2>
    {monthly_table}
    <h2>Incident vs observation trend overview</h2>
    <img src="data:image/png;base64,{trend_img}" />
    <h2>Effectiveness analysis</h2>
    {eff_table}
    <h2>Guidance by location</h2>
    {guidance_table}
    </body></html>
    """
    Path(output_path).write_text(html, encoding="utf-8")


def _plot_incident_observation_trends(monthly: pd.DataFrame) -> str:
    plot_df = monthly.groupby("month").agg(
        incidents=("incident_count", "sum"), observations=("observation_count", "sum")
    )
    fig, ax = plt.subplots(figsize=(8, 4))
    plot_df.plot(ax=ax, marker="o")
    ax.set_title("Total Incidents vs Observations by Month")
    ax.set_ylabel("Count")
    ax.grid(True, alpha=0.3)
    buf = BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format="png")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("utf-8")
