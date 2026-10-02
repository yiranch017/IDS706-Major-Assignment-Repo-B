# Asheville Airbnb Reproducible Data Pipeline — Implementation Plan

## 1. Purpose of this document

This file is the implementation contract for Repository B of the IDS706 major assignment.

The project will build a reproducible data-analysis pipeline using the Asheville, North Carolina Inside Airbnb snapshot dated **2026-06-25**. The required Stage 1 deliverable is a tested, containerized pipeline that validates and combines listing, calendar, and review data into a one-row-per-listing analytical table and produces focused descriptive outputs tied to the research questions below.

This plan is intentionally detailed so that a separate Builder agent and a separate Tester agent can implement and verify the project without access to the prior architecture conversation.

### Decision provenance

The plan uses three labels:

- **USER-REVIEWED DECISION — LOCKED:** explicitly selected or approved by the project owner. The Builder must not change it silently.
- **ARCHITECT IMPLEMENTATION DETAIL:** a concrete implementation rule added to make the specification unambiguous while remaining consistent with the reviewed architecture.
- **APPROVAL REQUIRED:** a decision that must come back to the project owner before implementation changes.

If real-data inspection reveals that a locked threshold, rule, or assumption creates an unexpected problem, the Builder must report the issue and request approval before changing it.

---

## 2. Project purpose

The project will study the Asheville Airbnb market by examining how listing characteristics, neighborhood, pricing, future availability, recent review activity, and host portfolio structure relate to one another.

The main engineering product is not merely an exploratory notebook. It is a reproducible transformation pipeline that:

1. validates three raw Inside Airbnb sources;
2. cleans only variables relevant to the research questions;
3. aggregates calendar and review records from many rows per listing to one row per listing;
4. joins those features safely to the listing table;
5. produces a documented analytical dataset;
6. creates a small set of reproducible descriptive tables and figures;
7. verifies core data invariants with automated tests; and
8. runs locally and in Docker without baking raw third-party data into the image.

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

The amenities sub-question is specifically:

> Is a greater number of listed amenities associated with a higher listing price?

This is an association question. The project must not claim that more amenities are objectively better or more optimal for consumers.

### RQ2 — Dynamic pricing and future availability

How do future quoted prices vary across listings, including:

- 30-day and 90-day median future quoted price;
- 30-day and 90-day price variability;
- Friday/Saturday weekend price premium; and
- 30-day and 90-day forward availability?

How does forward availability relate to future quoted price?

### RQ3 — Recent review activity

Can recent review frequency and review recency serve as rough listing-activity signals, and how do those signals relate descriptively to price, availability, room type, or neighborhood?

Review activity is only a proxy. It must not be interpreted as a direct count of bookings or occupancy.

### RQ4 — Host portfolio structure

How do single-listing and multi-listing hosts differ descriptively in relevant listing characteristics such as:

- listing price;
- future pricing;
- future availability;
- amenity count;
- room type; and
- recent review activity?

For the required comparison, single-listing means calculated_host_listings_count == 1 and multi-listing means calculated_host_listings_count > 1.

---

## 4. Data sources and fixed snapshot

> **USER-REVIEWED DECISION — LOCKED**

Use exactly these three Asheville Inside Airbnb files from the **2026-06-25 snapshot**:

1. detailed listings: listings.csv.gz
2. detailed calendar: calendar.csv.gz
3. summary review dates: reviews.csv

Source page:

https://insideairbnb.com/get-the-data/

The project must document the source page, city, exact snapshot date, and expected filenames in the README.

### Fixed temporal reference

Define one project-wide constant:

~~~text
SNAPSHOT_DATE = 2026-06-25
~~~

All relative date features must be calculated from this fixed date. They must never depend on the date when the pipeline happens to run.

No use of system "today", current date, or execution timestamp is permitted for analytical window definitions.

---

## 5. Scope

### Required scope

- Python-based reproducible pipeline
- listings.csv.gz
- calendar.csv.gz
- reviews.csv
- listing-level feature engineering
- calendar aggregation
- review-date aggregation
- explicit join diagnostics
- focused descriptive analysis
- automated tests
- tiny committed test fixtures
- Docker image for code and dependencies
- mounted raw-data and output volumes
- clear setup/run/test documentation

### Explicitly excluded

> **USER-REVIEWED DECISION — LOCKED**

Do not add the following unless a later finding provides a strong reason and the project owner explicitly approves it:

- review-text NLP;
- detailed reviews.csv.gz for text analysis;
- GeoJSON or spatial analysis;
- maps requiring spatial joins;
- Streamlit or another dashboard;
- database infrastructure;
- API/service layer;
- Docker Compose;
- individual amenity indicators;
- arbitrary property-type regrouping;
- arbitrary host-size bins beyond 1 versus >1;
- automatic IQR-based price outlier deletion;
- guaranteed modeling.

The purpose is to keep the assignment substantial but realistic.

---

## 6. Proposed repository structure

The Builder should target a structure equivalent to the following. Small naming changes are acceptable only if responsibilities remain clearly separated.

~~~text
.
├── README.md
├── docs/
│   └── plan.md
├── pyproject.toml
├── Makefile
├── Dockerfile
├── .gitignore
├── data/
│   └── raw/
│       └── .gitkeep
├── outputs/
│   ├── data/
│   │   └── .gitkeep
│   ├── tables/
│   │   └── .gitkeep
│   └── figures/
│       └── .gitkeep
├── src/
│   └── airbnb_pipeline/
│       ├── __init__.py
│       ├── config.py
│       ├── io.py
│       ├── validation.py
│       ├── cleaning.py
│       ├── features.py
│       ├── analysis.py
│       └── pipeline.py
└── tests/
    ├── fixtures/
    │   ├── listings_fixture.csv
    │   ├── calendar_fixture.csv
    │   └── reviews_fixture.csv
    ├── test_validation.py
    ├── test_cleaning.py
    ├── test_features.py
    ├── test_aggregation.py
    ├── test_outputs.py
    └── test_pipeline.py
~~~

### Responsibility boundaries

- config.py: fixed dates, thresholds, file names, and project constants.
- io.py: reading raw sources and writing artifacts.
- validation.py: schema, key, coverage, and join diagnostics.
- cleaning.py: type normalization, price parsing, amenities parsing, invalid-value handling.
- features.py: listing features, calendar aggregation, review aggregation, host classification.
- analysis.py: required summary tables and figures.
- pipeline.py: orchestration only; it should call the other modules rather than contain all logic itself.
- tests/: unit, aggregation, invariant, output, and end-to-end tests.

The Builder may adjust module boundaries if necessary, but must preserve separation between loading, validation, cleaning, feature construction, analysis, and orchestration.

---

## 7. Data acquisition and version-control strategy

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

### .gitignore

At minimum, ignore:

~~~text
data/raw/*
!data/raw/.gitkeep
outputs/data/asheville_listing_features.csv
Python caches
pytest caches
local virtual environments
OS/editor temporary files
~~~

### Derived outputs

**ARCHITECT IMPLEMENTATION DETAIL**

The full one-row-per-listing analytical table is a required generated artifact but should not be committed by default, because it is still row-level derivative data from the source.

Aggregate summary tables and figures may be versioned if useful for the course submission because they do not reproduce the raw source table row-for-row. Regardless of whether they are committed, the pipeline must regenerate them deterministically.

### Test fixtures

> **USER-REVIEWED DECISION — LOCKED**

Commit tiny fixtures under tests/fixtures/.

Prefer synthetic fixtures designed specifically to exercise edge cases rather than copying a meaningful portion of the original raw dataset.

---

## 8. Data grains and join architecture

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
one row = one observed review event/date record
~~~

Foreign key:

~~~text
listing_id -> listings.id
~~~

This is a one-to-many relationship from listings to reviews.

Multiple reviews for the same listing may occur on the same date. Therefore the review table must not be deduplicated merely on (listing_id, date).

### Safe join rule

Never directly join raw calendar rows to raw review rows.

The required order is:

~~~text
listings
   |
   +-- calendar -> aggregate to one row per listing_id
   |
   +-- reviews  -> aggregate to one row per listing_id
   |
   -> LEFT JOIN both aggregated feature tables to listings
~~~

This avoids a many-to-many row explosion.

The listing table is the authoritative base table for the final analytical dataset.

---

## 9. Raw-data validation rules

Validation occurs before analytical transformations.

### 9.1 Listings validation

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

### 9.2 Calendar validation

Minimum required columns:

~~~text
listing_id
date
available
price
~~~

Required checks:

- dates parse successfully where present;
- listing_id is normalized to the same key type used for listings.id;
- each (listing_id, date) should be unique;
- price parsing failures are counted;
- invalid availability values are counted;
- dates used in future windows are assessed relative to SNAPSHOT_DATE.

**APPROVAL REQUIRED IF ENCOUNTERED:** If duplicate (listing_id, date) rows exist, do not silently deduplicate or average them. Report their number and inspect their pattern before choosing a resolution.

### 9.3 Reviews validation

Minimum required columns:

~~~text
listing_id
date
~~~

Required checks:

- review dates parse successfully where present;
- listing_id is normalized to the listing key type;
- rows later than SNAPSHOT_DATE are counted and excluded from historical activity features;
- repeated dates are allowed because multiple reviews can occur on the same date.

### 9.4 Cross-table join diagnostics

> **USER-REVIEWED DECISION — LOCKED**

Compute and report:

- unique listing IDs in listings;
- unique listing IDs represented in calendar;
- unique listing IDs represented in reviews;
- calendar listing IDs not found in listings;
- review listing IDs not found in listings;
- proportion of listings with any calendar coverage;
- proportion of listings with at least one review row.

Unmatched calendar/review IDs must not create extra rows in the final table because the final table uses listings as the left side of the join.

These diagnostics must be written into data_quality_summary.csv.

---

## 10. Cleaning rules

### 10.1 General principle

> **USER-REVIEWED DECISION — LOCKED**

Do not apply a global missing-value strategy.

Missingness must be handled according to variable meaning. Do not simply drop all incomplete listings and do not globally fill missing values with zero.

### 10.2 ID handling

**ARCHITECT IMPLEMENTATION DETAIL**

Normalize listings.id, calendar.listing_id, and reviews.listing_id to a consistent representation before comparison or joins. Do not alter identifier semantics.

### 10.3 Date handling

Parse calendar and review dates to date/datetime objects before window filtering.

Analytical windows must use the exact rules in Section 12.

### 10.4 Listing price

Create a cleaned listing-level price field, conceptually:

~~~text
listing_price
~~~

Rules:

- strip currency formatting safely;
- convert to numeric;
- values <= 0 are invalid for price analysis;
- unparseable values are invalid;
- statistically extreme but positive, parseable values are not automatically invalid.

> **USER-REVIEWED DECISION — LOCKED:** Do not remove statistically extreme but plausible positive prices merely because they are IQR or z-score outliers.

**ARCHITECT IMPLEMENTATION DETAIL:** Preserve the listing row when price is invalid. Set the cleaned analytical price to missing and record a validity flag/diagnostic rather than dropping the entire listing solely because price is invalid.

Descriptive price summaries should emphasize median, quartiles, and IQR.

Any later log transformation, winsorization, trimming, or robust-model choice belongs to the conditional modeling stage and requires explicit review.

### 10.5 Calendar price

Parse calendar price independently from listing price.

A valid quoted calendar price is:

- parseable numeric;
- positive.

Invalid calendar prices do not count as valid price observations.

Calendar price metrics are based on valid quoted prices regardless of whether the corresponding date is marked available. This keeps future pricing behavior conceptually separate from availability.

### 10.6 Amenities

> **USER-REVIEWED DECISION — LOCKED**

Engineer only:

~~~text
amenity_count
~~~

Do not create individual amenity indicators.

The amenities field must be parsed as the serialized list structure. Do not estimate amenity count by counting commas, brackets, or characters.

Rules:

- successfully parsed empty list -> amenity_count = 0;
- successfully parsed list -> amenity_count = length of list;
- true missing value -> amenity_count = NA;
- malformed/unparseable list -> amenity_count = NA and record a parsing failure diagnostic.

The parser must correctly handle an amenity string that itself contains punctuation or commas.

### 10.7 Host listing count

Retain:

~~~text
calculated_host_listings_count
~~~

as numeric.

Derive:

~~~text
host_type = "single" when calculated_host_listings_count == 1
host_type = "multi" when calculated_host_listings_count > 1
~~~

Missing or invalid host counts should not be forced into a category.

Do not create additional host-size bins without approval.

### 10.8 Neighborhood

Use:

~~~text
neighbourhood_cleansed
~~~

as the main location variable.

Do not use GeoJSON or spatial joins in Stage 1.

### 10.9 Property/room type

Retain original property_type values.

Use room_type as the primary compact listing-type category.

Do not combine rare property-type labels into arbitrary larger categories without approval.

---

## 11. Variable-specific missingness rules

### 11.1 No review rows

If a listing exists in listings but has no review rows at or before SNAPSHOT_DATE:

~~~text
reviews_last_30d  = 0
reviews_last_90d  = 0
reviews_last_180d = 0
last_review_date  = NA
days_since_last_review = NA
~~~

Reason: zero observed recent reviews is meaningful, but there is no last-review date from which recency can be calculated.

### 11.2 Insufficient calendar coverage

If a listing fails the required calendar-coverage threshold for a window:

- availability rate for that window = NA;
- calendar median price for that window = NA;
- calendar price IQR for that window = NA;
- any other dynamic-price metric tied to that window = NA.

Do not substitute zero.

Zero availability means observed calendar records showed zero available dates. Missing means the metric could not be calculated reliably.

### 11.3 Missing/malformed amenities

As defined above:

- parsed empty list -> 0;
- missing or malformed -> NA.

### 11.4 Missing category fields

Do not invent categories such as "Other" or "Unknown" unless explicitly required for display and clearly labeled. Raw category missingness should remain observable.

---

## 12. Exact temporal windows

> **USER-REVIEWED DECISION — LOCKED**

All windows are deterministic relative to:

~~~text
SNAPSHOT_DATE = 2026-06-25
~~~

### 12.1 Future calendar windows

Use half-open intervals.

30-day future window:

~~~text
SNAPSHOT_DATE <= calendar_date < SNAPSHOT_DATE + 30 days
~~~

Expected number of dates:

~~~text
30
~~~

90-day future window:

~~~text
SNAPSHOT_DATE <= calendar_date < SNAPSHOT_DATE + 90 days
~~~

Expected number of dates:

~~~text
90
~~~

The start date is included. The upper boundary is excluded.

### 12.2 Review lookback windows

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

These exact inequalities must be unit-tested at the boundary dates.

---

## 13. Calendar coverage definitions

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

If actual data inspection reveals that this project rule causes an unexpected systematic problem, the Builder must report it before changing the threshold.

### Availability-rate denominator

**ARCHITECT IMPLEMENTATION DETAIL**

After passing the coverage gate, calculate:

~~~text
availability_rate_N =
number of observed window dates marked available
/
number of observed window dates with valid availability status
~~~

Do not use expected_dates as the denominator because doing so would implicitly treat missing calendar dates as unavailable.

If availability values themselves are unexpectedly missing or malformed at a material rate, report this before modifying the rule.

---

## 14. Calendar-derived feature definitions

### 14.1 Required coverage/QA features

For both 30 and 90 days:

~~~text
calendar_expected_days_30
calendar_observed_days_30
calendar_coverage_rate_30
calendar_expected_days_90
calendar_observed_days_90
calendar_coverage_rate_90
~~~

Recommended transparency fields:

~~~text
calendar_valid_price_days_30
calendar_valid_price_days_90
calendar_has_data
~~~

### 14.2 Availability

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

### 14.3 Median future quoted price

For each qualifying window, use all valid positive quoted calendar prices inside the window, regardless of available status.

Required:

~~~text
calendar_median_price_30d
calendar_median_price_90d
~~~

If coverage is below 80%, return NA.

If there are no valid positive quoted prices despite sufficient date coverage, return NA and expose the valid-price count in QA.

### 14.4 Future price variability

Use IQR as the primary robust variability measure:

~~~text
calendar_price_iqr_N =
Q75(valid quoted calendar price in window N)
-
Q25(valid quoted calendar price in window N)
~~~

Required:

~~~text
calendar_price_iqr_30d
calendar_price_iqr_90d
~~~

Reason: quoted Airbnb prices may contain legitimate event/holiday extremes; IQR is less sensitive than standard deviation.

Do not delete extreme positive calendar prices merely to reduce IQR.

### 14.5 Weekend-price premium

> **USER-REVIEWED DECISION — LOCKED**

Define weekend nights as:

~~~text
Friday
Saturday
~~~

Use the 90-day future window.

The 90-day window must first satisfy the overall 80% calendar coverage requirement.

Within that window, use valid positive quoted prices regardless of availability status.

Define:

~~~text
weekend_median_price_90d =
median(valid Friday/Saturday quoted prices)

weekday_median_price_90d =
median(valid Sunday-Thursday quoted prices)
~~~

Observation thresholds:

~~~text
valid weekend prices >= 8
valid weekday prices >= 20
~~~

If either threshold fails, both premium measures must be NA.

Absolute premium:

~~~text
weekend_premium_abs_90d =
weekend_median_price_90d
-
weekday_median_price_90d
~~~

Percentage premium:

~~~text
weekend_premium_pct_90d =
(weekend_median_price_90d - weekday_median_price_90d)
/
weekday_median_price_90d
~~~

Because all valid prices are positive, the denominator should be positive. If it is not, treat the percentage premium as invalid/missing and report the anomaly.

Keep both absolute and percentage forms in the analytical table.

Use the **percentage premium** as the primary form for descriptive reporting because it is comparable across cheap and expensive listings.

Required transparency counts:

~~~text
weekend_valid_price_count_90d
weekday_valid_price_count_90d
~~~

The Builder must not silently change the 8/20 observation thresholds.

---

## 15. Review-derived feature definitions

Aggregate review rows by listing_id.

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

Do not create an arbitrary weighted "activity score" in Stage 1.

Counts and recency should remain directly interpretable.

Expected invariant:

~~~text
reviews_last_30d <= reviews_last_90d <= reviews_last_180d
~~~

---

## 16. Required listing-derived analytical fields

The final analytical table must contain, at minimum, enough source and engineered variables to support all research questions.

Required listing-side fields:

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

The Builder may retain additional QA/source fields if they help validation, but should not expand the descriptive scope without a research reason.

---

## 17. Aggregation and final join

### Calendar aggregation

Input:

~~~text
many calendar rows per listing
~~~

Output:

~~~text
one row per listing_id
~~~

The output must be unique on listing_id before joining.

### Review aggregation

Input:

~~~text
many review rows per listing
~~~

Output:

~~~text
one row per listing_id
~~~

The output must be unique on listing_id before joining.

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
- listings with no child-table coverage remain present with appropriate missing/zero rules.

Required output:

~~~text
outputs/data/asheville_listing_features.csv
~~~

---

## 18. Reporting thresholds for categories

### 18.1 Neighborhoods

> **USER-REVIEWED DECISION — LOCKED**

Use neighbourhood_cleansed.

For the final reported neighborhood comparison and neighborhood figure:

~~~text
minimum listings per neighborhood = 10
~~~

A neighborhood with 9 listings is not report-eligible. A neighborhood with 10 listings is.

This threshold affects only neighborhood-level reporting and visualization.

It must **not** remove those listings from the analytical table.

The neighborhood summary CSV should retain counts for transparency and should clearly indicate which neighborhoods meet the reporting threshold.

Primary price statistics:

- listing count;
- median listing price;
- Q1;
- Q3;
- IQR.

### 18.2 Room type

Use room_type as the primary categorical listing-type variable.

Do not force a minimum-count threshold unless an actual unexpected data issue makes one necessary. Report such an issue before changing the design.

### 18.3 Property type

> **USER-REVIEWED DECISION — LOCKED**

Retain original property_type values in the analytical table.

For final reported property-type summaries:

~~~text
minimum listings per property_type = 10
~~~

Do not combine rare categories automatically.

Any category regrouping requires approval.

---

## 19. Stage 1 descriptive-analysis modules

Exploration may inspect distributions and relationships needed to understand the data, but final reporting should remain selective.

The project should not generate an "everything versus everything" EDA.

### Module A — Listing price structure

Focus on:

- listing_price by room_type;
- listing_price by report-eligible property_type;
- listing_price by report-eligible neighbourhood_cleansed;
- amenity_count versus listing_price;
- accommodates/bedrooms as contextual variables when needed to interpret price patterns.

Use robust summaries such as median/IQR.

Do not delete extreme positive prices.

### Module B — Dynamic pricing and future availability

Focus on:

- calendar_median_price_30d and 90d;
- calendar_price_iqr_30d and 90d;
- weekend_premium_pct_90d;
- availability_rate_30d and 90d.

The required availability-versus-price figure should use:

~~~text
calendar_median_price_90d
vs.
availability_rate_90d
~~~

**ARCHITECT IMPLEMENTATION DETAIL:** These two features use the same future horizon, avoiding an unnecessary mismatch between a snapshot listing price and a 90-day availability measure.

Listing_price may be inspected secondarily against availability if useful, but should not replace the required aligned 90-day relationship without approval.

### Module C — Recent review activity

Focus on:

- reviews_last_30d;
- reviews_last_90d;
- reviews_last_180d;
- days_since_last_review.

Explore their relationships with relevant listing price, availability, room type, or neighborhood variables only when useful for answering RQ3 or identifying a possible later modeling question.

Do not infer bookings directly from review counts.

### Module D — Host portfolio structure

Use:

~~~text
single: calculated_host_listings_count == 1
multi:  calculated_host_listings_count > 1
~~~

Compare relevant descriptive measures including:

- listing price;
- calendar median price;
- availability;
- amenity count;
- room type;
- recent review activity.

Keep calculated_host_listings_count numeric in the analytical table.

Do not add additional host-size bins unless approved after inspecting the distribution.

---

## 20. Required Stage 1 outputs

> **USER-REVIEWED DECISION — LOCKED**

The pipeline must generate all of the following successfully.

### 20.1 Analytical dataset

~~~text
outputs/data/asheville_listing_features.csv
~~~

One row per cleaned listing.

### 20.2 Summary tables

~~~text
outputs/tables/data_quality_summary.csv
outputs/tables/neighborhood_summary.csv
outputs/tables/room_property_summary.csv
outputs/tables/host_type_summary.csv
~~~

#### data_quality_summary.csv

Should contain compact metric/value-style diagnostics covering at least:

- raw and cleaned listing row counts;
- unique listing IDs;
- unique calendar listing IDs;
- unique review listing IDs;
- unmatched calendar ID count;
- unmatched review ID count;
- proportion of listings with calendar coverage;
- proportion of listings with review coverage;
- listing price parse/validity failures;
- amenity parse failures;
- count/proportion passing 30-day calendar coverage threshold;
- count/proportion passing 90-day calendar coverage threshold;
- count/proportion with calculable weekend premium.

#### neighborhood_summary.csv

At minimum:

- neighborhood;
- listing count;
- report eligibility flag for n >= 10;
- valid-price count;
- median listing price;
- Q1;
- Q3;
- IQR.

The file may contain all neighborhoods for transparency, but final reporting/figure must filter to report-eligible neighborhoods.

#### room_property_summary.csv

Use a tidy schema that distinguishes room_type from property_type, for example via:

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

Room types are primary.

Property types are report-eligible only at n >= 10.

#### host_type_summary.csv

At minimum compare single and multi hosts on relevant metrics such as:

- n listings;
- median listing price;
- median amenity count;
- median availability_rate_90d where available;
- median calendar_median_price_90d where available;
- median reviews_last_90d;
- relevant room-type composition where practical.

The exact table layout may be tidy/long or wide, but must remain human-readable and reproducible.

---

## 21. Required figures

> **USER-REVIEWED DECISION — LOCKED**

Generate four required figures under:

~~~text
outputs/figures/
~~~

Recommended deterministic filenames:

~~~text
01_price_by_room_type.png
02_amenities_vs_listing_price.png
03_neighborhood_price_comparison.png
04_future_availability_vs_price.png
~~~

### Figure 1 — Price by room type

Show listing-price distribution across room_type.

Do not remove plausible expensive listings solely as statistical outliers.

If extreme values make a linear plot unreadable, a clearly labeled log-scaled axis may be considered as a presentation choice without deleting data; the Builder should document that choice.

### Figure 2 — Amenity count versus listing price

Show the relationship between amenity_count and listing_price.

The visualization should support an association interpretation only.

A scatter/transparent-point display, binned robust summaries, or another clearly descriptive approach is acceptable as long as no causal interpretation is implied.

### Figure 3 — Neighborhood price comparison

Include only neighborhoods with at least 10 listings.

Emphasize median and spread rather than mean alone.

### Figure 4 — Future availability versus price

Required primary variables:

~~~text
x: calendar_median_price_90d
y: availability_rate_90d
~~~

Use only listings for which both variables are nonmissing under the locked coverage rules.

Do not call low availability "high occupancy."

### Optional Figure 5

A fifth figure is not required.

It may be added only if Stage 1 exploration reveals a meaningful result around:

- host structure;
- recent reviews/activity;
- weekend pricing.

Do not add a fifth figure merely to reach a number.

---

## 22. Testing strategy

Tests must verify analytical meaning, not just that functions execute.

### 22.1 Unit tests

#### Price parsing

Test examples including:

- normal currency-formatted positive price -> expected numeric value;
- unparseable value -> missing/invalid flag;
- zero price -> invalid;
- negative price -> invalid;
- very large but positive, parseable price -> retained as valid and not removed automatically.

#### Amenities parsing

Test:

~~~text
[] -> 0
["Wifi"] -> 1
["Wifi", "Kitchen"] -> 2
missing -> NA
malformed -> NA + parse failure
~~~

Include at least one amenity string containing a comma or punctuation to prove that count is based on parsed list length rather than delimiter counting.

#### Review-window boundaries

With SNAPSHOT_DATE = 2026-06-25, test explicitly that:

- review_date == SNAPSHOT_DATE is included;
- review_date == SNAPSHOT_DATE - N days is excluded;
- review_date one day after the lower bound is included.

Test N = 30 and at least one of 90/180, preferably all three.

#### Calendar-window boundaries

Test that:

- calendar_date == SNAPSHOT_DATE is included;
- calendar_date == SNAPSHOT_DATE + N days is excluded;
- the date immediately before the upper bound is included.

Test both 30 and 90 days.

#### Coverage threshold

Test:

- exactly 24/30 qualifies;
- 23/30 does not;
- exactly 72/90 qualifies;
- 71/90 does not.

When below threshold, derived calendar metrics must be NA rather than zero.

#### Weekend premium thresholds

Test:

- 8 valid weekend and 20 valid weekday prices + sufficient coverage -> premium calculated;
- 7 weekend + 20 weekday -> NA;
- 8 weekend + 19 weekday -> NA;
- insufficient overall 90-day coverage -> NA regardless of group counts.

Verify both absolute and percentage formulas.

### 22.2 Aggregation tests

Calendar aggregation must produce unique listing_id.

Review aggregation must produce unique listing_id.

Review aggregation must count review rows, not merely unique review dates.

### 22.3 Join tests

Verify:

- final analytical table row count equals cleaned listing row count;
- final id is unique;
- child-table unmatched IDs do not create rows;
- a listing with no review records remains in final table;
- a listing with no/insufficient calendar coverage remains in final table.

### 22.4 Missingness tests

Explicitly verify:

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
calendar_median_price = NA
calendar_price_iqr = NA
~~~

not zero.

### 22.5 Domain/invariant tests

At minimum:

~~~text
0 <= availability_rate_30d <= 1 when present
0 <= availability_rate_90d <= 1 when present

reviews_last_30d <= reviews_last_90d
reviews_last_90d <= reviews_last_180d

amenity_count >= 0 when successfully parsed
~~~

### 22.6 Reporting-threshold tests

Test:

- neighborhood n = 10 -> report eligible;
- neighborhood n = 9 -> not report eligible;
- property type n = 10 -> report eligible;
- property type n = 9 -> not report eligible.

These thresholds must not remove rows from the final analytical dataset.

### 22.7 Output tests

Verify that all required Stage 1 files exist after a successful test-fixture pipeline run.

### 22.8 End-to-end fixture test

A tiny synthetic fixture set must pass through:

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

Expected output values for key fixture listings should be known in advance so this is a real correctness test, not only a smoke test.

---

## 23. Explicit acceptance invariants

> **USER-REVIEWED DECISION — LOCKED**

The Builder and Tester must treat the following as correctness requirements.

1. Cleaned listings have unique id.
2. Calendar aggregation has unique listing_id.
3. Review aggregation has unique listing_id.
4. Final analytical table has one row per cleaned listing.
5. Final joins do not increase listing count.
6. Availability rates are between 0 and 1 when present.
7. Review counts satisfy reviews_last_30d <= reviews_last_90d <= reviews_last_180d.
8. Listings with no reviews have zero review-window counts but missing days_since_last_review.
9. Listings without sufficient calendar coverage have calendar-derived features missing rather than zero.
10. amenity_count >= 0 whenever amenities parsed successfully.
11. All required output files are generated successfully.

Additional project-level invariants from this plan:

12. Every time-window calculation uses SNAPSHOT_DATE = 2026-06-25 rather than execution date.
13. Calendar coverage threshold is 80% unless approval is obtained to change it.
14. Weekend premium uses Friday/Saturday, a 90-day window, >=8 valid weekend prices, and >=20 valid weekday prices.
15. The final reported neighborhood comparison uses only neighborhoods with n >= 10.
16. Reported property-type comparisons use only property types with n >= 10.
17. Plausible positive price extremes are not automatically deleted.
18. Raw calendar and raw reviews are never directly many-to-many joined.
19. Full raw datasets are not committed to the repository.
20. Stage 1 does not require a predictive/statistical model.

---

## 24. Docker/container workflow

> **USER-REVIEWED DECISION — LOCKED**

The Docker image should contain:

- project code;
- Python runtime;
- dependencies;
- tests as needed for containerized testing.

The image should **not** contain the full raw Airbnb datasets or permanently embed generated outputs.

Raw data and outputs must be mounted at runtime.

Conceptual container paths:

~~~text
/app/data/raw
/app/outputs
~~~

Example workflow the Builder should support:

~~~bash
docker build -t asheville-airbnb-pipeline .

docker run --rm   -v "$(pwd)/data/raw:/app/data/raw:ro"   -v "$(pwd)/outputs:/app/outputs"   asheville-airbnb-pipeline
~~~

The raw-data mount should be read-only where practical.

No Docker Compose is required.

A containerized test command should also be supported, either by overriding the default command or via a documented test invocation.

---

## 25. Local setup/run/test interface

The Builder should make the project runnable through simple documented commands.

### Required behaviors

#### Install/setup

Preferred developer workflow:

~~~bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
~~~

The README should also note the Windows activation equivalent if needed.

#### Run tests

~~~bash
pytest -q
~~~

#### Run the Stage 1 pipeline

Preferred module interface:

~~~bash
python -m airbnb_pipeline.pipeline   --raw-dir data/raw   --output-dir outputs
~~~

Equivalent CLI naming is acceptable if documented consistently.

### Makefile convenience interface

The Builder should support simple wrappers such as:

~~~bash
make install
make test
make run
make docker-build
make docker-run
~~~

The Makefile should call the same canonical implementation rather than duplicate logic.

### Successful pipeline behavior

A normal run should:

1. verify expected inputs;
2. validate schemas/keys;
3. emit or record data-quality diagnostics;
4. clean relevant variables;
5. aggregate calendar;
6. aggregate reviews;
7. join features;
8. write the final analytical table;
9. write the four required summary tables;
10. generate the four required figures;
11. fail clearly on unrecoverable contract violations rather than silently producing misleading output.

---

## 26. Data-quality reporting versus hard failures

**ARCHITECT IMPLEMENTATION DETAIL**

Not every anomaly should crash the pipeline.

### Hard-failure examples

- required input file missing;
- required column missing;
- cleaned listing id cannot be made unique without an unresolved duplicate problem;
- calendar duplicate (listing_id, date) issue that would materially affect aggregation and has not been approved/resolved;
- final join increases listing row count;
- required output cannot be generated because of a code failure.

### Diagnostic/nonfatal examples

- unmatched review listing IDs;
- unmatched calendar listing IDs;
- invalid listing price values;
- malformed amenities values;
- listings with insufficient calendar coverage;
- listings with no reviews;
- rare property types;
- neighborhoods below the reporting threshold.

These should be visible in data_quality_summary.csv and/or logs rather than silently discarded.

If an unexpected anomaly requires a new cleaning rule, the Builder must report it before inventing a rule that changes analytical meaning.

---

## 27. Risks and interpretation caveats

The README/reporting should state these clearly.

### 27.1 Availability is not occupancy

An unavailable calendar date may reflect a booking or a host-blocked date. Therefore:

- call the measure forward availability;
- do not label 1 - availability_rate as occupancy;
- do not infer booking demand directly.

### 27.2 Reviews are an imperfect activity proxy

Not every stay produces a review. Recent review counts and recency can be treated as rough activity signals, not actual stay counts.

### 27.3 Listing price and calendar price are different concepts

listing_price is a snapshot listing-level quoted price used primarily for cross-sectional comparisons.

calendar_median_price_Nd is derived from dated future quoted prices and measures future pricing behavior.

Do not silently substitute one for the other.

### 27.4 Calendar prices are asking/quoted prices

They are not transaction prices and do not prove what guests actually paid.

### 27.5 Snapshot design limits temporal claims

This project uses one Asheville snapshot. It can describe cross-sectional and forward-calendar patterns from that snapshot but cannot establish long-run market trends.

### 27.6 Amenity count is intentionally simplified

amenity_count treats each listed amenity equally and does not distinguish amenity importance or quality.

A larger count is not automatically greater consumer utility.

### 27.7 Price associations are confounded by property characteristics

A listing with more amenities may also be larger, have more bedrooms, accommodate more guests, or be located in a more expensive neighborhood.

Stage 1 should describe these relationships rather than claim causal effects.

### 27.8 Extreme positive prices may be real

Luxury/large/event-driven prices should not be deleted merely because they are statistically unusual.

### 27.9 Host portfolio measure is snapshot/context specific

calculated_host_listings_count should be interpreted according to the listings captured in the Inside Airbnb scrape, not automatically as a host's complete global business portfolio.

### 27.10 Coverage thresholds are project design rules

The 80% calendar threshold and 8/20 weekend/weekday observation rules are explicit quality rules selected for this project. They are not universal truths.

### 27.11 Reporting thresholds affect presentation, not the dataset

Neighborhood/property-type n >= 10 thresholds are designed to reduce unstable small-group reporting. They must not delete underlying listing rows.

### 27.12 Association is not causation

All Stage 1 relationships are descriptive.

---

## 28. Conditional modeling checkpoint

> **USER-REVIEWED DECISION — LOCKED**

Modeling is **not guaranteed** and is not part of Stage 1's definition of done.

After Stage 1:

1. the project owner reviews the analytical table, summary tables, figures, and descriptive findings;
2. the owner decides whether a relationship is meaningful enough to model;
3. no model is implemented until docs/plan.md is updated.

If modeling is approved, the plan must be amended **before the Builder writes modeling code** to specify:

- exact target/outcome;
- predictor set;
- model family;
- baseline;
- train/test or validation design where applicable;
- evaluation metric(s);
- any price transformation;
- any trimming/winsorization/robust treatment;
- handling of categories/missingness;
- modeling-specific tests and acceptance criteria.

The Tester must receive this updated specification before validating modeling behavior.

Stage 1 remains valid and complete even if the modeling checkpoint results in a decision not to add a model.

---

## 29. Builder implementation sequence

A downstream Builder should implement in this order.

### Phase 1 — Project skeleton

- create package/module structure;
- add project dependencies;
- add configuration constants;
- add .gitignore;
- add Makefile;
- add Dockerfile;
- create output directories/placeholders.

### Phase 2 — Fixtures and tests first

- create tiny synthetic fixtures;
- encode temporal-boundary tests;
- encode missingness tests;
- encode coverage tests;
- encode weekend-premium tests;
- encode join invariants.

The Builder does not need perfect test completeness before implementation, but should establish the contracts early.

### Phase 3 — Loading and validation

- implement raw loaders;
- validate required columns;
- normalize join-key types;
- implement join diagnostics;
- implement data-quality metrics.

### Phase 4 — Cleaning and listing features

- parse listing price;
- parse amenity list;
- compute amenity_count;
- retain neighborhood/room/property/host variables;
- create host_type.

### Phase 5 — Calendar features

- enforce fixed 30/90-day windows;
- compute coverage metrics;
- apply 80% gate;
- compute availability;
- compute median/IQR future prices;
- compute 90-day weekend premiums with 8/20 observation rules.

### Phase 6 — Review features

- enforce fixed lookback windows;
- compute 30/90/180-day counts;
- compute last review date and days-since-last-review;
- apply no-review missingness rules.

### Phase 7 — Integration

- assert unique aggregated keys;
- left-join to listings;
- assert one row per cleaned listing;
- write asheville_listing_features.csv.

### Phase 8 — Descriptive outputs

- generate data-quality summary;
- generate neighborhood summary with n >= 10 reporting flag;
- generate room/property summary;
- generate host summary;
- generate four required figures.

### Phase 9 — Reproducibility

- verify clean local run from documented commands;
- verify pytest;
- build Docker image;
- run with mounted raw/output volumes;
- verify outputs match required contract.

### Phase 10 — Handoff

Report to the project owner:

- any unexpected data-quality findings;
- any thresholds that create surprising loss of usable data;
- any proposed technical change requiring approval;
- Stage 1 descriptive findings;
- whether a modeling question appears potentially worthwhile.

Do not implement a model during this handoff.

---

## 30. Definition of done — Stage 1

Stage 1 is complete when all of the following are true:

### Purpose and data

- README clearly states the project purpose and research questions.
- README documents the Asheville 2026-06-25 snapshot.
- README gives exact raw-data download/placement instructions.
- Raw source files are not committed.

### Pipeline

- all three raw datasets load successfully;
- required validation executes;
- fixed temporal rules are used;
- listing/calendar/review features are constructed according to this plan;
- calendar and reviews are aggregated before joining;
- final table contains one row per cleaned listing.

### Outputs

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

- unit tests cover key parsers and feature formulas;
- time-window boundaries are tested;
- 80% calendar threshold boundaries are tested;
- weekend 8/20 thresholds are tested;
- missingness rules are tested;
- aggregation uniqueness is tested;
- join invariants are tested;
- category-reporting thresholds are tested;
- required output generation is tested;
- one end-to-end fixture test passes.

### Reproducibility

- local setup/run/test commands are documented and work;
- Docker image builds;
- Docker pipeline runs with raw-data/output volume mounts;
- Docker does not embed full raw Airbnb data;
- generated artifacts are deterministic given the same input files and project version.

### Analytical integrity

- no occupancy claims are made from availability;
- no booking-count claims are made from reviews;
- listing price and calendar-derived prices are kept conceptually separate;
- statistically extreme but valid positive prices are not automatically deleted;
- small neighborhood/property categories are filtered only from reporting, not from the analytical dataset;
- no excluded-scope features are added without approval.

When these conditions are met, the assignment has a complete Stage 1 project even if no model is ever added.

---

## 31. Locked decisions from project-owner review — consolidated checklist

The following choices were explicitly made or approved by the project owner and must be treated as fixed unless approval is obtained to revise them:

1. Use listings.csv.gz + calendar.csv.gz + reviews.csv only.
2. Use the Asheville snapshot dated 2026-06-25.
3. Make all temporal windows deterministic relative to SNAPSHOT_DATE.
4. Future windows are half-open: snapshot <= date < snapshot + N days.
5. Review windows use: snapshot - N days < review_date <= snapshot.
6. Distinguish zero activity from missing information.
7. Listing price is for cross-sectional listing analysis; calendar prices are separate dynamic-price features.
8. Use all valid quoted calendar prices for dynamic-price calculations rather than only available dates.
9. Calendar coverage must be measured explicitly.
10. Require >=80% calendar coverage before calendar-derived 30/90-day analytical features are valid.
11. Below-threshold calendar features are NA, not zero.
12. Weekend means Friday/Saturday.
13. Keep both absolute and percentage weekend premium.
14. Main weekend analysis uses percentage premium.
15. Weekend premium requires 90-day coverage plus >=8 valid weekend and >=20 valid weekday prices.
16. Use only amenity_count; no individual amenity indicators.
17. Parse amenities as a list rather than counting delimiters.
18. Use neighbourhood_cleansed as the main location variable.
19. Final neighborhood reporting requires >=10 listings.
20. Use room_type as the main compact listing-type variable.
21. Preserve original property_type values.
22. Report property types only when n >= 10.
23. Do not regroup property types without approval.
24. Do not automatically delete plausible statistical price outliers.
25. Keep calculated_host_listings_count numeric.
26. Required host comparison is 1 versus >1; additional bins require inspection/approval.
27. Include explicit unmatched-ID and coverage diagnostics.
28. Stage 1 descriptive analysis is the required core deliverable.
29. Modeling is conditional on owner review after Stage 1.
30. Modeling requires a plan amendment before implementation.
31. Full raw datasets are not committed.
32. Tiny test fixtures are committed.
33. Docker contains code/dependencies; raw data and outputs are mounted volumes.
34. Required outputs are the analytical CSV, four summary CSVs, and four required figures listed above.
35. A fifth figure is optional and evidence-driven.
36. Do not add NLP, GeoJSON/spatial analysis, dashboards, databases, APIs, Docker Compose, or individual amenity indicators without explicit approval.
37. The acceptance invariants in Section 23 define correctness for Builder and Tester.

This checklist is intended to make the downstream workflow unambiguous and to preserve the technical decisions made during architecture review.
