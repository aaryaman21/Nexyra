# Nexyra model-validation status

Reviewed: 2026-10-09

## Model A — numerical onion price forecast

**Status: blocked by validation for production; historical research baseline functional.**

The target in the saved Phase 5A replay is modal wholesale onion price in INR/quintal for the exact identity Maharashtra / Nashik / Lasalgaon (Niphad) / Onion / Other / FAQ. It uses calendar-day origins and exact 1-, 3-, and 7-day targets. Price availability in that historical dataset is unknown; the evaluation used an explicit seven-day retrospective assumption. The source URL is a Kaggle dataset and its AGMARKNET attribution claim was not independently verified.

The selection rule retained the last-available-price baseline (`naive`) at all three horizons. Selection used rolling validation only. These metrics are historical diagnostics from a reused test period, not prospective performance or a fresh holdout:

| Horizon | Validation n | Validation MAE / RMSE | Reused test dates | Test n | Test MAE / RMSE | Empirical interval coverage |
|---|---:|---:|---|---:|---:|---:|
| 1 calendar day | 63 | 357.22 / 547.41 | 2024-08-01 to 2024-12-10 | 70 | 411.39 / 585.39 | 30.0% |
| 3 calendar days | 63 | 415.67 / 623.84 | 2024-08-01 to 2024-12-10 | 72 | 463.22 / 594.25 | 12.5% |
| 7 calendar days | 63 | 278.79 / 461.50 | 2024-08-01 to 2024-12-10 | 68 | 615.10 / 765.60 | 14.7% |

The nominal interval target was 90%; observed coverage was poor. No calibrated coverage guarantee is claimed. The saved evaluation includes alternative-model results; no learned candidate passed the baseline selection gate. The historical test period and its targets have already been examined and cannot be reused as a new untouched holdout.

At the current verification date the saved exact FAQ series ends on 2024-12-10. The canonical table has 291 observations through 2026-10-08, but the newer rows are different Local-grade identities and source availability remains unverified. The latest canonical observation is not silently joined to the old FAQ series. No currently registered production model is available.

## Model B — event classification and evidence

**Status: functional but experimental; real-world accuracy blocked by missing human labels.**

- 18 unique PIB article identities; 19 source capture rows because one article has two captures.
- 18 selected full-body representations; extraction status does not mean every body has been human-checked for completeness.
- 34 experimental article/category assignments across 11 categories.
- 0 human-reviewed articles; accuracy metrics are unavailable.
- The 18 existing articles are development-reused and not an independent test sample.
- The persisted prospective cutoff is 2026-10-10 00:00 UTC. No eligible prospective test articles have been reviewed.

The local review interface records relevance, commodity/geographic relevance, category-level approve/reject/correct/unsupported decisions, exact evidence passages, date roles, publication-date correctness, reviewer-supplied identity, and actual save time. Reviews append and preserve the prior source predictions and history. Evaluation now reports relevance scores, event micro/macro and per-category counts, exact evidence and date-role matches, publication-date denominator, missing-evidence rate, and exclusions when gold labels exist. No actual review labels were added during this work.

Near-duplicate bodies are grouped at the frozen five-word-shingle Jaccard threshold of 0.90. Revisions stay in the same article identity. Same-event announcements still require human grouping before a defensible train/test separation.

## Model C — combined context

**Status: context-only architecture implemented; operational output blocked by missing eligible inputs.**

The `model-c-context-only-v1` contract requires a Model A forecast, a matching exact-series identity, current source-revision checksum, human-reviewed event labels, and first-seen time no later than the forecast origin. It returns sourced context with the original Model A forecast unchanged. There are no price adjustments, learned impact coefficients, causal effects, or uplift claims. With no registered eligible production forecast and no reviewed event labels, the API reports `forecast_unavailable` and emits no context.

## Prospective evidence needed

1. Verify a stable exact-market price source and retain genuine acquisition timestamps and revisions.
2. Accumulate a sufficiently long exact series without merging markets, varieties, or grades.
3. Freeze a new untouched test window before observing its target prices.
4. Human-review the existing development articles, then collect future independent articles after the frozen cutoff and group revisions/near-duplicates/same events before scoring.
5. Require several independent reviewers and adjudicate evidence/date disagreements before making accuracy claims.
6. Evaluate Model C only on overlapping forecast origins for which both price and event features were genuinely available at the origin.
