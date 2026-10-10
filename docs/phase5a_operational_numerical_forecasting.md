# Nexyra Phase 5A — Operational Numerical Forecasting

Run date: 2026-10-09. All outputs are research-only.

## Result

Model A now runs end to end for the exact historical pilot: read-only extraction from SQLite, daily calendar-origin feature construction under the explicit seven-day retrospective availability assumption, chronological candidate evaluation, persisted research artifacts, historical replay endpoints, and dashboard display.

The exact series is **Maharashtra / Nashik / `Lasalgaon (Niphad)` / Onion / Other / FAQ**. No other market label or grade was joined. There are **797 unique observation dates**, 2021-01-01 through 2024-12-10. The source is the Kaggle publisher `khandelwalmanas`, with an AGMARKNET attribution claim that has not been independently verified. The recorded unit is **INR/quintal, provisional and unverified**. All source availability timestamps are unknown. Historical features use the documented assumption that an observation dated D becomes available at D+7, 23:59:59 Asia/Kolkata; this is not a measured publication delay.

The original Phase 3A artifacts and evaluation file remain unchanged. The reused test window begins 2024-08-01 and reaches the previously examined target end of 2024-12-10. All metrics from that period below are explicitly retrospective diagnostics, not a fresh or independent holdout.

## Training and evaluation

The pipeline formed **1,440 daily calendar origins** for each horizon. Missing observation dates were not filled. A target counted as scored only when the exact horizon target date had a recorded observation. Origins without an available as-of price or complete numerical feature row were excluded from model comparisons; no price was synthesized.

| Horizon | Exact observed targets | Targets with as-of price | Complete scored origins used | Incomplete feature origins excluded | Unscored calendar origins |
|---:|---:|---:|---:|---:|---:|
| 1 day | 796 | 793 | 358 | 435 | 644 |
| 3 days | 795 | 793 | 334 | 459 | 645 |
| 7 days | 793 | 793 | 413 | 380 | 647 |

The split boundaries were fixed to the existing Phase 3A schedule: validation begins 2023-06-01; the reused test origins begin 2024-08-01. For all horizons, the eligible pre-test history used for the final evaluated artifact runs from origin 2021-03 (2021-03-16 for seven-day) through a last training target of 2024-07-24. Validation used 63 origins per horizon: 2023-06-01–2023-11-16 (1 day), 2023-06-02–2023-11-14 (3 days), and 2023-06-01–2023-10-18 (7 days). The reused test counts were 70, 72, and 68 origins, respectively.

Candidates were last-available-price naive, Ridge regression (alpha 1 and 10), and HistGradientBoosting. Candidate fits used chronological rolling validation and were retained as separate research artifacts. Seasonal naive was unavailable because its target-minus-seven-day input was not available at the forecast origin under the seven-day delay. Selection used validation only, with the existing minimum-gain and fold-stability gate.

| Horizon | Candidate | Validation MAE / RMSE | Reused test MAE / RMSE |
|---:|---|---:|---:|
| 1 | Naive | 357.22 / 547.41 | 411.39 / 585.39 |
| 1 | Ridge alpha 1 | 378.12 / 539.67 | 668.95 / 830.66 |
| 1 | Ridge alpha 10 | 384.43 / 540.85 | 692.23 / 839.15 |
| 1 | HistGradientBoosting | 455.83 / 633.80 | 1,157.00 / 1,356.23 |
| 3 | Naive | 415.67 / 623.84 | 463.22 / 594.25 |
| 3 | Ridge alpha 1 | 398.77 / 598.61 | 633.18 / 779.19 |
| 3 | Ridge alpha 10 | 402.02 / 603.43 | 643.08 / 772.48 |
| 3 | HistGradientBoosting | 452.49 / 691.71 | 1,014.10 / 1,171.59 |
| 7 | Naive | 278.79 / 461.50 | 615.10 / 765.60 |
| 7 | Ridge alpha 1 | 279.48 / 415.86 | 663.22 / 845.25 |
| 7 | Ridge alpha 10 | 279.45 / 415.62 | 680.47 / 838.54 |
| 7 | HistGradientBoosting | 320.47 / 423.37 | 1,404.79 / 1,542.85 |

**Selected research candidate at 1, 3, and 7 days: the last-available-price naive baseline.** Ridge alpha 1 has a lower validation MAE at three days, but it did not pass the required 5% gain and all-fold stability gate. The seven-day Ridge candidates did not beat naive MAE. No model was chosen using the test metrics.

Selected naive baseline diagnostics on the reused test window were directional accuracy 1.4%, 0.0%, and 0.0%, and empirical interval coverage 30.0%, 12.5%, and 14.7% for the 1-, 3-, and 7-day horizons. Intervals use the past-only 20-row calibration residuals and a finite rank of 19, but are **experimental and not reliably calibrated**; observed coverage is well below nominal 90%. These diagnostic test results do not qualify as fresh validation.

## Genuine historical replay

The persisted replay date is 2024-11-20 at the end-of-day Asia/Kolkata cutoff. The only price available under the assumed delay was 5,600 on 2024-11-13 (seven days old). The selected baseline predicts that latest as-of value for each horizon. Recorded outcomes are shown after each prediction and were not used as features:

| Horizon | Target date | Computed forecast | Recorded modal outcome | Error (forecast − actual) |
|---:|---|---:|---:|---:|
| 1 day | 2024-11-21 | 5,600 | 4,800 | +800 |
| 3 days | 2024-11-23 | 5,600 | 5,100 | +500 |
| 7 days | 2024-11-27 | 5,600 | 5,261 | +339 |

Values use the source's provisional INR/quintal label. They are actual model/baseline outputs from the saved artifacts, not manually supplied values. These are historical replays on a previously examined test period, not fresh out-of-sample evidence.

The saved exact series ends 2024-12-10 and was **668 days old** at verification. `/api/agri/research/latest/{series_id}` therefore returns HTTP 409 with `unavailable_stale`; it does not present the old series as a current market forecast. Historical replay remains available.

## Saved artifacts and interfaces

The current run is stored separately under `ml/research_only/phase5a_lasalgaon_niphad_other_faq_v2/`:

- `manifest.json` records the exact identity, provisional unit status, source and source-row fingerprints, software versions, availability policy, split boundaries, candidate summaries, selected candidate per horizon, and research-only/not-fresh-test status.
- `input_series.csv` is the reproducible 797-row model input snapshot with exact source lineage fields and an explicit retrospective availability basis.
- `h1.joblib`, `h3.joblib`, and `h7.joblib` are the selected horizon artifacts. Candidate estimator bundles are under `candidates/`.
- `evaluation.json` contains validation and reused-test comparisons; `replay_examples.json` contains the three computed replay outputs.
- `manifest.sha256` and artifact hashes are verified before API serving.

The Phase 5A artifacts are **not registered in the active model registry**. `GET /api/agri/models` continues to report no evaluated active model. New research-only endpoints are:

- `GET /api/agri/research/series` — list exact Phase 5A research identities and evaluation state.
- `GET /api/agri/research/series/{series_id}` — stored observations, source information, and staleness.
- `GET /api/agri/research/replay/{series_id}?origin=2024-11-20&horizon=1|3|7` — actual as-of replay plus a separately labeled historical outcome.
- `GET /api/agri/research/latest/{series_id}?horizon=1|3|7` — latest-origin research forecast only when the stored exact series is fresh; currently blocked as stale.

The dashboard now lists the exact historical FAQ series, shows its source and provisional unit status, permits a historical origin and horizon selection, and displays the actual replay, outcome, error, model identity, assumed availability, and stale/test-period warnings. The visual styling and Model B/C code were not changed.

## Verification

- Database-backed training command completed using the read-only historical table:

  ```powershell
  .\venv\Scripts\python.exe -m backend.agri.research_phase5a --database nexyra.db --artifact-root ml/research_only/<new-unique-run-directory>
  ```

  If `--artifact-root` is omitted, the command makes a timestamped new directory and refuses to overwrite an existing run.
- `.\venv\Scripts\python.exe -m pytest backend/tests -q` — **81 passed**, 3 environment/deprecation warnings.
- `npm.cmd run build` in `frontend` — production build and TypeScript checks passed.
- `node agri-phase5a-check.cjs` in `frontend` against temporary local services — passed with **real API responses and persisted real-data artifacts**, no mocked routes and no screenshots. It selected the exact FAQ series and displayed all three forecast/outcome pairs.
- Direct API checks confirmed each replay response matches `replay_examples.json` and the latest-origin request returns HTTP 409 stale.
- `GET /api/agri/models` remained unavailable; research artifacts were not activated.
- Read-only post-run database counts were unchanged: 291 canonical prices, 21,864 historical observations, 0 prospective observations, 0 prospective runs, 0 captured events, and 0 predictions. No source database records were changed.

## Local run commands

From `C:\Nexyra`:

```powershell
.\venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal from `C:\Nexyra\frontend`:

```powershell
$env:NEXYRA_BACKEND_URL = "http://127.0.0.1:8000"
npm.cmd run dev
```

## Readiness

This delivers a reproducible **research-only numerical workflow**, not production forecasting. There is no fresh independent holdout for this exact series; 2024 targets were previously examined. Historical availability is not verified, the source lineage is an attribution claim, and the unit is provisional. Test interval coverage is poor. Latest-origin forecasts are blocked while the series is stale. A future production path needs new observations for this exact identity, verified unit and market/source lineage, genuine as-of timestamps, and a test period fixed before any of its targets are inspected.
