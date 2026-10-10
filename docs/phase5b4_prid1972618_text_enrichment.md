# Phase 5B.4 — PRID 1972618 Full-Text Enrichment

Date: 2026-10-09 (Asia/Kolkata)

## Result

The existing `data/pib/1972618_full.txt` contains the genuine PIB article text, not only the metadata excerpt. It includes the complete article paragraphs about the USD 800/MT MEP, its effective period, additional buffer procurement, earlier procurement and disposal quantities, and the policy rationale. The opening `Posted On` line is treated as source metadata and excluded from the article body. No text was generated or supplemented.

The TXT was attached to the existing PRID 1972618 capture as a separate `manual_txt` representation. Existing capture/run records, HTML bytes/checksum, verified publication metadata, and first-seen timestamp were preserved. No extra article capture card was created.

## Stored representation and identity

| Field | Value |
|---|---|
| PIB PRID | `1972618` |
| Existing capture ID | `a72daf8b-7b7d-4a3c-9def-e8d2d96a6132` |
| New representation ID | `0996048d-9ad4-47e5-a5e8-67a4854df50c` |
| Representation type | `manual_txt` |
| Source URL | `https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=1972618&reg=48&lang=1` |
| Content status | `full_text_extracted` |
| Actual import time (UTC) | `2026-10-09T12:35:57.845084+00:00` |
| Raw TXT SHA-256 | `ee29c1ed7de7a7f328474f61743335fdc00b0a2e86a3adfecb2b3318fc91bbce` |
| Normalized body SHA-256 | `0baae72fb8c6db41e6d1ed4eeb632c13d1f07ddb5268b1a129657982eb379924` |
| Existing HTML SHA-256 | `d676952902a7808a412261fc68aa2225177cbf23ed6d76c67dc86b31e1f633c9` |
| Existing first-seen time (UTC) | `2026-10-09T10:35:00.910957+00:00` |
| Existing capture/run counts | 5 / 5, unchanged |

The TXT storage is additive in `agri_event_source_representations`. Its import time is recorded independently. It does not replace `summary_text`, `raw_item_json`, the original HTML run payload, or its raw checksum. Reimporting the same bytes returns `duplicate` and refreshes only deterministic derived classification fields if rules have changed.

## Events and evidence

The full text produced exactly the two requested event classifications:

1. **`mep_introduction`** — effective 2023-10-29 through 2023-12-31. Evidence quotation: “The Government today notified Minimum Export Price (MEP) of USD 800 per Metric Ton, FOB basis, on onion export with effect from 29th October, 2023, till 31st December, 2023.”
2. **`government_procurement`** — additional 2 lakh tons for the buffer. Evidence quotation: “Along with the decision to impose MEP on onion exports, the Government has also announced the procurement of additional 2 lakh tons of onion for the buffer, over and above the 5 lakh tons already procured.”

Both passages are exact source text; their offsets refer to the concatenated article title and TXT body. The article body separately retains the historical references to 5 lakh tons already procured and about 1.70 lakh Metric Tons disposed. These are not confused with the additional 2 lakh-tonne procurement event.

The source publication date remains **2023-10-28**, date-only. The source-reported string `28 OCT 2023 7:03PM by PIB Delhi` is retained without UTC conversion because no timezone is stated. The two policy dates are separately emitted as `effective_date` (2023-10-29) and `effective_end_date` (2023-12-31). The existing verified ministry, **Ministry of Consumer Affairs, Food & Public Distribution**, remains unchanged.

Commodity relevance is `onion_direct`; geography is `india_wide` based on the article's reference to consumption centres “all over the country.” No Nashik market, variety, or grade mapping is assigned. The mechanism is export incentives plus domestic buffer procurement/disposal. The price hypothesis explicitly says net mandi-price effect and Nashik-specific impact are unknown and unvalidated. There are no human labels or classifier performance claims.

## API and dashboard

`GET /api/agri/events/recent?limit=50` returned HTTP 200 and four article cards for four distinct PIB identities. PRID 1972618 appears once, with `manual_txt` as the preferred representation, full text, both event categories, both exact quotations, source date/time/ministry, and date-only precision. Earlier duplicate capture representations remain stored but are deduplicated at article-card level.

A real Chrome/Playwright production-browser smoke passed after starting the production server on an isolated port. It verified one PRID 1972618 card, both categories, both evidence quotations, publication date, and both effective dates, with no browser errors. No layout, styling, font, theme, animation, or navigation changes were made; existing panel markup was extended to show the text representation/import time and search across all event categories.

## Tests and preservation

- Focused event tests: **14 passed** (one non-failing Windows pytest-cache warning).
- Full backend suite: **90 passed**, 3 non-failing dependency/cache warnings.
- Frontend production build and TypeScript: **passed**.
- Configured database API smoke: HTTP 200, `ready`, four deduplicated article cards.
- Real production browser smoke: **passed**, one card and both evidence-supported events.
- Counts before/after: canonical prices 291 → 291; historical prices 21,864 → 21,864; capture runs 5 → 5; captures 5 → 5; one TXT source representation added.
- Model A, Model C, forecast registrations, and price data were not changed. No training or production forecasts were run.

## Reusable import command for the remaining TXT files

Save each genuine copied body as UTF-8 text under `data\pib\`. The command associates it only with an existing PIB capture and rejects an absent identity; it does not create a free-standing article or backdate availability.

```powershell
Set-Location C:\Nexyra

venv\Scripts\python.exe -m backend.agri.events import-pib-text `
  --file data\pib\2042765_full.txt `
  --prid 2042765 `
  --source-url "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2042765&reg=48&lang=1"

venv\Scripts\python.exe -m backend.agri.events import-pib-text `
  --file data\pib\2114060_full.txt `
  --prid 2114060 `
  --source-url "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2114060&reg=48&lang=1"
```

Each successful import stores the TXT bytes/text and checksum as a revision-capable representation, derives evidence-backed classifications, and leaves the existing capture metadata and first-seen time intact. Same-file reimports are idempotent.
