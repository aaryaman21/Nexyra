# Phase 3F — Official AGMARKNET integration assessment

Review date: 2026-10-09. A bounded read-only probe was attempted, but the network refused the connection. No price response, collection, new protocol, or database write resulted.

## Officially verified

- The OGD catalog describes “Current daily price of various commodities from various markets (Mandi)” as AGMARKNET-generated daily data with wholesale minimum, maximum, and modal price. It lists the Department of Agriculture and Farmers Welfare / Directorate of Marketing and Inspection as contributor and shows two catalog resources, including “Variety-wise Daily Market Prices Data of Commodity.” [OGD catalog](https://www.data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi)
- The OGD resource listing identifies the variety-wise dataset and its daily granularity, but the accessible resource metadata does not expose its field list or API UUID. [OGD variety-wise resource](https://www.data.gov.in/resource/variety-wise-daily-market-prices-data-commodity)
- OGD help says registered users can generate an API key and access API URLs. A local credential is configured, but no resource UUID is configured. The credential value is not recorded or included in this report. [OGD API help](https://www.data.gov.in/help)
- The official AGMARKNET user manual describes a standard price unit of Rs./Quintal or Rs./Number for a commodity variety and allows a locally configured unit with a conversion formula. Therefore the unit must be checked for the exact variety/market record; INR/quintal cannot be assumed universally. [AGMARKNET user manual](https://www.agmarknet.gov.in/DailyDataEntry/UserManual.pdf)
- The AGMARKNET entry SOP describes daily variety-wise min/max/modal price entry and selecting dates for entries. It does not document a public per-observation first-publication timestamp, correction API, historical revision feed, or archive completeness. [AGMARKNET SOP](https://www.agmarknet.gov.in/DailyDataEntry/Docs/SOP_DEO.pdf)
- OGD portal terms direct users to the individual dataset license. The portal describes Government Open Data License India for portal content, but the resource-specific license and treatment of any third-party material must be checked before redistribution. [OGD terms](https://www.data.gov.in/terms-of-use), [GODL-India](https://ap.data.gov.in/godl)

## Unverified for the chosen resource

| Item | Finding |
|---|---|
| Resource UUID | Not exposed in accessible official metadata. UUID `9ef84268-d588-465a-a308-a864a43d0070` is commonly cited for the current daily mandi-price API by nonofficial references, but was not verified against an official API page or response in this review. It is not configured. A probe against this candidate did not connect, so it did not verify the UUID. |
| Endpoint | OGD advertises an API. The adapter's conventional URL is `https://api.data.gov.in/resource/{resource-id}`; the exact resource route and current availability remain unverified for this resource. |
| Authentication | OGD API-key access is documented. The adapter sends `api-key`, `format`, `limit`, and `offset` query parameters. Resource-specific limits and API-key query syntax were not verified directly against this endpoint. |
| Record schema | The official accessible resource page does not expose it. A commonly referenced schema has state, district, market, commodity, variety, grade, arrival_date, min_price, max_price, modal_price, but this was not confirmed from a live official schema. |
| Stable IDs | No market ID, commodity ID, variety ID, or grade ID is documented in the accessible resource metadata. Names are not identifiers. |
| Price unit | The catalog describes price fields but does not state the unit for each observation. AGMARKNET documentation indicates units can vary by variety and local configuration. |
| Date semantics | OGD describes daily granularity; the source page does not clarify whether `arrival_date` is also the exact price observation date in every record. |
| Publication/update time | No per-record publication timestamp or correction behavior is documented. Dataset-level `updated` metadata, if returned by a generic API, must not be used as an observation availability timestamp. |
| History/license | Completeness of historical archive for the exact market identity is unverified. Individual resource license should be confirmed before public redistribution. |

## Cached Nexyra coverage (not a live source check)

The latest report export already stored in Nexyra uses the exact label `Lasalgaon(Niphad)` (without a space before the parenthesis), and contains:

| Stored market label | Commodity | Variety | Grade | Rows | Date span |
|---|---|---|---|---:|---|
| `Lasalgaon(Niphad)` | Onion | Other | Local | 74 | 2025-11-07–2026-05-05 |
| `Lasalgaon(Niphad)` | Onion | Red | Local | 90 | 2025-11-25–2026-07-16 |
| `Lasalgaon(Niphad)` | Onion | Unhali | Local | 127 | 2026-05-05–2026-10-08 |

No Lasalgaon FAQ row appears in that cached canonical report subset. The historical Kaggle table separately has `Lasalgaon (Niphad)` / Onion / Other / Local (179 records, 2025-02-17–2025-11-01) and Red / Local (55, 2025-01-27–2025-04-15), but this is not verified as official API lineage. The previously frozen exact FAQ pilot remains unchanged. The two spellings are not treated as equivalent here.

These cached rows establish that Local values were present in a previous report export under the compact spelling; they do not prove that the live OGD API currently publishes those exact series. No live series counts were fetched.

## Adapter assessment and tests

`backend.agri.prospective.collect_datagov` now defaults to a bounded dry-run (10 rows, one page). It loads credentials from `.env` or process environment without printing them; the key is sent only in the API request and excluded from saved source URLs. A UUID syntax check is not evidence that a resource ID is official. Dry-run reports only metadata, row count, field names, and checksum, and does not create tables or print price values. Ingestion requires the explicit `--ingest` flag, exact filters, matching resource title and complete expected field set. It preserves raw UTF-8 response bytes and SHA-256, records retrieval time in UTC, and leaves source publication time null unless supplied by the source.

API-level limitations are fail-closed: missing credentials or resource ID cause no request; HTTP errors/network errors return sanitized errors; HTTP 429 and 5xx/network errors use bounded retries and backoff; malformed JSON/schema and incomplete pagination are rejected. Dry-run does not require exact filters; ingestion does. API keys are not persisted in the run URL or output. A failed/dry-run request creates no database tables or observations. Mock tests cover credential loading, resource validation, schema/title gates, filters, pagination, empty response, auth errors, rate limits, network failure, and no-write dry-run behavior.

The source-shaped API record mapping uses the explicit commodity code field, but it does not synthesize a market ID or infer a unit. A source record with the commonly cited 11 fields therefore fails normalization for missing stable market ID and unit; the raw response and validation errors are preserved if an operator explicitly requests ingestion after source verification. No observation is inserted for that record. The accessible official metadata does not establish those identifiers or units.

## Local-grade protocol decision

No separate Local protocol is initialized or activated. Although cached report rows show Local values, official live identity, source IDs, unit, and publication availability were not confirmed. Creating a protocol now would incorrectly promote cached label evidence to an official source identity. After those details are verified, a separately versioned proposal can target one exact identity (likely the compact market label and one variety/grade), with its own source lineage, calendar 1/3/7-day horizons, first-seen as-of rule, and future test dates fixed before their outcomes are observed. The frozen FAQ protocol remains untouched.

## Required next steps

1. Obtain an OGD API key from a registered OGD account and confirm access.
2. From the official resource page/API metadata, verify its UUID, exact field IDs/types, page-size/rate limits, identifier masters, and whether a stable market ID is available.
3. Confirm units by exact variety/market and determine whether the API supplies observation publication timestamps or corrections.
4. If market/commodity/variety/grade IDs or unit are absent, ask the data owner for authoritative code lists and mapping documentation. Do not derive IDs from labels.
5. Only after review, configure the resource ID in the local environment and separately approve creation of a Local protocol if exact Local identity is confirmed.

No scheduler is enabled. After resolving the resource/schema/identifier blockers and explicit approval, a bounded one-shot request can use `collect-datagov` with exact verified source filters, `--page-size 10`, and `--max-pages 1`:

```powershell
$env:DATA_GOV_IN_RESOURCE_ID = "<officially verified resource UUID>"
$env:DATA_GOV_IN_API_KEY = "<personal OGD API key>"
.\venv\Scripts\python.exe -m backend.agri.prospective collect-datagov `
  --resource-id "<officially verified resource UUID>" `
  --filter "<verified-market-field>=<exact-source-label>" `
  --filter "<verified-commodity-field>=<exact-source-value>" `
  --filter "<verified-variety-field>=<exact-source-value>" `
  --filter "<verified-grade-field>=<exact-source-value>" `
  --page-size 10 --max-pages 1
```

This command is a dry-run by default and reads the key from `.env`. The workspace has no `.git` directory, so tracked-file status cannot be determined; `.gitignore` now excludes `.env`. Verify the run checksum, UTC capture timestamp, raw response, validation errors, and unchanged canonical/historical row counts before approving ingestion. Do not choose filter names or a market spelling from the Nexyra cache alone.

## Implementation verification (Phase 3F follow-up)

- The candidate UUID probe requested one row and was read-only. The sandbox first reported a connection error; the permitted retry returned `connection_refused`. No response schema, prices, market identity, or live grades were obtained.
- Current access blockers: official UUID and API schema need authoritative confirmation; the network path to `api.data.gov.in` must permit access. Confirm stable market identity and per-series price units with official metadata before observation insertion.
- Existing cached coverage remains non-live evidence. FAQ and Local remain separate; no alias or protocol has been created.
- The one-shot CLI command is `python -m backend.agri.prospective collect-datagov --resource-id <verified-uuid>`. Without `--ingest` it is dry-run only. A real ingestion run additionally requires verified exact `--filter` arguments. A returned record cannot create an observation until mandatory market ID and source unit validate.
- API key has not been placed in source or output. Git status remains unavailable because this workspace is not a Git repository.
