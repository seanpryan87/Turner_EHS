from __future__ import annotations

import numpy as np
import pandas as pd


SEVERITY_WEIGHTS = {
    "near miss": 1,
    "first aid": 2,
    "property damage": 2,
    "recordable": 4,
}

DEFAULT_LEADING_WEIGHTS = {
    "observation_volume": 0.25,
    "corrective_action_rate": 0.25,
    "comment_quality": 0.20,
    "closure_speed": 0.20,
    "high_risk_coverage": 0.10,
}


def monthly_location_metrics(
    incidents: pd.DataFrame,
    observations: pd.DataFrame,
    exposure: pd.DataFrame | None,
) -> pd.DataFrame:
    inc = incidents.groupby(["location", "month"], dropna=False).agg(
        incident_count=("incident_id", "count"),
        severity_index=("severity", lambda s: s.astype(str).str.lower().map(SEVERITY_WEIGHTS).fillna(2).sum()),
        serious_incidents=("serious_potential", "sum"),
    )

    obs = observations.groupby(["location", "month"], dropna=False).agg(
        observation_count=("observation_id", "count"),
        corrective_action_rate=("corrective_action_created", "mean"),
        avg_comment_len=("comment_len", "mean"),
        avg_closure_days=("closure_days", "mean"),
        high_risk_coverage=("serious_potential", "mean"),
    )

    merged = inc.join(obs, how="outer").reset_index().fillna(0)
    if exposure is not None:
        merged = merged.merge(exposure, on=["location", "month"], how="left")
        merged["incident_rate_per_200k_hours"] = np.where(
            merged["exposure_hours"] > 0,
            (merged["incident_count"] / merged["exposure_hours"]) * 200000,
            np.nan,
        )
    return merged


def location_effectiveness(
    monthly: pd.DataFrame,
    lag_months: list[int],
    leading_weights: dict[str, float] | None = None,
) -> pd.DataFrame:
    weights = _normalized_weights(leading_weights or DEFAULT_LEADING_WEIGHTS)
    rows = []
    for location, group in monthly.groupby("location"):
        group = group.sort_values("month").copy()
        base_corr = group["observation_count"].corr(group["incident_count"]) if len(group) > 1 else np.nan
        lag_corrs = {}
        for lag in lag_months:
            shifted = group["incident_count"].shift(-lag)
            lag_corrs[f"lag_{lag}"] = group["observation_count"].corr(shifted) if len(group) > 1 else np.nan

        component_scores = {
            "observation_volume": _norm(group["observation_count"].mean(), monthly["observation_count"]),
            "corrective_action_rate": group["corrective_action_rate"].mean(),
            "comment_quality": _norm(group["avg_comment_len"].mean(), monthly["avg_comment_len"]),
            "closure_speed": 1
            - _norm(
                group["avg_closure_days"].replace(0, np.nan).mean(),
                monthly["avg_closure_days"].replace(0, np.nan),
            ),
            "high_risk_coverage": group["high_risk_coverage"].mean(),
        }

        leading_score = sum(component_scores[k] * weights[k] for k in weights) * 100

        rows.append(
            {
                "location": location,
                "obs_incident_corr": base_corr,
                **lag_corrs,
                "leading_indicator_score": leading_score,
                "mean_incidents": group["incident_count"].mean(),
                "mean_observations": group["observation_count"].mean(),
                "incident_trend": _slope(group["incident_count"]),
            }
        )
    return pd.DataFrame(rows)


def mismatch_flags(
    effectiveness: pd.DataFrame,
    high_incident_threshold_quantile: float = 0.7,
    low_observation_threshold_quantile: float = 0.3,
) -> pd.DataFrame:
    high_obs = effectiveness["mean_observations"] >= effectiveness["mean_observations"].quantile(1 - low_observation_threshold_quantile)
    low_obs = effectiveness["mean_observations"] <= effectiveness["mean_observations"].quantile(low_observation_threshold_quantile)
    high_inc = effectiveness["mean_incidents"] >= effectiveness["mean_incidents"].quantile(high_incident_threshold_quantile)
    flat_or_worse = effectiveness["incident_trend"] >= 0

    effectiveness = effectiveness.copy()
    effectiveness["quality_issue_flag"] = high_obs & flat_or_worse
    effectiveness["coverage_issue_flag"] = low_obs & high_inc
    return effectiveness


def top_categories(incidents: pd.DataFrame, observations: pd.DataFrame) -> pd.DataFrame:
    inc_top = incidents.groupby(["location", "category"]).size().reset_index(name="incident_hits")
    obs_top = observations.groupby(["location", "category"]).size().reset_index(name="observation_hits")
    return inc_top.merge(obs_top, on=["location", "category"], how="outer").fillna(0)


def build_guidance(effectiveness: pd.DataFrame, categories: pd.DataFrame) -> pd.DataFrame:
    guidance_rows = []
    for _, row in effectiveness.iterrows():
        location = row["location"]
        local_cats = categories[categories["location"] == location].sort_values("incident_hits", ascending=False)
        top_cat = local_cats.iloc[0]["category"] if not local_cats.empty else "general risk"

        recs = []
        if row.get("coverage_issue_flag"):
            recs.append(
                f"Increase observation coverage in {top_cat} work by scheduling weekly focused audits; KPI: +20% monthly observations."
            )
        if row.get("quality_issue_flag"):
            recs.append(
                f"Improve observation quality and coaching effectiveness in {top_cat}; KPI: reduce incident trend slope next month."
            )
        if (row.get("lag_1") or 0) > 0:
            recs.append(
                "Observation activity is not yet translating into lower next-month incidents; tighten closure accountability for high-risk findings."
            )
        if not recs:
            recs.append("Maintain current controls and focus on sustaining closure speed and supervisor participation.")

        guidance_rows.append(
            {
                "location": location,
                "recommendations": "\n".join(recs[:5]),
                "rationale": f"Mean incidents={row['mean_incidents']:.2f}, mean observations={row['mean_observations']:.2f}, top category={top_cat}.",
                "next_month_kpi": "Leading indicator score and incident count",
            }
        )
    return pd.DataFrame(guidance_rows)


def _normalized_weights(weights: dict[str, float]) -> dict[str, float]:
    merged = {**DEFAULT_LEADING_WEIGHTS, **weights}
    total = sum(max(0.0, v) for v in merged.values())
    if total <= 0:
        return DEFAULT_LEADING_WEIGHTS
    return {k: max(0.0, v) / total for k, v in merged.items()}


def _norm(value: float, series: pd.Series) -> float:
    mn, mx = np.nanmin(series), np.nanmax(series)
    if np.isnan(value) or np.isnan(mn) or np.isnan(mx) or mx == mn:
        return 0.5
    return float((value - mn) / (mx - mn))


def _slope(series: pd.Series) -> float:
    y = series.fillna(0).to_numpy(dtype=float)
    x = np.arange(len(y))
    if len(y) < 2:
        return 0.0
    return float(np.polyfit(x, y, 1)[0])
