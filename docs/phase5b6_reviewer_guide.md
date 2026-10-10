# Model B human review guide

Use the review queue to create source-grounded labels. The predictions in each JSON line are for reviewer context only; they are not gold labels.

## Export a fresh queue

From `C:\Nexyra`:

```powershell
venv\Scripts\python.exe -m backend.agri.event_evaluation export-review --output data\pib\phase5b6_review_queue.jsonl
```

Edit only the `review` object in each JSON line. Keep `capture_id`, `article_identity`, and `source_content_sha256` unchanged. Use:

- `status`: `reviewed`
- `reviewer_id`: a stable reviewer identifier
- `reviewed_at_utc`: actual review time with `Z` or an explicit UTC offset
- `relevance`: `relevant`, `irrelevant`, or `uncertain`
- `publication_date_correctness`: `correct`, `incorrect`, or `uncertain`; if incorrect and the source supports a correction, provide `corrected_publication_date` as ISO `YYYY-MM-DD`
- `events`: zero or more labels from `backend/agri/semantic.py`'s `EVENT_TAXONOMY`
- `evidence[].quote`: an exact, contiguous quotation from that article's exported `article_text`
- `dates[].date`: an ISO `YYYY-MM-DD` date, with a `role` such as `announcement_date`, `effective_date`, `reporting_period_end`, or `publication_date`

Do not mark a missing date or evidence span as a negative event label. Use `uncertain` when the source does not support a reliable decision. Keep corrections as new review submissions; the importer appends them and links them to the prior review. Re-importing an identical review is idempotent.

## Import and evaluate

```powershell
venv\Scripts\python.exe -m backend.agri.event_evaluation import-reviews --file data\pib\phase5b6_review_queue.jsonl
venv\Scripts\python.exe -m backend.agri.event_evaluation evaluate --json-output data\pib\phase5b6_evaluation.json --markdown-output data\pib\phase5b6_evaluation.md
```

The importer checks the source revision checksum, immutable article identity, event taxonomy, exact evidence text, and date format. It writes only to the new append-only review table. Current captures have already been inspected during development and are always reported as development-reused; they cannot form an independent test set.
