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
2. **RQ2 – Listing price and future availability:** how does 30/90-day forward availability vary
   across listings, and how does it relate to listing price?
3. **RQ3 – Recent review activity:** can recent review counts/recency serve as rough activity signals?
4. **RQ4 – Host portfolio:** how do single-listing (`calculated_host_listings_count == 1`) and
   multi-listing (`> 1`) hosts differ descriptively?

Stage 1 (this repository) is descriptive. No model is included.

> **Plan amendment A1 (project-owner-approved):** manual smoke testing showed the real Asheville
> 2026-06-25 `calendar.csv.gz` has **no price field** (columns: `listing_id`, `date`, `available`,
> `minimum_nights`, `maximum_nights`). `listing_price` from `listings.csv.gz` is therefore the only
> price measure, and the calendar is used for forward availability only. See `docs/plan.md` §1A.

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
| `outputs/tables/host_type_summary.csv` | Single vs multi hosts: counts, medians of listing price/amenities/availability/reviews, room-type shares |
| `outputs/figures/01_price_by_room_type.png` | Listing price by room type |
| `outputs/figures/02_amenities_vs_listing_price.png` | Amenity count vs listing price |
| `outputs/figures/03_neighborhood_price_comparison.png` | Median and IQR for neighborhoods with ≥ 10 listings |
| `outputs/figures/04_future_availability_vs_price.png` | `availability_rate_90d` vs `listing_price` |

Summary tables and figures may be committed as project evidence; the row-level CSV may not.
Price statistics use valid prices only; `n_listings` (used for the n ≥ 10 reporting rule) counts all
listings in the group. Reporting thresholds never remove rows from the analytical table.

### Key rules (see `docs/plan.md` for the full contract)

- Calendar and reviews are each aggregated to one row per listing *before* being left-joined onto listings.
- Future windows: `snapshot <= date < snapshot + N days`; review windows: `snapshot - N days < date <= snapshot`.
- Calendar features need ≥ 80 % date coverage in the window (24/30, 72/90) or they are `NA`, never 0.
  Coverage counts observed dates; the availability rate uses only dates with a valid `available` value.
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

Docker Compose is not used because this project runs as a single Python analysis service and does not require multiple containers.

## Interpretation caveats

- **Availability is not occupancy.** Unavailable dates may be bookings or host blocks; call it *forward availability*.
- **Reviews are an imperfect activity proxy**, not a count of stays or bookings.
- **Price comes from listings only.** The calendar has no price, so nothing here describes how prices vary by date or weekday. `listing_price` is a quoted snapshot price, not a transaction price.
- **Single snapshot:** cross-sectional and forward-calendar patterns only; no long-run trends.
- **Amenity count** treats all amenities equally; more amenities is not "better". Price associations are confounded by size, location, etc.
- Extreme positive prices may be real and are not deleted; summaries emphasize median and IQR.
- `calculated_host_listings_count` reflects listings in this scrape, not a host's complete portfolio.
- **Late calendar start:** 284 listings begin their calendar on 2026-07-03 rather than the 2026-06-25 snapshot date, so they have 22/30 observed days and fail the 30-day 80 % coverage rule (their `availability_rate_30d` is `NA`), while still passing the 90-day rule with 82/90 observed days. Overall 2,581 of 2,865 listings pass the 30-day rule and all 2,865 pass the 90-day rule.
- The 80 % coverage rule and n ≥ 10 reporting thresholds are project rules, not universal truths.
- All Stage 1 relationships are descriptive, not causal.

## Manual smoke test 
I completed the manual smoke test on October 1, 2026 on macOS.

I first verified the local setup by installing the dependencies from `requirements.txt` and running the full automated test suite. `python -m pytest -v` passed all 115 tests.
<img width="1026" height="607" alt="Screenshot 2026-10-01 at 22 39 40" src="https://github.com/user-attachments/assets/c88c10c4-84ef-4c58-9bc8-15544f09fcc7" />

I then ran `python main.py` using the real Asheville June 25, 2026 Inside Airbnb files. The pipeline successfully processed 2,865 listings, 1,046,820 calendar rows, and 345,241 review rows, and generated the required analytical dataset, four summary tables, and four figures.

During the real-data test, I found that the Asheville calendar file did not contain a price column even though the original architecture assumed it would. I reviewed the actual schema and approved an amendment that removed calendar-price features and kept the calendar analysis focused on forward availability. I reran the tests after this revision and confirmed that all 115 passed.

I also inspected the calendar-coverage results. 284 listings had calendar data starting on July 3 rather than the June 25 snapshot date, giving them 22/30 observed days. They correctly failed the predefined 80% 30-day coverage threshold while still passing the 90-day threshold with 82/90 observed days.

Finally, I built the Docker image successfully and ran the real Stage 1 pipeline using a read-only mounted `data/raw` directory and writable `outputs` directory. The container completed successfully and regenerated the required outputs on the host.

The documented local and Docker commands worked as expected.
<img width="1037" height="479" alt="Screenshot 2026-10-01 at 22 42 20" src="https://github.com/user-attachments/assets/66eb1817-219c-45ab-a887-8f90cc32fcdf" />
<img width="601" height="130" alt="Screenshot 2026-10-01 at 22 42 39" src="https://github.com/user-attachments/assets/1610afed-c89e-437d-97b8-998320c93291" />

**Known unresolved issues:** none.

Final Tester verification: **139 tests passed**.
<img width="1023" height="44" alt="Screenshot 2026-10-01 at 23 20 11" src="https://github.com/user-attachments/assets/b3445605-9f56-4740-9d9a-427dea7239ef" />


## AI-assisted workflow and reflection

I used three separate AI roles for this project: Architect(ChatGPT), Builder(ClaudeCode), and Tester(ClaudeCode).

The Architect helped define the project structure, analytical questions, data rules, output requirements, testing strategy, and Docker workflow. I reviewed the proposed architecture and made several implementation decisions before approving the plan.

The Builder implemented the pipeline from the approved plan, including data validation, feature engineering, aggregation, analysis outputs, tests, and containerization. I manually reviewed the implementation and then ran the project myself on the real Asheville data.

One AI recommendation I accepted was the use of fixed 30-day and 90-day calendar windows with an 80% coverage threshold. During manual testing, I verified that this rule behaved meaningfully on the real data: 284 listings started their calendar on July 3 and therefore had only 22/30 observed days, so they correctly failed the 30-day threshold while still passing the 90-day threshold.

One AI recommendation I changed was the original plan to analyze calendar-based pricing. During my real-data smoke test, I discovered that the actual Asheville calendar file did not contain a price column. Rather than fabricate or substitute a different variable, I approved Amendment A1, removed the calendar-price and weekend-premium features, and refocused that part of the project on listing price and future availability.

The independent Tester then reviewed the implementation against the amended plan rather than assuming the Builder was correct. The Tester identified gaps in figure-level testing and price parsing. I accepted those fixes, rejected lower-priority scope expansion such as fully pinning every dependency, and reran the final test suite locally. The final version passes 139 automated tests.

I independently verified the project by running the real-data pipeline, inspecting the generated tables and figures, checking calendar coverage behavior, building the Docker image, and running the real pipeline through the container with mounted raw-data and output directories.
