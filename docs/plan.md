# Asheville Airbnb Reproducible Data Pipeline — Implementation Plan

## 1. Purpose of this document

This file is the implementation contract for Repository B of the IDS706 major assignment.

The project will build a reproducible data-analysis pipeline using the Asheville, North Carolina Inside Airbnb snapshot dated **2026-06-25**. The required Stage 1 deliverable is a tested, containerized pipeline that validates and combines listing, calendar, and review data into a one-row-per-listing analytical table and produces focused descriptive outputs tied directly to the research questions below.

This plan is intentionally detailed enough for a separate Builder agent and a later independent Tester agent to work from it without needing the architecture conversation.

### Decision provenance

The plan uses three labels:

- **USER-REVIEWED DECISION — LOCKED:** explicitly selected or approved by the project owner. The Builder must not change it silently.
- **ARCHITECT IMPLEMENTATION DETAIL:** a concrete implementation rule added to make the specification unambiguous while remaining consistent with the reviewed architecture.
- **APPROVAL REQUIRED:** a decision that must come back to the project owner before implementation changes.

If real-data inspection reveals that a locked threshold, rule, or assumption creates an unexpected problem, the Builder must report it before changing the implementation.

---

## 1A. Amendment A1 — no calendar price field (project-owner-approved)

> **USER-REVIEWED DECISION — LOCKED (Amendment A1)**

This amendment was made **after manual smoke testing**, which revealed that the actual Asheville
**2026-06-25** `calendar.csv.gz` schema contains **no price field** (no `price` and no
`adjusted_price`). Its columns are `listing_id`, `date`, `available`, `minimum_nights`,
`maximum_nights`. The original plan assumed calendar prices existed. This was a
project-owner-approved change based on the real data; calendar prices are not fabricated,
reconstructed or substituted.

What changed (smallest consistent change):

- **Price measure:** `listing_price` from `listings.csv.gz` is the project's only price measure.
- **Calendar role:** the calendar is used for forward availability only
  (`availability_rate_30d`, `availability_rate_90d`), with the same fixed windows, 80% coverage
  rule, missingness rules and the "availability is not occupancy" caveat.
- **Removed features:** `calendar_median_price_30d/90d`, `calendar_price_iqr_30d/90d`,
  `weekend_median_price_90d`, `weekday_median_price_90d`, `weekend_premium_abs_90d`,
  `weekend_premium_pct_90d`, `weekend_valid_price_count_90d`, `weekday_valid_price_count_90d`,
  `calendar_valid_price_days_30/90`, and the calendar price parsing/validation rules. The
  Friday/Saturday weekend definition and the 8/20 weekend thresholds no longer exist.
- **RQ2** is now the relationship between listing price and future availability.
- **Figure 4** is now `listing_price` (x) versus `availability_rate_90d` (y).
- `minimum_nights` / `maximum_nights` stay in the raw file but are **not** used in Stage 1 and are
  not a substitute for price. No new analysis was added to replace the removed features.

Sections whose content was removed keep their heading with a short "removed" stub so section
numbers and cross-references stay stable. The acceptance invariants (§24), the test strategy
(§23) and the definition of done (§32) below describe the **revised** specification, which is
what the Tester evaluates.

---

## 2. Project purpose

The project will study the Asheville Airbnb market by examining how listing characteristics, neighborhood, pricing, future availability, recent review activity, and host portfolio structure relate to one another.

The main engineering product is not merely an exploratory notebook. It is a reproducible transformation pipeline that:

1. validates three raw Inside Airbnb sources;
2. cleans variables needed for the research questions;
3. engineers listing-level features;
4. aggregates calendar and review data from many rows per listing to one row per listing;
5. safely joins those features to the listing table;
6. produces a documented analytical dataset;
7. creates a small set of reproducible descriptive tables and figures;
8. verifies core data invariants with automated tests; and
9. runs both locally and in Docker without embedding raw third-party data in the image.

Stage 1 is a complete project on its own. Modeling is conditional and is not required unless separately approved after Stage 1 results are reviewed.

---

## 3. Research questions

The Stage 1 descriptive analysis should be organized around these questions rather than around a generic review of every available column.

### RQ1 — Listing price structure

How does listing-level nightly price differ across:

- room type;
- sufficiently common property types;
- sufficiently represented neighborhoods;
- listing capacity/size characteristics where useful for interpretation; and
- number of listed amenities?

The amenities sub-question is:

> Is a greater number of listed amenities associated with a higher listing price?

This is an association question. The project must not claim that more amenities are objectively better or more optimal for consumers.

### RQ2 — Listing price and future availability

How does forward availability over the next 30 and 90 days vary across listings, and how does it
relate descriptively to listing price?

- 30-day and 90-day forward availability rate; and
- the relationship between `listing_price` and `availability_rate_90d`, with room type or
  neighborhood used where helpful for interpretation.

This is a descriptive association. Forward availability is not occupancy, and the calendar
provides no price (see Amendment A1).

### RQ3 — Recent review activity

Can recent review frequency and review recency serve as rough listing-activity signals, and how do those signals relate descriptively to price, availability, room type, or neighborhood?

Review activity is only a proxy. It must not be interpreted as a direct count of bookings or occupancy.

### RQ4 — Host portfolio structure

How do single-listing and multi-listing hosts differ descriptively in relevant listing characteristics such as:

- listing price;
- future availability;
- amenity count;
- room type; and
- recent review activity?

For the required comparison:

~~~text
single-listing host: calculated_host_listings_count == 1
multi-listing host:  calculated_host_listings_count > 1
~~~

---

## 4. Data sources and fixed snapshot

> **USER-REVIEWED DECISION — LOCKED**

Use exactly these three Asheville Inside Airbnb files from the **2026-06-25 snapshot**:

1. detailed listings: `listings.csv.gz`
2. detailed calendar: `calendar.csv.gz`
3. summary review dates: `reviews.csv`

Source page:

https://insideairbnb.com/get-the-data/

The README must document:

- source site;
- city: Asheville, NC;
- exact snapshot date: 2026-06-25;
- expected filenames;
- expected location under `data/raw/`.

### Fixed temporal reference

Define one project-wide constant:

~~~text
SNAPSHOT_DATE = 2026-06-25
~~~

All relative date features must be calculated from this fixed date.

The analytical pipeline must never use the machine's current date, `today()`, or execution timestamp to define review or calendar windows.

---

## 5. Scope

### Required scope

- Python-based reproducible pipeline
- `listings.csv.gz`
- `calendar.csv.gz`
- `reviews.csv`
- listing-level feature engineering
- calendar aggregation
- review-date aggregation
- explicit join diagnostics
- focused descriptive analysis
- automated tests
- tiny committed test fixtures
- Docker image containing code and dependencies
- mounted raw-data and output volumes
- clear setup/run/test documentation
- a manual Builder smoke-test stage before independent Tester review

### Explicitly excluded

> **USER-REVIEWED DECISION — LOCKED**

Do not add the following unless a later finding provides a strong reason and the project owner explicitly approves it:

- review-text NLP;
- detailed reviews text analysis;
- GeoJSON or spatial analysis;
- spatial joins;
- Streamlit or another dashboard;
- database infrastructure;
- API/service layer;
- Docker Compose;
- individual amenity indicators;
- arbitrary property-type regrouping;
- arbitrary host-size bins beyond 1 versus >1;
- automatic IQR-based price outlier deletion;
- guaranteed modeling.

The project should remain substantial but realistic for a course assignment.

---

## 6. Required repository/file layout

> **USER-REVIEWED DECISION — LOCKED IN PRINCIPLE**

Keep the implementation simple. Do not overengineer the repository into a large package with many small modules.

The Builder should use the following layout unless a minor naming adjustment is clearly justified:

~~~text
IDS706-Major-Assignment-Repo-B/
├── data/
│   ├── raw/                 # gitignored real Inside Airbnb files
│   └── fixtures/            # tiny committed synthetic test datasets
├── src/
│   ├── data.py              # loading, validation, cleaning, QA diagnostics
│   ├── features.py          # listing/calendar/review feature engineering
│   ├── analysis.py          # summary tables and figures
│   └── pipeline.py          # Stage 1 orchestration functions
├── tests/
│   ├── test_data.py
│   ├── test_features.py
│   └── test_pipeline.py
├── outputs/
│   ├── data/
│   ├── tables/
│   └── figures/
├── docs/
│   ├── plan.md
│   └── transcripts/
├── main.py                  # single obvious entry point for Stage 1
├── Dockerfile
├── .dockerignore
├── .gitignore
├── Makefile
├── requirements.txt
└── README.md
~~~

### File responsibilities

#### `main.py`

This is the canonical user-facing entry point.

Running:

~~~bash
python main.py
~~~

must execute the full real Stage 1 pipeline using the default raw-data and output locations.

It should orchestrate, conceptually:

~~~text
validate raw inputs
clean listing data
engineer listing features
aggregate calendar data
aggregate review data
join to one row per listing
run focused descriptive analysis
save analytical table
save summary tables
save figures
~~~

`main.py` should stay thin and call functions from `src/`; it should not contain the whole implementation itself.

#### `src/data.py`

Responsible for:

- raw file loading;
- required-column validation;
- key normalization;
- date parsing;
- price parsing;
- amenity parsing;
- raw/cleaned row diagnostics;
- join-ID diagnostics;
- variable-specific cleaning rules.

#### `src/features.py`

Responsible for:

- listing feature construction;
- amenity_count;
- host_type;
- fixed review-window features;
- calendar coverage features;
- calendar availability features;
- calendar aggregation;
- review aggregation.

#### `src/analysis.py`

Responsible for:

- required summary CSVs;
- required figures;
- report-threshold filtering;
- descriptive statistics used in Stage 1.

Figures must be **saved to `outputs/figures/`**.

Do not rely on interactive `plt.show()` as the delivery mechanism. The analysis must work in a headless Docker container.

#### `src/pipeline.py`

Responsible for connecting the major stages in the correct order and returning/writing final artifacts.

It should not duplicate transformation logic from the other modules.

#### `data/fixtures/`

Contains tiny committed synthetic datasets used by automated tests.

Fixtures should be designed to exercise boundary conditions and known expected outputs.

#### `docs/transcripts/`

Reserved for assignment-relevant Builder/Tester workflow transcripts or documentation if needed later.

---

## 7. Canonical commands the Builder must support

> **USER-REVIEWED DECISION — LOCKED**

The project must have one obvious command for the full Stage 1 pipeline:

~~~bash
python main.py
~~~

The README must document commands that actually work.

### Install dependencies

~~~bash
python -m pip install -r requirements.txt
~~~

### Run the full Stage 1 pipeline

~~~bash
python main.py
~~~

### Run tests

~~~bash
python -m pytest -v
~~~

### Build Docker image

~~~bash
docker build -t asheville-airbnb-analysis .
~~~

### Run real Stage 1 pipeline in Docker

~~~bash
docker run --rm \
  -v "$(pwd)/data/raw:/app/data/raw:ro" \
  -v "$(pwd)/outputs:/app/outputs" \
  asheville-airbnb-analysis
~~~

The Docker container's normal/default command must run the **real Stage 1 pipeline**, not a trivial demonstration, placeholder, shell command, or toy example.

### Makefile convenience commands

The Builder may provide convenience wrappers such as:

~~~bash
make install
make run
make test
make docker-build
make docker-run
~~~

These should invoke the same canonical commands rather than duplicate implementation logic.

---

## 8. Data acquisition and version-control strategy

> **USER-REVIEWED DECISION — LOCKED**

The repository must **not commit the full raw Inside Airbnb files**.

The README must instruct the user to download the Asheville 2026-06-25 versions of:

~~~text
listings.csv.gz
calendar.csv.gz
reviews.csv
~~~

and place them under:

~~~text
data/raw/
~~~

The pipeline should expect these exact filenames by default.

### .gitignore expectations

At minimum, ignore:

~~~text
data/raw/*
outputs/data/asheville_listing_features.csv
Python caches
pytest caches
local virtual environments
OS/editor temporary files
~~~

If empty directories need to be retained in Git, use a placeholder such as `.gitkeep`.

### .dockerignore expectations

At minimum, exclude from the Docker build context where appropriate:

~~~text
data/raw/
outputs/
.git/
.venv/
__pycache__/
.pytest_cache/
~~~

The Docker image should not contain the real raw dataset or stale generated artifacts from the host.

### Derived outputs

**ARCHITECT IMPLEMENTATION DETAIL**

The full one-row-per-listing analytical table is a required generated artifact but should not be committed by default because it remains row-level derivative data from the source.

Aggregate summary tables and figures may be committed if useful for course submission, but the pipeline must regenerate them deterministically.

### Test fixtures

> **USER-REVIEWED DECISION — LOCKED**

Commit tiny synthetic fixtures under:

~~~text
data/fixtures/
~~~

Do not use the real full raw datasets in automated unit tests.

---

## 9. Data grains and join architecture

The raw sources have different grains.

### Listings

Grain:

~~~text
one row = one Airbnb listing
~~~

Primary key:

~~~text
id
~~~

### Calendar

Grain:

~~~text
one row = one listing × one calendar date
~~~

Foreign key:

~~~text
listing_id -> listings.id
~~~

This is a one-to-many relationship from listings to calendar.

### Reviews

Grain:

~~~text
one row = one review-event/date record
~~~

Foreign key:

~~~text
listing_id -> listings.id
~~~

This is a one-to-many relationship from listings to reviews.

Multiple reviews for the same listing may occur on the same date, so review rows must not be deduplicated merely on `(listing_id, date)`.

### Safe join rule

> **USER-REVIEWED DECISION — LOCKED**

Never directly join raw calendar rows to raw review rows.

Required order:

~~~text
listings
   |
   +-- calendar -> aggregate to one row per listing_id
   |
   +-- reviews  -> aggregate to one row per listing_id
   |
   -> LEFT JOIN both aggregated feature tables to listings
~~~

This prevents a many-to-many row explosion.

The listing table is the authoritative base table for the final analytical dataset.

---

## 10. Raw-data validation rules

Validation occurs before analytical transformations.

### 10.1 Listings validation

Required checks:

- expected file is present;
- required columns are present;
- id is parseable and nonmissing for retained records;
- id is unique after key normalization;
- raw and cleaned row counts are recorded;
- required research variables are present.

Minimum required listing columns:

~~~text
id
host_id
neighbourhood_cleansed
property_type
room_type
accommodates
bedrooms
beds
price
amenities
calculated_host_listings_count
~~~

The Builder may retain additional columns for QA, but analysis should remain focused on the research questions.

### 10.2 Calendar validation

Minimum required columns:

~~~text
listing_id
date
available
~~~

Additional calendar columns (such as `minimum_nights`, `maximum_nights`) may be present and are ignored. The real 2026-06-25 calendar has no price field (Amendment A1).

Required checks:

- dates parse successfully where present;
- listing_id is normalized to the same key type used for listings.id;
- each `(listing_id, date)` should be unique;
- invalid availability values are counted;
- calendar dates used in future windows are assessed relative to SNAPSHOT_DATE.

**APPROVAL REQUIRED IF ENCOUNTERED:** If duplicate `(listing_id, date)` rows exist, do not silently deduplicate or average them. Report the number/pattern before choosing a resolution.

### 10.3 Reviews validation

Minimum required columns:

~~~text
listing_id
date
~~~

Required checks:

- review dates parse successfully where present;
- listing_id is normalized to the listing key type;
- rows later than SNAPSHOT_DATE are counted and excluded from historical activity features;
- repeated dates are allowed because multiple reviews can occur on one date.

### 10.4 Cross-table join diagnostics

> **USER-REVIEWED DECISION — LOCKED**

Compute and report:

- unique listing IDs in listings;
- unique listing IDs represented in calendar;
- unique listing IDs represented in reviews;
- calendar listing IDs not found in listings;
- review listing IDs not found in listings;
- proportion of listings with any calendar coverage;
- proportion of listings with at least one review row.

Unmatched calendar/review IDs must not create extra rows in the final table because listings is the left/base table.

These diagnostics must appear in `data_quality_summary.csv`.

---

## 11. Cleaning rules

### 11.1 General principle

> **USER-REVIEWED DECISION — LOCKED**

Do not apply a global missing-value strategy.

Missingness must be handled according to variable meaning.

Do not simply drop all incomplete listings and do not globally fill missing values with zero.

### 11.2 ID handling

**ARCHITECT IMPLEMENTATION DETAIL**

Normalize:

~~~text
listings.id
calendar.listing_id
reviews.listing_id
~~~

to a consistent key representation before comparisons or joins.

Do not alter identifier semantics.

### 11.3 Date handling

Parse calendar and review dates to date/datetime values before window filtering.

Analytical windows must use the exact rules in Section 13.

### 11.4 Listing price

Create a cleaned listing-level analytical price field:

~~~text
listing_price
~~~

Rules:

- strip currency formatting safely;
- convert to numeric;
- values <= 0 are invalid for price analysis;
- unparseable values are invalid;
- statistically extreme but positive, parseable values remain valid.

> **USER-REVIEWED DECISION — LOCKED:** Do not remove statistically extreme but plausible positive prices merely because they are IQR or z-score outliers.

**ARCHITECT IMPLEMENTATION DETAIL:** Preserve the listing row when price is invalid. Set the cleaned analytical price to missing and expose a validity flag/diagnostic rather than dropping the listing solely because of invalid price.

Descriptive price summaries should emphasize median, quartiles, and IQR.

Any later log transformation, winsorization, trimming, or robust-model treatment belongs to the conditional modeling stage and requires review.

### 11.5 Calendar price — removed (Amendment A1)

The real calendar file has no price field, so there is no calendar price parsing or calendar
price feature. `listing_price` (§11.4) is the only price measure.

### 11.6 Amenities

> **USER-REVIEWED DECISION — LOCKED**

Engineer only:

~~~text
amenity_count
~~~

Do not create individual amenity indicators.

The amenities field must be parsed as the serialized list structure.

Do not estimate amenity count by counting commas, brackets, or characters.

Rules:

- successfully parsed empty list -> `amenity_count = 0`;
- successfully parsed list -> list length;
- true missing value -> `amenity_count = NA`;
- malformed/unparseable list -> `amenity_count = NA` and record a parsing-failure diagnostic.

The parser must correctly handle amenity strings that themselves contain punctuation or commas.

### 11.7 Host listing count

Retain:

~~~text
calculated_host_listings_count
~~~

as numeric.

Derive only:

~~~text
host_type = "single" when calculated_host_listings_count == 1
host_type = "multi"  when calculated_host_listings_count > 1
~~~

Missing or invalid host counts must not be forced into a category.

Do not create additional host-size bins without approval.

### 11.8 Neighborhood

Use:

~~~text
neighbourhood_cleansed
~~~

as the main location variable.

Do not use GeoJSON or spatial joins in Stage 1.

### 11.9 Property type and room type

Retain original `property_type` values.

Use `room_type` as the primary compact listing-type category.

Do not combine rare property-type labels into arbitrary larger categories without approval.

---

## 12. Variable-specific missingness rules

### 12.1 Listing with no review rows

If a listing exists in listings but has no review rows at or before SNAPSHOT_DATE:

~~~text
reviews_last_30d  = 0
reviews_last_90d  = 0
reviews_last_180d = 0
last_review_date  = NA
days_since_last_review = NA
~~~

Reason: zero observed recent reviews is meaningful, but there is no last-review date from which recency can be calculated.

### 12.2 Insufficient calendar coverage

If a listing fails the required calendar-coverage threshold for a window:

- availability rate for that window = NA.

Do not substitute zero.

Zero availability means observed calendar records showed zero available dates. Missing means the metric could not be calculated reliably.

### 12.3 Missing/malformed amenities

- parsed empty list -> 0;
- missing -> NA;
- malformed/unparseable -> NA plus QA diagnostic.

### 12.4 Missing category fields

Do not invent categories such as "Other" or "Unknown" unless explicitly needed for presentation and clearly labeled.

Raw category missingness should remain observable.

---

## 13. Exact temporal windows

> **USER-REVIEWED DECISION — LOCKED**

All windows are deterministic relative to:

~~~text
SNAPSHOT_DATE = 2026-06-25
~~~

### 13.1 Future calendar windows

Use half-open intervals.

30-day future window:

~~~text
SNAPSHOT_DATE <= calendar_date < SNAPSHOT_DATE + 30 days
~~~

Expected dates:

~~~text
30
~~~

90-day future window:

~~~text
SNAPSHOT_DATE <= calendar_date < SNAPSHOT_DATE + 90 days
~~~

Expected dates:

~~~text
90
~~~

The start date is included. The upper boundary is excluded.

### 13.2 Review lookback windows

30-day review window:

~~~text
SNAPSHOT_DATE - 30 days < review_date <= SNAPSHOT_DATE
~~~

90-day review window:

~~~text
SNAPSHOT_DATE - 90 days < review_date <= SNAPSHOT_DATE
~~~

180-day review window:

~~~text
SNAPSHOT_DATE - 180 days < review_date <= SNAPSHOT_DATE
~~~

The lower boundary is excluded. SNAPSHOT_DATE is included.

These exact inequalities must be unit-tested.

---

## 14. Calendar coverage definitions

> **USER-REVIEWED DECISION — LOCKED**

For each listing and each 30/90-day future window, calculate:

~~~text
expected_dates
observed_dates
coverage_rate
~~~

Definitions:

~~~text
expected_dates_30 = 30
expected_dates_90 = 90

observed_dates_N =
number of unique valid calendar dates for the listing inside the N-day window

coverage_rate_N =
observed_dates_N / expected_dates_N
~~~

Minimum coverage requirement:

~~~text
coverage_rate >= 0.80
~~~

Therefore:

- 30-day features require at least 24 observed unique dates;
- 90-day features require at least 72 observed unique dates.

Exactly 80% qualifies.

If real-data inspection shows that this rule creates an unexpected systematic problem, the Builder must report it before changing the threshold.

### Availability-rate denominator

**ARCHITECT IMPLEMENTATION DETAIL**

After passing the coverage gate:

~~~text
availability_rate_N =
number of observed window dates marked available
/
number of observed window dates with valid availability status
~~~

Do not use expected_dates as the denominator because that would implicitly treat missing dates as unavailable.

A row with a valid date but an invalid or missing `available` value **counts as an observed date for coverage**, but is excluded from both the numerator and the denominator of the availability rate. Coverage and the availability denominator are deliberately separate.

If availability status itself is unexpectedly missing or malformed at a material rate, report the problem before changing the rule.

---

## 15. Calendar-derived feature definitions

### 15.1 Coverage/QA features

Required:

~~~text
calendar_expected_days_30
calendar_observed_days_30
calendar_coverage_rate_30
calendar_expected_days_90
calendar_observed_days_90
calendar_coverage_rate_90
calendar_has_data
~~~

### 15.2 Availability

For windows passing the 80% coverage rule:

~~~text
availability_rate_30d
availability_rate_90d
~~~

Otherwise:

~~~text
NA
~~~

Interpretation must always be "forward availability," not occupancy.

### 15.3–15.5 Calendar price, price variability and weekend premium — removed (Amendment A1)

The real calendar has no price field, so calendar median price, calendar price IQR, weekend and
weekday median prices, weekend premiums and their valid-price counts are not part of the project.

---

## 16. Review-derived feature definitions

Aggregate review rows by `listing_id`.

Required features:

~~~text
reviews_last_30d
reviews_last_90d
reviews_last_180d
last_review_date
days_since_last_review
~~~

Definitions:

~~~text
reviews_last_Nd =
number of review rows satisfying the exact N-day lookback interval

last_review_date =
latest review_date <= SNAPSHOT_DATE

days_since_last_review =
SNAPSHOT_DATE - last_review_date
~~~

Do not create an arbitrary weighted activity score in Stage 1.

Required invariant:

~~~text
reviews_last_30d <= reviews_last_90d <= reviews_last_180d
~~~

---

## 17. Required listing-derived analytical fields

The final analytical table must contain enough listing-side and engineered variables to support all four research questions.

At minimum:

~~~text
id
host_id
neighbourhood_cleansed
property_type
room_type
accommodates
bedrooms
beds
listing_price
listing_price_valid
amenity_count
calculated_host_listings_count
host_type
~~~

The Builder may retain additional QA/source fields if useful, but should not broaden the analytical scope without a research reason.

---

## 18. Aggregation and final join

### Calendar aggregation

Input:

~~~text
many calendar rows per listing
~~~

Output:

~~~text
one row per listing_id
~~~

The aggregated output must be unique on `listing_id` before joining.

### Review aggregation

Input:

~~~text
many review rows per listing
~~~

Output:

~~~text
one row per listing_id
~~~

The aggregated output must be unique on `listing_id` before joining.

### Final join

Use cleaned listings as the left/base table:

~~~text
cleaned_listings
LEFT JOIN calendar_features
    ON id = listing_id
LEFT JOIN review_features
    ON id = listing_id
~~~

After the join:

- exactly one row must remain per cleaned listing;
- final row count must equal cleaned listing row count;
- unmatched calendar/review IDs must not increase row count;
- listings with no child-table coverage remain present with the required missing/zero rules.

Required output:

~~~text
outputs/data/asheville_listing_features.csv
~~~

---

## 19. Reporting thresholds for categories

### 19.1 Neighborhoods

> **USER-REVIEWED DECISION — LOCKED**

Use `neighbourhood_cleansed`.

For the final neighborhood comparison and neighborhood figure:

~~~text
minimum listings per neighborhood = 10
~~~

A neighborhood with 9 listings is not report-eligible.

A neighborhood with 10 listings is report-eligible.

This threshold affects reporting and visualization only.

It must not remove listings from the analytical table.

Neighborhood summary statistics should emphasize:

- listing count;
- valid-price count;
- median listing price;
- Q1;
- Q3;
- IQR.

### 19.2 Room type

Use `room_type` as the primary categorical listing-type variable.

Do not impose a minimum-count threshold unless real inspection reveals an unexpected issue requiring review.

### 19.3 Property type

> **USER-REVIEWED DECISION — LOCKED**

Retain original `property_type` values in the analytical table.

For final property-type reporting:

~~~text
minimum listings per property_type = 10
~~~

Do not combine rare categories automatically.

Any regrouping requires approval.

---

## 20. Stage 1 descriptive-analysis modules

Exploration may inspect distributions and relationships needed to understand the data, but final reporting should remain selective.

Do not generate an "everything versus everything" EDA.

### Module A — Listing price structure

Focus on:

- listing_price by room_type;
- listing_price by report-eligible property_type;
- listing_price by report-eligible neighbourhood_cleansed;
- amenity_count versus listing_price;
- accommodates/bedrooms when useful for interpreting price relationships.

Use robust summaries such as median and IQR.

Do not delete extreme positive prices.

### Module B — Future availability and listing price

Focus on:

- availability_rate_30d;
- availability_rate_90d;
- listing_price (valid values only).

The required availability-versus-price figure uses:

~~~text
x = listing_price
y = availability_rate_90d
~~~

**ARCHITECT IMPLEMENTATION DETAIL:** Only rows with a valid `listing_price` and a nonmissing `availability_rate_90d` (coverage rule satisfied) appear in the figure. The relationship is descriptive only.

### Module C — Recent review activity

Focus on:

- reviews_last_30d;
- reviews_last_90d;
- reviews_last_180d;
- days_since_last_review.

Explore relationships with listing price, future availability, room type, or neighborhood only when useful for RQ3 or for identifying a potential later modeling question.

Do not infer bookings directly from review counts.

### Module D — Host portfolio structure

Compare single-listing and multi-listing hosts on relevant measures such as:

- listing price;
- future availability;
- amenity count;
- room type;
- recent review activity.

Keep `calculated_host_listings_count` numeric in the analytical table.

Do not add additional host-size bins without approval.

---

## 21. Required Stage 1 outputs

> **USER-REVIEWED DECISION — LOCKED**

The pipeline must generate all of the following.

### 21.1 Analytical dataset

~~~text
outputs/data/asheville_listing_features.csv
~~~

One row per cleaned listing.

### 21.2 Summary tables

~~~text
outputs/tables/data_quality_summary.csv
outputs/tables/neighborhood_summary.csv
outputs/tables/room_property_summary.csv
outputs/tables/host_type_summary.csv
~~~

#### data_quality_summary.csv

Must include compact metric/value diagnostics covering at least:

- raw listing row count;
- cleaned listing row count;
- unique listing IDs;
- unique calendar listing IDs;
- unique review listing IDs;
- unmatched calendar listing-ID count;
- unmatched review listing-ID count;
- proportion of listings with calendar coverage;
- proportion of listings with review coverage;
- invalid/unparseable listing prices;
- amenity parse failures;
- count/proportion passing 30-day calendar-coverage threshold;
- count/proportion passing 90-day calendar-coverage threshold;
- count of calendar rows with invalid `available` values.

#### neighborhood_summary.csv

At minimum:

- neighborhood;
- listing count;
- report-eligibility flag;
- valid-price count;
- median listing price;
- Q1;
- Q3;
- IQR.

The file may contain all neighborhoods for transparency.

Final reporting/figure must filter to neighborhoods with n >= 10.

#### room_property_summary.csv

Use a tidy schema that distinguishes room type from property type, for example:

~~~text
category_variable
category_value
n_listings
report_eligible
valid_price_count
median_price
q1_price
q3_price
iqr_price
~~~

Room type is primary.

Property types are report-eligible only at n >= 10.

#### host_type_summary.csv

At minimum compare single and multi hosts on relevant metrics such as:

- number of listings;
- median listing price;
- median amenity count;
- median availability_rate_90d when available;
- median reviews_last_90d;
- relevant room-type composition where practical.

---

## 22. Required figures

> **USER-REVIEWED DECISION — LOCKED**

All figures must be written to:

~~~text
outputs/figures/
~~~

Do not depend on interactive `plt.show()`.

The pipeline must work in a headless container.

Recommended filenames:

~~~text
outputs/figures/01_price_by_room_type.png
outputs/figures/02_amenities_vs_listing_price.png
outputs/figures/03_neighborhood_price_comparison.png
outputs/figures/04_future_availability_vs_price.png
~~~

### Figure 1 — Price by room type

Show listing-price distribution across room_type.

Do not remove plausible expensive listings solely as statistical outliers.

If extremes make a linear axis unreadable, a clearly labeled log-scaled axis may be used as a presentation choice without deleting observations.

### Figure 2 — Amenity count versus listing price

Show the relationship between `amenity_count` and `listing_price`.

The figure must support an association interpretation only.

### Figure 3 — Neighborhood price comparison

Include only neighborhoods with at least 10 listings.

Emphasize median and spread.

### Figure 4 — Future availability versus listing price

Use:

~~~text
x = listing_price
y = availability_rate_90d
~~~

Include only rows where both are nonmissing (valid listing price; 90-day coverage rule satisfied).

Do not label low availability as high occupancy.

### Optional Figure 5

A fifth figure is optional.

It may be added only if Stage 1 exploration reveals a meaningful result around:

- host structure;
- recent review activity.

Do not add a fifth figure merely to reach a target count.

---

## 23. Testing strategy

Tests must verify analytical meaning, not merely that functions execute.

### 23.1 Unit tests

#### Price parsing

Test:

- ordinary currency-formatted positive price -> expected numeric value;
- unparseable value -> missing/invalid;
- zero -> invalid;
- negative -> invalid;
- very large but positive, parseable price -> retained as valid.

#### Amenities parsing

Test:

~~~text
[] -> 0
["Wifi"] -> 1
["Wifi", "Kitchen"] -> 2
missing -> NA
malformed -> NA + parse-failure diagnostic
~~~

Include at least one amenity string containing punctuation or a comma to prove that the parser counts parsed list elements rather than delimiters.

#### Review-window boundaries

Using SNAPSHOT_DATE = 2026-06-25, verify:

- review_date == SNAPSHOT_DATE is included;
- review_date == SNAPSHOT_DATE - N days is excluded;
- review_date just inside the lower boundary is included.

Test the exact 30-, 90-, and 180-day logic.

#### Calendar-window boundaries

Verify:

- calendar_date == SNAPSHOT_DATE is included;
- calendar_date == SNAPSHOT_DATE + N days is excluded;
- the date immediately before the upper boundary is included.

Test both 30 and 90 days.

#### Coverage threshold

Verify:

- 24/30 qualifies;
- 23/30 does not;
- 72/90 qualifies;
- 71/90 does not.

Below-threshold derived calendar metrics must be NA rather than zero.

#### Coverage versus availability denominator

Verify that a row with a valid date but an invalid `available` value:

- counts as an observed calendar date for coverage; and
- is excluded from both the numerator and the denominator of the availability rate.

Verify that zero availability (all valid statuses unavailable) is a real value `0.0`, not NA.

### 23.2 Aggregation tests

Calendar aggregation must produce unique `listing_id`.

Review aggregation must produce unique `listing_id`.

Review aggregation must count review rows, not merely unique review dates.

### 23.3 Join tests

Verify:

- final analytical table row count equals cleaned listing row count;
- final id is unique;
- child-table unmatched IDs do not create new rows;
- a listing with no review records remains in the final table;
- a listing with no or insufficient calendar coverage remains in the final table.

### 23.4 Missingness tests

No reviews:

~~~text
reviews_last_30d = 0
reviews_last_90d = 0
reviews_last_180d = 0
days_since_last_review = NA
~~~

Insufficient calendar coverage:

~~~text
availability_rate = NA
~~~

not zero.

### 23.5 Domain/invariant tests

At minimum:

~~~text
0 <= availability_rate_30d <= 1 when present
0 <= availability_rate_90d <= 1 when present

reviews_last_30d <= reviews_last_90d
reviews_last_90d <= reviews_last_180d

amenity_count >= 0 when successfully parsed
~~~

### 23.6 Reporting-threshold tests

Verify:

- neighborhood n = 10 -> report eligible;
- neighborhood n = 9 -> not report eligible;
- property type n = 10 -> report eligible;
- property type n = 9 -> not report eligible.

These thresholds must not remove rows from the final analytical dataset.

### 23.7 Output tests

After a successful fixture-based pipeline run, verify that all required Stage 1 output files exist.

### 23.8 End-to-end fixture test

The tiny synthetic fixture set in `data/fixtures/` must pass through:

~~~text
load
-> validate
-> clean
-> build listing features
-> aggregate calendar
-> aggregate reviews
-> join
-> build summaries
-> generate required outputs
~~~

Expected values for key fixture listings should be known in advance so this is a real correctness test rather than only a smoke test.

---

## 24. Explicit acceptance invariants

> **USER-REVIEWED DECISION — LOCKED**

The Builder and Tester must treat the following as correctness requirements.

1. Cleaned listings have unique `id`.
2. Calendar aggregation has unique `listing_id`.
3. Review aggregation has unique `listing_id`.
4. Final analytical table has one row per cleaned listing.
5. Final joins do not increase listing count.
6. Availability rates are between 0 and 1 when present.
7. Review counts satisfy `reviews_last_30d <= reviews_last_90d <= reviews_last_180d`.
8. Listings with no reviews have zero review-window counts but missing `days_since_last_review`.
9. Listings without sufficient calendar coverage have calendar-derived features missing rather than zero.
10. `amenity_count >= 0` whenever amenities parsed successfully.
11. All required output files are generated successfully.
12. Every time-window calculation uses `SNAPSHOT_DATE = 2026-06-25`.
13. Calendar coverage threshold is 80% unless approval is obtained to change it.
14. `listing_price` is the only price measure; the analytical table contains no calendar price features, and calendar-derived features are limited to coverage/QA fields and availability rates (Amendment A1).
15. Final neighborhood reporting uses only neighborhoods with n >= 10.
16. Reported property-type comparisons use only property types with n >= 10.
17. Plausible positive price extremes are not automatically deleted.
18. Raw calendar and raw reviews are never directly many-to-many joined.
19. Full raw datasets are not committed.
20. Stage 1 does not require a statistical/predictive model.
21. `python main.py` executes the complete Stage 1 pipeline.
22. Required figures are written to `outputs/figures/` without requiring an interactive display.
23. The default Docker container command executes the real Stage 1 pipeline.
24. Mounted Docker outputs appear under the host `outputs/` directory.

---

## 25. Docker/container workflow

> **USER-REVIEWED DECISION — LOCKED**

The Docker image should contain:

- project code;
- Python runtime;
- dependencies;
- any files needed to execute the application.

The image must **not** contain:

- the full real Inside Airbnb raw datasets;
- permanently embedded generated Stage 1 outputs.

Raw data and outputs must be mounted at runtime.

Expected container paths:

~~~text
/app/data/raw
/app/outputs
~~~

Canonical workflow:

~~~bash
docker build -t asheville-airbnb-analysis .

docker run --rm \
  -v "$(pwd)/data/raw:/app/data/raw:ro" \
  -v "$(pwd)/outputs:/app/outputs" \
  asheville-airbnb-analysis
~~~

The raw-data mount should be read-only.

The Dockerfile's default command should execute the equivalent of:

~~~bash
python main.py
~~~

from the application directory.

The container must therefore:

1. read the mounted real raw data;
2. run the same validation/cleaning/feature pipeline used locally;
3. generate the same required Stage 1 artifacts; and
4. write them into the mounted `/app/outputs` directory so they appear on the host.

No Docker Compose is required.

A containerized test command may additionally be documented, but it does not replace the requirement that the default container execution runs the actual pipeline.

---

## 26. Headless plotting requirement

> **USER-REVIEWED DECISION — LOCKED**

All required figures must be saved as files.

The analysis must not depend on a graphical desktop session or interactive plotting window.

Required behavior:

~~~text
analysis creates figure
-> save to outputs/figures/<required_filename>.png
-> close/release figure
~~~

Interactive `plt.show()` may be omitted entirely.

If used during local exploration, it must not be required by `python main.py` and must not block headless Docker execution.

---

## 27. Data-quality reporting versus hard failures

**ARCHITECT IMPLEMENTATION DETAIL**

Not every anomaly should crash the pipeline.

### Hard-failure examples

- required input file missing;
- required column missing;
- cleaned listing ID cannot be made unique without an unresolved duplicate problem;
- duplicate calendar `(listing_id, date)` rows create unresolved aggregation ambiguity;
- final join increases listing row count;
- required outputs cannot be generated because of code failure.

### Diagnostic/nonfatal examples

- unmatched review listing IDs;
- unmatched calendar listing IDs;
- invalid listing prices;
- malformed amenities values;
- listings with insufficient calendar coverage;
- listings with no reviews;
- rare property types;
- neighborhoods below reporting threshold.

These should be visible in `data_quality_summary.csv` and/or concise pipeline logs rather than silently discarded.

If an unexpected anomaly requires a new cleaning rule that changes analytical meaning, the Builder must report it before inventing the rule.

---

## 28. Risks and interpretation caveats

The README and final descriptive discussion should preserve these caveats.

### 28.1 Availability is not occupancy

An unavailable calendar date may reflect a booking or a host-blocked date.

Therefore:

- call the measure forward availability;
- do not label `1 - availability_rate` as occupancy;
- do not infer booking demand directly.

### 28.2 Reviews are an imperfect activity proxy

Not every stay produces a review.

Recent review counts and recency are rough activity signals, not actual stay counts.

### 28.3 Price comes from listings only

`listing_price` is a snapshot listing-level quoted price used for cross-sectional comparisons.

The calendar file in this snapshot contains no price, so nothing here describes how prices vary by date, season or weekday. The project makes no dynamic-pricing claims, and `minimum_nights` is not a price substitute.

### 28.4 Listing prices are quoted prices

They are not transaction prices and do not prove what guests actually paid.

### 28.5 Snapshot design limits temporal claims

This project uses one Asheville snapshot.

It can describe cross-sectional and forward-calendar patterns from that snapshot but cannot establish long-run market trends.

### 28.6 Amenity count is intentionally simplified

`amenity_count` treats each listed amenity equally and does not distinguish amenity importance or quality.

A larger count is not automatically greater consumer utility.

### 28.7 Price associations are confounded

Listings with more amenities may also be larger, accommodate more guests, have more bedrooms, or be located in more expensive neighborhoods.

Stage 1 should describe associations rather than claim causal effects.

### 28.8 Extreme positive prices may be real

Luxury, large-property, or event-driven prices should not be deleted merely because they are statistically unusual.

### 28.9 Host portfolio measure is snapshot/context specific

`calculated_host_listings_count` should be interpreted according to listings captured in the Inside Airbnb scrape, not automatically as a host's complete global business portfolio.

### 28.10 Coverage thresholds are project rules

The 80% calendar-coverage threshold is an explicit project quality rule, not a universal truth.

### 28.11 Reporting thresholds affect presentation, not the dataset

Neighborhood/property-type n >= 10 thresholds reduce unstable small-group reporting.

They must not delete underlying listing rows.

### 28.12 Association is not causation

All Stage 1 relationships are descriptive.

---

## 29. Builder implementation sequence

A downstream Builder should implement in this order.

### Phase 1 — Repository skeleton

- create the file layout in Section 6;
- add `requirements.txt`;
- add `.gitignore`;
- add `.dockerignore`;
- add Makefile;
- add Dockerfile;
- create output directories;
- keep `main.py` as the single obvious Stage 1 entry point.

### Phase 2 — Fixtures and test contracts

- create tiny synthetic fixtures under `data/fixtures/`;
- encode temporal-boundary tests;
- encode missingness tests;
- encode calendar-coverage tests;
- encode coverage-vs-availability-denominator tests;
- encode reporting-threshold tests;
- encode join invariants.

### Phase 3 — Loading and validation

- implement raw loaders;
- validate required columns;
- normalize join-key types;
- implement join diagnostics;
- implement data-quality metrics.

### Phase 4 — Cleaning and listing features

- parse listing price;
- parse amenities;
- compute amenity_count;
- retain neighborhood/room/property/host variables;
- create host_type.

### Phase 5 — Calendar features

- apply fixed 30/90-day windows;
- compute coverage metrics;
- apply 80% gate;
- compute availability from valid `available` values only.

### Phase 6 — Review features

- apply fixed 30/90/180-day lookback windows;
- compute review counts;
- compute last-review date;
- compute days-since-last-review;
- apply no-review missingness rules.

### Phase 7 — Integration

- assert unique aggregated keys;
- left-join onto listings;
- verify row-count invariants;
- write `asheville_listing_features.csv`.

### Phase 8 — Descriptive outputs

- generate data-quality summary;
- generate neighborhood summary;
- generate room/property summary;
- generate host summary;
- generate four required figures;
- save figures to disk rather than showing them interactively.

### Phase 9 — Reproducibility

Verify locally:

~~~bash
python -m pip install -r requirements.txt
python main.py
python -m pytest -v
~~~

Then verify Docker:

~~~bash
docker build -t asheville-airbnb-analysis .

docker run --rm \
  -v "$(pwd)/data/raw:/app/data/raw:ro" \
  -v "$(pwd)/outputs:/app/outputs" \
  asheville-airbnb-analysis
~~~

### Phase 10 — Builder handoff

The Builder should report:

- any unexpected data-quality findings;
- any locked thresholds that create surprising loss of usable data;
- any proposed technical change requiring approval;
- confirmation that required outputs are produced;
- confirmation that tests pass;
- confirmation that Docker executes the real pipeline.

The Builder must not proceed directly into optional modeling.

---

## 30. Required manual smoke-test gate before Tester stage

> **USER-REVIEWED DECISION — LOCKED**

The assignment requires the project owner to manually verify the Builder implementation before an independent Tester stage begins.

This is a separate acceptance gate from the automated test suite.

After the Builder finishes Stage 1 implementation, the project owner should personally verify all of the following from a clean or reasonably clean environment:

1. setup instructions in README are understandable and complete;
2. dependencies install successfully with:

   ~~~bash
   python -m pip install -r requirements.txt
   ~~~

3. the full real pipeline completes without errors with:

   ~~~bash
   python main.py
   ~~~

4. the final listing-level analytical file is generated:

   ~~~text
   outputs/data/asheville_listing_features.csv
   ~~~

5. all four required summary CSVs are generated:

   ~~~text
   outputs/tables/data_quality_summary.csv
   outputs/tables/neighborhood_summary.csv
   outputs/tables/room_property_summary.csv
   outputs/tables/host_type_summary.csv
   ~~~

6. all four required figures are generated under `outputs/figures/`;
7. the figures are usable image files and do not require an interactive plotting window;
8. the automated tests pass with:

   ~~~bash
   python -m pytest -v
   ~~~

9. the Docker image builds successfully with:

   ~~~bash
   docker build -t asheville-airbnb-analysis .
   ~~~

10. the Docker container runs the actual Stage 1 pipeline successfully with:

   ~~~bash
   docker run --rm \
     -v "$(pwd)/data/raw:/app/data/raw:ro" \
     -v "$(pwd)/outputs:/app/outputs" \
     asheville-airbnb-analysis
   ~~~

11. outputs generated inside the container appear correctly in the host `outputs/` directory;
12. the README commands match the commands that actually worked during the manual test.

### Smoke-test documentation requirement

The result of this manual smoke test must later be documented in the Repository B README **before the independent Tester stage begins**.

The README smoke-test note should record, at minimum:

- that the manual verification was performed;
- whether local setup/run/test succeeded;
- whether Docker build/run succeeded;
- whether mounted outputs appeared correctly;
- any known issue that remains unresolved.

Do not begin the independent Tester stage until this manual smoke-test gate is complete.

The Tester should then compare the implementation against this plan independently rather than relying only on the Builder's own tests.

---

## 31. Conditional modeling checkpoint

> **USER-REVIEWED DECISION — LOCKED**

Modeling is **not guaranteed** and is not part of Stage 1's definition of done.

After Stage 1:

1. the project owner reviews the analytical table, summary tables, figures, and descriptive findings;
2. the owner decides whether a relationship is meaningful enough to model;
3. no model is implemented until `docs/plan.md` is updated.

If modeling is approved, the plan must be amended **before** the Builder writes modeling code to specify:

- exact target/outcome;
- predictor set;
- model family;
- baseline;
- train/test or validation design where applicable;
- evaluation metric(s);
- any price transformation;
- any trimming/winsorization/robust treatment;
- category handling;
- missingness handling;
- modeling-specific tests;
- modeling acceptance criteria.

The Tester must receive the updated specification before validating modeling behavior.

Stage 1 remains complete even if the modeling checkpoint results in a decision not to add a model.

---

## 32. Definition of done — Stage 1

Stage 1 is complete only when all requirements below are met.

### Purpose and data

- README clearly states project purpose and research questions.
- README documents the Asheville 2026-06-25 snapshot.
- README gives exact raw-data placement instructions.
- Full raw source files are not committed.

### Repository and command interface

- the repository follows the simple structure in Section 6;
- `requirements.txt` installs the required dependencies;
- `python main.py` is the obvious and documented full-pipeline command;
- `python -m pytest -v` is the documented test command;
- Docker commands in README match the working commands.

### Pipeline

- all three raw datasets load successfully;
- required validation executes;
- fixed temporal rules are used;
- listing/calendar/review features are constructed according to this plan;
- calendar and review tables are aggregated before joining;
- final table contains one row per cleaned listing.

### Required outputs

The pipeline generates:

~~~text
outputs/data/asheville_listing_features.csv

outputs/tables/data_quality_summary.csv
outputs/tables/neighborhood_summary.csv
outputs/tables/room_property_summary.csv
outputs/tables/host_type_summary.csv

outputs/figures/01_price_by_room_type.png
outputs/figures/02_amenities_vs_listing_price.png
outputs/figures/03_neighborhood_price_comparison.png
outputs/figures/04_future_availability_vs_price.png
~~~

The optional fifth figure is not required.

### Tests

- price parsing tests pass;
- amenities parsing tests pass;
- temporal-window boundary tests pass;
- 80% calendar threshold tests pass;
- coverage-versus-availability-denominator tests pass;
- variable-specific missingness tests pass;
- aggregation uniqueness tests pass;
- join invariants pass;
- category-reporting threshold tests pass;
- required output generation tests pass;
- one end-to-end fixture test passes.

### Reproducibility

- local dependency installation works;
- `python main.py` completes successfully;
- required output files are written;
- required figures are saved noninteractively;
- Docker image builds;
- Docker default command runs the real Stage 1 pipeline;
- raw data are mounted rather than embedded;
- output volume mount writes results back to the host;
- generated artifacts are deterministic given the same inputs and project version.

### Manual verification

- the project owner completes the smoke-test checklist in Section 30;
- smoke-test results are documented in README;
- only then is the project ready for independent Tester review.

### Analytical integrity

- no occupancy claims are made from availability;
- no booking-count claims are made from reviews;
- listing price is the only price measure; no calendar price is fabricated or substituted;
- statistically extreme but valid positive prices are not automatically deleted;
- small neighborhood/property categories are filtered only from reporting;
- no excluded-scope feature is added without approval.

When these conditions are met, Repository B has a complete Stage 1 project even if no model is added.

---

## 33. Locked decisions from project-owner review — consolidated checklist

The following choices were explicitly made or approved by the project owner and must be treated as fixed unless approval is obtained to revise them:

1. Use `listings.csv.gz` + `calendar.csv.gz` + `reviews.csv` only.
2. Use the Asheville snapshot dated 2026-06-25.
3. Make all temporal windows deterministic relative to SNAPSHOT_DATE.
4. Future windows are half-open: snapshot <= date < snapshot + N days.
5. Review windows use: snapshot - N days < review_date <= snapshot.
6. Distinguish zero activity from missing information.
7. Listing price is the project's only price measure; the 2026-06-25 calendar has no price field (Amendment A1).
8. (Removed by Amendment A1: calendar price features no longer exist.)
9. Calendar coverage must be measured explicitly.
10. Require >=80% calendar coverage before 30/90-day calendar-derived analytical features are valid.
11. Below-threshold calendar features are NA, not zero.
12.-15. (Removed by Amendment A1: weekend-premium rules no longer exist.)
16. Use only `amenity_count`; no individual amenity indicators.
17. Parse amenities as a list rather than counting delimiters.
18. Use `neighbourhood_cleansed` as the main location variable.
19. Final neighborhood reporting requires >=10 listings.
20. Use `room_type` as the main compact listing-type variable.
21. Preserve original `property_type` values.
22. Report property types only when n >= 10.
23. Do not regroup property types without approval.
24. Do not automatically delete plausible statistical price outliers.
25. Keep `calculated_host_listings_count` numeric.
26. Required host comparison is 1 versus >1; additional bins require inspection/approval.
27. Include explicit unmatched-ID and coverage diagnostics.
28. Stage 1 descriptive analysis is the required core deliverable.
29. Modeling is conditional on owner review after Stage 1.
30. Modeling requires a plan amendment before implementation.
31. Full raw datasets are not committed.
32. Tiny synthetic test fixtures are committed.
33. Docker contains code/dependencies; raw data and outputs are mounted volumes.
34. Docker default execution runs the real pipeline.
35. Required outputs are the analytical CSV, four summary CSVs, and four required figures.
36. Figures are saved to `outputs/figures/`; the pipeline must not depend on interactive `plt.show()`.
37. A fifth figure is optional and evidence-driven.
38. Do not add NLP, GeoJSON/spatial analysis, dashboards, databases, APIs, Docker Compose, or individual amenity indicators without explicit approval.
39. Keep the repository/file structure simple and close to the layout in Section 6.
40. `python main.py` is the canonical full Stage 1 command.
41. `python -m pip install -r requirements.txt` is the canonical dependency-install command.
42. `python -m pytest -v` is the canonical test command.
43. The manual smoke-test gate must occur after Builder implementation and before independent Tester review.
44. Smoke-test results must be documented in README before the Tester stage.
45. The acceptance invariants in Section 24 define correctness for Builder and Tester.

This checklist exists to preserve the technical decisions made during architecture review and make the downstream workflow unambiguous.
