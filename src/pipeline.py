"""Stage 1 orchestration: validate -> clean -> features -> aggregate -> join -> outputs."""
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.analysis import (
    FIGURE_FILES,
    build_data_quality_summary,
    build_host_type_summary,
    build_neighborhood_summary,
    build_room_property_summary,
    make_figures,
)
from src.data import (
    SNAPSHOT_DATE,
    DataValidationError,
    clean_calendar,
    clean_listings,
    clean_reviews,
    compute_join_diagnostics,
    load_calendar,
    load_listings,
    load_reviews,
    require_raw_files,
)
from src.features import aggregate_calendar, aggregate_reviews, build_listing_features, join_features

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs"

ANALYTICAL_FILE = "data/asheville_listing_features.csv"
TABLE_FILES = {
    "data_quality": "tables/data_quality_summary.csv",
    "neighborhood": "tables/neighborhood_summary.csv",
    "room_property": "tables/room_property_summary.csv",
    "host_type": "tables/host_type_summary.csv",
}
REQUIRED_OUTPUTS = [ANALYTICAL_FILE, *TABLE_FILES.values(),
                    *(f"figures/{name}" for name in FIGURE_FILES.values())]


@dataclass
class Stage1Result:
    final: pd.DataFrame
    diagnostics: dict
    output_dir: Path


def _log(message: str) -> None:
    print(f"[stage1] {message}", flush=True)


def run_stage1(raw_dir=DEFAULT_RAW_DIR, output_dir=DEFAULT_OUTPUT_DIR) -> Stage1Result:
    """Run the full Stage 1 pipeline and write every required output."""
    output_dir = Path(output_dir)
    paths = require_raw_files(raw_dir)
    _log(f"snapshot date {SNAPSHOT_DATE.date()}; reading raw files from {raw_dir}")

    listings, diag = clean_listings(load_listings(paths["listings"]))
    calendar, cal_diag = clean_calendar(load_calendar(paths["calendar"]))
    reviews, rev_diag = clean_reviews(load_reviews(paths["reviews"]))
    diag.update(cal_diag)
    diag.update(rev_diag)
    diag.update(compute_join_diagnostics(listings["id"], calendar["listing_id"], reviews["listing_id"]))
    _log(f"cleaned {len(listings)} listings, {len(calendar)} calendar rows, {len(reviews)} review rows")

    listing_feats = build_listing_features(listings)
    calendar_feats = aggregate_calendar(calendar)
    review_feats = aggregate_reviews(reviews)
    _log(f"aggregated calendar to {len(calendar_feats)} listings and reviews to {len(review_feats)} listings")

    final = join_features(listing_feats, calendar_feats, review_feats)
    _log(f"joined: {len(final)} rows (one per listing)")

    for sub in ("data", "tables", "figures"):
        (output_dir / sub).mkdir(parents=True, exist_ok=True)
    final.to_csv(output_dir / ANALYTICAL_FILE, index=False, date_format="%Y-%m-%d")
    tables = {
        "data_quality": build_data_quality_summary(diag, final),
        "neighborhood": build_neighborhood_summary(final),
        "room_property": build_room_property_summary(final),
        "host_type": build_host_type_summary(final),
    }
    for key, table in tables.items():
        table.to_csv(output_dir / TABLE_FILES[key], index=False)
    make_figures(final, output_dir / "figures")
    _log(f"wrote analytical table, {len(tables)} summary tables and 4 figures to {output_dir}")
    return Stage1Result(final=final, diagnostics=diag, output_dir=output_dir)


def run_pipeline() -> int:
    """Canonical entry point (python main.py). Returns a process exit code."""
    try:
        run_stage1()
    except (FileNotFoundError, DataValidationError) as exc:
        print(f"[stage1] ERROR: {exc}", flush=True)
        return 1
    return 0
