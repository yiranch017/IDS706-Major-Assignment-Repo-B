# Asheville Airbnb Reproducible Data Pipeline

**IDS706 major assignment — Repository B, Option 3: Create a New Project.**

A tested, containerized Python pipeline that validates and combines three Inside Airbnb files for
Asheville, NC into a one-row-per-listing analytical table, plus focused descriptive tables and
figures. The full specification is in [`docs/plan.md`](docs/plan.md) (the implementation contract).

## Purpose and research questions

How do listing characteristics, neighborhood, price, future availability, recent review activity
and host portfolio structure relate to one another in the Asheville Airbnb market?

1. **RQ1 – Price structure:** how does listing price differ by room type, property type,
   neighborhood and number of listed amenities? (Association only.)
2. **RQ2 – Dynamic pricing and availability:** how do 30/90-day future quoted prices, their
   variability, the Friday/Saturday premium and forward availability vary, and how do availability
   and price relate?
3. **RQ3 – Recent review activity:** can recent review counts/recency serve as rough activity signals?
4. **RQ4 – Host portfolio:** how do single-listing (`calculated_host_listings_count == 1`) and
   multi-listing (`> 1`) hosts differ descriptively?

Stage 1 (this repository) is descriptive. No model is included.

## Data source

- Source: [Inside Airbnb](https://insideairbnb.com/get-the-data/), city **Asheville, NC**
- Snapshot date: **2026-06-25** (fixed project constant `SNAPSHOT_DATE`; the current date is never used)
- Download these three files and place them, with exactly these names, in `data/raw/`:

```text
data/raw/listings.csv.gz    # "Detailed Listings data"
data/raw/calendar.csv.gz    # "Detailed Calendar Data"
data/raw/reviews.csv        # "Summary Review data"
```

Raw files are git-ignored and are never committed or copied into the Docker image.

## Setup and usage

```bash
python -m pip install -r requirements.txt   # Python 3.12 recommended (also tested on 3.11)
python main.py                              # full Stage 1 pipeline (raw data -> outputs/)
python -m pytest -v                         # automated tests (synthetic fixtures only)
```

`make install`, `make run`, `make test`, `make docker-build` and `make docker-run` are thin
wrappers around the same commands.

The tests use the tiny synthetic files in [`data/fixtures/`](data/fixtures/README.md) and do not need
the real data.

## Outputs

| File | Contents |
|---|---|
| `outputs/data/asheville_listing_features.csv` | One row per cleaned listing with listing, calendar and review features (**git-ignored**: row-level derivative data) |
| `outputs/tables/data_quality_summary.csv` | `metric,value` diagnostics: row counts, unmatched IDs, coverage, parsing failures, threshold pass counts |
| `outputs/tables/neighborhood_summary.csv` | Per neighborhood: `n_listings`, `report_eligible` (n ≥ 10), `n_valid_price`, median/Q1/Q3/IQR price |
| `outputs/tables/room_property_summary.csv` | Same statistics, tidy by `category_variable` (`room_type`, `property_type`); property types eligible at n ≥ 10 |
| `outputs/tables/host_type_summary.csv` | Single vs multi hosts: counts, medians of price/amenities/availability/future price/reviews, room-type shares |
| `outputs/figures/01_price_by_room_type.png` | Listing price by room type |
| `outputs/figures/02_amenities_vs_listing_price.png` | Amenity count vs listing price |
| `outputs/figures/03_neighborhood_price_comparison.png` | Median and IQR for neighborhoods with ≥ 10 listings |
| `outputs/figures/04_future_availability_vs_price.png` | `availability_rate_90d` vs `calendar_median_price_90d` |

Summary tables and figures may be committed as project evidence; the row-level CSV may not.
Price statistics use valid prices only; `n_listings` (used for the n ≥ 10 reporting rule) counts all
listings in the group. Reporting thresholds never remove rows from the analytical table.

### Key rules (see `docs/plan.md` for the full contract)

- Calendar and reviews are each aggregated to one row per listing *before* being left-joined onto listings.
- Future windows: `snapshot <= date < snapshot + N days`; review windows: `snapshot - N days < date <= snapshot`.
- Calendar features need ≥ 80 % date coverage in the window (24/30, 72/90) or they are `NA`, never 0.
  Coverage counts observed dates; the availability rate uses only dates with a valid `available` value.
- Weekend = Friday/Saturday, 90-day window, requires ≥ 8 weekend and ≥ 20 weekday valid prices.
- Listings with no reviews have 0 review counts but `NA` last-review date / days since last review.
- `amenity_count` comes from parsing the amenity list (never counting commas); missing or malformed → `NA`.
- Two review-coverage QA metrics are reported: `prop_listings_with_any_review_row` and
  `prop_listings_with_review_on_or_before_snapshot`.

## Docker

The image contains code and dependencies only. Raw data (read-only) and outputs are mounted:

```bash
docker build -t asheville-airbnb-analysis .

docker run --rm \
  -v "$(pwd)/data/raw:/app/data/raw:ro" \
  -v "$(pwd)/outputs:/app/outputs" \
  asheville-airbnb-analysis
```

The default container command is `python main.py`, which runs the real pipeline. Plots are written
with the headless `Agg` backend, so no display is needed. To run the tests in the image:
`docker run --rm asheville-airbnb-analysis python -m pytest -v`.

## Interpretation caveats

- **Availability is not occupancy.** Unavailable dates may be bookings or host blocks; call it *forward availability*.
- **Reviews are an imperfect activity proxy**, not a count of stays or bookings.
- **Listing price ≠ calendar price.** `listing_price` is a snapshot price; `calendar_median_price_Nd` describes future *quoted* prices (not transaction prices).
- **Single snapshot:** cross-sectional and forward-calendar patterns only; no long-run trends.
- **Amenity count** treats all amenities equally; more amenities is not "better". Price associations are confounded by size, location, etc.
- Extreme positive prices may be real and are not deleted; summaries emphasize median and IQR.
- `calculated_host_listings_count` reflects listings in this scrape, not a host's complete portfolio.
- The 80 % coverage rule, 8/20 weekend rule and n ≥ 10 reporting thresholds are project rules, not universal truths.
- All Stage 1 relationships are descriptive, not causal.

## Manual smoke test (project owner — to be completed before the Tester stage)

> **Not yet performed.** Fill this in after running the checklist in `docs/plan.md` §30.

- [ ] Date performed / environment:
- [ ] `python -m pip install -r requirements.txt` succeeded:
- [ ] `python main.py` completed on the real data:
- [ ] All 9 required output files generated (CSV, 4 tables, 4 figures):
- [ ] Figures open correctly and need no display:
- [ ] `python -m pytest -v` passed:
- [ ] `docker build` succeeded:
- [ ] `docker run` (mounted raw data, writable outputs) succeeded and outputs appeared on host:
- [ ] README commands matched what actually worked:
- [ ] Known unresolved issues:

## AI-assisted workflow and reflection

> To be completed as the Architect, Builder and Tester stages finish.

- **Architect:** _(contribution, recommendations accepted/rejected)_
- **Builder:** _(contribution, recommendations accepted/rejected)_
- **Tester:** _(findings, fixes)_
- **My independent verification:** _(what I checked myself and what I found)_
- **Reflection:** _(what worked, what I would change)_
