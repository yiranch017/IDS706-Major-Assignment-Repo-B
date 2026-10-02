"""Descriptive summary tables and the four required figures (saved to files, never shown)."""
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: no display needed (Docker, CI)
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

MIN_REPORT_N = 10  # LOCKED: minimum listings per neighborhood / property type for reporting
MISSING_LABEL = "(missing)"  # presentation label only; the analytical table keeps true NA

# Presentation choices, deliberately NOT locked: set to "log" after reviewing the real
# distributions (see README / handoff). Observations are never removed either way.
PRICE_AXIS_SCALE = {"fig1": "linear", "fig2": "linear"}

FIGURE_FILES = {
    "fig1": "01_price_by_room_type.png",
    "fig2": "02_amenities_vs_listing_price.png",
    "fig3": "03_neighborhood_price_comparison.png",
    "fig4": "04_future_availability_vs_price.png",
}

PRICE_STAT_COLUMNS = ["n_listings", "report_eligible", "n_valid_price",
                      "median_price", "q1_price", "q3_price", "iqr_price"]


# ------------------------------------------------------------ price summaries
def _price_stats(df: pd.DataFrame, column: str, apply_threshold: bool) -> pd.DataFrame:
    keys = df[column].astype(object).where(df[column].notna(), MISSING_LABEL)
    rows = []
    for value, grp in df.groupby(keys, sort=True):
        prices = grp["listing_price"].dropna()          # statistics use valid prices only
        q1, q3 = prices.quantile(0.25), prices.quantile(0.75)
        rows.append({
            column: value,
            "n_listings": len(grp),                      # eligibility counts ALL listings
            "report_eligible": (len(grp) >= MIN_REPORT_N) if apply_threshold else True,
            "n_valid_price": len(prices),
            "median_price": prices.median() if len(prices) else np.nan,
            "q1_price": q1 if len(prices) else np.nan,
            "q3_price": q3 if len(prices) else np.nan,
            "iqr_price": (q3 - q1) if len(prices) else np.nan,
        })
    return pd.DataFrame(rows, columns=[column] + PRICE_STAT_COLUMNS)


def build_neighborhood_summary(df: pd.DataFrame) -> pd.DataFrame:
    """All neighborhoods are listed for transparency; report_eligible marks n >= 10."""
    return _price_stats(df, "neighbourhood_cleansed", apply_threshold=True)


def build_room_property_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Tidy table: room_type (primary, no minimum) then property_type (n >= 10 to report)."""
    parts = []
    for variable, threshold in (("room_type", False), ("property_type", True)):
        part = _price_stats(df, variable, apply_threshold=threshold).rename(columns={variable: "category_value"})
        part.insert(0, "category_variable", variable)
        parts.append(part)
    return pd.concat(parts, ignore_index=True)


def build_host_type_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Single (== 1) versus multi (> 1) hosts. Listings with missing host_type are excluded."""
    d = df[df["host_type"].notna()].copy()
    for col in ("amenity_count", "availability_rate_90d", "reviews_last_90d"):
        d[col] = pd.to_numeric(d[col], errors="coerce")
    rows = []
    for host_type in ("single", "multi"):
        g = d[d["host_type"] == host_type]
        row = {
            "host_type": host_type,
            "n_listings": len(g),
            "median_listing_price": g["listing_price"].median(),
            "median_amenity_count": g["amenity_count"].median(),
            "median_availability_rate_90d": g["availability_rate_90d"].median(),
            "median_reviews_last_90d": g["reviews_last_90d"].median(),
        }
        for room, count in g["room_type"].fillna(MISSING_LABEL).value_counts().sort_index().items():
            row[f"room_share_{re.sub(r'[^a-z0-9]+', '_', room.lower()).strip('_')}"] = count / len(g)
        rows.append(row)
    out = pd.DataFrame(rows)
    share_cols = [c for c in out.columns if c.startswith("room_share_")]
    out[share_cols] = out[share_cols].fillna(0.0)
    return out


# --------------------------------------------------------- data quality summary
def build_data_quality_summary(diag: dict, final: pd.DataFrame) -> pd.DataFrame:
    """Compact metric/value diagnostics: parsing/ID diagnostics from cleaning plus final-table counts."""
    n = len(final)

    def count_prop(name, mask):
        k = int(mask.sum())
        return {f"n_{name}": k, f"prop_{name}": k / n if n else np.nan}

    metrics = dict(diag)
    metrics["listing_price_invalid_or_missing"] = int((~final["listing_price_valid"]).sum())
    metrics["amenity_parse_failures"] = int(final["amenity_parse_failed"].sum())
    metrics["amenity_count_missing"] = int(final["amenity_count"].isna().sum())
    metrics["host_type_missing"] = int(final["host_type"].isna().sum())
    metrics.update(count_prop("listings_passing_calendar_coverage_30d", final["calendar_coverage_rate_30"] * 100 >= 80))
    metrics.update(count_prop("listings_passing_calendar_coverage_90d", final["calendar_coverage_rate_90"] * 100 >= 80))
    # Two distinct review-coverage concepts (listing 3 in the fixtures separates them):
    metrics["prop_listings_with_review_on_or_before_snapshot"] = (
        float(final["has_review_on_or_before_snapshot"].mean()) if n else np.nan
    )
    return pd.DataFrame({"metric": list(metrics), "value": pd.Series(list(metrics.values()), dtype=object)})


# ------------------------------------------------------------------ figures
def _finish(fig, path: Path) -> Path:
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)                                       # release the figure; no plt.show()
    return path


def _no_data(ax, message="No data available for this figure"):
    ax.text(0.5, 0.5, message, ha="center", va="center", transform=ax.transAxes)
    ax.set_xticks([])
    ax.set_yticks([])


def _fig1(df, path):
    fig, ax = plt.subplots(figsize=(8, 5))
    d = df.dropna(subset=["listing_price", "room_type"])
    if d.empty:
        _no_data(ax)
    else:
        groups = sorted(d["room_type"].unique())
        ax.boxplot([d.loc[d.room_type == g, "listing_price"] for g in groups], tick_labels=groups,
                   showfliers=True)                       # extreme plausible prices are kept
        ax.set_yscale(PRICE_AXIS_SCALE["fig1"])
        ax.set_ylabel(f"Listing price (USD, {PRICE_AXIS_SCALE['fig1']} scale)")
        ax.set_xlabel("Room type")
    ax.set_title("Listing price by room type")
    return _finish(fig, path)


def _fig2(df, path):
    fig, ax = plt.subplots(figsize=(8, 5))
    d = df.dropna(subset=["listing_price", "amenity_count"])
    if d.empty:
        _no_data(ax)
    else:
        ax.scatter(d["amenity_count"].astype(float), d["listing_price"], alpha=0.4, s=14)
        ax.set_yscale(PRICE_AXIS_SCALE["fig2"])
        ax.set_xlabel("Number of listed amenities")
        ax.set_ylabel(f"Listing price (USD, {PRICE_AXIS_SCALE['fig2']} scale)")
    ax.set_title("Amenity count vs listing price (association only)")
    return _finish(fig, path)


def _fig3(df, path):
    fig, ax = plt.subplots(figsize=(8, 6))
    s = build_neighborhood_summary(df)
    s = s[s["report_eligible"] & (s["n_valid_price"] > 0)].sort_values("median_price")
    if s.empty:
        _no_data(ax, f"No neighborhood has at least {MIN_REPORT_N} listings")
    else:
        y = np.arange(len(s))
        ax.barh(y, s["median_price"], color="#7aa6c2")
        ax.errorbar(s["median_price"], y, xerr=[s["median_price"] - s["q1_price"], s["q3_price"] - s["median_price"]],
                    fmt="none", ecolor="black", capsize=3)
        ax.set_yticks(y)
        ax.set_yticklabels([f"{r.neighbourhood_cleansed} (n={r.n_listings})" for r in s.itertuples()])
        ax.set_xlabel("Median listing price (USD); bars show Q1-Q3")
    ax.set_title(f"Neighborhood prices (neighborhoods with >= {MIN_REPORT_N} listings)")
    return _finish(fig, path)


def _fig4(df, path):
    fig, ax = plt.subplots(figsize=(8, 5))
    d = df.dropna(subset=["listing_price", "availability_rate_90d"])
    if d.empty:
        _no_data(ax)
    else:
        ax.scatter(d["listing_price"], d["availability_rate_90d"], alpha=0.4, s=14)
        ax.set_xlabel("Listing price (USD)")
        ax.set_ylabel("Forward availability rate, next 90 days")
        ax.set_ylim(-0.02, 1.02)
    ax.set_title("Forward availability (90 days) vs listing price")
    return _finish(fig, path)


def make_figures(df: pd.DataFrame, figures_dir) -> dict:
    """Save the four required figures into figures_dir and return {key: path}."""
    figures_dir = Path(figures_dir)
    figures_dir.mkdir(parents=True, exist_ok=True)
    builders = {"fig1": _fig1, "fig2": _fig2, "fig3": _fig3, "fig4": _fig4}
    return {k: builders[k](df, figures_dir / FIGURE_FILES[k]) for k in builders}
