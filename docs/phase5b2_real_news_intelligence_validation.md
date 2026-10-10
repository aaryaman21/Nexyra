# Phase 5B.2 — Real News Intelligence and Validation Audit

Audit date: 2026-10-09

## Completion status

Engineering improvements are implemented and the existing real PIB capture is now returned by the API and displayed in the existing Semantic Intelligence panel. Data coverage remains too small for classifier validation. Only PRID 2114060 exists in the configured database; the other three known articles below were source-verified but have not been downloaded/imported. Model B is an experimental retrieval/classification capability, not a validated price predictor. Model C remains blocked.

## Real article and database evidence

The configured `nexyra.db` already contained one real PIB capture/run for PRID 2114060. The first inspection of the default engine missed `.env` loading; this audit explicitly loaded the project environment. The saved file is `data/pib/2114060.html` (229,188 bytes), and its SHA-256 remains `3b5b2b91be180708df1a826b7ffc3436f3b03100bacb736feb960acab4e8234d`.

The saved HTML has a matching PIB saved-from URL, `og:title`, `og:url`, and `og:description`. It does **not** contain the actual article body or a visible publication header; the release appears to be loaded separately by PIB page scripts. Earlier extraction had incorrectly treated PIB navigation/footer text as article text. The importer now marks this capture `metadata_excerpt_only`, stores the genuine source description as the only excerpt, and ties the classification evidence to exact headline and excerpt passages. The original HTML remains in the capture-run raw payload; its checksum was recomputed from the stored raw payload and matched.

The official PIB release page was independently inspected. It reports the title, Ministry of Consumer Affairs, Food & Public Distribution, and `Posted On: 22 MAR 2025 7:18PM by PIB Delhi`. The time string has no explicit timezone in that source display. The record stores publication date `2025-03-22` at **date-only precision**, preserves the source time text without converting it to UTC, and records the official PIB verification URL, evidence, and actual metadata-verification time separately. These fields came from the official page rendering, not from the incomplete local HTML file.

Database state after this work:

| Table | Rows | Change in this phase |
|---|---:|---|
| `agri_daily_prices` | 291 | 0 |
| `agri_event_capture_runs` | 1 | 0; existing run/raw HTML preserved |
| `agri_event_captures` | 1 | 0; existing capture enriched in place |

One authentic article is classified with one supported event category, `export_duty_reduction`, backed by two exact text passages (headline and official meta description). Commodity relevance is `onion_direct`; geography is `india_wide`, not Nashik-specific; market series remains `unassigned`. The hypothesized mechanism is explicitly uncertain and unvalidated. No severity or source-confidence score is invented.

## Additional PIB articles verified for batch import

Official PIB pages/search results confirm the following identities and source facts:

| Article | PRID | Official date/ministry | Import status |
|---|---:|---|---|
| “2.60 lakh tons of onion exported in 2024-25, till 31st July, 2024” | 2042765 | 7 Aug 2024; Ministry of Consumer Affairs, Food & Public Distribution | Verified from official page; not present as a local HTML file |
| “Government notifies Minimum Export Price (MEP) of USD 800 per Metric Ton on onion export to maintain domestic availability” | 1972618 | 28 Oct 2023; Ministry of Consumer Affairs, Food & Public Distribution | Verified from official page; not present as a local HTML file |
| “Prohibition removed from Onion Export” | 1684194 | 28 Dec 2020; Ministry of Commerce & Industry | Verified from official PIB search result; not present as a local HTML file |

The source URLs are linked below. No record was created for these articles because no corresponding saved source HTML exists in `data/pib/`. The only local PIB HTML file is `2114060.html`.

## Implemented work

- Added `extract_event_intelligence` in `backend/agri/semantic.py`: explainable multi-label event rules, exact evidence passages and offsets, separate commodity/geographic relevance, mechanism labels, effective-date mentions, and explicitly unvalidated impact hypotheses. It distinguishes export-duty reduction from export-ban removal and avoids treating a historical ban mention as a new restriction.
- Generalized the PIB HTML adapter to inspect official `og:title`, `og:url`, `og:description`, PRID, and visible text. It rejects missing PIB identity/headline/description, records full source bytes and hash, extracts only article content after a visible headline, and labels incomplete pages as excerpt-only.
- Added repeatable batch import: `import-pib-directory`. Same identity plus same extracted-content checksum is deduplicated; a changed content checksum is stored as a revision; if the saved raw response is byte-identical to an existing capture, derived metadata/classification is enriched on that capture while the raw capture is left untouched.
- Added separate verification metadata recording for publication date/ministry, preserving the date-only value, source evidence, verification URL, and verification retrieval time.
- Expanded `GET /api/agri/events/recent` with date precision, captured/first-seen/available timestamps, source relevance, issuer, article text/content status, multi-label event classifications, evidence, and verification provenance.
- Extended the existing Semantic Intelligence panel to show the official source, publication date/time precision, retrieval/availability timestamps, exact evidence quotations, classifications, content completeness, and uncertain hypothesis. Existing layout and styling were retained.
- Added CSV annotation export/evaluation in `backend/agri/event_evaluation.py`. `data/pib/annotations.csv` contains one genuine capture row with empty human-label fields. No synthetic article is included.

## Validation and temporal limits

Current annotation status: **1 real article exported, 0 human-reviewed labels**. Evaluation returns `insufficient_labels`; precision, recall, F1, confusion analysis, and generalization claims are not reported. This is intentional. Manually review the CSV row and add more real article files before metrics are meaningful.

The event’s historical publication date does not imply historical Nexyra availability. `first_seen_at` and `available_at` remain the original local capture time in 2026. The event is ineligible as an as-of feature before that capture time. Model C feature generation remains blocked until source availability, event labels, and aligned price evaluation meet a leakage-safe protocol.

## Verified sources and remaining source work

- [PIB PRID 2114060](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2114060&lang=2&reg=48) — publication date, issuing ministry, reported 7:18 PM source text, and duty withdrawal.
- [PIB PRID 2042765](https://www.pib.gov.in/Pressreleaseshare.aspx?PRID=2042765&lang=2&reg=48) — Article A.
- [PIB PRID 1972618](https://www.pib.gov.in/Pressreleaseshare.aspx?PRID=1972618&lang=2&reg=48) — Article B.
- [PIB PRID 1684194](https://www.pib.gov.in/PressReleasePage.aspx?PRID=1684194&lang=2&reg=48) — Article C.

No other source adapter was added: no specific accessible official endpoint/feed was verified for the proposed IMD, DGFT, Department of Consumer Affairs, or Maharashtra sources in this phase. Their documents can use a later source-specific adapter or a separately attributed manual importer after their formats and terms are checked. No access controls were bypassed.

## Commands

Download official PIB pages in Chrome using **Ctrl+S → Webpage, HTML Only** into `C:\Nexyra\data\pib\` with filenames such as `2042765.html`, `1972618.html`, and `1684194.html`. Then batch import and reclassify:

```powershell
venv\Scripts\python.exe -m backend.agri.events import-pib-directory --directory data\pib
```

The command reports success, existing-capture enrichment, duplicate, review-required, or failed results by filename. For one page:

```powershell
venv\Scripts\python.exe -m backend.agri.events import-pib-html --file data\pib\2042765.html
```

Review records and evidence via the running API:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/agri/events/recent?limit=50 | ConvertTo-Json -Depth 12
```

Export the human annotation sheet, fill in `human_reviewed=true`, `human_categories`, commodity/geography labels, and review notes only after checking each cited source, then calculate exploratory metrics:

```powershell
venv\Scripts\python.exe -m backend.agri.event_evaluation export --output data\pib\annotations.csv
venv\Scripts\python.exe -m backend.agri.event_evaluation evaluate --file data\pib\annotations.csv
```

Start the API and frontend in separate terminals:

```powershell
venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
cd frontend
npm.cmd run dev
```

## Test results

- Backend suite: **87 passed**, 3 non-failing dependency/cache warnings.
- Frontend production build: **passed**, including TypeScript.
- API smoke via FastAPI TestClient: **200**, one genuine event returned with date-only publication precision, ministry, category, evidence, and excerpt status.
- Local Chrome/Playwright smoke against a production build on isolated ports: **passed**; the Semantic Intelligence panel displayed the actual PIB headline, `export_duty_reduction`, date `2025-03-22`, and the `metadata_excerpt_only` label.
- Raw-source integrity: recomputed stored raw payload SHA-256 matches the recorded hash.

## Remaining limitations

Only one genuine article is stored; its local source save lacks full body and publication header, although publication metadata was independently verified from PIB. Three more PIB releases have verified identifiers but still need HTML downloads/import. Other official sources need format verification. The rule classifier is experimental and has no manually reviewed labels or metrics. Price impact remains a hypothesis. No current event-based forecast or Model C feature is available.
