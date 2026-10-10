"""Isolated, retrospective-only Model A experiment for Phase 3A.

This module reads the historical observations table in SQLite read-only mode.
It never writes the production registry or canonical agricultural tables.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
import json
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

import joblib
import numpy as np
import pandas as pd

from .data import HORIZONS, NUMERICAL, make_features
from .evaluation import Protocol, candidates, fit, metrics, predict
from .registry import ROOT

ZONE = ZoneInfo("Asia/Kolkata")
SERIES = {
    "market": "Lasalgaon (Niphad)",
    "commodity": "Onion",
    "variety": "Other",
    "grade": "FAQ",
}
POLICY = "retrospective_assumed_availability_plus_7_calendar_days_at_23:59:59_Asia/Kolkata"


def local_end(day: date) -> datetime:
    """Timezone-aware local end-of-second used by the approved policy."""
    return datetime.combine(day, time(23, 59, 59), tzinfo=ZONE)


def assumed_available_at(observation_date: date) -> datetime:
    return local_end(observation_date + timedelta(days=7))


def forecast_origin(origin_date: date) -> datetime:
    return local_end(origin_date)


def load_series_read_only(db_path, series=SERIES):
    db_path = Path(db_path).resolve()
    con = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """SELECT source_file, source_row_number, source_sha256, state, district,
                      market_original, commodity, variety, grade, observation_date,
                      min_price, max_price, modal_price, price_unit_status,
                      availability_status, verified_available_at
               FROM agri_historical_price_observations
               WHERE market_original=? AND commodity=? AND variety=? AND grade=?
                 AND review_status='eligible_historical'
               ORDER BY observation_date""",
            (series["market"], series["commodity"], series["variety"], series["grade"]),
        ).fetchall()
        if not rows:
            raise ValueError("The exact pilot series has no eligible historical observations")
        result = [dict(row) for row in rows]
        if any(row["availability_status"] != "unknown" or row["verified_available_at"] is not None for row in result):
            raise ValueError("Expected unknown historical availability; refusing implicit timestamp substitution")
        return result
    finally:
        con.close()


def build_asof_features(observations):
    """Build features at the latest price observation available at each origin.

    With a seven-day publication-delay assumption, a price dated D enters the
    information set at D+7 23:59:59; price features therefore end at O-7 on
    forecast origin O.
    """
    raw = pd.DataFrame(observations)
    raw["observation_date"] = pd.to_datetime(raw["observation_date"], format="%Y-%m-%d")
    feature_series = pd.DataFrame({
        "series_id": "research-only-lasalgaon-niphad-other-faq",
        "date": raw["observation_date"],
        "modal_price": pd.to_numeric(raw["modal_price"], errors="raise"),
    })
    feature_series["available_at"] = pd.to_datetime(
        [assumed_available_at(value.date()) for value in feature_series["date"]], utc=True)
    # Shift the observation date to its assumed availability date exactly once.
    feature_series["date"] = feature_series["date"] + pd.Timedelta(days=7)
    feature_series["available_at"] = pd.to_datetime(
        [local_end(value.date()) for value in feature_series["date"]], utc=True)
    feature_series["series_id"] = "research-only-lasalgaon-niphad-other-faq"
    features = make_features(feature_series)
    features["observation_date"] = features["origin"].map(
        lambda value: value.date() - timedelta(days=7))
    features["origin_date"] = features["origin"].dt.date
    features["origin_at"] = features["origin_date"].map(local_end)
    return raw, feature_series, features


def build_supervised_rows(observations, features, horizon):
    if horizon not in HORIZONS:
        raise ValueError(f"Unsupported horizon {horizon}")
    actuals = {pd.Timestamp(row["observation_date"]).date(): float(row["modal_price"])
               for row in observations}
    rows = []
    for feature in features.to_dict(orient="records"):
        origin_date = feature["origin_date"]
        target_date = origin_date + timedelta(days=horizon)
        if target_date not in actuals:
            continue
        seasonal_date = target_date - timedelta(days=7)
        seasonal_available = assumed_available_at(seasonal_date) <= feature["origin_at"]
        rows.append({
            **{name: float(feature[name]) for name in NUMERICAL},
            "origin_date": origin_date,
            "origin_at": feature["origin_at"],
            "target_date": target_date,
            "target": actuals[target_date],
            "target_available_at": assumed_available_at(target_date),
            "current": float(feature["current"]),
            "seasonal": actuals.get(seasonal_date, np.nan) if seasonal_available else np.nan,
            "seasonal_source_date": seasonal_date,
            "seasonal_available": bool(seasonal_available and seasonal_date in actuals),
            "feature_anchor_date": feature["observation_date"],
        })
    frame = pd.DataFrame(rows).sort_values("origin_date").reset_index(drop=True)
    if frame.empty:
        return frame
    # Every price feature uses only observations whose assumed availability is
    # at or before the forecast origin.
    if not (frame["feature_anchor_date"].map(assumed_available_at) <= frame["origin_at"]).all():
        raise ValueError("Feature anchor was not available by the forecast origin")
    if not (frame["target_date"] > frame["origin_date"]).all():
        raise ValueError("A target date is not strictly after its forecast origin")
    return frame


def research_eligible(rows, first_origin: date):
    """Apply the existing one-day embargo plus assumed target availability purge."""
    availability_cutoff = local_end(first_origin - timedelta(days=1))
    mask = rows["target_date"].map(lambda value: value < first_origin)
    mask &= rows["target_available_at"].map(lambda value: value <= availability_cutoff)
    return rows.loc[mask].reset_index(drop=True)


def assert_identical_origins(frames):
    signatures = [tuple(zip(frame.origin_date, frame.target_date)) for frame in frames]
    if signatures and any(signature != signatures[0] for signature in signatures[1:]):
        raise ValueError("Compared models do not share identical origins and target dates")
    return signatures[0] if signatures else ()


def _calibrated_fit(spec, training, protocol, *, refit=False):
    if len(training) < protocol.min_train + protocol.calibration:
        raise ValueError("Insufficient eligible training plus calibration history")
    calibration = training.iloc[-protocol.calibration:]
    proper = research_eligible(training.iloc[:-protocol.calibration], calibration.origin_date.iloc[0])
    if len(proper) < protocol.min_train:
        raise ValueError("Insufficient proper training after calibration-label availability purge")
    model = fit(spec, proper.rename(columns={"target": "target"}))
    errors = np.abs(calibration.target.to_numpy(float) - predict(spec, model, calibration))
    level = min(1.0, np.ceil((len(errors) + 1) * protocol.coverage) / len(errors))
    radius = float(np.quantile(errors, level, method="higher"))
    if refit:
        model = fit(spec, training)
    return model, radius, {"proper_training": len(proper), "calibration": len(calibration),
                           "training_pool": len(training)}


def _compare_validation(rows, specs, validation_start, test_start, protocol):
    pretest = research_eligible(rows, test_start)
    validation_candidates = pretest.loc[pretest.origin_date >= validation_start].reset_index(drop=True)
    required_validation = protocol.folds * protocol.fold_size
    if len(validation_candidates) < required_validation:
        raise ValueError(f"Need {required_validation} eligible validation origins; found {len(validation_candidates)}")
    validation = validation_candidates.iloc[:required_validation].reset_index(drop=True)
    folds = [validation.iloc[i * protocol.fold_size:(i + 1) * protocol.fold_size].reset_index(drop=True)
             for i in range(protocol.folds)]
    predictions = {spec["id"]: [] for spec in specs}
    actuals, currents = [], []
    reports = {spec["id"]: dict(spec, status="evaluated", fold_metrics=[], folds=[]) for spec in specs}
    for fold_number, block in enumerate(folds, start=1):
        training = research_eligible(pretest, block.origin_date.iloc[0])
        for spec in specs:
            model, radius, counts = _calibrated_fit(spec, training, protocol)
            pred = predict(spec, model, block)
            reports[spec["id"]]["fold_metrics"].append(
                metrics(block.target, pred, block.current, radius))
            reports[spec["id"]]["folds"].append({
                "fold": fold_number,
                "proper_training": counts["proper_training"],
                "training_pool": counts["training_pool"],
                "calibration": counts["calibration"],
                "validation": len(block),
                "origin_start": block.origin_date.iloc[0].isoformat(),
                "origin_end": block.origin_date.iloc[-1].isoformat(),
            })
            predictions[spec["id"]].extend(pred.tolist())
        actuals.extend(block.target.tolist())
        currents.extend(block.current.tolist())
    common_signature = assert_identical_origins([validation for _ in specs])
    for spec in specs:
        report = reports[spec["id"]]
        report["validation"] = metrics(actuals, predictions[spec["id"]], currents,
                                       np.asarray([0.0] * len(actuals)))
        # Point-metric calculations do not consume interval values; replace
        # interval outputs with calibrated fold radii below.
        folded_metrics = report["fold_metrics"]
        report["validation"]["interval_coverage"] = float(np.mean([m["interval_coverage"] for m in folded_metrics]))
        report["validation"]["interval_width"] = float(np.mean([m["interval_width"] for m in folded_metrics]))
        report["stability_mae_std"] = float(np.std([m["mae"] for m in folded_metrics]))
    return pretest, validation, validation_candidates, reports, common_signature


def _select_model(reports, protocol):
    baseline = reports["naive"]
    contenders = [r for r in reports.values() if r["family"] != "baseline"]
    eligible = [r for r in contenders
                if r["validation"]["mae"] < baseline["validation"]["mae"] * (1 - protocol.min_relative_gain)
                and all(candidate["mae"] <= base["mae"]
                        for candidate, base in zip(r["fold_metrics"], baseline["fold_metrics"]))]
    if not eligible:
        return "naive", "No numerical model passed the validation MAE improvement and all-fold stability gate"
    winner = min(eligible, key=lambda r: (r["validation"]["mae"], r["validation"]["rmse"],
                                          r["stability_mae_std"], r["id"]))
    return winner["id"], "Validation only: at least 5% MAE improvement and no fold worse than last-price naive"


def run_experiment(db_path, *, artifact_root=None, validation_start=date(2023, 6, 1),
                   test_start=date(2024, 8, 1), protocol=Protocol()):
    """Run Model A on the approved pilot; return/write research-only outputs."""
    protocol.validate()
    validation_start = pd.Timestamp(validation_start).date()
    test_start = pd.Timestamp(test_start).date()
    if validation_start >= test_start:
        raise ValueError("Validation must precede untouched test")
    observations = load_series_read_only(db_path)
    raw, feature_series, features = build_asof_features(observations)
    # Demonstrate all feature inputs are assumed available by their origins.
    for feature in features.itertuples():
        origin_at = forecast_origin(feature.origin_date)
        available = feature_series.loc[feature_series.date <= feature.origin, "available_at"]
        if (available > pd.Timestamp(origin_at).tz_convert("UTC")).any():
            raise ValueError("Feature builder admitted a price after forecast origin")
    all_specs = candidates(semantic=False)
    specs = [s for s in all_specs if s["id"] in {"naive", "A_ridge_1", "A_ridge_10", "A_boosting"}]
    horizon_results, prepared_horizons, model_artifacts = {}, {}, {}
    for horizon in HORIZONS:
        rows = build_supervised_rows(observations, features, horizon)
        if rows.empty:
            raise ValueError(f"No exact-observation supervised rows for horizon {horizon}")
        seasonal_available = bool(rows.seasonal_available.all())
        pretest, validation, validation_candidates, reports, common = _compare_validation(
            rows, specs, validation_start, test_start, protocol)
        if len(common) != protocol.folds * protocol.fold_size:
            raise ValueError("Validation origin comparison is not identical across models")
        if not seasonal_available:
            # Preserve all supervised rows, while making the baseline's status explicit.
            seasonal_report = next(s for s in all_specs if s["id"] == "seasonal_naive")
            reports["seasonal_naive"] = dict(seasonal_report, status="unavailable",
                reason="target-minus-7-day price is not available at forecast origin under the seven-day policy",
                eligible_origins=0)
        selected, selection_reason = _select_model(reports, protocol)
        test = rows.loc[rows.origin_date >= test_start].reset_index(drop=True)
        if len(test) < protocol.min_test:
            raise ValueError(f"Horizon {horizon}: need {protocol.min_test} untouched test rows; found {len(test)}")
        test_signature = tuple(zip(test.origin_date, test.target_date))
        if len(test_signature) != len(set(test_signature)):
            raise ValueError("Duplicate test origin/target pairs")
        prepared_horizons[horizon] = (pretest, test, reports)
        horizon_results[str(horizon)] = {
            "candidate_origins": len(rows),
            "validation_candidates_before_cap": len(validation_candidates),
            "validation_origins": len(validation),
            "validation_origin_start": validation.origin_date.iloc[0].isoformat(),
            "validation_origin_end": validation.origin_date.iloc[-1].isoformat(),
            "test_origins": len(test),
            "test_origin_start": test.origin_date.iloc[0].isoformat(),
            "test_origin_end": test.origin_date.iloc[-1].isoformat(),
            "seasonal_naive_7d": "unavailable" if not seasonal_available else "available",
            "selected_model": selected,
            "selection_reason": selection_reason,
            "comparison": list(reports.values()),
        }

    # All horizon/model selections are frozen before any untouched-test metric is calculated.
    for horizon in HORIZONS:
        pretest, test, reports = prepared_horizons[horizon]
        for spec in specs:
            final_model, radius, final_counts = _calibrated_fit(spec, pretest, protocol, refit=True)
            test_prediction = predict(spec, final_model, test)
            reports[spec["id"]]["test"] = metrics(test.target, test_prediction, test.current, radius)
            reports[spec["id"]]["test_split"] = {
                "origin_start": test.origin_date.iloc[0].isoformat(),
                "origin_end": test.origin_date.iloc[-1].isoformat(),
                "target_start": test.target_date.iloc[0].isoformat(),
                "target_end": test.target_date.iloc[-1].isoformat(),
                "origins": len(test), "final_proper_training": final_counts["proper_training"],
                "calibration": final_counts["calibration"],
            }
            if spec["family"] != "baseline":
                model_artifacts[f"h{horizon}_{spec['id']}"] = final_model
    result = {
        "experiment": "Nexyra Phase 3A retrospective Model A",
        "research_only": True,
        "policy": POLICY,
        "availability_verified": False,
        "price_unit": "INR/quintal (provisional; unverified for Kaggle annual files)",
        "series": SERIES,
        "split": {"validation_start": validation_start.isoformat(), "untouched_test_start": test_start.isoformat()},
        "protocol": {"min_proper_training": protocol.min_train, "calibration_rows": protocol.calibration,
                     "rolling_folds": protocol.folds, "origins_per_fold": protocol.fold_size,
                     "min_test_rows": protocol.min_test, "interval_coverage": protocol.coverage,
                     "minimum_validation_mae_gain": protocol.min_relative_gain},
        "feature_columns": NUMERICAL,
        "models": {"ridge_alphas": [1.0, 10.0], "hist_gradient_boosting": {
            "max_iter": 80, "max_leaf_nodes": 7, "l2_regularization": 10.0,
            "random_state": 42, "early_stopping": False}},
        "horizons": horizon_results,
        "source_file_hashes": sorted({r["source_sha256"] for r in observations}),
        "production_registry_modified": False,
    }
    if artifact_root is None:
        artifact_root = ROOT / "ml" / "research_only" / "phase3a_lasalgaon_niphad"
    artifact_root = Path(artifact_root)
    artifact_root.mkdir(parents=True, exist_ok=False)
    for name, model in model_artifacts.items():
        joblib.dump(model, artifact_root / f"{name}.joblib")
    (artifact_root / "input_series.csv").write_text(
        raw[["observation_date", "modal_price"]].to_csv(index=False), encoding="utf-8")
    (artifact_root / "evaluation.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    (artifact_root / "manifest.json").write_text(json.dumps({
        "research_only": True,
        "production_registry": False,
        "series_id": "research-only-lasalgaon-niphad-other-faq",
        "policy": POLICY,
        "horizons": list(HORIZONS),
        "model_artifacts": sorted(model_artifacts),
        "evaluation_file": "evaluation.json",
        "data_snapshot": "input_series.csv",
    }, indent=2), encoding="utf-8")
    result["artifact_directory"] = str(artifact_root.resolve())
    return result
