"""Validation-only model selection. Test data is consumed after selection freezes."""
from dataclasses import asdict, dataclass
import hashlib
import json
import pickle

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .data import DataUnavailable, NUMERICAL, SEMANTIC, cutoff


@dataclass(frozen=True)
class Protocol:
    min_train: int = 60
    calibration: int = 20
    folds: int = 3
    fold_size: int = 21
    min_test: int = 21
    coverage: float = .9
    min_relative_gain: float = .05

    def validate(self):
        if self.min_train < 30 or self.calibration < 10 or self.folds < 3 or self.fold_size < 7 or self.min_test < 7:
            raise DataUnavailable("Protocol requires meaningful training, calibration and rolling evaluation samples")
        if not 0 < self.coverage < 1 or not 0 <= self.min_relative_gain < 1:
            raise DataUnavailable("Invalid coverage or baseline improvement threshold")


def metrics(actual, predicted, current, radius):
    actual, predicted, current = map(lambda a: np.asarray(a, dtype=float), (actual, predicted, current))
    if not len(actual) or not all(np.isfinite(a).all() for a in (actual, predicted, current)):
        raise DataUnavailable("Cannot evaluate empty or non-finite predictions")
    error = actual - predicted
    denominator = np.abs(actual) + np.abs(predicted)
    lower, upper = np.maximum(0, predicted-radius), predicted+radius
    return {"n": len(actual), "mae": float(np.abs(error).mean()),
            "rmse": float(np.sqrt(np.mean(error**2))),
            "smape": float(200*np.divide(np.abs(error), denominator, out=np.zeros_like(error), where=denominator!=0).mean()),
            "directional_accuracy": float(np.mean(np.sign(actual-current) == np.sign(predicted-current))),
            "interval_coverage": float(np.mean((actual >= lower) & (actual <= upper))),
            "interval_width": float(np.mean(upper-lower))}


def candidates(semantic):
    result = [{"id": "naive", "family": "baseline", "algorithm": "last_observation", "features": [], "params": {}},
              {"id": "seasonal_naive", "family": "baseline", "algorithm": "seasonal_naive", "features": [], "params": {"period_days": 7}}]
    for family, columns in [("A", NUMERICAL), ("B", SEMANTIC), ("C", NUMERICAL+SEMANTIC)]:
        if family != "A" and not semantic:
            continue
        for alpha in (1., 10.):
            result.append(dict(id=f"{family}_ridge_{alpha:g}", family=family, algorithm="ridge", features=columns, params={"alpha": alpha}))
        result.append(dict(id=f"{family}_boosting", family=family, algorithm="hist_gradient_boosting", features=columns,
                           params={"max_iter": 80, "max_leaf_nodes": 7, "l2_regularization": 10., "random_state": 42, "early_stopping": False}))
    return result


def fit(spec, rows):
    if spec["family"] == "baseline":
        return None
    model = (make_pipeline(StandardScaler(), Ridge(**spec["params"])) if spec["algorithm"] == "ridge"
             else HistGradientBoostingRegressor(**spec["params"]))
    return model.fit(rows[spec["features"]], rows.target)


def predict(spec, model, rows):
    if spec["id"] == "naive":
        return rows.current.to_numpy(float)
    if spec["id"] == "seasonal_naive":
        return rows.seasonal.to_numpy(float)
    return np.maximum(0, model.predict(rows[spec["features"]]))


def eligible(rows, first_origin):
    # Both event-time and label availability must precede the next prediction block.
    return rows[(rows.target_date < first_origin) & (rows.target_available_at < cutoff(first_origin-pd.Timedelta(days=1)))]


def predictor_fingerprint(spec, model):
    """Fingerprint the exact predictor state used to produce calibration residuals."""
    if model is None:
        payload = json.dumps({"spec": spec, "baseline": True}, sort_keys=True, separators=(",", ":")).encode()
    else:
        payload = pickle.dumps(model, protocol=5)
    return hashlib.sha256(payload).hexdigest()


def calibrated_fit(spec, training, protocol):
    if len(training) < protocol.min_train + protocol.calibration:
        raise DataUnavailable("Insufficient training and interval calibration history")
    calibration = training.iloc[-protocol.calibration:]
    proper = eligible(training.iloc[:-protocol.calibration], calibration.origin.iloc[0])
    if len(proper) < protocol.min_train:
        raise DataUnavailable("Insufficient history after purging calibration label overlap")
    model = fit(spec, proper)
    errors = np.abs(calibration.target.to_numpy()-predict(spec, model, calibration))
    rank = int(np.ceil((len(errors)+1)*protocol.coverage))
    if rank > len(errors):
        raise DataUnavailable("Calibration sample is too small for a finite interval at the requested coverage")
    radius = float(np.sort(errors)[rank-1])
    return model, radius


def choose(reports, protocol):
    usable = [r for r in reports if r["status"] == "evaluated"]
    key = lambda r: (r["validation"]["mae"], r["validation"]["rmse"], r["stability_mae_std"], r["id"])
    baselines = [r for r in usable if r["family"] == "baseline"]
    if not baselines:
        raise DataUnavailable("At least one eligible baseline must complete evaluation")
    baseline = min(baselines, key=key)
    contenders = sorted([r for r in usable if r["family"] != "baseline"], key=key)
    for candidate in contenders:
        aggregate_win = candidate["validation"]["mae"] < baseline["validation"]["mae"]*(1-protocol.min_relative_gain)
        stable_win = all(c["mae"] <= b["mae"] for c, b in zip(candidate["fold_metrics"], baseline["fold_metrics"]))
        if aggregate_win and stable_win:
            return candidate["id"], baseline["id"], "Lowest validation MAE among models passing the baseline reliability gate"
    return baseline["id"], baseline["id"], "No learned model reliably beat the baseline: baseline retained"


def evaluate(rows, validation_start, test_start, protocol=Protocol()):
    protocol.validate()
    validation_start, test_start = pd.Timestamp(validation_start), pd.Timestamp(test_start)
    if validation_start >= test_start:
        raise DataUnavailable("Validation must precede untouched test history")
    # Inspect no test labels during tuning, calibration or selection.
    pretest = eligible(rows, test_start)
    semantic = not pretest[SEMANTIC].isna().any().any()
    validation = pretest[pretest.origin >= validation_start]
    if len(validation) < protocol.folds*protocol.fold_size:
        raise DataUnavailable("Insufficient identical validation origins for rolling backtesting")
    validation = validation.iloc[:protocol.folds*protocol.fold_size]
    folds = [validation.iloc[i*protocol.fold_size:(i+1)*protocol.fold_size] for i in range(protocol.folds)]
    reports, specs = [], candidates(semantic)
    for spec in specs:
        if spec["id"] == "seasonal_naive" and rows.seasonal.isna().any():
            reports.append(dict(spec, status="unavailable",
                                reason="Seven-day seasonal inputs are missing or unavailable on the shared origin set"))
            continue
        report = dict(spec, status="evaluated", fold_metrics=[], folds=[])
        predictions, actuals, currents, radii = [], [], [], []
        try:
            for block in folds:
                training = eligible(pretest, block.origin.iloc[0])
                model, radius = calibrated_fit(spec, training, protocol)
                pred = predict(spec, model, block)
                report["fold_metrics"].append(metrics(block.target, pred, block.current, radius))
                report["folds"].append({"train_start": str(training.origin.min().date()),
                                        "train_target_end": str(training.target_date.max().date()),
                                        "origin_start": str(block.origin.min().date()), "origin_end": str(block.origin.max().date())})
                predictions.extend(pred); actuals.extend(block.target); currents.extend(block.current)
                radii.extend([radius]*len(block))
            report["validation"] = metrics(actuals, predictions, currents, np.asarray(radii))
            report["stability_mae_std"] = float(np.std([m["mae"] for m in report["fold_metrics"]]))
        except (ValueError, FloatingPointError) as exc:
            report.update(status="failed", reason=str(exc))
        reports.append(report)
    if not semantic:
        for family in ("B", "C"):
            reports.append(dict(id=family, family=family, status="unavailable", reason="Complete as-of semantic coverage is unavailable"))
    selected, baseline, reason = choose(reports, protocol)
    # Selection is frozen. All successful configurations see the SAME test rows once.
    test = rows[rows.origin >= test_start]
    if len(test) < protocol.min_test:
        raise DataUnavailable("Insufficient untouched chronological test history")
    if semantic and test[SEMANTIC].isna().any().any():
        raise DataUnavailable("Test semantic coverage missing; refusing incomparable tests")
    artifacts = {}
    for report in reports:
        if report["status"] != "evaluated":
            continue
        spec = next(s for s in specs if s["id"] == report["id"])
        # Keep the fitted predictor identical to the one that generated its
        # held-out calibration residuals. Do not refit on calibration rows.
        model, radius = calibrated_fit(spec, pretest, protocol)
        pred = predict(spec, model, test)
        report["test"] = metrics(test.target, pred, test.current, radius)
        fingerprint = predictor_fingerprint(spec, model)
        report["predictor_fingerprint"] = fingerprint
        report["calibration"] = {"method": "past_only_split_conformal_absolute_residual",
                                  "sample_size": protocol.calibration,
                                  "rank_one_based": int(np.ceil((protocol.calibration+1)*protocol.coverage)),
                                  "nominal_coverage": protocol.coverage,
                                  "predictor_fingerprint": fingerprint,
                                  "predictor_refit_after_calibration": False,
                                  "coverage_guarantee": "not guaranteed under temporal dependence"}
        artifacts[spec["id"]] = dict(spec=spec, model=model, radius=radius,
                                     model_fingerprint=fingerprint,
                                     calibration=report["calibration"])
    summary = dict(selected_model=selected, baseline=baseline, selection_reason=reason,
                   selection_basis="rolling_validation_only", protocol=asdict(protocol), comparison=reports,
                   training_period={"origin_start": str(pretest.origin.min().date()), "target_end": str(pretest.target_date.max().date())},
                   validation_period={"origin_start": str(validation.origin.min().date()), "origin_end": str(validation.origin.max().date())},
                   test_period={"origin_start": str(test.origin.min().date()), "target_end": str(test.target_date.max().date())},
                   interval_method="Past-only held-out absolute residual rank; predictor is not refit after calibration; empirical, not guaranteed under temporal dependence",
                   horizon_definition="calendar_days", unit="INR/quintal")
    return summary, artifacts[selected]
