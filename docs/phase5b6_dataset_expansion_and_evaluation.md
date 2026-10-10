# Phase 5B.6 — Real-World Dataset Expansion and Semantic Evaluation

Date: 2026-10-09 (Asia/Kolkata)

## Outcome

Fourteen additional unique official PIB releases were retrieved live, saved as immutable raw HTML files, and imported. Together with the four existing PIB articles, the dashboard/API now serve **18 distinct PIB article identities**. The database has 19 capture rows because PRID 1684194 already has two source captures; the new fetch added exactly 14 capture rows, one for each new PRID. The source-representation table remains at three manual TXT representations. No duplicate article cards were added.

All 18 selected article representations report `full_text_extracted` or `full_body_verified` and expose body text. This count means extraction completed from the stored source representation; extraction completeness has not been human-reviewed for every article. One new Tomato Market Intervention release (PRID 2102360) is an agriculture-adjacent cross-commodity control; it is not counted as an unrelated neutral control.

The 50-article expansion target was not met: **14 additional articles were captured, leaving 36 to reach 50**. Only 13 of the 14 new pages fit the requested sampling strata based on their initial source/topic selection (9 policy/procurement, 3 production/market, 1 export/trade). The remaining one is the cross-commodity control. No dedicated official weather-advisory sample or neutral unrelated control sample was acquired. Stratum assignments are sampling metadata, not human-reviewed gold labels.

## Source coverage

All sources are official PIB releases. The source publisher count is one; the stored issuing ministries span three organizations: 16 Consumer Affairs releases, one Agriculture & Farmers Welfare release, and one Commerce & Industry release.

| New PRID | Source publication date | Topic/source identity |
|---|---|---|
| 1869581 | 2022-10-20 | Consumer Affairs onion buffer and price-stability release |
| 1950595 | 2023-08-20 | Onion buffer expansion and retail disposal |
| 2003590 | 2024-02-07 | Subsidized onion retail-sale reporting |
| 2016405 | 2024-03-26 | Onion buffer procurement and historical export-policy context |
| 2054873 | 2024-09-14 | Onion retail and bulk-sale intervention |
| 2057920 | 2024-09-23 | Rabi onion mobile-van sale |
| 2088051 | 2024-12-26 | Consumer Affairs year-end review, including onion buffer activity |
| 2102360 | 2025-02-12 | Tomato Market Intervention Scheme release; cross-commodity control |
| 2163638 | 2025-09-04 | Subsidized onion sale and buffer disposal |
| 2280999 | 2026-07-04 | Onion procurement price and production report |
| 2303587 | 2026-08-26 | Onion availability, procurement and buffer release |
| 2303921 | 2026-08-27 | Onion market intervention and buffer logistics |
| 2313926 | 2026-09-23 | Buffer onion movement to Kolkata |
| 2320278 | 2026-10-07 | Onion availability, arrivals, prices and Kharif/weather outlook |

Examples of the source pages and their text include PIB's [March 2024 procurement release](https://www.pib.gov.in/Pressreleaseshare.aspx?PRID=2016405&lang=2&reg=48), [September 2025 buffer-sale release](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2163638&lang=2&reg=3), [July 2026 procurement-price release](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2280999&lang=1&reg=1), and [October 2026 onion-market release](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2320278&lang=1&reg=48). These releases report government actions or observations; they do not establish causal price effects.

### Sampling target status

| Initial sampling stratum | Target | New pages assigned | Remaining |
|---|---:|---:|---:|
| Government policy/procurement | 15 | 9 | 6 |
| Weather/crop disruption | 10 | 0 | 10 |
| Production/market arrivals | 10 | 3 | 7 |
| Export/trade | 10 | 1 | 9 |
| Neutral/unrelated controls | 5 | 0 | 5 |

The 2026 onion availability release (PRID 2320278) contains an IMD/rainfall outlook and the experimental rules emit `crop_damage` and `extreme_weather` labels for its passage. It is not a separately collected IMD advisory. Current event labels are rule outputs and do not count as human verification of these strata.

## Acquisition and preservation

- The 14 live requests returned official PIB pages and were retrieved between `2026-10-09T14:52:59.281205Z` and `2026-10-09T14:53:19.220866Z`.
- Raw responses are in `data/pib/phase5b6_raw/PRID_<id>_<UTC>_<hash-prefix>.html`; the response bytes are never overwritten. The receipts file records PRID, requested source URL, raw file, SHA-256, actual retrieval time, capture ID, and import/content status.
- Source publication dates are extracted from the PIB page header with date-only precision. The visible source-reported time is retained as text where present; no timezone is inferred. The actual local retrieval/first-seen timestamp remains distinct from publication time.
- The prior four PRIDs, all five old capture rows, the three manual TXT representations, their capture IDs, raw checksums, publication metadata, and first-seen timestamps remain present and unchanged. Counts after collection: 19 capture rows, 3 source representations, 18 distinct PIB PRIDs.
- Canonical prices remain **291** (`agri_daily_prices`); historical price observations remain **21,864** (`agri_historical_price_observations`). No price table was written.

Official PIB pages are publicly accessible, but this phase did not establish a redistribution license for the page text. The retained corpus is for the requested local research workflow; no broader republication permission is asserted. No other publisher was ingested.

## Normalization and experimental classifications

The derived normalization table (`agri_event_text_normalizations`) has 18 records, one for each current article identity. Normalization is deterministic and append-only; source HTML/TXT bytes and source checksums remain intact. Three bodies received layout/header whitespace cleanup (PRIDs 1972618, 2042765, and 2114060); the others required no change. The saved PRID 2114060 TXT currently contains readable curly apostrophes, so no mojibake repair was applied. A reversible repair is implemented only for the known, exact malformed byte-to-text sequences if they occur in a future source representation.

The transparent experimental rules emitted 34 article/category labels across 11 categories (categories overlap):

| Experimental category | Articles |
|---|---:|
| `government_procurement` | 9 |
| `market_price_report` | 7 |
| `buffer_stock_release` | 4 |
| `production_estimate` | 3 |
| `market_arrivals` | 2 |
| `reported_export_volume` | 2 |
| `mep_introduction` | 2 |
| `export_duty_reduction` | 2 |
| `export_restriction_removal` | 1 |
| `crop_damage` | 1 |
| `extreme_weather` | 1 |

Five articles have no emitted event category: PRIDs 2003590, 2057920, 2054873, 2102360, and 2303921. Four are onion releases where the rule set may have missed a described intervention; PRID 2102360 concerns tomatoes and was retained as a cross-commodity control. There is also a review candidate in the other direction: PRID 2016405 is a 2024 procurement article that mentions earlier MEP/export actions, while the rules emit `mep_introduction`. These are examples for human review, not measured false-positive or false-negative counts.

## Review and reproducible evaluation

`data/pib/phase5b6_review_queue.jsonl` contains 18 pending article records. Predictions are separated under `predictions_for_reference_only`; no prediction was copied into a gold label. Review identity is pinned to the selected capture ID, source article identity, and body checksum. Review import validates exact quotation spans, event taxonomy, and date formats. Corrections append a review-history record with a link to the prior review; identical reimports are skipped.

Source revisions are grouped by immutable article identity (PIB PRID). Near-duplicate normalized bodies are grouped for split control using five-word-shingle Jaccard similarity at 0.90 or higher. Grouping does not merge or delete source records. The current 18 selected articles form 18 such groups. All current data and classifier decisions have been seen during development and are permanently marked `development_reused`.

Evaluation result: **0 human-reviewed articles; 18 unreviewed; 0 eligible; metrics null/not computed**. Publication-date extraction correctness also has a zero-label denominator. No relevance, multilabel event, exact evidence-span, or date-role accuracy is claimed. The persisted protocol (`data/pib/phase5b6_evaluation_protocol.json`) reserves independent test eligibility for articles first captured on or after `2026-10-10T00:00:00Z`, groups revisions/near-duplicates before splitting, and prohibits using publication time as system availability. No future test articles are currently present. Model B is a keyword-rule system, so learned-model training/calibration is not applicable here.

See [the reviewer guide](phase5b6_reviewer_guide.md) for the queue format and commands.

## Reusable commands

From `C:\Nexyra`:

```powershell
# Fetch only manifest rows not already captured; --refresh is required to poll for later source revisions.
venv\Scripts\python.exe -m backend.agri.event_dataset manifest --file data\pib\phase5b6_collection_manifest.json --fetch

# Import saved PIB HTML or attach a manual full-text TXT to an existing PRID.
venv\Scripts\python.exe -m backend.agri.events import-pib-html --file data\pib\PRID_123.html
venv\Scripts\python.exe -m backend.agri.events import-pib-text --file data\pib\123_full.txt --prid 123 --source-url "https://www.pib.gov.in/PressReleasePage.aspx?PRID=123"

# Report stored experimental categories and append normalized text revisions.
venv\Scripts\python.exe -m backend.agri.event_dataset classify
venv\Scripts\python.exe -m backend.agri.event_dataset normalize

# Export a review queue, import completed reviews, and write JSON/Markdown evaluation results.
venv\Scripts\python.exe -m backend.agri.event_evaluation export-review --output data\pib\phase5b6_review_queue.jsonl
venv\Scripts\python.exe -m backend.agri.event_evaluation import-reviews --file data\pib\phase5b6_review_queue.jsonl
venv\Scripts\python.exe -m backend.agri.event_evaluation evaluate --json-output data\pib\phase5b6_evaluation.json --markdown-output data\pib\phase5b6_evaluation.md
```

The manifest collector has bounded 15-second requests by default, a 10 MB page-size limit, exact PRID/official-host validation, a 200 ms inter-request delay, exclusive raw-file creation, and no scheduler. It does not log response bodies or credentials. `--refresh` is an explicit choice to make a new source poll; changed source text is retained as a source revision by the existing importer.

## Validation

- Backend suite: **99 passed** (final run; only upstream deprecation warnings).
- Added checks: deterministic normalization, exact reversible mojibake handling, near-duplicate grouping, append-only/correction/idempotent human reviews, exact evidence validation, null metrics with no labels, mocked official HTTP collection, source identity rejection, true retrieval timestamps, raw-byte checksum preservation, and real saved HTML normalization without changing capture rows.
- API smoke: **HTTP 200**, 18 unique cards, 18 extracted full bodies, dataset-health status `insufficient_labels`, zero human reviews, no accuracy score. The running process on port 8000 was an older backend and returned the legacy response shape; it was left untouched. The updated API was run on port 8001 for verification. Restart the normal backend process to load the updated route before relying on the dashboard health line.
- Frontend TypeScript check: passed.
- Next.js production build: passed.
- Microsoft Edge/Playwright production smoke against the updated API: passed. It verified one card for each of the 18 PRIDs, the health line, the original article details, and no browser exceptions.
- Model A files were not changed. Model C remains inactive. No price data, model registry, or forecasts were modified.

## Next phase

Continue source expansion from authorized official weather, crop-production, mandi-arrival, and export/trade sources. Verify reuse terms before redistribution. Review the 18 existing articles with at least two independent annotators for relevance, event category, exact evidence, and date roles; adjudicate disagreements. Keep those articles in development because they have already informed rule decisions. Once the classifier and taxonomy are frozen, collect and sequester the prospective test group under the persisted cutoff; report denominators and disagreements before any accuracy summary.
