"""Loading, validation, parsing and cleaning (src/data.py)."""
import numpy as np
import pandas as pd
import pytest

from src.data import (
    SNAPSHOT_DATE,
    DataValidationError,
    DuplicateCalendarKeyError,
    clean_calendar,
    clean_listings,
    clean_reviews,
    compute_join_diagnostics,
    load_calendar,
    load_listings,
    load_reviews,
    normalize_ids,
    parse_amenity_count,
    parse_price,
    require_raw_files,
)


def test_snapshot_date_is_fixed():
    assert SNAPSHOT_DATE == pd.Timestamp("2026-06-25")


# ---------------------------------------------------------------- price parsing
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("$100.00", 100.0),
        ("$1,250.50", 1250.5),
        ("85", 85.0),
        ("$25,000.00", 25000.0),   # extreme but positive and parseable -> stays valid
        ("$999999.00", 999999.0),
    ],
)
def test_parse_price_valid(raw, expected):
    assert parse_price(pd.Series([raw])).iloc[0] == pytest.approx(expected)


@pytest.mark.parametrize(
    "raw",
    ["abc", "", "   ", None, np.nan, "$0.00", "0", "$-10.00", "-5", "$",
     "inf", "Infinity", "-inf", "$1e400", "1e3", "$1E3", "1e-2", "$1.5e2", "NaN", "0x10",
     "€100", "100 USD", "1.2.3", "+5", "9" * 400],   # non-finite, scientific, signed or non-plain -> invalid
)
def test_parse_price_invalid_becomes_missing(raw):
    assert pd.isna(parse_price(pd.Series([raw], dtype=object)).iloc[0])


def test_parse_price_only_valid_entries_survive_in_a_mixed_series():
    out = parse_price(pd.Series(["$1,250.50", "1e3", "inf", "$ 85 ", "$1e400", "$25,000.00"], dtype=object))
    assert out.iloc[[0, 3, 5]].tolist() == [1250.5, 85.0, 25000.0]
    assert out.iloc[[1, 2, 4]].isna().all()
    assert np.isfinite(out.dropna()).all()


# ------------------------------------------------------------- amenity parsing
def amenity(value):
    out = parse_amenity_count(pd.Series([value], dtype=object))
    count = out["amenity_count"].iloc[0]
    return (None if pd.isna(count) else int(count)), bool(out["amenity_parse_failed"].iloc[0])


@pytest.mark.parametrize(
    "value, expected",
    [
        ("[]", 0),
        ('["Wifi"]', 1),
        ('["Wifi", "Kitchen"]', 2),
        # commas/punctuation INSIDE items must not inflate the count
        ('["Hair dryer, ceramic", "TV with Netflix, HBO", "Wifi"]', 3),
        ('["Bed linens (cotton, 400 thread count)"]', 1),
        # JSON unicode escape
        ('["Caf\\u00e9 machine", "Wifi"]', 2),
        # python-style list -> ast.literal_eval fallback
        ("['Wifi', 'Kitchen']", 2),
    ],
)
def test_amenity_count_parsed_lists(value, expected):
    assert amenity(value) == (expected, False)


@pytest.mark.parametrize("value", [None, np.nan, "", "   "])
def test_amenity_true_missing_is_na_without_failure(value):
    assert amenity(value) == (None, False)


@pytest.mark.parametrize("value", ['["Wifi", "Kitchen', "not a list", '{"a": 1}', "[1, 2", '"Wifi"', "42"])
def test_amenity_malformed_is_na_with_failure(value):
    assert amenity(value) == (None, True)


def test_amenity_count_is_nullable_integer_dtype():
    out = parse_amenity_count(pd.Series(["[]", None, '["a"]']))
    assert str(out["amenity_count"].dtype) == "Int64"
    assert out["amenity_count"].tolist()[0] == 0 and pd.isna(out["amenity_count"].iloc[1])


# ------------------------------------------------------------- key normalization
def test_normalize_ids():
    out = normalize_ids(pd.Series(["1", " 7 ", "1.0", "abc", "", None, "1.5", "123456789012"]))
    assert str(out.dtype) == "Int64"
    assert out.tolist()[:3] == [1, 7, 1]
    assert out.iloc[3:7].isna().all()
    assert out.iloc[7] == 123456789012


def test_normalize_ids_real_scale_airbnb_ids_keep_full_precision():
    # Current Airbnb ids are ~1.5e18, above 2**53: they must not pass through float64.
    big = ["1500000000000000001", "1500000000000000003", "1500000000000000005"]
    out = normalize_ids(pd.Series(big + ["abc"]))                 # an invalid id in the same column
    assert out.iloc[:3].tolist() == [1500000000000000001, 1500000000000000003, 1500000000000000005]
    assert out.iloc[3] is pd.NA or pd.isna(out.iloc[3])
    assert out.iloc[:3].is_unique


# ---------------------------------------------------------------------- loading
def test_require_raw_files_reports_all_missing(tmp_path):
    (tmp_path / "reviews.csv").write_text("listing_id,date\n")
    with pytest.raises(FileNotFoundError) as exc:
        require_raw_files(tmp_path)
    assert "listings.csv.gz" in str(exc.value) and "calendar.csv.gz" in str(exc.value)
    assert "reviews.csv" not in str(exc.value)


def test_require_raw_files_returns_paths(raw_dir):
    paths = require_raw_files(raw_dir)
    assert set(paths) == {"listings", "calendar", "reviews"}
    assert paths["listings"].name == "listings.csv.gz"


def test_loaders_read_gzipped_fixtures_and_tolerate_extra_columns(raw_dir):
    listings = load_listings(raw_dir / "listings.csv.gz")
    calendar = load_calendar(raw_dir / "calendar.csv.gz")
    reviews = load_reviews(raw_dir / "reviews.csv")
    assert len(listings) == 22 and len(calendar) == 420 and len(reviews) == 16


@pytest.mark.parametrize(
    "loader, header, missing",
    [
        (load_listings, "id,host_id,price", "neighbourhood_cleansed"),
        (load_calendar, "listing_id,date,minimum_nights", "available"),
        (load_reviews, "id,reviewer", "listing_id"),
    ],
)
def test_loaders_fail_on_missing_required_column(tmp_path, loader, header, missing):
    path = tmp_path / "x.csv"
    path.write_text(header + "\n1,2,3\n")
    with pytest.raises(DataValidationError, match=missing):
        loader(path)


# ----------------------------------------------------------------- cleaning
def raw_listings(**overrides):
    base = {
        "id": ["1", "2"], "host_id": ["10", "11"], "neighbourhood_cleansed": ["A", "B"],
        "property_type": ["x", "y"], "room_type": ["r", "r"], "accommodates": ["2", "4"],
        "bedrooms": ["1", ""], "beds": ["1", "2"], "price": ["$10.00", "$20.00"],
        "amenities": ["[]", "[]"], "calculated_host_listings_count": ["1", "2"],
    }
    base.update(overrides)
    return pd.DataFrame(base)


def test_clean_listings_fixture(raw_dir):
    cleaned, diag = clean_listings(load_listings(raw_dir / "listings.csv.gz"))
    assert diag["raw_listing_rows"] == 22 and diag["cleaned_listing_rows"] == 22
    assert cleaned["id"].is_unique and str(cleaned["id"].dtype) == "Int64"
    host_counts = cleaned.set_index("id")["calculated_host_listings_count"]
    assert host_counts[1] == 1 and host_counts[4] == 0
    assert pd.isna(host_counts[5]) and pd.isna(host_counts[6])    # blank / "abc" -> NA, not forced


def test_clean_listings_duplicate_id_is_hard_failure():
    with pytest.raises(DataValidationError, match="duplicate"):
        clean_listings(raw_listings(id=["1", "1.0"]))


def test_clean_listings_drops_and_counts_missing_ids():
    cleaned, diag = clean_listings(raw_listings(id=["1", "abc"]))
    assert list(cleaned["id"]) == [1]
    assert diag["raw_listing_rows"] == 2 and diag["cleaned_listing_rows"] == 1
    assert diag["listing_rows_missing_id"] == 1


def test_clean_calendar_fixture_diagnostics(raw_dir):
    cal, diag = clean_calendar(load_calendar(raw_dir / "calendar.csv.gz"))
    assert diag["raw_calendar_rows"] == 420
    assert diag["calendar_rows_invalid_date"] == 0
    assert diag["calendar_invalid_availability_rows"] == 2          # listing 6, two 'x' rows
    assert "price" not in cal.columns                                # real calendar has no price field
    assert str(cal["listing_id"].dtype) == "Int64"
    assert pd.api.types.is_datetime64_any_dtype(cal["date"])


def test_clean_calendar_availability_parsing():
    raw = pd.DataFrame({
        "listing_id": ["1"] * 5,
        "date": ["2026-06-25", "2026-06-26", "2026-06-27", "2026-06-28", "2026-06-29"],
        "available": ["t", "f", "x", "", "T"],
    })
    cal, diag = clean_calendar(raw)
    assert cal["available"].tolist()[:2] == [True, False]
    assert cal["available"].iloc[2:4].isna().all()          # invalid / blank status stays NA
    assert diag["calendar_invalid_availability_rows"] == 2
    assert cal["available"].iloc[4]                          # case-insensitive 't'


def test_clean_calendar_duplicate_listing_date_is_reported_not_resolved():
    raw = pd.DataFrame({
        "listing_id": ["1", "1", "2"], "date": ["2026-07-01", "2026-07-01", "2026-07-01"],
        "available": ["t", "f", "t"],
    })
    with pytest.raises(DuplicateCalendarKeyError, match="1 duplicate"):
        clean_calendar(raw)


def test_clean_calendar_counts_unparseable_dates_and_keeps_listing_id():
    raw = pd.DataFrame({"listing_id": ["1", "1"], "date": ["2026-07-01", "07/01/xx"],
                        "available": ["t", "t"]})
    cal, diag = clean_calendar(raw)
    assert diag["calendar_rows_invalid_date"] == 1
    assert cal["date"].isna().sum() == 1 and len(cal) == 2


def test_clean_reviews_fixture_diagnostics(raw_dir):
    rev, diag = clean_reviews(load_reviews(raw_dir / "reviews.csv"))
    assert diag["raw_review_rows"] == 16
    assert diag["review_rows_invalid_date"] == 1
    assert diag["review_rows_after_snapshot"] == 2          # listing 1 (S+1) and listing 3 (S+5)
    assert len(rev) == 16                                    # nothing silently dropped


def test_clean_reviews_does_not_deduplicate_same_day_rows():
    raw = pd.DataFrame({"listing_id": ["1", "1", "1"], "date": ["2026-06-01"] * 3})
    rev, _ = clean_reviews(raw)
    assert len(rev) == 3


# --------------------------------------------------------- join diagnostics
def test_compute_join_diagnostics_unmatched_ids(raw_dir):
    listings, _ = clean_listings(load_listings(raw_dir / "listings.csv.gz"))
    cal, _ = clean_calendar(load_calendar(raw_dir / "calendar.csv.gz"))
    rev, _ = clean_reviews(load_reviews(raw_dir / "reviews.csv"))
    diag = compute_join_diagnostics(listings["id"], cal["listing_id"], rev["listing_id"])
    assert diag["unique_listing_ids"] == 22
    assert diag["unique_calendar_listing_ids"] == 6          # 1, 2, 3, 4, 6 and 9999
    assert diag["unique_review_listing_ids"] == 6            # 1, 2, 3, 5, 6 and 8888
    assert diag["calendar_ids_not_in_listings"] == 1
    assert diag["review_ids_not_in_listings"] == 1
    assert diag["prop_listings_with_calendar_rows"] == pytest.approx(5 / 22)
    assert diag["prop_listings_with_any_review_row"] == pytest.approx(5 / 22)
