from __future__ import annotations

import pandas as pd


def _map_columns(df: pd.DataFrame, mapping: dict[str, list[str]]) -> pd.DataFrame:
    rename_map: dict[str, str] = {}
    lower_to_real = {c.lower().strip(): c for c in df.columns}
    for canonical, candidates in mapping.items():
        for candidate in candidates:
            key = candidate.lower().strip()
            if key in lower_to_real:
                rename_map[lower_to_real[key]] = canonical
                break
    return df.rename(columns=rename_map)


def _normalize_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"1", "true", "yes", "y"})


def standardize_incidents(df: pd.DataFrame, mapping: dict[str, list[str]]) -> pd.DataFrame:
    out = _map_columns(df, mapping).copy()
    required = ["incident_id", "date", "location", "severity", "category"]
    for col in required:
        if col not in out.columns:
            out[col] = pd.NA
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    if "serious_potential" in out.columns:
        out["serious_potential"] = _normalize_bool(out["serious_potential"])
    out["month"] = out["date"].dt.to_period("M").dt.to_timestamp()
    return out


def standardize_observations(df: pd.DataFrame, mapping: dict[str, list[str]]) -> pd.DataFrame:
    out = _map_columns(df, mapping).copy()
    required = ["observation_id", "date", "location", "category", "observation_type"]
    for col in required:
        if col not in out.columns:
            out[col] = pd.NA
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["month"] = out["date"].dt.to_period("M").dt.to_timestamp()

    for numeric_col in ["at_risk_count", "safe_count"]:
        if numeric_col in out.columns:
            out[numeric_col] = pd.to_numeric(out[numeric_col], errors="coerce").fillna(0)
        else:
            out[numeric_col] = 0

    for bool_col in ["corrective_action_created", "supervisor_participation", "serious_potential"]:
        if bool_col in out.columns:
            out[bool_col] = _normalize_bool(out[bool_col])
        else:
            out[bool_col] = False

    if "closure_date" in out.columns:
        out["closure_date"] = pd.to_datetime(out["closure_date"], errors="coerce")
        out["closure_days"] = (out["closure_date"] - out["date"]).dt.days
    else:
        out["closure_days"] = pd.NA

    comments = out.get("comments", pd.Series("", index=out.index)).fillna("").astype(str)
    out["comment_len"] = comments.str.len()
    return out


def standardize_exposure(df: pd.DataFrame | None, mapping: dict[str, list[str]]) -> pd.DataFrame | None:
    if df is None:
        return None
    out = _map_columns(df, mapping).copy()
    if "location" not in out.columns or "date" not in out.columns or "exposure_hours" not in out.columns:
        return None
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["month"] = out["date"].dt.to_period("M").dt.to_timestamp()
    out["exposure_hours"] = pd.to_numeric(out["exposure_hours"], errors="coerce")
    return out[["location", "month", "exposure_hours"]]
