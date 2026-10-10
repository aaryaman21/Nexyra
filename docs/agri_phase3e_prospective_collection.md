# Phase 3E prospective collection

## Scope and source findings (verified 2026-10-09)

- The OGD catalog identifies the Department of Agriculture and Farmers Welfare / Directorate of Marketing and Inspection as contributor and says the current daily maximum, minimum and modal prices are generated through AGMARKNET. It describes daily granularity. This verifies the dataset description, not the correctness of every record or an update publication time. [OGD catalog](https://www.data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi)
- OGD advertises a data API, and its help says registered users can generate API keys. The precise resource ID and current field schema must be checked against the chosen resource before collection. This repository deliberately does not default to an unverified ID. [OGD API resource](https://www.data.gov.in/resource/variety-wise-daily-market-prices-data-commodity), [API help](https://www.data.gov.in/help)
- OGD catalog terms state that a dataset's license metadata controls. OGD describes Government Open Data License India for portal data, including provider/source/license attribution, non-endorsement, no warranty, and no guarantee of continued supply. Confirm the individual resource license and applicable third-party content before redistribution. [OGD terms](https://www.data.gov.in/terms-of-use), [GODL-India](https://ap.data.gov.in/godl)
- AGMARKNET's official data-entry SOP describes daily price/arrival entry; it does not establish a public historical first-publication timestamp or revision feed. The official resource page was unavailable during this review. [AGMARKNET SOP](https://www.agmarknet.gov.in/DailyDataEntry/Docs/SOP_DEO.pdf)
- The official OGD catalog describes minimum, maximum and modal prices but the accessible metadata does not define their unit, establish FAQ versus Local grade equivalence, provide stable market/commodity/variety identifier masters, or specify publication/revision timestamps. These remain unresolved. The app's prior stored INR/quintal values do not independently verify source-wide unit semantics.
- OGD describes current daily records and a separate variety-wise resource. Historical archive depth and completeness for the exact Lasalgaon identity were not verified. Do not treat an API's current response as a complete archive.

## Storage and revision model

The new backend.agri.prospective module creates four additive tables only:

- agri_prospective_ingestion_runs: source, method, actual retrieval time in UTC, payload checksum, status, and validation errors.
- agri_prospective_observations: exact source IDs and labels, date, price triple, source unit, nullable source publication time, immutable first-seen time, latest retrieval, and current revision count.
- agri_prospective_revisions: append-only raw record per poll, checksum, retrieval time, revision number, and initial/duplicate/correction classification.
- agri_prospective_protocols: a hash-protected frozen protocol record.

Each run retains the raw UTF-8 response payload alongside its SHA-256 checksum. The new path does not write to agri_daily_prices or agri_historical_price_observations. It never derives source publication time from retrieval time or observation date. An exact repeated poll is retained as a duplicate revision; a changed price is retained as a correction. Stable source IDs with changed labels or units are rejected for review. No alias resolution is attempted.

## Prospective protocol

The persisted protocol is phase3e-prospective-v1. It targets the exact prior pilot identity Lasalgaon (Niphad) / Onion / Other / FAQ. Its official market source ID is intentionally null until verified. It defines calendar-day origins at end of day Asia/Kolkata, exact 1/3/7 calendar-day targets, no interpolation, genuine as-of availability only, 60 proper training rows, 20 calibration rows, three validation folds of 21 scored origins, and at least 21 untouched test targets per horizon. The new test boundary must be set before its targets are observed. No test rows exist in the prospective store at setup.

For prospective as-of views, use an observation only from its genuine source publication timestamp, if provided, or from first_seen_at_utc. Later corrections cannot alter earlier snapshots. Freeze the evaluated revision snapshot and disclose later corrections separately. The prior retrospective seven-day proxy is not eligible as prospective publication evidence.

## Collection

Manual CSV is the safe path until the OGD API resource schema and credentials are confirmed. Required CSV columns:

market_id,market_label,commodity_id,commodity,variety_id,variety,grade_id,grade,observation_date,min_price,max_price,modal_price,source_unit,source_publication_at

Optional identifiers/publication time may be blank. Publication timestamps, when present, must include a timezone. Retrieval time is taken by the importer at capture and is never supplied in the file. Preserve the downloaded source file unchanged.

Initialize the four additive tables and persist the frozen protocol before collection:

```powershell
.\venv\Scripts\python.exe -m backend.agri.prospective initialize
```

```powershell
.\venv\Scripts\python.exe -m backend.agri.prospective import-csv `
  --file data\incoming\agmarknet-onion.csv `
  --source-url "https://www.data.gov.in/resource/<verified-resource>"
```

Official API adapter, only after obtaining credentials and verifying the resource ID/schema:

```powershell
$env:DATA_GOV_IN_RESOURCE_ID = "<verified-resource-id>"
$env:DATA_GOV_IN_API_KEY = "<personal-api-key>"
.\venv\Scripts\python.exe -m backend.agri.prospective collect-datagov `
  --filter "<verified-market-field>=<exact-label>" `
  --page-size 10 --max-pages 1
```

The adapter requires at least one exact source filter in the CLI and does not invent field mappings: a response lacking required stable IDs or exact normalized field names is recorded with validation errors and cannot create valid observations. See the Phase 3F source assessment for the bounded one-shot command. No recurring scheduler is configured. A recommended initial manual schedule is once after the official daily report is published on each working day, with a second capture the following day to detect corrections; confirm the source's actual release cadence first. Do not collect on a timer until the endpoint, usage limits, and release behavior are verified.

Read-only audit commands:

```powershell
.\venv\Scripts\python.exe -m backend.agri.prospective audit-integrity
.\venv\Scripts\python.exe -m backend.agri.prospective audit-gaps `
  --market-id "<verified-id>" --commodity-id "<verified-id>" `
  --variety-id "<verified-id>" --grade-id "<verified-id>"
```

Calendar gaps are reported as unobserved dates with closure status unknown.

## Readiness gates

Before a forecast study, verify with the data provider: stable market IDs and their geographic scope; commodity/variety/grade code lists and FAQ/Local definitions; price unit and any unit changes; source publication timestamp semantics and correction behavior; archive coverage; individual resource license and redistribution rights; API rate limits and key handling. Then select an exact source ID matching the frozen identity or create a separately versioned protocol before any targets are observed. This phase does not enable a scheduler, train/register models, or claim a populated holdout.
