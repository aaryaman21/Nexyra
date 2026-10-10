# Nexyra Phase 4 — End-to-End Model Development Audit

Review date: 2026-10-09

## Executive result

Phase 4 infrastructure and honest UI states are implemented for research use. No production forecast is currently eligible. No real-world model was trained, selected, or registered in this phase because no available exact series has both sufficient chronology and trustworthy as-of evidence for the frozen evaluation protocol. The existing FAQ test period has already influenced prior research decisions. The newer exact canonical Local series have unknown source availability timestamps and short/incomplete date coverage.

The existing database was inspected read-only. Counts remain 291 canonical observations, 21,864 historical observations, 0 prospective observations, 0 prospective ingestion runs, 0 captured news/event records, 0 evaluations, and 0 predictions. The event capture tables were not created in the application database. Synthetic fixtures used in tests are test-only and are not research results.

## Implementation matrix

| Capability | State | Evidence / limitation |
|---|---|---|
| Exact series-aware numerical input validation | Implemented | Grade, unit, source and exact labels are retained. Availability basis is required. Seven-day retrospective availability is explicit and cannot be presented as verified. |
| Model A candidates and rolling evaluation | Implemented, real-series evaluation blocked | Baseline, seasonal naive, regularized regression and gradient boosting candidates exist. Selection uses validation; test is reported after selection. No exact recent series qualifies for a fresh untouched test under the existing protocol. |
| Model A inference endpoint | Implemented, research-only and unavailable without an evaluated artifact | `/api/agri/forecast/{series_id}?horizon=1|3|7` checks predictor/calibration fingerprints and as-of features. No active artifacts exist. No horizon model is selected. |
| Interval calibration | Implemented with safeguards | Calibration residuals are past-only; the served predictor is not refit after calibration. Intervals are labeled experimental and temporal coverage is not guaranteed. |
| Model B event classification | Implemented as transparent heuristic extraction | Onion category, relevance, severity heuristic and directional hypothesis are marked unvalidated. Direction is not a causal or price-impact claim. |
| Model B source capture | Partially implemented | A manual import supports saved official PIB RSS XML, preserves raw input/checksum and local capture time, and only accepts PIB-hosted item URLs. No live retrieval or scheduled polling is enabled. Historical availability cannot be inferred from present-day capture. |
| Model B independent evaluation | Blocked | There is no captured, complete, timestamped event archive; no historical predictive evidence is available. |
| Model C fusion and comparison | Blocked by Model B evidence | No validated event features or same-origin event/numerical evaluation matrix exists. No fused prediction is emitted. |
| Exact canonical observations | Browseable, availability unknown | `/api/agri/series` and `/api/agri/series/{series_id}` expose exact stored identities and observations; these do not imply forecast eligibility. |
| Prospective data collection | Available by explicit one-shot/manual commands | Existing AGMARKNET API adapter remains fail-closed pending official resource UUID/schema and network verification. No scheduler is enabled. |
| Frontend | Connected to real status and observation endpoints | Exact series/grade/source browsing, observation history, forecast selection/status, comparison/evaluation workspace and unavailable/error states are wired without styling changes. |

## Available exact series and forecasting status

The canonical table currently contains these three exact series (market label spelling is preserved):

| Market | Commodity | Variety | Grade | Observations | First to last date | Forecast status |
|---|---|---|---|---:|---|---|
| `Lasalgaon(Niphad)` | Onion | Other | Local | 74 | 2025-11-07 to 2026-05-05 | Evaluation blocked |
| `Lasalgaon(Niphad)` | Onion | Red | Local | 90 | 2025-11-25 to 2026-07-16 | Evaluation blocked |
| `Lasalgaon(Niphad)` | Onion | Unhali | Local | 127 | 2026-05-05 to 2026-10-08 | Evaluation blocked |

Their `available_at` values in the canonical storage are ingestion-time artifacts, not independently verified source publication/availability times. API responses therefore report availability as unknown. The historical FAQ pilot is `Lasalgaon (Niphad)` / Onion / Other / FAQ, 797 observations ending 2024-12-10; its previously evaluated 2024 period is not a new untouched holdout. Historical source availability is handled only under the documented seven-day retrospective assumption where an evaluation input explicitly declares that basis.

No series is selected for 1-, 3-, or 7-day forecasting. This is not a finding that every baseline is inaccurate; it means there is no defensible fresh test result with which to select or authorize one. No future test-period outcomes were inspected to make a selection.

## Model A details

The existing numerical pipeline supports last available price, seasonal naive, ridge regression and histogram gradient boosting candidates. Features include lagged/rolling prices, calendar effects, observation age and missing-date information, and the forecast API verifies that the calibrated artifact matches the exact predictor being served. Source/grade/market identity is part of the internal series key so distinct identities do not silently combine.

No actual-series candidate metrics are reported: no training/evaluation run was performed against the database observations in Phase 4. The historical FAQ holdout is contaminated for a new untouched evaluation, while recent Local records do not provide a qualified chronology and verified as-of lineage. Thus selected model for each horizon is **none**. User-uploaded datasets can be preflighted and evaluated through the local research workspace when their chronology and timestamp declaration meet the protocol; any resulting artifact remains `research_only`.

## Model B source coverage and results

The implemented import path accepts an operator-saved PIB RSS XML file and keeps the source publication timestamp (if present) separate from the actual local first-capture timestamp. It preserves raw feed and item evidence, checksums, revisions, source URL, and processing errors. Repeated items are retained with duplicate lineage rather than silently discarded. Only PIB-hosted links enter the article archive; third-party links are excluded.

This is a manual-file workflow, not a live collector. No PIB feed was fetched during this phase, and no real article/event counts or predictive results are claimed. The classifier produces reproducible heuristic tags; no calibrated classifier or embedding model was trained. Event archives cannot be exported for predictive use unless capture coverage is complete across the requested calendar interval and each included event has a verified publication timestamp. A local capture date is not proof of historical availability.

## Model C details

Model C is not evaluated or exposed as an available forecast. It requires validated Model B features and chronological out-of-fold numerical predictions on identical eligible origins and targets. Neither condition is met. This prevents reporting a synthetic uplift or implying that event fusion improves Model A.

## Backend and frontend workflows

Read-only observation and status endpoints:

- `GET /api/agri/series` — exact stored series discovery.
- `GET /api/agri/series/{series_id}` — latest stored observation and recent history, explicitly availability-unknown.
- `GET /api/agri/models` — research registry status; unavailable when no eligible artifact exists.
- `GET /api/agri/markets` — evaluated research bundles only.
- `GET /api/agri/market/{series_id}` — evaluated bundle metadata/history when available.
- `GET /api/agri/forecast/{series_id}?horizon=1|3|7` — fail-closed research inference.
- `POST /api/agri/workspace/datasets`, `/check`, `/evaluate`, and `GET /api/agri/workspace/jobs/{job_id}` — local upload, readiness, research evaluation and job status.

The dashboard lets users browse exact stored Local series and inspect recorded prices while showing unknown availability and evaluation-blocked status. Forecast controls require an available bundle; they do not substitute dummy prices. The research workspace retains CSV template, validation, readiness, chronological boundary and evaluation job flows. Explicit mocked UI fixtures exercise otherwise unavailable comparison/evaluation states and are not shown as real market forecasts. No CSS, palette, typography, animation, navigation or component styling was changed.

## Source provenance and unresolved dependencies

The official data.gov.in daily mandi-price catalog describes AGMARKNET-generated daily wholesale minimum, maximum and modal prices. The accessible official resource details do not establish the resource UUID, stable market/commodity/variety/grade identifiers, exact per-record unit, publication timestamp, correction behavior or complete archive coverage. The AGMARKNET manual indicates units may vary. The AGMARKNET adapter therefore remains fail-closed and no API response is claimed. See the [Phase 3F source integration report](agri_phase3f_official_source_integration.md) for verified and unverified findings and official links.

The PIB RSS file importer is limited to official PIB-hosted releases. It does not fetch the feed, bypass access controls, or assume republication rights for third-party content. PIB lists its [official press-release RSS feed](https://www.pib.gov.in/ViewRss.aspx?lang=1&reg=1) and its [terms and copyright conditions](https://www.pib.gov.in/ContentPage.aspx?lang=2&menuid=19&reg=48); confirm current source terms before redistribution. The terms exclude third-party material from the reproduction grant. Scheduler activation, live AGMARKNET collection, and protocol initialization remain separate future decisions.

## Tests and local commands

Verification performed:

- `.\venv\Scripts\python.exe -m pytest backend/tests -q` — full backend suite: **76 passed**, with two dependency deprecation warnings and one Windows pytest cache warning.
- `.\venv\Scripts\python.exe -m pytest backend/tests/test_agri.py backend/tests/test_agri_events.py -q` — latest targeted agriculture rerun: **40 passed**, three environment/deprecation warnings.
- `npm.cmd run build` in `frontend` — succeeded; Next.js production build and TypeScript checks passed.
- `python -m backend.agri.events --help` and `python -m backend.agri.prospective collect-datagov --help` — CLI help succeeded.
- Mock tests cover numerical provenance and availability, leakage/calibration fingerprints, API unknown-availability behavior, event timestamp separation, official-host filtering, duplicates/revisions, checksum preservation, date-gap rejection and archive reading.

No live external source collection was performed. A local browser workflow check (`node agri-workspace-check.cjs`) passed against temporary local backend and frontend services: it exercised actual series discovery/history, the real same-origin proxy's invalid-upload rejection, template download, validation/readiness gating, edit invalidation, mocked evaluation-job polling, mobile layout and reduced-motion behavior. Successful uploaded-data/evaluation responses in that script are explicitly mocked; this is an integration smoke test, not a real-data model evaluation. The separate dashboard browser check was not run because it writes screenshots over existing visual artifacts. The development server could not reach Google Fonts and used Next.js font fallbacks; the production build completed successfully. Both temporary services were stopped after the check.

Local startup commands:

```powershell
# From C:\Nexyra
.\venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# In a second terminal, from C:\Nexyra\frontend
$env:NEXT_PUBLIC_API_URL = "http://localhost:8000/api"
npm.cmd run dev
```

Manual PIB capture (first save an official RSS response through an authorized method; no timestamp is backdated):

```powershell
# From C:\Nexyra
.\venv\Scripts\python.exe -m backend.agri.events import-pib-rss --file C:\path\to\saved-pib-feed.xml
```

This import creates only additive event-capture tables in the configured app database and should be run only when the operator intends to persist the capture. No background schedule is enabled. To inspect commands without writing: `.\venv\Scripts\python.exe -m backend.agri.events --help`. AGMARKNET dry-run instructions and unresolved identity requirements remain in the Phase 3F report.

## Release status and next gates

All forecasting artifacts remain research-only; none is active or production-authorized. There are no selected horizon models and no populated prospective holdout. Next evidence gates are: verify the official AGMARKNET resource and exact source identity/unit; collect prospective records with genuine capture timestamps; select one exact series and freeze a distinct untouched future test before outcomes are observed; and build a complete, timestamped event archive before evaluating Model B or C. Until those gates pass, the correct dashboard state is observations available / forecasting evaluation blocked.
