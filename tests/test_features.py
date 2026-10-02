"""Listing, calendar and review features, windows, thresholds and the final join (src/features.py)."""
from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from src.data import (
    SNAPSHOT_DATE,
    DataValidationError,
    clean_calendar,
    clean_listings,
    clean_reviews,
    load_calendar,
    load_listings,
    load_reviews,
)
from src.features import (
    aggregate_calendar,
    aggregate_reviews,
    build_listing_features,
    in_future_window,
    in_review_window,
    join_features,
    meets_coverage_threshold,
)

S = SNAPSHOT_DATE


def day(offset):
    return S + timedelta(days=offset)


# =================================================================== windows
@pytest.mark.parametrize("n", [30, 90])
def test_future_window_boundaries(n):
    dates = pd.Series([day(-1), day(0), day(n - 1), day(n), day(n + 1)])
    # start included, last inside date included, upper boundary (S + N) excluded
    assert in_future_window(dates, n).tolist() == [False, True, True, False, False]


@pytest.mark.parametrize("n", [30, 90, 180])
def test_review_window_boundaries(n):
    dates = pd.Series([day(-n - 1), day(-n), day(-n + 1), day(0), day(1)])
    # S - N excluded, S - N + 1 included, S included, after S excluded
    assert in_review_window(dates, n).tolist() == [False, False, True, True, False]


def test_windows_ignore_missing_dates():
    dates = pd.Series([pd.NaT, day(0)])
    assert in_future_window(dates, 30).tolist() == [False, True]
    assert in_review_window(dates, 30).tolist() == [False, True]


def test_windows_use_the_fixed_snapshot_not_today():
    other = pd.Timestamp("2030-01-01")
    assert not in_future_window(pd.Series([day(0)]), 30, snapshot=other).iloc[0]
    assert in_future_window(pd.Series([other]), 30, snapshot=other).iloc[0]


@pytest.mark.parametrize(
    "observed, expected, ok",
    [(24, 30, True), (23, 30, False), (72, 90, True), (71, 90, False), (30, 30, True), (0, 30, False)],
)
def test_coverage_threshold_exactly_80_percent(observed, expected, ok):
    assert bool(meets_coverage_threshold(pd.Series([observed]), expected).iloc[0]) is ok


# ========================================================= listing features
@pytest.fixture(scope="module")
def listing_feats(raw_dir):
    cleaned, _ = clean_listings(load_listings(raw_dir / "listings.csv.gz"))
    return build_listing_features(cleaned).set_index("id")


def test_listing_price_validity(listing_feats):
    f = listing_feats
    assert f.loc[1, "listing_price"] == 100.0 and f.loc[1, "listing_price_valid"]
    assert f.loc[2, "listing_price"] == 25000.0 and f.loc[2, "listing_price_valid"]  # extreme kept
    for bad in (4, 5, 6, 7):                         # $0, blank, negative, text
        assert pd.isna(f.loc[bad, "listing_price"]) and not f.loc[bad, "listing_price_valid"]
    assert len(f) == 22                              # invalid prices never drop a listing


def test_amenity_count_and_parse_failure_flags(listing_feats):
    f = listing_feats
    expected = {1: 2, 2: 0, 3: 1, 4: 3, 8: 2, 9: 2}
    for lid, n in expected.items():
        assert f.loc[lid, "amenity_count"] == n and not f.loc[lid, "amenity_parse_failed"]
    assert pd.isna(f.loc[5, "amenity_count"]) and not f.loc[5, "amenity_parse_failed"]   # true missing
    for bad in (6, 7):
        assert pd.isna(f.loc[bad, "amenity_count"]) and f.loc[bad, "amenity_parse_failed"]
    assert (f["amenity_count"].dropna() >= 0).all()
    assert f["amenity_parse_failed"].sum() == 2


def test_host_type(listing_feats):
    f = listing_feats
    assert f.loc[1, "host_type"] == "single" and f.loc[3, "host_type"] == "single"
    assert f.loc[2, "host_type"] == "multi" and f.loc[7, "host_type"] == "multi"
    for lid in (4, 5, 6):                            # 0, blank, "abc": not forced into a category
        assert pd.isna(f.loc[lid, "host_type"])
    assert set(f["host_type"].dropna()) == {"single", "multi"}


def test_listing_features_keep_required_columns(listing_feats):
    required = {"host_id", "neighbourhood_cleansed", "property_type", "room_type", "accommodates",
                "bedrooms", "beds", "listing_price", "listing_price_valid", "amenity_count",
                "calculated_host_listings_count", "host_type"}
    assert required <= set(listing_feats.columns)


# ===================================================== calendar aggregation
def cal_frame(listing_id, offsets, price=100.0, available=True):
    offsets = list(offsets)
    return pd.DataFrame({
        "listing_id": pd.array([listing_id] * len(offsets), dtype="Int64"),
        "date": [day(o) for o in offsets],
        "available": pd.array([available] * len(offsets), dtype="boolean"),
        "price": [price] * len(offsets),
    })


@pytest.fixture(scope="module")
def cal_feats(raw_dir):
    cal, _ = clean_calendar(load_calendar(raw_dir / "calendar.csv.gz"))
    return aggregate_calendar(cal).set_index("listing_id")


def test_calendar_aggregation_is_unique_per_listing(cal_feats):
    assert cal_feats.index.is_unique
    assert set(cal_feats.index) == {1, 2, 3, 4, 5, 6, 9999}


def test_calendar_listing_with_full_coverage_and_known_values(cal_feats):
    r = cal_feats.loc[1]                      # rows at -1 and +90 must be excluded from both windows
    assert (r.calendar_expected_days_30, r.calendar_observed_days_30) == (30, 30)
    assert (r.calendar_expected_days_90, r.calendar_observed_days_90) == (90, 90)
    assert r.calendar_coverage_rate_30 == 1.0 and r.calendar_coverage_rate_90 == 1.0
    assert r.availability_rate_30d == pytest.approx(0.5)
    assert r.availability_rate_90d == pytest.approx(75 / 90)
    assert r.calendar_median_price_30d == 100 and r.calendar_median_price_90d == 100
    assert r.calendar_price_iqr_30d == 50 and r.calendar_price_iqr_90d == 50   # $5,000 quote kept, IQR robust
    assert (r.weekend_valid_price_count_90d, r.weekday_valid_price_count_90d) == (26, 64)
    assert r.weekend_median_price_90d == 150 and r.weekday_median_price_90d == 100
    assert r.weekend_premium_abs_90d == pytest.approx(50)
    assert r.weekend_premium_pct_90d == pytest.approx(0.5)
    assert bool(r.calendar_has_data)


def test_calendar_exactly_80_percent_qualifies_in_both_windows(cal_feats):
    r = cal_feats.loc[2]
    assert (r.calendar_observed_days_30, r.calendar_observed_days_90) == (24, 72)
    assert r.calendar_coverage_rate_30 == pytest.approx(0.8)
    assert r.availability_rate_30d == 1.0 and r.availability_rate_90d == 1.0
    assert r.calendar_median_price_30d == 200 and r.calendar_price_iqr_90d == 0


def test_calendar_one_date_below_80_percent_is_na_not_zero(cal_feats):
    r = cal_feats.loc[3]
    assert (r.calendar_observed_days_30, r.calendar_observed_days_90) == (23, 71)
    for col in ("availability_rate_30d", "availability_rate_90d", "calendar_median_price_30d",
                "calendar_median_price_90d", "calendar_price_iqr_30d", "calendar_price_iqr_90d",
                "weekend_premium_abs_90d", "weekend_premium_pct_90d"):
        assert pd.isna(r[col]), col
    assert bool(r.calendar_has_data)          # has calendar rows, just not enough of them


def test_calendar_prices_count_regardless_of_availability_and_invalid_prices_are_not_observations(cal_feats):
    r = cal_feats.loc[4]                       # every date unavailable; only 28 of 90 prices valid
    assert r.calendar_observed_days_90 == 90   # coverage counts dates, not valid prices
    assert r.calendar_valid_price_days_90 == 28 and r.calendar_valid_price_days_30 == 28
    assert r.availability_rate_90d == 0.0      # a genuine zero, not NA
    assert r.calendar_median_price_90d == 100
    assert (r.weekend_valid_price_count_90d, r.weekday_valid_price_count_90d) == (8, 20)
    assert r.weekend_premium_abs_90d == pytest.approx(20) and r.weekend_premium_pct_90d == pytest.approx(0.2)


@pytest.mark.parametrize("listing, wk, wd", [(5, 7, 20), (6, 8, 19)])
def test_weekend_premium_na_when_group_below_minimum_but_other_metrics_remain(cal_feats, listing, wk, wd):
    r = cal_feats.loc[listing]
    assert (r.weekend_valid_price_count_90d, r.weekday_valid_price_count_90d) == (wk, wd)
    assert pd.isna(r.weekend_premium_abs_90d) and pd.isna(r.weekend_premium_pct_90d)
    assert pd.notna(r.calendar_median_price_90d)


def test_calendar_date_coverage_is_separate_from_availability_denominator(cal_feats):
    r = cal_feats.loc[6]                      # two rows: valid date, invalid available status ('x')
    assert r.calendar_observed_days_30 == 30 and r.calendar_observed_days_90 == 90   # still observed dates
    assert r.calendar_coverage_rate_30 == 1.0
    assert r.availability_rate_30d == pytest.approx(1.0)      # 28 / 28, not 28 / 30
    assert r.availability_rate_90d == pytest.approx(1.0)      # 88 / 88, not 88 / 90


def test_availability_denominator_unit():
    # 30 observed dates: 10 available, 10 unavailable, 10 with invalid status
    df = cal_frame(1, range(30), available=True)
    df["available"] = pd.array([True] * 10 + [False] * 10 + [pd.NA] * 10, dtype="boolean")
    r = aggregate_calendar(df).set_index("listing_id").loc[1]
    assert r.calendar_observed_days_30 == 30 and r.calendar_coverage_rate_30 == 1.0
    assert r.availability_rate_30d == pytest.approx(10 / 20)      # not 10/30, not 10/(10+20)


def test_all_invalid_availability_gives_na_rate_but_keeps_coverage():
    df = cal_frame(1, range(30))
    df["available"] = pd.array([pd.NA] * 30, dtype="boolean")
    r = aggregate_calendar(df).set_index("listing_id").loc[1]
    assert r.calendar_observed_days_30 == 30 and pd.isna(r.availability_rate_30d)


@pytest.mark.parametrize("n, offsets_ok", [(30, 24), (90, 72)])
def test_calendar_coverage_boundaries_via_unit_frames(n, offsets_ok):
    ok = aggregate_calendar(cal_frame(1, range(offsets_ok))).set_index("listing_id").loc[1]
    short = aggregate_calendar(cal_frame(1, range(offsets_ok - 1))).set_index("listing_id").loc[1]
    col = f"calendar_median_price_{n}d"
    if n == 30:
        assert ok[col] == 100 and pd.isna(short[col])
    else:
        # 72 dates inside 90 and 71 dates inside 90
        assert ok[col] == 100 and pd.isna(short[col])


def test_calendar_dates_outside_windows_do_not_count():
    r = aggregate_calendar(cal_frame(1, [-5, -1, 90, 120])).set_index("listing_id").loc[1]
    assert r.calendar_observed_days_30 == 0 and r.calendar_observed_days_90 == 0
    assert bool(r.calendar_has_data) and pd.isna(r.availability_rate_90d)


def test_calendar_valid_price_required_even_with_coverage():
    df = cal_frame(1, range(90), price=np.nan)
    r = aggregate_calendar(df).set_index("listing_id").loc[1]
    assert r.calendar_observed_days_90 == 90 and r.calendar_valid_price_days_90 == 0
    assert pd.isna(r.calendar_median_price_90d) and pd.isna(r.calendar_price_iqr_90d)
    assert r.availability_rate_90d == 1.0


def weekend_frame(n_weekend, n_weekday, n_dates=90):
    """Valid prices on exactly n_weekend Fri/Sat and n_weekday Sun-Thu dates among n_dates dates."""
    offsets = list(range(n_dates))
    wk = [o for o in offsets if day(o).dayofweek in (4, 5)][:n_weekend]
    wd = [o for o in offsets if day(o).dayofweek not in (4, 5)][:n_weekday]
    df = cal_frame(1, offsets, price=np.nan)
    price = {**{o: 130.0 for o in wk}, **{o: 100.0 for o in wd}}
    df["price"] = [price.get(o, np.nan) for o in offsets]
    return df


@pytest.mark.parametrize(
    "n_wknd, n_wkdy, n_dates, calculated",
    [
        (8, 20, 90, True),      # exactly the minimums, full coverage
        (7, 20, 90, False),     # one weekend price short
        (8, 19, 90, False),     # one weekday price short
        (20, 40, 90, True),
        (8, 20, 71, False),     # 71/90 coverage fails the gate regardless of group counts
        (8, 20, 72, True),      # 72/90 passes
    ],
)
def test_weekend_premium_thresholds(n_wknd, n_wkdy, n_dates, calculated):
    r = aggregate_calendar(weekend_frame(n_wknd, n_wkdy, n_dates)).set_index("listing_id").loc[1]
    if calculated:
        assert r.weekend_premium_abs_90d == pytest.approx(30.0)
        assert r.weekend_premium_pct_90d == pytest.approx(0.3)      # (130 - 100) / 100
    else:
        assert pd.isna(r.weekend_premium_abs_90d) and pd.isna(r.weekend_premium_pct_90d)


def test_weekend_is_friday_and_saturday_only():
    # S = Thursday 2026-06-25. Only Thursday/Sunday prices differ -> they must be 'weekday'.
    offsets = list(range(90))
    df = cal_frame(1, offsets, price=100.0)
    df.loc[df["date"].dt.dayofweek.isin([4, 5]), "price"] = 200.0
    df.loc[df["date"].dt.dayofweek.isin([6]), "price"] = 300.0    # Sunday is a weekday here
    r = aggregate_calendar(df).set_index("listing_id").loc[1]
    assert r.weekend_median_price_90d == 200 and r.weekday_median_price_90d == 100
    assert r.weekend_premium_pct_90d == pytest.approx(1.0)


def test_calendar_aggregation_multiple_listings_unique_keys():
    df = pd.concat([cal_frame(1, range(90)), cal_frame(2, range(40)), cal_frame(3, range(90))])
    out = aggregate_calendar(df)
    assert out["listing_id"].is_unique and len(out) == 3


# ======================================================== review aggregation
@pytest.fixture(scope="module")
def review_feats(raw_dir):
    rev, _ = clean_reviews(load_reviews(raw_dir / "reviews.csv"))
    return aggregate_reviews(rev).set_index("listing_id")


def test_review_aggregation_is_unique_per_listing(review_feats):
    assert review_feats.index.is_unique
    assert set(review_feats.index) == {1, 2, 3, 5, 6, 8888}


def test_review_windows_on_fixture_boundaries_count_rows_not_dates(review_feats):
    r = review_feats.loc[1]
    # dates: S, S, S-29, S-30, S-89, S-90, S-179, S-180, S+1
    assert r.reviews_last_30d == 3        # two same-day rows counted separately; S-30 excluded
    assert r.reviews_last_90d == 5        # + S-30, S-89; S-90 excluded
    assert r.reviews_last_180d == 7       # + S-90, S-179; S-180 excluded; S+1 excluded
    assert r.last_review_date == S and r.days_since_last_review == 0


def test_listing_with_only_old_reviews_has_zero_counts_but_recency(review_feats):
    r = review_feats.loc[2]
    assert (r.reviews_last_30d, r.reviews_last_90d, r.reviews_last_180d) == (0, 0, 0)
    assert r.last_review_date == day(-400) and r.days_since_last_review == 400


def test_post_snapshot_only_reviews_are_treated_as_no_reviews(review_feats):
    r = review_feats.loc[3]
    assert (r.reviews_last_30d, r.reviews_last_90d, r.reviews_last_180d) == (0, 0, 0)
    assert pd.isna(r.last_review_date) and pd.isna(r.days_since_last_review)
    assert bool(r.has_any_review_row) and not bool(r.has_review_on_or_before_snapshot)


def test_invalid_review_date_is_ignored_in_counts(review_feats):
    r = review_feats.loc[5]
    assert (r.reviews_last_30d, r.reviews_last_90d, r.reviews_last_180d) == (1, 1, 1)
    assert r.days_since_last_review == 10
    r6 = review_feats.loc[6]
    assert (r6.reviews_last_30d, r6.reviews_last_90d, r6.reviews_last_180d) == (0, 0, 1)
    assert r6.days_since_last_review == 100


def test_review_count_invariant_across_windows(review_feats):
    assert (review_feats.reviews_last_30d <= review_feats.reviews_last_90d).all()
    assert (review_feats.reviews_last_90d <= review_feats.reviews_last_180d).all()


def test_review_window_unit_boundaries_per_window():
    rows = {"listing_id": pd.array([1] * 12, dtype="Int64"),
            "date": [day(o) for o in (0, -29, -30, -31, -89, -90, -91, -179, -180, -181, 1, 400)]}
    r = aggregate_reviews(pd.DataFrame(rows)).set_index("listing_id").loc[1]
    assert r.reviews_last_30d == 2       # 0, -29
    assert r.reviews_last_90d == 5       # + -30, -31, -89
    assert r.reviews_last_180d == 8      # + -90, -91, -179


# ============================================================== final join
@pytest.fixture(scope="module")
def parts(raw_dir):
    listings, _ = clean_listings(load_listings(raw_dir / "listings.csv.gz"))
    cal, _ = clean_calendar(load_calendar(raw_dir / "calendar.csv.gz"))
    rev, _ = clean_reviews(load_reviews(raw_dir / "reviews.csv"))
    return build_listing_features(listings), aggregate_calendar(cal), aggregate_reviews(rev)


def test_join_keeps_exactly_one_row_per_cleaned_listing(parts):
    listings, cal, rev = parts
    final = join_features(listings, cal, rev)
    assert len(final) == len(listings) == 22
    assert final["id"].is_unique
    assert set(final["id"]) == set(listings["id"])


def test_join_unmatched_calendar_and_review_ids_do_not_add_rows(parts):
    listings, cal, rev = parts
    assert 9999 in set(cal["listing_id"]) and 8888 in set(rev["listing_id"])
    final = join_features(listings, cal, rev)
    assert 9999 not in set(final["id"]) and 8888 not in set(final["id"])
    assert len(final) == len(listings)


def test_join_listing_without_reviews_stays_with_zero_counts_and_na_recency(parts):
    final = join_features(*parts).set_index("id")
    r = final.loc[4]
    assert (r.reviews_last_30d, r.reviews_last_90d, r.reviews_last_180d) == (0, 0, 0)
    assert pd.isna(r.last_review_date) and pd.isna(r.days_since_last_review)
    assert not bool(r.has_any_review_row) and not bool(r.has_review_on_or_before_snapshot)


def test_join_listing_without_calendar_stays_with_na_features(parts):
    final = join_features(*parts).set_index("id")
    r = final.loc[10]
    assert not bool(r.calendar_has_data)
    assert r.calendar_observed_days_30 == 0 and r.calendar_observed_days_90 == 0
    assert r.calendar_expected_days_30 == 30 and r.calendar_expected_days_90 == 90
    for col in ("availability_rate_30d", "availability_rate_90d", "calendar_median_price_30d",
                "calendar_median_price_90d", "calendar_price_iqr_30d", "calendar_price_iqr_90d",
                "weekend_premium_pct_90d", "weekend_premium_abs_90d"):
        assert pd.isna(r[col]), col


def test_join_rejects_non_unique_aggregates(parts):
    listings, cal, rev = parts
    with pytest.raises(DataValidationError, match="not unique"):
        join_features(listings, pd.concat([cal, cal.iloc[:1]]), rev)
    with pytest.raises(DataValidationError, match="not unique"):
        join_features(listings, cal, pd.concat([rev, rev.iloc[:1]]))


def test_acceptance_invariants_on_final_table(parts):
    final = join_features(*parts)
    for col in ("availability_rate_30d", "availability_rate_90d"):
        present = final[col].dropna()
        assert ((present >= 0) & (present <= 1)).all()
    assert (final.reviews_last_30d <= final.reviews_last_90d).all()
    assert (final.reviews_last_90d <= final.reviews_last_180d).all()
    assert (final["amenity_count"].dropna() >= 0).all()
