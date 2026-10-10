# Phase 5B.3 — Model B Comprehensive Repair and Validation

Audit date: 2026-10-09 (Asia/Kolkata)

## Executive summary

Model B now ingests the four genuine PIB captures already present and can extract a complete body from the saved, full official PIB page for PRID 1684194. The other three saved files remain metadata excerpts. Official PIB publication dates and ministries have been verified for all four identities and are stored separately from local availability. The saved source bytes and checksums are retained.

The importer now preserves independently verified metadata when the same HTML is re-imported, and a richer source page can upgrade derived extraction fields without erasing the earlier excerpt capture. A classification error that treated a historical reference to a prohibition lift as a new policy event was corrected: PRID 2042765 is identified as a reported export-volume record. Existing captures and price rows were not removed or rewritten.

There are five capture rows because PRID 1684194 has two distinct source representations (an earlier excerpt capture and a later full-page capture). There are zero human-reviewed labels, so no precision, recall, F1, or abstention metric is reported. Model B remains experimental and is not connected to Model A or Model C.

## 1. Baseline audit

The configured `.env` database was explicitly loaded before inspection. Immediately before this phase's database enrichment/import, it contained 291 canonical price rows, 21,864 historical price rows, four capture runs, and four capture rows. The four original capture IDs and raw checksums were:

| PRID | Original capture ID | Raw SHA-256 |
|---|---|---|
| 1684194 | `f5b185d0-34ea-4553-9551-17ea769f3416` | `fecf6b62d312990a7529778734ea5942617d5c4fb9aa1c5f16e85d1060e05ab8` |
| 1972618 | `a72daf8b-7b7d-4a3c-9def-e8d2d96a6132` | `d676952902a7808a412261fc68aa2225177cbf23ed6d76c67dc86b31e1f633c9` |
| 2042765 | `a4aba132-443a-40e6-8e50-e5da8c8e203c` | `69ed15b57be13c4fddeb8f3de3da32e0657acadaf2249deb56ddbccce5b1520f` |
| 2114060 | `b120024d-7bee-4f43-8582-e2c8ff7fbde1` | `3b5b2b91be180708df1a826b7ffc3436f3b03100bacb736feb960acab4e8234d` |

The baseline four rows had no verified metadata stored for PRIDs 1684194, 1972618, or 2042765. PRID 2114060 had already been independently verified in the prior phase. All four local files were genuine PIB HTML saves but contained only title/description metadata rather than full body text. The PIB `PressReleasePage.html` file under the saved page's companion folder is a separate, full-rendered source page for PRID 1684194.

The database uses the existing event-capture schema; no schema migration was needed. Existing schema migration history is recorded in the Phase 3/5 reports and remains untouched. This phase added one capture run and one capture for the distinct full-page representation. Final counts: 291 canonical prices, 21,864 historical prices, five event runs, five event captures.

## 2. Source and content investigation

The four top-level files (`1684194.html`, `1972618.html`, `2042765.html`, `2114060.html`) contain PIB Open Graph title, URL, and a truncated description. In those files, the headline and excerpt are present, but full article-body content is not. The text is not hidden in the visible HTML and the saved markup does not expose it through a complete body container; the page's dynamic behavior therefore did not survive those saves as article text. Treating surrounding website text as article content would have been incorrect.

The companion `PressReleasePage.html` is an official full page for PRID 1684194. It includes the headline, ministry, `Posted On` header, release body, and PIB release ID in server-rendered markup. It is the only full-body source among the saved materials located. Extraction now strips PIB publication heading, signature/footer, duplicate desktop/mobile copy, and navigation before classifying the body. The extracted body is checked against the text in the saved official page. It is not reconstructed from title or description.

Attempts to use the authoritative PIB pages confirmed the article metadata and text through official page views. Programmatic direct downloading was not used to bypass any restrictions. The exact remaining content action for PRIDs 1972618, 2042765, and 2114060 is to save their official English or Hindi PIB pages with the complete body in a browser-supported official page/print/PDF form, then place the files in `data/pib/` and run the documented batch importer. Do not use the excerpt-only saves as full-body documents.

## 3. Collection and metadata results

All four records are genuine official PIB releases. Verified publication dates and issuing ministries:

| PRID | Verified publication date (date-only) | Issuing ministry | Source page time text (not UTC) | Body status |
|---|---|---|---|---|
| 1684194 | 2020-12-28 | Ministry of Commerce & Industry | `28 DEC 2020 8:03PM by PIB Delhi`; timezone not stated | One full-body capture and one earlier excerpt capture |
| 1972618 | 2023-10-28 | Ministry of Consumer Affairs, Food & Public Distribution | `28 OCT 2023 7:03PM by PIB Delhi`; timezone not stated | Metadata excerpt only |
| 2042765 | 2024-08-07 | Ministry of Consumer Affairs, Food & Public Distribution | `07 AUG 2024 6:09PM by PIB Delhi`; timezone not stated | Metadata excerpt only |
| 2114060 | 2025-03-22 | Ministry of Consumer Affairs, Food & Public Distribution | `22 MAR 2025 7:18PM by PIB Delhi`; timezone not stated | Metadata excerpt only |

For each verification, the record stores the exact official verification URL, quoted source evidence, a UTC metadata-verification timestamp, and `date_only` precision. The displayed PIB local time is preserved as source text; `source_publication_at_utc` is a date-only value, not an invented timestamp. Policy effective date remains distinct from publication date: PRID 2114060 says the 20% duty withdrawal takes effect on 2025-04-01; PRID 1684194 says the prohibition removal takes effect on 2021-01-01.

The metadata enrichment function now refuses conflicting publication dates or ministry values rather than silently overwriting them, and keeps a verification history. Re-import of identical raw bytes merges the stored verification provenance instead of clearing it. The source payload SHA is unchanged.

## 4. Semantic classification and evidence

The deterministic multi-label classifier remains the reproducible Candidate B0. No B1 model was trained because there are no ground-truth annotations; no pretrained model or weights were downloaded. Classifications are tentative rule signals, not validated policy labels or price forecasts.

Categories supported by the current real sources:

- `export_restriction_removal` — PRID 1684194.
- `mep_introduction` — PRID 1972618.
- `reported_export_volume` — PRID 2042765.
- `export_duty_reduction` — PRID 2114060.

The classifier distinguishes the export-volume report from a new restriction-removal action, and tests cover restriction removal versus introduction and duty reduction/effective-date extraction. Exact evidence strings and offsets point into captured headline/body or the source description. Excerpt-only items remain marked as such; title/description evidence is not represented as full-body evidence. A possible economic mechanism remains unvalidated, no calibrated confidence percentage is used, and exact target series association stays `unassigned`.

Known limitations: rules are conservative keyword/context patterns rather than a complete language understanding system. PRID 2042765's meta excerpt itself discusses the earlier prohibition lift, so its label is intentionally `reported_export_volume` based on its report headline, not an assertion that all event details were extracted. For strong policy interpretation and evaluation, obtain full bodies and human labels.

## 5. Human review and evaluation

`data/pib/annotations.csv` now exports five capture rows with source identifiers, headline, date, predicted categories, exact evidence, completeness, and blank human review fields. Each row is labelled `development_reused`, because these captures and classifier outputs have already been inspected during this phase. None can be presented as an untouched evaluation sample.

The review file includes explicit reviewer provenance, review time, review decision/category fields, commodity/geography labels, and notes. No human labels were added. The CLI evaluation returned `insufficient_labels`; it produced no scores. Therefore:

- Precision: not available.
- Recall: not available.
- F1/macro-F1: not available.
- Coverage/abstention: not available.
- False-positive/false-negative counts: not available.

This is the correct outcome for zero reviewed examples. Do not use the current CSV's predictions as ground truth.

## 6. Historical availability and leakage

Original local first-seen timestamps are retained. Verified publication dates do not imply historical Nexyra availability. The prior captures first appeared locally in 2026; the separate full-page PRID 1684194 capture retains its original article-level first-seen lineage, while its retrieval is recorded on its capture run. No record is backdated to publication or policy-effective time. These articles cannot be used as known 2020–2025 news features in a historical replay merely because their release dates are old. Model C remains blocked pending a documented availability policy and adequate prospective/source-dated collection.

## 7. Frontend/API and operational commands

No frontend files or visual styles were changed in this phase. The existing `/api/agri/events/recent` route was exercised against the configured database using FastAPI TestClient and returned HTTP 200, `status=ready`, and five source-backed capture representations. The existing Semantic Intelligence panel consumes this endpoint. A real browser automation run was not performed in this environment; the prior Phase 5B.2 report records a browser smoke for the then-single capture, so current five-row visual rendering remains unverified here.

Repeat the supported manual import from PowerShell:

```powershell
Set-Location C:\Nexyra
venv\Scripts\python.exe -m backend.agri.events import-pib-directory --directory data\pib
```

This command is idempotent for identical source bytes and updates derived extraction/classification without creating a fake source revision. A changed raw official page or source text is preserved as a distinct capture revision. To export review tasks and inspect evaluation:

```powershell
venv\Scripts\python.exe -m backend.agri.event_evaluation export --output data\pib\annotations.csv
venv\Scripts\python.exe -m backend.agri.event_evaluation evaluate --file data\pib\annotations.csv
```

After a reviewer actually checks each source passage, fill human fields and reviewer provenance in the CSV. Do not mark predicted categories as human labels by copying them without review. Live collection remains manual/one-shot; no scheduler was enabled.

## 8. Tests and integrity checks

- Backend suite: **89 passed**, 3 warnings (Starlette/httpx deprecations and a Windows pytest-cache warning).
- Focused event suite: **13 passed**, 1 Windows pytest-cache warning.
- Frontend production build and TypeScript: **passed** (`npm.cmd run build`).
- Real API smoke: **HTTP 200**, five events returned from the configured database.
- Real browser smoke: **not run in this execution**; see frontend limitation above.
- Source importer re-run: four top-level source files processed, four existing captures enriched, zero new duplicates or failures; the separate full PIB page remains an independent fifth capture.
- Final database: `agri_daily_prices=291`; `agri_historical_price_observations=21864`; `agri_event_capture_runs=5`; `agri_event_captures=5`.
- The four original capture IDs and raw checksums remain present; the full-page source has its own raw checksum `a7f0b3b97efc200c589c16f81be9b85fdd28eed6ba2647673ce65cd4951787dd`.
- No price tables, Model A numerical code/artifacts, model registrations, Model C, or frontend design files were changed. Only event capture metadata/classification/extraction data and the annotation export were updated.

## 9. Completion gates

| Gate | Status | Evidence |
|---|---|---|
| 1 — Genuine data ingestion | PASS | Five authentic source capture representations across four PIB article identities, with raw source checksums. |
| 2 — Content extraction | PARTIAL | One full official article body; three identities remain excerpt-only. |
| 3 — Metadata integrity | PASS | All four dates and ministries have official source evidence and date-only precision; timezone ambiguity preserved. |
| 4 — Semantic event extraction | PARTIAL | Four useful event categories and source-linked evidence; deterministic rules still experimental. |
| 5 — Classification evaluation | BLOCKED | Zero genuine human-reviewed labels; no metrics can be computed. |
| 6 — Operational repeatability | PARTIAL | Batch manual import, safe metadata enrichment, annotation export/evaluation, and repeat-import preservation work; broader multi-source collection is not yet implemented. |
| 7 — Dashboard integration | PARTIAL | Real API route returns all five; no current browser smoke was performed. |
| 8 — Historical integrity | PASS | Original capture first-seen times and raw checksums retained; no backdating; prices unchanged. |

## 10. Remaining blockers and exact actions

1. **Three full bodies:** download the official full page or print/PDF for PRIDs 1972618, 2042765, and 2114060; save the genuine source files under `data/pib/`; run the batch import command above. Current metadata excerpt files are insufficient.
2. **Human evaluation:** review each source-backed annotation row, enter decision and corrected labels with reviewer provenance/time, then run the evaluation CLI. Do not include these inspected development rows as an untouched model test.
3. **Fresh blinded evaluation:** collect new, future official releases after freezing classifier rules; label those without changing rules; use them for a chronological test, keeping near-duplicate/revised releases together.
4. **Dashboard browser check:** run the app and verify five actual records in the existing panel in a browser. API and production build passed; browser automation was not available/run in this phase.
5. **Broader collection:** verified candidate PIB URLs in earlier reports can be used as a download manifest; additional official source adapters and licensing/source coverage checks are still needed before claiming multi-source or 30–50 article coverage.

## Final status

**REAL DATA**
- Genuine article identities: 4; capture representations: 5.
- Full-body article count: 1 capture (PRID 1684194).
- Excerpt-only article identities: 3 (plus the earlier excerpt representation for PRID 1684194).
- Verified publication dates: 4/4.
- Verified ministries: 4/4.
- Human-reviewed labels: 0.

**MODEL B**
- Event categories observed: export restriction removal, MEP introduction, reported export volume, export duty reduction.
- Classification method: deterministic evidence-linked rules (Candidate B0).
- Precision/recall/F1/abstention: unavailable; zero reviewed labels.
- Known limitations: three article bodies truncated; rules unvalidated; no evidence of measured or causal price effect; historical availability is local capture only.

**SYSTEM**
- Backend tests: 89 passed.
- Frontend build/TypeScript: passed.
- Real API smoke: passed, HTTP 200, five events.
- Real browser smoke: not run in this execution.
- Existing price data preserved: yes, 291 canonical and 21,864 historical rows.
- Model A unchanged: yes.
- Model C unchanged/unactivated: yes.

**NEXT REQUIRED USER ACTIONS**
- Provide full official page or print/PDF saves for PRIDs 1972618, 2042765, and 2114060 if body-level analysis is required.
- Human-review the five annotation rows and record reviewer provenance. A fresh future collection is required for a truly untouched chronological test.
- Run a browser smoke check against the current backend if visual confirmation of all five rows is required.
