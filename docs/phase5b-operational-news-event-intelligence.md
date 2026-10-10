# Phase 5B — Operational News and Event Intelligence

## Outcome

The source-attributed PIB capture path, recent-capture API, and dashboard display are implemented. **No authentic PIB response was retrieved**, so no article/event rows were created and the dashboard correctly displays an empty/unavailable state. The Phase 5B real-data acceptance criterion is therefore not yet met. No scheduler, model training, model registration, or price-table changes were made.

## Source contact and evidence

- Official feed URL attempted once directly: `https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=1`.
- Result: PowerShell `Invoke-WebRequest` failed with `Unable to connect to the remote server`; no HTTP status, headers, or response bytes were received. This is a network connectivity limitation in the current environment, not an observed PIB response or a confirmed source outage.
- No authentic local PIB RSS/article material was found in the repository. Test RSS fixtures are synthetic and were not imported.
- Current DB before/after implementation: `agri_daily_prices` 291 rows; legacy `agri_news_articles` 0 rows; prospective event capture tables absent; no event capture or run rows. Implementation does not create tables on API reads or on failed retrieval.

## Implementation

- `backend/agri/events.py`: reusable byte-response importer plus a one-shot fixed-URL HTTP adapter. Connect timeout is bounded to 1–30 seconds; retries to 0–3; response body limit 5 MB; short bounded exponential backoff; only PIB-hosted article links accepted. Raw response is stored with SHA-256, capture method and genuine UTC retrieval timestamp. Source `pubDate` remains a separate nullable field and is never synthesized. No credentials are required by this RSS feed adapter. CLI: `python -m backend.agri.events fetch-pib-rss` (optional `--timeout 10 --retries 2`). This can write additive event tables/rows only after a valid authentic response is received.
- `GET /api/agri/events/recent?limit=50`: read-only, returns source URL, article URL, raw checksum, title, classification evidence, publication timestamp/status, retrieval time, first-seen time, geographic/commodity relevance, and impact hypothesis. It returns `status=unavailable` with no events when the capture tables do not exist; it never initializes them.
- `frontend/components/modules/AgriDashboard.tsx`: the existing Semantic intelligence panel reads the endpoint, displays real source records and separates publication from retrieval time, labels rule outputs experimental, and provides explicit empty/unavailable states. Styling and layout were not changed.
- Classification remains transparent keyword rules (`transparent_keyword_rules_v1`). Rules record matched evidence; severity is only a lexical heuristic; price pressure is a hypothesis. No labeled real-article review set exists, so precision/recall/F1/confusion matrix are not estimable and no classifier was trained. Predictive forecasting from events is unavailable and unvalidated.

## Verification

- `venv\\Scripts\\python.exe -m pytest -q backend\\tests\\test_agri_events.py`: **7 passed**. Covers parsing, dedup/revisions, source restrictions, timestamp separation, missing publication time, successful mocked one-shot response with checksum, bounded network retries/failure, and no table creation on failure/read.
- `npm.cmd run build` in `frontend`: **passed**, including TypeScript.
- Genuine endpoint/browser display with real records: **not verifiable**, because no live official response was accessible and no backend dashboard browser service was running. The zero-record UI state is implemented; no real article is claimed.
- Model A artifacts and historical/canonical price records were not edited. No frontend style files were changed.

## Operational status and next action

Model B is operational as a **bounded retrieval/import and heuristic classification pipeline in code**, and the dashboard/API path is connected. It is **not yet operational with genuine records in this environment** because the source request could not connect. It is not a validated price predictor.

After network access to `pib.gov.in` is available, run once from `C:\\Nexyra`:

```powershell
venv\\Scripts\\python.exe -m backend.agri.events fetch-pib-rss --timeout 10 --retries 2
```

Then verify, without initiating another collection:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/agri/events/recent?limit=50
```

The command itself stores authentic items and a raw response only after a successful HTTP response and valid PIB RSS parsing. It is one-shot; no recurring schedule is configured. Once real articles exist, manually review a documented sample before reporting classifier metrics or training any classifier. Historical use remains barred unless both source publication time and first local capture/availability meet the forecast-origin cutoff.
