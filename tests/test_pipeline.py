"""Summary tables, figures and end-to-end fixture pipeline (src/analysis.py, src/pipeline.py)."""
import gzip
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from src.analysis import (
    MIN_REPORT_N,
    build_host_type_summary,
    build_neighborhood_summary,
    build_room_property_summary,
)
from src import analysis, features
from src.analysis import (
    MISSING_LABEL,
    build_data_quality_summary,
    fig1_data,
    fig2_data,
    fig3_data,
    fig4_data,
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


# ------------------------------------------------- missing-category reporting
def test_missing_category_is_listed_but_never_report_eligible():
    rows = [{"neighbourhood_cleansed": None, "property_type": None, "room_type": None,
             "listing_price": 100.0 + i} for i in range(12)]           # 12 >= 10 missing rows
    rows += [{"neighbourhood_cleansed": "A", "property_type": "P", "room_type": "R",
              "listing_price": 50.0 + i} for i in range(10)]
    df = pd.DataFrame(rows)
    nb = build_neighborhood_summary(df).set_index("neighbourhood_cleansed")
    assert nb.loc[MISSING_LABEL, "n_listings"] == 12                   # visible for transparency
    assert not bool(nb.loc[MISSING_LABEL, "report_eligible"]) and bool(nb.loc["A", "report_eligible"])
    rp = build_room_property_summary(df)
    for variable in ("property_type", "room_type"):
        row = rp[(rp.category_variable == variable) & (rp.category_value == MISSING_LABEL)].iloc[0]
        assert row.n_listings == 12 and not bool(row.report_eligible)
    assert list(fig3_data(df)["neighbourhood_cleansed"]) == ["A"]      # never in the comparison figure
    assert MISSING_LABEL not in set(fig1_data(df)["room_type"])


# ----------------------------------------------------- figure data selection
def figure_df():
    return pd.DataFrame({
        "neighbourhood_cleansed": ["Big"] * 10 + ["Small"] * 9,
        "room_type": ["Entire home/apt"] * 19,
        "listing_price": [100.0 + i for i in range(19)],
        "amenity_count": pd.array(list(range(19)), dtype="Int64"),
        "beds": [7.0] * 19,
        "availability_rate_30d": [0.1] * 19,
        "availability_rate_90d": [0.5 + (i % 3) / 10 for i in range(19)],
    })


def test_fig2_uses_amenity_count_against_listing_price():
    df = figure_df()
    df.loc[0, "amenity_count"] = pd.NA
    df.loc[1, "listing_price"] = None
    d = fig2_data(df)
    assert len(d) == 17                                                # either missing -> excluded
    kept = df.dropna(subset=["amenity_count", "listing_price"])
    assert d["x"].tolist() == kept["amenity_count"].astype(float).tolist()
    assert d["y"].tolist() == kept["listing_price"].tolist()
    assert (d["x"] != df["beds"].iloc[0]).any()                       # not beds, not another column


def test_fig3_includes_only_neighborhoods_with_at_least_10_listings():
    d = fig3_data(figure_df())
    assert list(d["neighbourhood_cleansed"]) == ["Big"] and int(d["n_listings"].iloc[0]) == 10
    df = figure_df()
    df.loc[df.neighbourhood_cleansed == "Small", "neighbourhood_cleansed"] = "Big"   # now 19
    assert list(fig3_data(df)["neighbourhood_cleansed"]) == ["Big"]
    df.loc[0, "neighbourhood_cleansed"] = "Tiny"                       # Big 18, Tiny 1
    assert "Tiny" not in set(fig3_data(df)["neighbourhood_cleansed"])


def test_fig4_uses_listing_price_against_availability_rate_90d_and_drops_missing():
    df = figure_df()
    df.loc[2, "availability_rate_90d"] = None
    df.loc[3, "listing_price"] = None
    d = fig4_data(df)
    kept = df.dropna(subset=["availability_rate_90d", "listing_price"])
    assert len(d) == 17
    assert d["x"].tolist() == kept["listing_price"].tolist()
    assert d["y"].tolist() == kept["availability_rate_90d"].tolist()   # 90d, not the 30d column
    assert d["y"].notna().all() and d["x"].notna().all()


def _plotted(monkeypatch, builder, df):
    """Run a figure builder and capture the matplotlib figure instead of saving it."""
    captured = {}

    def fake_finish(fig, path):
        captured["fig"] = fig
        return path

    monkeypatch.setattr(analysis, "_finish", fake_finish)
    builder(df, Path("unused.png"))
    return captured["fig"].axes[0]


def test_drawn_figures_use_the_selected_data(monkeypatch):
    df = figure_df()
    df.loc[0, "amenity_count"] = pd.NA
    df.loc[2, "availability_rate_90d"] = None
    ax2 = _plotted(monkeypatch, analysis._fig2, df)
    assert ax2.collections[0].get_offsets().data.tolist() == fig2_data(df)[["x", "y"]].values.tolist()
    ax4 = _plotted(monkeypatch, analysis._fig4, df)
    assert ax4.collections[0].get_offsets().data.tolist() == fig4_data(df)[["x", "y"]].values.tolist()
    ax3 = _plotted(monkeypatch, analysis._fig3, df)
    assert [t.get_text() for t in ax3.get_yticklabels()] == ["Big (n=10)"]
    assert ax2.get_yscale() == "log" and ax4.get_xscale() == "log" and ax3.get_xscale() == "linear"


# --------------------------------------------- single source of truth for coverage
def test_data_quality_coverage_counts_use_the_shared_threshold_rule(final, monkeypatch):
    final = final.reset_index()
    diag = {"raw_listing_rows": len(final)}
    base = dict(zip(*build_data_quality_summary(diag, final)[["metric", "value"]].values.T))
    assert base["n_listings_passing_calendar_coverage_90d"] == 4
    # Raising the shared rule must change the data-quality counts: no private copy of 80% in analysis.py
    monkeypatch.setattr(features, "MIN_COVERAGE_PCT", 100)
    strict = dict(zip(*build_data_quality_summary(diag, final)[["metric", "value"]].values.T))
    assert strict["n_listings_passing_calendar_coverage_30d"] == 3      # listing 2 (24/30) drops out
    assert strict["n_listings_passing_calendar_coverage_90d"] == 3      # listing 2 (72/90) drops out


# --------------------------------------------------------- main.py error path
def test_main_exits_nonzero_with_clear_message_when_raw_inputs_are_missing(tmp_path):
    root = Path(__file__).resolve().parents[1]
    (tmp_path / "src").mkdir()
    for f in (root / "src").glob("*.py"):
        shutil.copy(f, tmp_path / "src" / f.name)
    shutil.copy(root / "main.py", tmp_path / "main.py")                # empty data/raw in this copy
    r = subprocess.run([sys.executable, "main.py"], cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 1
    assert "Missing raw input file(s)" in r.stdout and "listings.csv.gz" in r.stdout
    assert not (tmp_path / "outputs").exists()                         # nothing half-written
