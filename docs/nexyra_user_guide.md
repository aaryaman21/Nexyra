# Nexyra user guide

## Start Nexyra on Windows

From `C:\Nexyra`, run:

```powershell
.\scripts\run-dev.ps1
```

The script binds the backend and frontend to loopback only, checks that ports 8000 and 3000 are free, verifies API/database and frontend health, and stops only the two processes it launched when you press Ctrl+C. It does not terminate an existing process. If it reports an occupied port, inspect that PID and close the intended Nexyra terminal before retrying.

Open `http://127.0.0.1:3000`. The API health check is `http://127.0.0.1:8000/api/health`. Development logs are written under `logs/dev/`.

## Read market data

The dashboard keeps market, commodity, variety, grade, and source identities separate. It displays observed prices and dates from the local canonical series; an observation date does not prove the source publication time. No forecast is displayed as production-ready because no currently eligible production model is registered.

The saved Lasalgaon FAQ research baseline is a historical diagnostic ending 2024-12-10. Its test period was already examined, its availability policy was retrospective, and it is stale. Do not interpret that replay as a current market forecast or an independent accuracy result.

Choose a 1-, 3-, or 7-calendar-day horizon only when the dashboard reports an eligible forecast. If a model or exact target series is unavailable, the application reports that state instead of filling in a price. Historical and canonical observations are not interpolated across missing dates.

## Read market events

The Semantic Intelligence panel shows captured official releases, publication-date precision, local first-seen time, source links, experimental categories, and evidence passages. Rule-based categories are unvalidated. They are not causal price effects. An article first seen after a historical forecast origin cannot be used as context for that forecast.

## Review Model B articles

Open **Open local article review workspace** in the Semantic Intelligence panel, or visit `/review` directly.

1. Select an article and read the saved representation beside its source URL and capture metadata.
2. Enter your own reviewer identifier and explicitly choose relevance, commodity relevance, geography, and publication-date correctness.
3. Approve, reject, correct, or mark each predicted category unsupported. A relevant event requires a reviewed category and exact quotation from the saved text.
4. Add source-supported event dates with roles such as `effective_date`, `announcement_date`, or `reporting_period_end`.
5. Save only after completing the review. Nexyra records the actual server submission time and appends a review-history entry.

The current 18 PIB articles have already been inspected during development. Reviews of them are descriptive development data, not an independent test set. No human labels are present yet, so evaluation metrics remain unavailable. Reopening a reviewed article shows its previous history. Reviews tied to an older source revision do not mark a newer revision as reviewed.

This is a local-only review mode, not user authentication. The backend rejects non-loopback requests and cross-site browser origins for review routes. Do not expose the development server to a network or deploy this review API publicly.

## Add saved official agricultural text

The manual importer accepts a UTF-8 text file saved from an official IMD, AGMARKNET, or data.gov.in page. It copies the original bytes into `data/official_sources/`, stores checksums and a genuine local import/first-seen time, and deduplicates identical imports. A supplied publication date is marked unverified; no source publication time or timezone is inferred. Text stays a `manual_text_import_candidate` until a reviewer checks it against the original page.

Example, after you have obtained a genuine full-text copy yourself:

```powershell
New-Item -ItemType Directory -Force data\official_sources | Out-Null
.\venv\Scripts\python.exe -m backend.agri.official_documents import-text `
  --file data\official_sources\nashik_advisory.txt `
  --source-url "https://mausam.imd.gov.in/exact-original-document-url" `
  --title "Exact headline shown by the official source" `
  --reported-publication-date 2026-10-08
```

Omit `--reported-publication-date` unless the source page actually reports a date. This path does not download or authenticate article text. It accepts only official IMD, AGMARKNET, and data.gov.in hostnames, keeps source revisions, and does not merge identities by similar names. It does not by itself verify redistribution rights.

## Data limitations

- Canonical price observations: 291, latest observation date 2026-10-08; source availability timestamps remain unverified.
- Historical price observations: 21,864; the evaluated FAQ research series ends 2024-12-10.
- Prospective price observations: 0.
- PIB articles: 18 unique source identities, 18 stored full-body representations, 0 human-reviewed articles.
- No numerical news adjustment, production forecast, or independently measured Model B accuracy is available.

See the [release-candidate report](nexyra_release_candidate_report.md), [model-validation status](nexyra_model_validation_status.md), and [developer setup](nexyra_developer_setup.md) for the evidence and commands.
