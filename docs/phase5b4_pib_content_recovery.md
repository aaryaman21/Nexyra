# Phase 5B.4 — Existing PIB Capture Recovery and Dashboard Verification

Date: 2026-10-09 (Asia/Kolkata)

## Outcome

Inspected all four existing article HTML files and the existing PIB companion `_files` directory and ZIP. Recovered the full body for PRID 1684194 from the already-present official `PressReleasePage.html`. Re-imported that same saved page to refresh its extracted text and evidence **in place**; the existing capture and run were reused. No database rows were added or deleted during this recovery.

The source body for PRIDs 1972618, 2042765, and 2114060 is not present in their saved HTML or the companion assets/archive. They remain metadata-excerpt-only. No article body was synthesized.

## Files inspected

- `data/pib/1684194.html`
- `data/pib/1972618.html`
- `data/pib/2042765.html`
- `data/pib/2114060.html`
- `data/pib/Press Release_ Press Information Bureau_files/PressReleasePage.html`
- `data/pib/Press Release_ Press Information Bureau_files.zip` and the companion asset directory

The three companion-page candidates were checked for article identifiers, body text and PIB body fields. The archived `PressReleasePage.aspx` entry is a JavaScript library (`//START Common.Common.js`), not an article document. The archived companion HTML is a full official page for PRID 1684194 and contains its release body, ministry, date header, and release ID. The other three headline/description files have no corresponding full body in the inspected companion material.

## Recovered record

| Field | Value |
|---|---|
| PRID | 1684194 |
| Existing capture ID | `b21d5968-db18-464a-bdb2-33ae2232d206` |
| Existing run ID | `23541aee-e2b3-4010-9edf-b2574d6c80e1` |
| Raw source SHA-256 | `a7f0b3b97efc200c589c16f81be9b85fdd28eed6ba2647673ce65cd4951787dd` |
| Extracted body | “Central Government removes prohibition for the export of all varieties of Onions with effect from 01.01.2021” |
| Content status | `full_text_extracted` |
| Publication date | `2020-12-28`, date-only |
| Ministry | Ministry of Commerce & Industry |
| Classification | `export_restriction_removal` |
| Evidence | Exact headline plus exact complete body, with source offsets |

The stored run SHA matches the companion HTML file byte-for-byte. Reprocessing returned `enriched_existing` with the same capture ID; counts remained five runs and five capture rows. The earlier excerpt capture for PRID 1684194 remains intact, as required. Its verified metadata, raw SHA, and first-seen time were not deleted or replaced.

## Other existing article identities

| PRID | Existing file | Content status | Classification after source-based processing |
|---|---|---|---|
| 1972618 | `1972618.html` | `metadata_excerpt_only` | `mep_introduction` |
| 2042765 | `2042765.html` | `metadata_excerpt_only` | `reported_export_volume` |
| 2114060 | `2114060.html` | `metadata_excerpt_only` | `export_duty_reduction` |

The companion files/assets contain no additional article body for these PRIDs. Their complete-body limitation is specifically the absence of that text in the saved source material, not an uninspected hidden field. The existing official metadata remains present: dates and ministries are verified separately from the HTML excerpts, and source times remain unconverted because PIB does not specify a timezone.

## API and dashboard verification

- Configured backend endpoint `/api/agri/events/recent?limit=50`: HTTP 200, `ready`, five stored capture representations returned.
- Production frontend route: HTTP 200.
- Real Chrome/Playwright smoke: navigated through the existing “Skip intro” interaction, then observed all four genuine PIB headlines and the excerpt-completeness indicator in the rendered page. No browser page errors were reported.
- No frontend source or style files were changed. Existing theme, navigation, animation and component design are preserved.

The API returns five capture representations because PRID 1684194 intentionally retains both its prior excerpt capture and the distinct full-page capture. This phase did not create another duplicate.

## Checks and data preservation

- Backend suite: **89 passed**, 3 non-failing dependency/cache warnings.
- Frontend build and TypeScript check: **passed** (`npm.cmd run build`).
- Before/after counts around full-page refresh: canonical prices 291 → 291; historical prices 21,864 → 21,864; event runs 5 → 5; event captures 5 → 5.
- Full-page source file checksum equals the checksum already stored on its capture run.
- Existing four original source captures/checksums and the previously verified publication metadata remain intact.
- No forecast training, Model A/model-artifact changes, Model C activation, scheduler, or frontend redesign.

## Remaining limitation

Three official article bodies are genuinely absent from the existing saved files and companion assets. They remain correctly excerpt-only. The full body for the 2020 release is available and extracted; the other records retain their exact genuine excerpts and evidence. Human-reviewed labels remain zero, so classifier performance metrics are still unavailable.
