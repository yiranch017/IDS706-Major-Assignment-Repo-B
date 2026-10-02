# Synthetic test fixtures

Tiny, hand-designed data (not Inside Airbnb data) with the same column names as the real
files. Snapshot date is `2026-06-25`; calendar "offset" `k` means `snapshot + k days`.

Files: `listings.csv` (22 rows), `calendar.csv` (420 rows), `reviews.csv` (16 rows).
Extra non-required columns (`name`, `minimum_nights`, `maximum_nights`) are included to prove
extra columns are tolerated. Plain CSV is used so the files are reviewable; gzip loading is
tested separately by compressing them in a temp dir.

## Listings

| id | what it tests | expected |
|---|---|---|
| 1 | normal row | price 100, 2 amenities, host single |
| 2 | very large positive price | `$25,000.00` stays valid; `[]` -> amenity_count 0; host_count 3 -> multi |
| 3 | missing bedrooms; 1 amenity | amenity_count 1 |
| 4 | price `$0.00` | listing_price NA, valid=False; amenities with commas inside items -> count 3; host_count 0 -> host_type NA |
| 5 | blank price, blank amenities, blank host count | price NA/invalid; amenity_count NA with **no** parse failure (true missing); host_type NA |
| 6 | negative price, truncated amenity JSON, host count `abc` | price NA; amenity NA **plus** parse failure; host_type NA |
| 7 | `abc` price; amenities `{"a": 1}` (valid JSON, not a list) | price NA; amenity NA + parse failure |
| 8 | Python-style list `['Wifi', 'Kitchen']` | `ast.literal_eval` fallback -> 2 |
| 9 | JSON `é` escape | 2 |
| 10-22 | filler, amenity count `(id % 5) + 1`, host alternates 1/2 | |

Reporting thresholds (counts are **listings**, valid price or not):

* neighbourhood: Downtown ids 1-10 = **10** (eligible; only 6 have valid price), Montford ids 11-19 = **9** (not eligible), West Asheville ids 20-22 = 3.
* property type: Entire rental unit (1-5, 11-15) = **10** (eligible), Entire home (6-10, 16-19) = **9** (not eligible), Private room in home (20-22) = 3. Deliberately crosses the neighbourhood groups so the two thresholds are tested independently.
* room_type: Entire home/apt, Private room (3, 12, 20, 21), Shared room (22).

## Calendar (listings 1, 2, 3, 4, 6 and unmatched ID 9999 have rows)

Schema matches the real 2026-06-25 file: `listing_id,date,available,minimum_nights,maximum_nights`
(no price field; `minimum_nights`/`maximum_nights` are ignored).

| listing | rows | what it tests | expected |
|---|---|---|---|
| 1 | offsets -1..90 (92) | rows at -1 and +90 are **outside** both windows; offsets 0 and 89 inside. `available='f'` on offsets 0-14 | 30d: observed 30, coverage 1.0, availability 0.5. 90d: observed 90, availability 75/90 |
| 2 | 24 dates in days 0-29 + 48 in days 30-89, all `t` | exactly 80% in both windows | 30d observed 24, 90d observed 72, both qualify; availability 1.0 |
| 3 | 23 + 48 | one date short in both windows | 30d observed 23, 90d observed 71 -> availability **NA** (not 0); `calendar_has_data` True |
| 4 | 90 dates, all `f` | zero availability is a real value | availability 0.0 in both windows (not NA) |
| 6 | 90 dates: offsets 0-1 invalid `available='x'`, offsets 2-14 `f` (13), the rest `t` | **coverage vs availability denominator**: a valid date with an invalid status is an *observed date* for coverage but is excluded from both numerator and denominator | observed 30 / 90 (coverage 1.0); availability 15/28 (30d) and 75/88 (90d) - **not** 15/30 or 75/90 |
| 5, 7-22 | no calendar rows | no coverage | `calendar_has_data` False; observed days 0; availability NA |
| 9999 | 5 rows | calendar ID not in listings | counted as unmatched; never adds a row |

Calendar `listing_id`/`date` pairs are unique in the fixture (duplicate detection is tested with
in-memory frames and by appending a duplicate row to a gzipped copy in the pipeline tests).

## Reviews (reference S = 2026-06-25)

| listing | review dates | expected |
|---|---|---|
| 1 | S, S (same-day duplicate), S-29, S-30, S-89, S-90, S-179, S-180, S+1 | 30d = 3 (S, S, S-29; S-30 excluded); 90d = 5 (adds S-30, S-89; S-90 excluded); 180d = 7 (adds S-90, S-179; S-180 = 2025-12-27 excluded); S+1 is post-snapshot: excluded and counted. last_review_date = S, days_since = 0. Counts rows, not unique dates |
| 2 | S-400 | counts 0/0/0 but last_review_date = S-400, days_since 400 (zero recent activity is not missing recency) |
| 3 | S+5 only | no review at or before snapshot -> counts 0, last_review_date NA, days_since NA |
| 4, 7-22 except 5, 6 | none | counts 0, last_review_date/days_since NA |
| 5 | S-10, plus a row with date `not a date` | 30d = 1; invalid date counted and ignored |
| 6 | S-100 | 30/90 = 0, 180 = 1; days_since 100 |
| 8888 | 2 rows | review ID not in listings -> unmatched, no new row |

## Row-count facts used by tests

22 listings in -> 22 rows out. 1 calendar ID and 1 review ID unmatched. 5 listings with calendar
rows that match listings (1, 2, 3, 4, 6), 4 of which pass the 30- and 90-day coverage gates
(1, 2, 4, 6). 5 listings with review rows (1, 2, 3, 5, 6) of which 4 (1, 2, 5, 6) have a review
at or before the snapshot.
