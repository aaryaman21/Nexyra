# Nexyra developer setup

## Supported local workflow

This release candidate was validated on Windows PowerShell with the repository's Python virtual environment, Node dependencies, Microsoft Edge, and Next.js 16.3.4. It uses the existing SQLite database. Do not reset or replace `nexyra.db`.

If setting up a new checkout, create an environment file only if one does not already exist. Do not overwrite an existing `.env`:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Push-Location frontend
npm.cmd install
Pop-Location
```

The checked-in `.env.example` contains no credentials. The optional data.gov.in key and resource ID remain blank until a specific official resource is verified. The review API requires no key because it is restricted to local loopback access.

## Start and stop

From `C:\Nexyra`:

```powershell
.\scripts\run-dev.ps1
```

The script checks the exact TCP listening ports with `netstat`, reports owner PIDs, and refuses to launch if either configured port is occupied. It never stops an existing process. It starts Uvicorn and Next.js bound to `127.0.0.1`, checks `/api/health` and the frontend root, and remains in the terminal until Ctrl+C. Logs are under `logs/dev/`; only processes started by the script are stopped during cleanup.

Manual startup is available in separate terminals:

```powershell
# Backend, from C:\Nexyra
.\venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

```powershell
# Frontend, from C:\Nexyra\frontend
$env:NEXYRA_BACKEND_URL = "http://127.0.0.1:8000"
npm.cmd run dev -- --hostname 127.0.0.1 --port 3000
```

Health checks:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-WebRequest http://127.0.0.1:3000 -UseBasicParsing
```

`/api/health` returns `status`, `database`, and the `loopback_only` review mode. An old backend process may answer `/api/health` without the `database` field; stop only the stale Nexyra instance identified by its port owner and old API response.

## Database and source preservation

The application database defaults to `sqlite:///./nexyra.db`. Existing price and PIB tables are not reset by startup. Event schema setup is additive. The manual source importer creates a capture run, a source capture, and a text representation while preserving the original text file under `data/official_sources/`.

Read-only price data counts can be checked with:

```powershell
.\venv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect('file:C:/Nexyra/nexyra.db?mode=ro',uri=True); print({'canonical':c.execute('select count(*) from agri_daily_prices').fetchone()[0], 'historical':c.execute('select count(*) from agri_historical_price_observations').fetchone()[0], 'prospective':c.execute('select count(*) from agri_prospective_observations').fetchone()[0]}); print(c.execute('pragma integrity_check').fetchone()[0]); c.close()"
```

Do not use database deletion, `DROP`, or destructive initialization commands. The storage migration CLI is additive, but this release does not require a migration reset.

## Model B review and evaluation

The review page is `/review`. Its API is local-only:

- `GET /api/agri/review/queue`
- `GET /api/agri/review/evaluation`
- `GET /api/agri/review/articles/{capture_id}/history`
- `POST /api/agri/review/articles/{capture_id}`

Each explicit submission is validated against the current source checksum and article identity. Evidence quotations must be contiguous text in the saved representation; event date fields require valid ISO dates and roles. Reviews append and link to earlier reviews; source predictions are retained independently. Reviewer identifiers are entered by the reviewer, and the submission timestamp is generated at save time.

The equivalent CLI for queue export/import/evaluation is:

```powershell
.\venv\Scripts\python.exe -m backend.agri.event_evaluation export-review --output data\pib\phase5b6_review_queue.jsonl
.\venv\Scripts\python.exe -m backend.agri.event_evaluation import-reviews --file data\pib\phase5b6_review_queue.jsonl
.\venv\Scripts\python.exe -m backend.agri.event_evaluation evaluate --json-output data\pib\phase5b6_evaluation.json --markdown-output data\pib\phase5b6_evaluation.md
```

No human annotation has been supplied. The current articles are development-reused, and the prospective eligibility cutoff remains 2026-10-10 UTC. Do not report the current set as an independent test. Same-event relationships and reviewer disagreements still need explicit adjudication.

## Official-source text import

The new manual importer does not issue HTTP requests. It is available for genuine text files saved from official IMD, AGMARKNET, or data.gov.in sources:

```powershell
.\venv\Scripts\python.exe -m backend.agri.official_documents import-text `
  --file data\official_sources\document.txt `
  --source-url "https://mausam.imd.gov.in/exact-original-document-url" `
  --title "Exact official headline"
```

Optionally pass `--reported-publication-date YYYY-MM-DD` only when the official page reports a date. The importer stores it as operator-supplied and unverified, keeps source publication time null, archives the original bytes, and records the current local import time. It rejects non-HTTPS or non-allowlisted hosts, short content, invalid UTF-8, and files above 5 MB. Duplicate bytes for one exact source URL are idempotent; changed source bytes create a new revision.

For PIB, use the existing `backend.agri.event_dataset` manifest collector and `backend.agri.events` importers. Live PIB collection remains bounded and one-shot; there is no scheduler.

## Validation and build commands

From project root:

```powershell
.\venv\Scripts\python.exe -m pytest backend\tests -q -p no:cacheprovider
```

From `C:\Nexyra\frontend`:

```powershell
npx.cmd tsc --noEmit
npm.cmd run build
```

Browser smoke with Microsoft Edge and Playwright installed:

```powershell
node agri-phase5b6-check.cjs
```

That script expects the local backend and frontend to be running. The populated dashboard data comes from the local real capture database; any fixture-specific tests are not production or accuracy evidence.

## Model commands and boundaries

The historical replay command and its saved artifacts are described in `docs/phase5a_operational_numerical_forecasting.md`. They are research-only. The old Lasalgaon FAQ series has a previously examined test period ending 2024-12-10. Do not retrain or register it as a production forecast. No fresh exact-series price data was added in this release candidate.

Model C is exposed as `GET /api/agri/combined/{series_id}?horizon=1|3|7`. It pairs an eligible Model A forecast with checksum-matched, human-reviewed evidence available by the forecast origin. It never changes the numeric forecast. Because no production Model A bundle or human-reviewed articles exist, the current response is `forecast_unavailable` with no event context.

## Security and licensing

Keep Uvicorn on `127.0.0.1`. The review API checks loopback client, host, and browser origin; CORS allows local development origins only. This is a local-development control, not authentication or deployment hardening. Never publish the service or expose review data on a shared network.

PIB says its website material may be reproduced with attribution and accuracy, while third-party material is excluded. data.gov.in terms defer to each resource's `license` metadata; verify that metadata for any selected dataset. We did not verify IMD/AGMARKNET redistribution permissions for stored full text. Keep source links and attribution, avoid packaging their full documents for redistribution, and treat any manual source-text import as local research material until its terms are checked.
