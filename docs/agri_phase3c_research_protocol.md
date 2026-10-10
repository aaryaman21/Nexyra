# Phase 3C retrospective research protocol

## Scope and safeguards

This protocol is research-only. The Phase 3A report and model artifacts remain unchanged. The Phase 3C adapter performs no model fitting, registration, database writes, source-data writes, alias resolution, or frontend work.

The exact pilot identity remains **market label `Lasalgaon (Niphad)` / Onion / Other / FAQ**. No market spelling, APMC suffix, Niphad/Vinchur location, or FAQ/Local grade is merged without a documented and verified mapping.

## Calendar origins and target eligibility

- Origins cover every calendar date in an explicitly supplied inclusive period, at **23:59:59 Asia/Kolkata**.
- The seven-day availability rule remains an explicitly retrospective assumption: an observation dated D is assumed available at D+7, 23:59:59 Asia/Kolkata. It is not a verified timestamp and is never written to the database.
- Every feature is formed from observations whose assumed availability is no later than that origin. The latest available price may be carried forward as a feature; no synthetic observation is created. The adapter reports both the age of that price from its market observation date and the age since its assumed release.
- Exact availability-calendar lags at 1 and 7 days remain missing when no observation was released on that date. Missing flags accompany those values. Rolling summaries use only actual released observations in their window; no date or price is filled.
- Horizon targets remain exact calendar offsets of 1, 3, or 7 days. An origin with no observed target on its exact target date is retained as **unscored**. Reports must show total calendar origins, scored origins, and unscored origins separately.
- The seasonal-naive comparator is unavailable on shared scored origins when any required target-minus-seven price is absent or unavailable by the origin. Under the seven-day delay and positive calendar horizons, that input is generally future-available, so zero eligibility is expected.

## Chronology and holdout policy

The Phase 3A 2024 test period has already been examined and its target observations extend through **2024-12-10**. Those outcomes are historical diagnostics and cannot support a new untouched-test claim.

For a future experiment, first collect or acquire later observations for this exact identity. Record the exact series key and source lineage. Reserve a holdout whose target dates are strictly after 2024-12-10 before examining its scores. Keep all training, calibration, feature/model selection, and validation origins earlier than that holdout. Purge training labels if either their target date is not earlier than the next evaluation origin or their assumed target availability is later than the prior-day cutoff. Require at least 60 proper training rows, 20 calibration rows, three validation folds of 21 scored origins each, and at least 21 scored holdout origins per horizon; report unscored dates separately. Any later verified availability timestamps must replace the retrospective policy only with documented source evidence.

The exact eligible historical `Lasalgaon (Niphad)` / Onion / Other / FAQ series has 797 rows from 2021-01-01 through 2024-12-10. **No fresh holdout is currently available for that exact series.** Later canonical Lasalgaon records are grade Local and use market label `Lasalgaon(Niphad)`; they are not merged into this FAQ series. Other historical labels such as `Lasalgaon` remain separate as well.

## Metrics and prediction intervals

- Preserve legacy exact three-way sign agreement for historical comparability. Its reference is the latest price available at the origin; exact ties are no-change.
- Also report up/down accuracy restricted to targets that actually move, the count/rate of no-change predictions, no-change correctness, and actual/predicted up/down/no-change class distributions. The default diagnostic deadband is zero until price-unit provenance is verified. Any different deadband must be fixed before a new experiment.
- Use a past-only split-conformal absolute-residual radius with one-based rank `ceil((n+1) × nominal_coverage)`. If that rank exceeds the calibration sample count, report an unbounded radius instead of silently using an insufficient order statistic.
- Calibration residuals must be produced by the same fitted model instance and serialized model state used for the associated interval predictions. In-place refitting is detected; refitting requires fresh chronological calibration, and a prior model's radius must not be reused implicitly.
- Report nominal coverage, empirical coverage, interval width, calibration sample count, rank, method, and assumptions. Temporal residuals may not be exchangeable; nominal 90% coverage is not guaranteed by this procedure alone.

## Provenance limitations

The annual Kaggle files carry an AGMARKNET attribution as a publisher claim; primary-source provenance has not been independently verified. Their price unit remains provisionally INR/quintal. They contain no historical publication timestamps. Do not infer availability from download time, observation date, or current API state. A shorter verified delay requires timestamped primary-source publication/first-seen evidence for the historical records being evaluated.
