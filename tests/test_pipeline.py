"""Summary tables, figures and end-to-end fixture pipeline (src/analysis.py, src/pipeline.py)."""
import gzip
import shutil

import pandas as pd
import pytest

from src.analysis import (
    MIN_REPORT_N,
    build_host_type_summary,
    build_neighborhood_summary,
    build_room_property_summary,
)
from src.data import DataValidationError, DuplicateCalendarKeyError
from src.pipeline import REQUIRED_OUTPUTS, run_stage1

EXPECTED_FILES = [
    "data/asheville_listing_features.csv",
    "tables/data_quality_summary.csv",
    "tables/neighborhood_summary.csv",
    "tables/room_property_summary.csv",
    "tables/host_type_summary.csv",
    "figures/01_price_by_room_type.png",
    "figures/02_amenities_vs_listing_price.png",
    "figures/03_neighborhood_price_comparison.png",
    "figures/04_future_availability_vs_price.png",
]


def group_df(neigh_counts=(("A", 10), ("B", 9)), valid=True):
    rows = []
    for name, n in neigh_counts:
        for i in range(n):
            rows.append({"neighbourhood_cleansed": name, "property_type": f"P_{name}",
                         "room_type": "Entire home/apt", "listing_price": 100.0 + i if valid else None})
    return pd.DataFrame(rows)


# ------------------------------------------------------- reporting thresholds
def test_min_report_n_is_ten():
    assert MIN_REPORT_N == 10


def test_neighborhood_threshold_n10_eligible_n9_not():
    summary = build_neighborhood_summary(group_df()).set_index("neighbourhood_cleansed")
    assert bool(summary.loc["A", "report_eligible"]) and not bool(summary.loc["B", "report_eligible"])
    assert summary.loc["A", "n_listings"] == 10 and summary.loc["B", "n_listings"] == 9


def test_threshold_counts_all_listings_but_stats_use_valid_prices_only():
    df = group_df(neigh_counts=(("A", 10),))
    df.loc[:3, "listing_price"] = None               # 4 invalid -> 6 valid; still n_listings = 10
    row = build_neighborhood_summary(df).set_index("neighbourhood_cleansed").loc["A"]
    assert row.n_listings == 10 and row.n_valid_price == 6 and bool(row.report_eligible)
    valid = df["listing_price"].dropna()
    assert row.median_price == pytest.approx(valid.median())
    assert row.q1_price == pytest.approx(valid.quantile(0.25))
    assert row.q3_price == pytest.approx(valid.quantile(0.75))
    assert row.iqr_price == pytest.approx(row.q3_price - row.q1_price)


def test_group_with_no_valid_prices_has_na_stats_and_zero_count():
    row = build_neighborhood_summary(group_df(valid=False)).set_index("neighbourhood_cleansed").loc["A"]
    assert row.n_valid_price == 0 and pd.isna(row.median_price) and pd.isna(row.iqr_price)


def test_room_property_summary_is_tidy_and_property_threshold_applies():
    df = pd.concat([group_df((("A", 10), ("B", 9)))])
    summary = build_room_property_summary(df)
    assert set(summary["category_variable"]) == {"room_type", "property_type"}
    prop = summary[summary.category_variable == "property_type"].set_index("category_value")
    assert bool(prop.loc["P_A", "report_eligible"]) and not bool(prop.loc["P_B", "report_eligible"])
    room = summary[summary.category_variable == "room_type"]
    assert room["report_eligible"].all()             # no minimum for room_type
    assert {"n_listings", "n_valid_price", "median_price", "q1_price", "q3_price", "iqr_price"} <= set(summary)


def test_host_type_summary_excludes_missing_host_type(final):
    summary = build_host_type_summary(final.reset_index()).set_index("host_type")
    assert set(summary.index) == {"single", "multi"}
    assert summary["n_listings"].sum() == 19          # 22 listings, 3 with missing host_type
    assert {"median_listing_price", "median_amenity_count", "median_availability_rate_90d",
            "median_reviews_last_90d"} <= set(summary.columns)
    assert not [c for c in summary.columns if "calendar_median_price" in c]


# --------------------------------------------------------- end-to-end fixture run
def test_required_outputs_constant_matches_plan():
    assert sorted(REQUIRED_OUTPUTS) == sorted(EXPECTED_FILES)


def test_pipeline_writes_all_required_outputs(stage1):
    for rel in EXPECTED_FILES:
        path = stage1.output_dir / rel
        assert path.is_file() and path.stat().st_size > 0, rel
    for fig in (stage1.output_dir / "figures").glob("*.png"):
        assert fig.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"      # real PNG files


def test_end_to_end_final_table_row_count_and_keys(stage1):
    saved = pd.read_csv(stage1.output_dir / "data" / "asheville_listing_features.csv")
    assert len(saved) == 22 and saved["id"].is_unique
    assert len(stage1.final) == 22


def test_final_table_has_no_calendar_price_features(final):
    banned = ("calendar_median_price", "calendar_price_iqr", "weekend", "weekday", "valid_price_days")
    assert not [c for c in final.columns if any(b in c for b in banned)]
    assert {"listing_price", "availability_rate_30d", "availability_rate_90d"} <= set(final.columns)


def test_end_to_end_known_listing_values(final):
    r1 = final.loc[1]
    assert r1.amenity_count == 2 and r1.host_type == "single"
    assert r1.availability_rate_30d == pytest.approx(0.5)
    assert (r1.reviews_last_30d, r1.reviews_last_90d, r1.reviews_last_180d) == (3, 5, 7)
    r2 = final.loc[2]
    assert r2.listing_price == 25000.0 and r2.amenity_count == 0 and r2.host_type == "multi"
    assert r2.calendar_coverage_rate_30 == pytest.approx(0.8)
    r3 = final.loc[3]
    assert pd.isna(r3.availability_rate_90d)
    assert r3.reviews_last_180d == 0 and pd.isna(r3.days_since_last_review)
    assert pd.isna(final.loc[4, "listing_price"]) and final.loc[4, "availability_rate_90d"] == 0.0   # real zero


def test_end_to_end_data_quality_summary(stage1):
    dq = pd.read_csv(stage1.output_dir / "tables" / "data_quality_summary.csv")
    assert list(dq.columns) == ["metric", "value"]
    m = dict(zip(dq["metric"], dq["value"]))
    expected = {
        "raw_listing_rows": 22,
        "cleaned_listing_rows": 22,
        "unique_listing_ids": 22,
        "unique_calendar_listing_ids": 6,
        "unique_review_listing_ids": 6,
        "calendar_ids_not_in_listings": 1,
        "review_ids_not_in_listings": 1,
        "listing_price_invalid_or_missing": 4,
        "amenity_parse_failures": 2,
        "calendar_invalid_availability_rows": 2,
        "n_listings_passing_calendar_coverage_30d": 4,
        "n_listings_passing_calendar_coverage_90d": 4,
    }
    for key, value in expected.items():
        assert m[key] == pytest.approx(value), key
    assert m["prop_listings_with_calendar_rows"] == pytest.approx(5 / 22)
    # two distinct review-coverage concepts must both be reported and must differ (listing 3)
    assert m["prop_listings_with_any_review_row"] == pytest.approx(5 / 22)
    assert m["prop_listings_with_review_on_or_before_snapshot"] == pytest.approx(4 / 22)
    assert m["prop_listings_passing_calendar_coverage_90d"] == pytest.approx(4 / 22)
    assert not [k for k in m if "weekend" in k or "calendar_price" in k]


def test_end_to_end_neighborhood_and_property_summaries(stage1):
    tables = stage1.output_dir / "tables"
    nb = pd.read_csv(tables / "neighborhood_summary.csv").set_index("neighbourhood_cleansed")
    assert nb.loc["Downtown", "n_listings"] == 10 and nb.loc["Downtown", "n_valid_price"] == 6
    assert bool(nb.loc["Downtown", "report_eligible"])
    assert nb.loc["Downtown", "median_price"] == pytest.approx(185.0)
    assert not bool(nb.loc["Montford", "report_eligible"]) and nb.loc["Montford", "n_listings"] == 9
    assert len(nb) == 3                                    # all neighborhoods kept for transparency
    rp = pd.read_csv(tables / "room_property_summary.csv")
    prop = rp[rp.category_variable == "property_type"].set_index("category_value")
    assert bool(prop.loc["Entire rental unit", "report_eligible"])
    assert not bool(prop.loc["Entire home", "report_eligible"])


def test_thresholds_do_not_remove_rows_from_analytical_table(stage1):
    nb = pd.read_csv(stage1.output_dir / "tables" / "neighborhood_summary.csv")
    assert nb["n_listings"].sum() == len(stage1.final) == 22


def test_pipeline_is_deterministic(raw_dir, tmp_path, stage1):
    again = run_stage1(raw_dir=raw_dir, output_dir=tmp_path)
    for rel in EXPECTED_FILES[:5]:
        assert (again.output_dir / rel).read_bytes() == (stage1.output_dir / rel).read_bytes(), rel


# ---------------------------------------------------------------- hard failures
def test_missing_raw_file_is_a_hard_failure(tmp_path):
    with pytest.raises(FileNotFoundError):
        run_stage1(raw_dir=tmp_path, output_dir=tmp_path / "out")


def test_duplicate_calendar_rows_are_a_hard_failure(raw_dir, tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    shutil.copy(raw_dir / "listings.csv.gz", raw / "listings.csv.gz")
    shutil.copy(raw_dir / "reviews.csv", raw / "reviews.csv")
    with gzip.open(raw_dir / "calendar.csv.gz", "rt") as src:
        lines = src.read().splitlines()
    with gzip.open(raw / "calendar.csv.gz", "wt") as dst:
        dst.write("\n".join(lines + [lines[1]]) + "\n")
    with pytest.raises(DuplicateCalendarKeyError):
        run_stage1(raw_dir=raw, output_dir=tmp_path / "out")


def test_main_entry_point_exists():
    import main  # noqa: F401  (thin wrapper; importing must not run the pipeline)


def test_figure_axis_scales_are_presentation_only():
    from src.analysis import PRICE_AXIS_SCALE

    assert PRICE_AXIS_SCALE == {"fig1": "log", "fig2": "log", "fig4": "log"}   # figure 3 stays linear
    # scale is a plotting choice: the analytical table keeps every listing and its raw price
