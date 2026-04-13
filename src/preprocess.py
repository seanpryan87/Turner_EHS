from __future__ import annotations

import re

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


def _normalize_text(series: pd.Series) -> pd.Series:
    return (
        series.fillna("")
        .astype(str)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )


def _entity_key(series: pd.Series) -> pd.Series:
    return (
        _normalize_text(series)
        .str.lower()
        .map(lambda value: re.sub(r"[^a-z0-9]+", "", value))
    )


def _canonical_label(series: pd.Series) -> pd.DataFrame:
    labels = _normalize_text(series)
    keys = _entity_key(labels)
    temp = pd.DataFrame({"entity_key": keys, "entity_label": labels})
    temp = temp[temp["entity_key"] != ""]
    if temp.empty:
        return pd.DataFrame(columns=["entity_key", "entity_label"])
    counts = temp.value_counts(["entity_key", "entity_label"]).reset_index(name="hits")
    canonical = counts.sort_values(["entity_key", "hits", "entity_label"], ascending=[True, False, True]).drop_duplicates(
        "entity_key"
    )
    return canonical[["entity_key", "entity_label"]]


def standardize_incidents(df: pd.DataFrame, mapping: dict[str, list[str]]) -> pd.DataFrame:
    out = _map_columns(df, mapping).copy()
    required = [
        "incident_id",
        "date",
        "location",
        "project",
        "business_unit",
        "business_center",
        "severity",
        "category",
        "subcontractor",
        "user",
    ]
    for col in required:
        if col not in out.columns:
            out[col] = pd.NA
    out["project"] = _normalize_text(out["project"].fillna(out["location"]))
    out["business_unit"] = _normalize_text(out["business_unit"])
    out["business_center"] = _normalize_text(out["business_center"])
    out["subcontractor"] = _normalize_text(out["subcontractor"])
    out["user"] = _normalize_text(out["user"])
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    if "serious_potential" in out.columns:
        out["serious_potential"] = _normalize_bool(out["serious_potential"])
    else:
        out["serious_potential"] = False
    out["month"] = out["date"].dt.to_period("M").dt.to_timestamp()
    return out


def standardize_observations(df: pd.DataFrame, mapping: dict[str, list[str]]) -> pd.DataFrame:
    out = _map_columns(df, mapping).copy()
    required = [
        "observation_id",
        "date",
        "location",
        "project",
        "business_unit",
        "business_center",
        "category",
        "observation_type",
        "subcontractor",
        "user",
    ]
    for col in required:
        if col not in out.columns:
            out[col] = pd.NA
    out["project"] = _normalize_text(out["project"].fillna(out["location"]))
    out["business_unit"] = _normalize_text(out["business_unit"])
    out["business_center"] = _normalize_text(out["business_center"])
    out["subcontractor"] = _normalize_text(out["subcontractor"])
    out["user"] = _normalize_text(out["user"])
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
    if "project" not in out.columns:
        out["project"] = out["location"]
    if "business_unit" not in out.columns:
        out["business_unit"] = pd.NA
    if "business_center" not in out.columns:
        out["business_center"] = pd.NA
    out["project"] = _normalize_text(out["project"])
    out["business_unit"] = _normalize_text(out["business_unit"])
    out["business_center"] = _normalize_text(out["business_center"])
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["month"] = out["date"].dt.to_period("M").dt.to_timestamp()
    out["exposure_hours"] = pd.to_numeric(out["exposure_hours"], errors="coerce")
    return out[["location", "project", "business_unit", "business_center", "month", "exposure_hours"]]


def resolve_dimensions(
    incidents: pd.DataFrame,
    observations: pd.DataFrame,
    exposure: pd.DataFrame | None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame | None]:
    records = []
    for source, frame in [("incidents", incidents), ("observations", observations)]:
        entity = frame[["project", "business_unit", "business_center"]].copy()
        entity["source"] = source
        records.append(entity)
    if exposure is not None:
        entity = exposure[["project", "business_unit", "business_center"]].copy()
        entity["source"] = "exposure"
        records.append(entity)

    hierarchy = pd.concat(records, ignore_index=True)
    hierarchy = hierarchy.fillna("")
    hierarchy = hierarchy[(hierarchy["project"] != "") | (hierarchy["business_unit"] != "") | (hierarchy["business_center"] != "")]

    project_lookup = _canonical_label(hierarchy["project"]).rename(columns={"entity_label": "project"})
    bu_lookup = _canonical_label(hierarchy["business_unit"]).rename(columns={"entity_label": "business_unit"})
    bc_lookup = _canonical_label(hierarchy["business_center"]).rename(columns={"entity_label": "business_center"})

    def _apply_lookup(frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.copy()
        out["project_key"] = _entity_key(out["project"])
        out["business_unit_key"] = _entity_key(out["business_unit"])
        out["business_center_key"] = _entity_key(out["business_center"])
        out = out.merge(project_lookup.rename(columns={"entity_key": "project_key"}), on="project_key", how="left", suffixes=("", "_canon"))
        out["project"] = out["project_canon"].fillna(out["project"])
        out = out.merge(bu_lookup.rename(columns={"entity_key": "business_unit_key"}), on="business_unit_key", how="left", suffixes=("", "_canon"))
        out["business_unit"] = out["business_unit_canon"].fillna(out["business_unit"])
        out = out.merge(bc_lookup.rename(columns={"entity_key": "business_center_key"}), on="business_center_key", how="left", suffixes=("", "_canon"))
        out["business_center"] = out["business_center_canon"].fillna(out["business_center"])
        drop_cols = [c for c in out.columns if c.endswith("_canon") or c.endswith("_key")]
        return out.drop(columns=drop_cols)

    incidents_clean = _apply_lookup(incidents)
    observations_clean = _apply_lookup(observations)
    exposure_clean = _apply_lookup(exposure) if exposure is not None else None

    hierarchy_map = (
        pd.concat(
            [
                incidents_clean[["project", "business_unit", "business_center"]],
                observations_clean[["project", "business_unit", "business_center"]],
                exposure_clean[["project", "business_unit", "business_center"]] if exposure_clean is not None else pd.DataFrame(),
            ],
            ignore_index=True,
        )
        .replace("", pd.NA)
        .dropna(how="all")
        .drop_duplicates()
        .sort_values(["business_center", "business_unit", "project"], na_position="last")
    )

    return hierarchy_map, incidents_clean, observations_clean, exposure_clean
