"""Loading, validation, cleaning and QA diagnostics for the three raw Inside Airbnb files."""
import ast
import json
from pathlib import Path

import numpy as np
import pandas as pd

# Single project-wide temporal reference. Never use the machine's current date.
SNAPSHOT_DATE = pd.Timestamp("2026-06-25")

RAW_FILENAMES = {
    "listings": "listings.csv.gz",
    "calendar": "calendar.csv.gz",
    "reviews": "reviews.csv",
}

REQUIRED_LISTING_COLUMNS = [
    "id", "host_id", "neighbourhood_cleansed", "property_type", "room_type", "accommodates",
    "bedrooms", "beds", "price", "amenities", "calculated_host_listings_count",
]
# The real 2026-06-25 calendar has no price field (Amendment A1): availability only.
REQUIRED_CALENDAR_COLUMNS = ["listing_id", "date", "available"]
REQUIRED_REVIEW_COLUMNS = ["listing_id", "date"]


class DataValidationError(ValueError):
    """A raw input violates a structural requirement of the pipeline."""


class DuplicateCalendarKeyError(DataValidationError):
    """Duplicate (listing_id, date) calendar rows. Reported, never silently resolved."""


# ------------------------------------------------------------------ loading
def require_raw_files(raw_dir) -> dict:
    """Return the three expected raw paths, or raise listing every missing file."""
    raw_dir = Path(raw_dir)
    paths = {key: raw_dir / name for key, name in RAW_FILENAMES.items()}
    missing = [p.name for p in paths.values() if not p.is_file()]
    if missing:
        raise FileNotFoundError(
            f"Missing raw input file(s) in {raw_dir}: {', '.join(missing)}. "
            "See the README for download instructions."
        )
    return paths


def _read(path, required) -> pd.DataFrame:
    """Read only the needed columns as strings so parsing rules stay explicit and auditable."""
    header = pd.read_csv(path, nrows=0).columns
    absent = [c for c in required if c not in header]
    if absent:
        raise DataValidationError(f"{Path(path).name} is missing required column(s): {', '.join(absent)}")
    return pd.read_csv(path, usecols=required, dtype=str, keep_default_na=False)


def load_listings(path) -> pd.DataFrame:
    return _read(path, REQUIRED_LISTING_COLUMNS)


def load_calendar(path) -> pd.DataFrame:
    return _read(path, REQUIRED_CALENDAR_COLUMNS)


def load_reviews(path) -> pd.DataFrame:
    return _read(path, REQUIRED_REVIEW_COLUMNS)


# ---------------------------------------------------------- field parsers
def normalize_ids(series: pd.Series) -> pd.Series:
    """Parse identifiers to nullable Int64. Non-integers become <NA>; semantics are unchanged."""
    num = pd.to_numeric(series.astype("string").str.strip(), errors="coerce")
    num = num.where(num.notna() & (num == np.floor(num)))
    return num.astype("Int64")


def parse_price(series: pd.Series) -> pd.Series:
    """Currency string -> positive float. Blank, unparseable and non-positive values -> NaN.

    Large positive values are valid: statistical outliers are never removed here.
    """
    text = series.astype("string").str.replace(r"[$,\s]", "", regex=True)
    num = pd.to_numeric(text, errors="coerce").astype("float64")
    return num.where(num > 0)


def _amenity_list(value):
    """Return (list | None, failed). None with failed=False means truly missing."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None, False
    text = str(value).strip()
    if text == "":
        return None, False
    for parse in (json.loads, ast.literal_eval):
        try:
            parsed = parse(text)
        except (ValueError, SyntaxError, MemoryError, RecursionError):
            continue
        if isinstance(parsed, list):
            return parsed, False
        break
    return None, True


def parse_amenity_count(series: pd.Series) -> pd.DataFrame:
    """Count list elements (never delimiters). Returns amenity_count (Int64) and amenity_parse_failed."""
    parsed = [_amenity_list(v) for v in series]
    counts = [len(lst) if lst is not None else pd.NA for lst, _ in parsed]
    return pd.DataFrame(
        {
            "amenity_count": pd.array(counts, dtype="Int64"),
            "amenity_parse_failed": [failed for _, failed in parsed],
        },
        index=series.index,
    )


def _blank(series: pd.Series) -> pd.Series:
    return series.isna() | (series.astype("string").str.strip() == "")


# ---------------------------------------------------------------- cleaning
def clean_listings(raw: pd.DataFrame):
    """Normalize keys/numerics; one row per listing. Returns (cleaned, diagnostics)."""
    df = raw.copy()
    df["id"] = normalize_ids(df["id"])
    missing_id = df["id"].isna()
    df = df.loc[~missing_id].copy()
    dup = df["id"].duplicated(keep=False)
    if dup.any():
        raise DataValidationError(
            f"listings has {df.loc[dup, 'id'].nunique()} duplicate id value(s) "
            f"({int(dup.sum())} rows); resolve before continuing"
        )
    df["host_id"] = normalize_ids(df["host_id"])
    for col in ("accommodates", "bedrooms", "beds", "calculated_host_listings_count"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ("neighbourhood_cleansed", "property_type", "room_type"):
        df[col] = df[col].where(~_blank(df[col]))      # blank category stays missing (observable)
    diag = {
        "raw_listing_rows": len(raw),
        "listing_rows_missing_id": int(missing_id.sum()),
        "cleaned_listing_rows": len(df),
    }
    return df.reset_index(drop=True), diag


def clean_calendar(raw: pd.DataFrame):
    """Parse calendar rows. Returns (cleaned, diagnostics); raises on duplicate (listing_id, date).

    Rows with an unparseable date are kept (date = NaT) so the listing still counts as having
    calendar rows, but they never fall inside any window.
    """
    df = pd.DataFrame({"listing_id": normalize_ids(raw["listing_id"])})
    df["date"] = pd.to_datetime(raw["date"], format="%Y-%m-%d", errors="coerce")
    status = raw["available"].astype("string").str.strip().str.lower()
    df["available"] = status.map({"t": True, "f": False}).astype("boolean")   # anything else -> <NA>

    dup = df.dropna(subset=["listing_id", "date"]).duplicated(["listing_id", "date"], keep=False)
    if dup.any():
        n_extra = int(df.dropna(subset=["listing_id", "date"]).duplicated(["listing_id", "date"]).sum())
        raise DuplicateCalendarKeyError(
            f"calendar has {n_extra} duplicate (listing_id, date) row(s) across "
            f"{int(df.dropna(subset=['listing_id', 'date'])[dup].listing_id.nunique())} listing(s); "
            "not deduplicating silently - report and choose a resolution"
        )
    diag = {
        "raw_calendar_rows": len(raw),
        "calendar_rows_missing_listing_id": int(df["listing_id"].isna().sum()),
        "calendar_rows_invalid_date": int(df["date"].isna().sum()),
        "calendar_invalid_availability_rows": int(df["available"].isna().sum()),
    }
    return df.dropna(subset=["listing_id"]).reset_index(drop=True), diag


def clean_reviews(raw: pd.DataFrame):
    """Parse review rows without deduplicating (several reviews may share a date)."""
    df = pd.DataFrame({"listing_id": normalize_ids(raw["listing_id"])})
    df["date"] = pd.to_datetime(raw["date"], format="%Y-%m-%d", errors="coerce")
    diag = {
        "raw_review_rows": len(raw),
        "review_rows_missing_listing_id": int(df["listing_id"].isna().sum()),
        "review_rows_invalid_date": int(df["date"].isna().sum()),
        "review_rows_after_snapshot": int((df["date"] > SNAPSHOT_DATE).sum()),
    }
    return df.dropna(subset=["listing_id"]).reset_index(drop=True), diag


# ------------------------------------------------------- join diagnostics
def compute_join_diagnostics(listing_ids: pd.Series, calendar_ids: pd.Series, review_ids: pd.Series) -> dict:
    """Cross-table ID diagnostics. Unmatched child IDs are reported, never joined in."""
    base = set(listing_ids.dropna())
    cal = set(calendar_ids.dropna())
    rev = set(review_ids.dropna())
    n = len(base)
    return {
        "unique_listing_ids": n,
        "unique_calendar_listing_ids": len(cal),
        "unique_review_listing_ids": len(rev),
        "calendar_ids_not_in_listings": len(cal - base),
        "review_ids_not_in_listings": len(rev - base),
        "prop_listings_with_calendar_rows": len(base & cal) / n if n else float("nan"),
        "prop_listings_with_any_review_row": len(base & rev) / n if n else float("nan"),
    }
