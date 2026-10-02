"""Shared fixtures. Real Inside Airbnb data is never used by the automated tests."""
import gzip
import shutil
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "data" / "fixtures"


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture(scope="session")
def raw_dir(tmp_path_factory) -> Path:
    """Fixtures laid out like data/raw/: listings and calendar gzipped (real .csv.gz path)."""
    raw = tmp_path_factory.mktemp("raw")
    for name in ("listings.csv", "calendar.csv"):
        with open(FIXTURES_DIR / name, "rb") as src, gzip.open(raw / f"{name}.gz", "wb") as dst:
            shutil.copyfileobj(src, dst)
    shutil.copy(FIXTURES_DIR / "reviews.csv", raw / "reviews.csv")
    return raw


@pytest.fixture(scope="session")
def stage1(raw_dir, tmp_path_factory):
    """One end-to-end fixture run shared by tests that only read its results."""
    from src.pipeline import run_stage1

    out = tmp_path_factory.mktemp("outputs")
    return run_stage1(raw_dir=raw_dir, output_dir=out)


@pytest.fixture(scope="session")
def final(stage1):
    """Final analytical table indexed by listing id."""
    return stage1.final.set_index("id")
