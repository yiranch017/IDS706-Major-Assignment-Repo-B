"""Listing, calendar and review feature engineering plus the safe final join."""
import numpy as np
import pandas as pd

from src.data import SNAPSHOT_DATE, DataValidationError, parse_amenity_count, parse_price

FUTURE_WINDOWS = (30, 90)
REVIEW_WINDOWS = (30, 90, 180)
MIN_COVERAGE_PCT = 80            # LOCKED: coverage_rate >= 0.80 (integer math avoids float edge cases)

LISTING_COLUMNS = [
    "id", "host_id", "neighbourhood_cleansed", "property_type", "room_type", "accommodates",
    "bedrooms", "beds", "listing_price", "listing_price_valid", "amenity_count",
    "amenity_parse_failed", "calculated_host_listings_count", "host_type",
]


# ---------------------------------------------------------------- windows
def in_future_window(dates: pd.Series, n: int, snapshot=SNAPSHOT_DATE) -> pd.Series:
    """snapshot <= date < snapshot + n days (start included, upper boundary excluded)."""
    return (dates >= snapshot) & (dates < snapshot + pd.Timedelta(days=n))


def in_review_window(dates: pd.Series, n: int, snapshot=SNAPSHOT_DATE) -> pd.Series:
    """snapshot - n days < date <= snapshot (lower boundary excluded, snapshot included)."""
    return (dates > snapshot - pd.Timedelta(days=n)) & (dates <= snapshot)


def meets_coverage_threshold(observed: pd.Series, expected: int) -> pd.Series:
    """observed / expected >= 0.80, computed exactly in integers (24/30 and 72/90 qualify)."""
    return observed * 100 >= expected * MIN_COVERAGE_PCT


# --------------------------------------------------------- listing features
def build_listing_features(cleaned: pd.DataFrame) -> pd.DataFrame:
    """Add listing_price(+valid flag), amenity_count(+parse flag) and host_type. Keeps every row."""
    df = cleaned.copy()
    df["listing_price"] = parse_price(df["price"])
    df["listing_price_valid"] = df["listing_price"].notna()
    df = df.join(parse_amenity_count(df["amenities"]))
    hc = df["calculated_host_listings_count"]
    df["host_type"] = np.select([hc == 1, hc > 1], ["single", "multi"], default=None)
    df["host_type"] = df["host_type"].astype(object).where(df["host_type"].notna(), np.nan)
    return df[LISTING_COLUMNS]


# -------------------------------------------------------- calendar features
def _window_stats(cal: pd.DataFrame, n: int, snapshot) -> pd.DataFrame:
    """Per-listing coverage and forward availability for one future window (coverage gate applied)."""
    w = cal[in_future_window(cal["date"], n, snapshot)]
    ids = pd.Index(cal["listing_id"].unique(), name="listing_id")
    out = pd.DataFrame(index=ids)

    out[f"calendar_expected_days_{n}"] = n
    # Coverage counts unique valid dates, regardless of the availability status of the row.
    observed = w.groupby("listing_id")["date"].nunique().reindex(ids, fill_value=0)
    out[f"calendar_observed_days_{n}"] = observed
    out[f"calendar_coverage_rate_{n}"] = observed / n
    qualifies = meets_coverage_threshold(observed, n)

    # Availability uses only rows with a valid status in numerator AND denominator.
    status = w[w["available"].notna()]
    avail = status.groupby("listing_id")["available"].agg(lambda s: s.astype(bool).sum()).reindex(ids)
    n_status = status.groupby("listing_id").size().reindex(ids)
    out[f"availability_rate_{n}d"] = (avail / n_status).astype("float64").where(qualifies)
    return out


def aggregate_calendar(cal: pd.DataFrame, snapshot=SNAPSHOT_DATE) -> pd.DataFrame:
    """Many calendar rows per listing -> exactly one row per listing_id."""
    out = pd.concat([_window_stats(cal, n, snapshot) for n in FUTURE_WINDOWS], axis=1)
    out["calendar_has_data"] = True            # listing appears in the calendar at all
    out = out.reset_index()
    out["listing_id"] = out["listing_id"].astype("Int64")
    return out


# ---------------------------------------------------------- review features
def aggregate_reviews(rev: pd.DataFrame, snapshot=SNAPSHOT_DATE) -> pd.DataFrame:
    """Many review rows per listing -> exactly one row per listing_id (rows counted, not dates)."""
    ids = pd.Index(rev["listing_id"].unique(), name="listing_id")
    out = pd.DataFrame(index=ids)
    out["has_any_review_row"] = True
    for n in REVIEW_WINDOWS:
        in_win = rev[in_review_window(rev["date"], n, snapshot)]
        out[f"reviews_last_{n}d"] = in_win.groupby("listing_id").size().reindex(ids, fill_value=0)
    hist = rev[rev["date"] <= snapshot]
    last = hist.groupby("listing_id")["date"].max().reindex(ids)
    out["last_review_date"] = last
    out["days_since_last_review"] = (snapshot - last).dt.days.astype("Int64")
    out["has_review_on_or_before_snapshot"] = last.notna()
    out = out.reset_index()
    out["listing_id"] = out["listing_id"].astype("Int64")
    return out


# --------------------------------------------------------------- final join
def _assert_unique(df: pd.DataFrame, name: str) -> None:
    if not df["listing_id"].is_unique:
        raise DataValidationError(f"{name} aggregate is not unique on listing_id; refusing to join")


def join_features(listings: pd.DataFrame, calendar_feats: pd.DataFrame, review_feats: pd.DataFrame) -> pd.DataFrame:
    """LEFT JOIN the two aggregates onto listings; assert one row per listing afterwards."""
    _assert_unique(calendar_feats, "calendar")
    _assert_unique(review_feats, "review")
    n_before = len(listings)
    out = (
        listings.merge(calendar_feats, left_on="id", right_on="listing_id", how="left", validate="one_to_one")
        .drop(columns="listing_id")
        .merge(review_feats, left_on="id", right_on="listing_id", how="left", validate="one_to_one")
        .drop(columns="listing_id")
    )

    # Listings absent from the child tables: observed zeros are real zeros; derived metrics stay NA.
    out["calendar_has_data"] = out["calendar_has_data"].fillna(False).astype(bool)
    for n in FUTURE_WINDOWS:
        out[f"calendar_expected_days_{n}"] = n
        out[f"calendar_observed_days_{n}"] = out[f"calendar_observed_days_{n}"].fillna(0).astype("Int64")
        out[f"calendar_coverage_rate_{n}"] = out[f"calendar_coverage_rate_{n}"].fillna(0.0)

    for col in ("has_any_review_row", "has_review_on_or_before_snapshot"):
        out[col] = out[col].fillna(False).astype(bool)
    for n in REVIEW_WINDOWS:
        out[f"reviews_last_{n}d"] = out[f"reviews_last_{n}d"].fillna(0).astype("Int64")

    if len(out) != n_before or not out["id"].is_unique:
        raise DataValidationError("final join changed the listing row count or broke id uniqueness")
    return out
