# Nexyra release-candidate report

Date: 2026-10-09  
Workspace: `C:\Nexyra`

## Release decision

**Status: blocked by validation.** Nexyra runs locally and now has a functional human-review workflow, a guarded context-only Model C contract, and a reproducible Windows startup script. It is not a validated forecasting product: there is no eligible production forecast, Model B has no human-reviewed labels, and the data does not support prospective combined-model evaluation.

## 1. Features completed

- Added a same-design-system Model B review route at `/review`, linked from Semantic Intelligence. It shows source metadata, saved body, model categories/evidence/date mentions, and append-only review history.
- Added loopback-only queue, evaluation, history, and save APIs. Reviews require explicit article/category decisions, use exact evidence spans, preserve source predictions, and record the actual submission time.
- Added Model B descriptive evaluation outputs for relevance, event micro/macro and per-category performance, exact evidence, date/role extraction, publication-date denominators, missing evidence, and exclusions. Metrics remain null when there are no reviewed labels.
- Added `model-c-context-only-v1` and `GET /api/agri/combined/{series_id}`. It filters by forecast-origin availability, source checksum, human review, commodity and geography, and never alters the forecast value.
- Added a manual official-text import adapter for saved IMD, AGMARKNET, and data.gov.in text. It checks source host, archives bytes, stores raw/content checksums, is idempotent for identical imports, keeps revisions, and marks supplied dates and body text unverified.
- Added `scripts/run-dev.ps1`. It binds both services to loopback, checks port ownership, verifies backend/database and frontend health, refuses occupied ports, and cleans up only its own process trees.
- Replaced public wildcard CORS with local development origins. Added health fields for database reachability and review-mode scope.
- Updated environment templates, README, and user/developer/validation documentation. The active `.env` was not changed.
- Existing fonts, palette, themes, backgrounds, animation, dashboard composition, and navigation styling were preserved. The review route uses the existing theme control and design tokens; no global CSS or dashboard styles were replaced.

## 2. Features still experimental

- Model A's last-available-price baseline and historical replay are research-only.
- Model B taxonomy outputs are transparent keyword-rule predictions, not a validated classifier.
- Exact source text completeness is not human-verified for every stored PIB article.
- The combined Model C layer displays context only and cannot claim uplift or causal price impact.
- Manual non-PIB text imports are candidates until a reviewer checks the original source. Their reported publication dates are unverified.

## 3. Features blocked by missing evidence

- Fresh, exact-series price observations with verified market identity, price unit, publication/availability timestamp, and source lineage.
- A new untouched price test period.
- Genuine Model B human annotations and adjudicated labels.
- A prospective Model B test sample captured after the frozen 2026-10-10 UTC cutoff.
- Same-event grouping across distinct announcements before a future test split.
- An overlapping, temporally valid dataset for evaluation of Model C.
- Verified IMD/AGMARKNET redistribution terms for full-text packaging.

## 4. Actual data counts

| Dataset | Count | Verification |
|---|---:|---|
| Canonical agricultural prices | 291 | Read-only SQLite count; latest date 2026-10-08 |
| Historical agricultural prices | 21,864 | Read-only SQLite count |
| Prospective price observations | 0 | Read-only SQLite count |
| Unique PIB article identities | 18 | API and saved capture archive |
| PIB source capture rows | 19 | Read-only SQLite count |
| Selected full-body PIB representations | 18 | API body status; completeness not human-reviewed |
| Manual PIB text representations | 3 | Read-only SQLite count |
| Human-reviewed articles | 0 | Append-only review table and evaluation endpoint |
| Current independent prospective test articles | 0 | Frozen protocol and current acquisition dates |

The Phase 5B.6 expansion previously added 14 genuine PIB articles. This phase added **no new source documents**: an official IMD PDF retrieval probe returned HTTP 404, while the official service pages expose dynamic/current and past bulletin paths. We did not substitute search snippets for captured source documents. The prior 50-article goal therefore remains at 18 total articles, 36 short, with no dedicated human-reviewed IMD/weather set or unrelated neutral controls.

## 5. Model A selected method and results

The saved Phase 5A exact-series research run selected **last-available-price baseline** independently at 1, 3, and 7 calendar days. Validation selected the method; test metrics were reported after that choice. The 2024 test period was already examined and is not an untouched holdout.

| Horizon | Validation n | Validation MAE / RMSE | Reused test n | Reused test MAE / RMSE | Reused test interval coverage |
|---|---:|---:|---:|---:|---:|
| 1 day | 63 | 357.22 / 547.41 | 70 | 411.39 / 585.39 | 30.0% |
| 3 days | 63 | 415.67 / 623.84 | 72 | 463.22 / 594.25 | 12.5% |
| 7 days | 63 | 278.79 / 461.50 | 68 | 615.10 / 765.60 | 14.7% |

Test origins begin 2024-08-01 and targets end 2024-12-10. Nominal interval coverage was 90%; observed coverage is poor and no guarantee is claimed. The exact series has 797 rows ending 2024-12-10 and is stale. No production artifact is registered. The current canonical series includes Local grades and is not merged with the old FAQ series.

## 6. Model B defensible evaluation results

**No accuracy metrics are available.** Current counts are 0 reviewed labels, 18 development-reused articles, and 0 eligible independent test articles. The prior stored evaluation remains `insufficient_labels`. The evaluation workflow was extended, but no human judgment was performed by engineering. Rule predictions are not counted as labels.

The test cutoff remains 2026-10-10 00:00 UTC. Publication dates do not stand in for `first_seen_at`. The current sample was already inspected during development and is not eligible as a fresh test.

## 7. Model C operational status

**Functional but experimental; currently blocked by inputs.** The endpoint requires a valid forecast and filters reviewed source evidence by exact current revision and availability at the forecast origin. It returns `forecast_unavailable` in the current database/registry state. It always returns `numerical_adjustment: null`; no news-driven price movement is generated.

## 8. Dataset freshness

- Latest canonical observation date: **2026-10-08**, modal price **3500.0** in the stored source unit. Publication availability remains unverified, so recency by date alone is not live-data evidence.
- Historical FAQ research series end: **2024-12-10** (668 days old on the report date).
- Prospective price rows: **0**.
- No new prices were fetched or imported in this work.

## 9. Source provenance and integrity

- Existing PIB source identities, original HTML captures, checksums, metadata, and text representations were preserved.
- The 14 Phase 5B.6 collection receipt files still match their recorded SHA-256 values (14 checked; 0 failures).
- SQLite integrity check returned `ok`; canonical and historical row counts remain 291 and 21,864.
- The manual official-text importer stores original bytes separately from decoded text, records current local import/first-seen time, leaves source publication timestamp null, and labels operator-supplied dates unverified.
- The [IMD Agromet service](https://mausam.imd.gov.in/responsive/agromet_adv_ser_national_past_en.php) exposes current and past district/state bulletin paths; its page directs historical-data questions to its official contact channel. The current [district English bulletin page](https://mausam.imd.gov.in/responsive/agromet_adv_ser_district_current_en.php) is dynamic. This confirms a source workflow exists, not that Nexyra has captured its historical bodies.
- [PIB's copyright policy](https://www.pib.gov.in/content/3604_2_CopyrightPolicy.aspx?lang=1&reg=3) allows accurate reproduction with prominent attribution for PIB material and excludes third-party content. [data.gov.in terms](https://www.data.gov.in/terms-of-use) defer to each resource's `license` metadata; no specific AGMARKNET resource license was verified here. IMD/AGMARKNET full-text redistribution rights remain unresolved.

## 10. Test outcomes

| Check | Result |
|---|---|
| Full backend suite | 108 passed; 2 upstream Starlette/httpx deprecation warnings |
| Review API integration | Passed: explicit save, actual timestamp, exact evidence, history, revision re-review state, invalid evidence, incomplete category decisions, cross-site origin rejection |
| Official text import tests | Passed: allowed-domain validation, checksums, genuine import timestamp, duplicate idempotency, append-only revisions, operator-date provenance |
| Model C temporal-safety tests | Passed: article first-seen after origin excluded; checksum-mismatched evidence excluded; missing forecast blocks context and price adjustments |
| PowerShell startup script syntax | Passed |
| Startup end-to-end | Passed: API/database healthy, frontend HTTP 200, occupied-port refusal verified, Ctrl+C cleanup verified |
| TypeScript / production build | Final `tsc --noEmit` and production build passed; `/review` was statically prerendered |
| Microsoft Edge browser smoke | Final run used the existing Skip intro control; dashboard and `/review` returned 200, 18 unique article identities and 18 review-queue rows loaded, article body visible, evaluation reported 0 reviewed labels, 390px viewport had no horizontal overflow, dark theme toggle worked, and there were no page errors. |
| Human review save in production DB | Not performed; no labels were fabricated |

The backend emitted only upstream Starlette/httpx deprecation warnings in the test run. The source-import tests used temporary databases and fixture text; no fixture content was imported into Nexyra's real database.

## 11. Outstanding bugs and limitations

- No production forecast exists. The canonical price dates are recent, but exact source availability provenance is unknown.
- The dashboard reports unavailable forecasts rather than extrapolating a model outside its valid status.
- Model B labels remain heuristic. Independent review, disagreements, and same-event grouping remain outstanding.
- The manual non-PIB text path does not fetch or verify source bodies; a human must compare the file to the original page.
- The run script is local development only. It is not a service manager and does not provide authenticated multi-user access.
- IMD bulletin archive URLs may be dynamic or short-lived; the bounded 2026-06-23 PDF probe returned 404.

## 12. Security and licensing limitations

- Review reads/writes are guarded to loopback client/host and same-machine origins; do not publish the app. This is not authentication.
- CORS no longer allows arbitrary origins. The active `.env` was not read into output or modified.
- Optional API credentials were not logged or reported. No AGMARKNET API key/resource identifier was configured as verified.
- PIB reuse terms exclude third-party material; data.gov.in rights are resource-specific; IMD/AGMARKNET redistribution permissions were not verified.

## 13. Prioritized release checklist

1. **Acquire exact-series prices** from an authoritative source, retain original records, verify market/grade/unit and capture genuine availability timestamps.
2. **Freeze a fresh numerical test window** before inspecting any target prices; evaluate each horizon against the naive baseline independently.
3. **Collect underrepresented official material** through stable IMD/AGMARKNET sources; retain source files, timestamps, checksums, resource identifiers, and license metadata. Do not pad the sample with near-identical PIB releases.
4. **Review the 18 development articles** with multiple human reviewers and adjudicate labels. Keep the current articles out of any future independent test.
5. **Collect a prospective Model B set** after the frozen cutoff and group revisions, near-duplicates, and same-event announcements before evaluation.
6. **Run the final clean-environment suite** and final frontend build after all edits.
7. **Evaluate Model C only with overlapping as-of price and reviewed event histories**; keep numerical news adjustments disabled unless a separate out-of-sample study supports them.
8. **Review redistribution rights** before packaging third-party or non-PIB official source text.

## Final validation rerun

The final validation completed after the implementation and documentation edits. The full backend suite passed (108 tests); TypeScript and the production build passed; and the real Edge smoke test exercised the existing intro flow, dashboard API, review queue, article body, mobile viewport, and dark theme. The startup script was also exercised end to end, including safe refusal when ports were occupied and cleanup of only the processes it started. No human review was submitted and no new source or price records were imported.

The stale backend process previously occupying port 8000 was stopped during this work. The final development server session was stopped after browser verification; the startup script left its owned frontend and backend ports free. This is a release-candidate implementation with validation blockers listed above, not approval to deploy or enable forecasting.
