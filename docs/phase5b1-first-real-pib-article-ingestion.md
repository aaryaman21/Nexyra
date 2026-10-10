# Phase 5B.1 — First PIB article ingestion

## Verification state

The specific official release URL was attempted with an eight-second timeout. The request failed with `Unable to connect to the remote server`; no HTTP response was received. No local HTML copy was present in the workspace. Consequently, **the article has not yet been retrieved or imported**, and no event capture rows were created for it. The reported headline, 22 March 2025 publication date, ministry, and article wording remain unverified until the saved source page is imported.

## Implemented manual import

`backend/agri/events.py import-pib-html` accepts a Chrome “Webpage, HTML Only” save for PIB PRID 2114060. It checks for the PIB hostname and PRID in saved source metadata/links, checks the onion export headline and minimum extracted body text, records the genuine UTC local import timestamp, stores the original HTML and SHA-256, extracts visible article text, preserves publication precision as `source_date_only`, and only identifies a ministry when an explicit supported ministry label occurs in that saved source text.

Imports deduplicate by canonical PIB release identity plus extracted article text checksum. A changed article body is preserved as a new capture revision. The dashboard API returns the headline, article text, source identity, source date precision, capture time, classification evidence, and price impact hypothesis.

The rule classification is experimental: `export_policy`, onion relevance, and an explicitly uncertain policy/supply price hypothesis. It does not assert a validated direction or causal price effect.

## Manual procedure

Save the official page in Chrome using **Ctrl+S → Webpage, HTML Only** to:

`C:\Nexyra\data\pib\2114060.html`

Then, from `C:\Nexyra`, run:

```powershell
venv\Scripts\python.exe -m backend.agri.events import-pib-html --file data\pib\2114060.html
```

The command prints the actual extracted headline/date/ministry and checksums. Inspect that result, then run the backend and open the dashboard; the event endpoint is `GET /api/agri/events/recent?limit=50`.

## Tests and constraints

- Event tests: 9 passed, including strict identity checks, date-only semantics, deduplication, revision retention, event classification, and API record payload mapping.
- Frontend production build and TypeScript: passed.
- Existing database before import: 291 canonical prices, no event capture tables/rows. No real article capture has been inserted. No Phase 5A/model artifacts or price records were changed; no scheduler or Model C was added.
- A test HTML page validates the importer only. It is not a claimed PIB article and was never written to the application database.
