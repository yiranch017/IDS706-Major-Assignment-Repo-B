"""Listing, calendar and review feature engineering plus the safe final join."""
import numpy as np
import pandas as pd

from src.data import SNAPSHOT_DATE, DataValidationError, parse_amenity_count, parse_price

FUTURE_WINDOWS = (30, 90)
REVIEW_WINDOWS = (30, 90, 180)
MIN_COVERAGE_PCT = 80            # LOCKED: coverage_rate >= 0.80 (integer math avoids float edge cases)
WEEKEND_DAYS = (4, 5)            # LOCKED: Friday, Saturday (Monday = 0)
MIN_WEEKEND_PRICES = 8           # LOCKED
MIN_WEEKDAY_PRICES = 20          # LOCKED

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
    """Per-listing statistics for one future window, with the coverage gate applied."""
    w = cal[in_future_window(cal["date"], n, snapshot)]
    ids = pd.Index(cal["listing_id"].unique(), name="listing_id")
    out = pd.DataFrame(index=ids)

    out[f"calendar_expected_days_{n}"] = n
    # Coverage counts unique valid dates, regardless of availability status or price validity.
    observed = w.groupby("listing_id")["date"].nunique().reindex(ids, fill_value=0)
    out[f"calendar_observed_days_{n}"] = observed
    out[f"calendar_coverage_rate_{n}"] = observed / n
    qualifies = meets_coverage_threshold(observed, n)

    priced = w[w["price"].notna()]
    out[f"calendar_valid_price_days_{n}"] = priced.groupby("listing_id").size().reindex(ids, fill_value=0)

    # Availability uses only rows with a valid status in numerator AND denominator.
    status = w[w["available"].notna()]
    avail = status.groupby("listing_id")["available"].agg(
        lambda s: s.astype(bool).sum()
    ).reindex(ids)
    n_status = status.groupby("listing_id").size().reindex(ids)
    rate = (avail / n_status).astype("float64")
    out[f"availability_rate_{n}d"] = rate.where(qualifies)

    prices = priced.groupby("listing_id")["price"]
    q1, q3 = prices.quantile(0.25).reindex(ids), prices.quantile(0.75).reindex(ids)
    out[f"calendar_median_price_{n}d"] = prices.median().reindex(ids).where(qualifies)
    out[f"calendar_price_iqr_{n}d"] = (q3 - q1).where(qualifies)
    return out


def _weekend_features(cal: pd.DataFrame, snapshot, ids, qualifies_90: pd.Series) -> pd.DataFrame:
    """Friday/Saturday vs Sunday-Thursday median price within the 90-day window."""
    w = cal[in_future_window(cal["date"], 90, snapshot) & cal["price"].notna()]
    is_weekend = w["date"].dt.dayofweek.isin(WEEKEND_DAYS)
    out = pd.DataFrame(index=ids)
    wk, wd = w[is_weekend].groupby("listing_id")["price"], w[~is_weekend].groupby("listing_id")["price"]
    out["weekend_valid_price_count_90d"] = wk.size().reindex(ids, fill_value=0)
    out["weekday_valid_price_count_90d"] = wd.size().reindex(ids, fill_value=0)
    out["weekend_median_price_90d"] = wk.median().reindex(ids)
    out["weekday_median_price_90d"] = wd.median().reindex(ids)
    ok = (
        qualifies_90
        & (out["weekend_valid_price_count_90d"] >= MIN_WEEKEND_PRICES)
        & (out["weekday_valid_price_count_90d"] >= MIN_WEEKDAY_PRICES)
    )
    out["weekend_premium_abs_90d"] = (
        out["weekend_median_price_90d"] - out["weekday_median_price_90d"]
    ).where(ok)
    out["weekend_premium_pct_90d"] = (
        (out["weekend_median_price_90d"] - out["weekday_median_price_90d"]) / out["weekday_median_price_90d"]
    ).where(ok)
    # Medians themselves are only reported when the premium is calculable.
    out["weekend_median_price_90d"] = out["weekend_median_price_90d"].where(ok)
    out["weekday_median_price_90d"] = out["weekday_median_price_90d"].where(ok)
    return out


def aggregate_calendar(cal: pd.DataFrame, snapshot=SNAPSHOT_DATE) -> pd.DataFrame:
    """Many calendar rows per listing -> exactly one row per listing_id."""
    parts = [_window_stats(cal, n, snapshot) for n in FUTURE_WINDOWS]
    out = pd.concat(parts, axis=1)
    ids = out.index
    qualifies_90 = meets_coverage_threshold(out["calendar_observed_days_90"], 90)
    out = pd.concat([out, _weekend_features(cal, snapshot, ids, qualifies_90)], axis=1)
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
        for col in (f"calendar_observed_days_{n}", f"calendar_valid_price_days_{n}"):
            out[col] = out[col].fillna(0).astype("Int64")
        out[f"calendar_coverage_rate_{n}"] = out[f"calendar_coverage_rate_{n}"].fillna(0.0)
    for col in ("weekend_valid_price_count_90d", "weekday_valid_price_count_90d"):
        out[col] = out[col].fillna(0).astype("Int64")

    for col in ("has_any_review_row", "has_review_on_or_before_snapshot"):
        out[col] = out[col].fillna(False).astype(bool)
    for n in REVIEW_WINDOWS:
        out[f"reviews_last_{n}d"] = out[f"reviews_last_{n}d"].fillna(0).astype("Int64")

    if len(out) != n_before or not out["id"].is_unique:
        raise DataValidationError("final join changed the listing row count or broke id uniqueness")
    return out
