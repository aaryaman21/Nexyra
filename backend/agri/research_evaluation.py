"""Research-only evaluation primitives; this module never fits or registers models."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import hashlib
import math
import pickle
from typing import Any, Callable, Mapping, Sequence
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .data import HORIZONS

ZONE = ZoneInfo("Asia/Kolkata")
AVAILABILITY_DELAY_DAYS = 7
AVAILABILITY_POLICY = (
    "retrospective assumption: observation date + 7 calendar days at 23:59:59 Asia/Kolkata; "
    "not verified historical availability"
)
PREVIOUSLY_EXAMINED_TARGET_END = date(2024, 12, 10)


def local_end(day: date) -> datetime:
    """Inclusive forecast cutoff used by the approved retrospective policy."""
    return datetime.combine(day, time(23, 59, 59), tzinfo=ZONE)


def assumed_available_at(observation_date: date, delay_days: int = AVAILABILITY_DELAY_DAYS) -> datetime:
    if not isinstance(delay_days, int) or delay_days < 0:
        raise ValueError("Availability delay must be a nonnegative whole number of days")
    return local_end(observation_date + timedelta(days=delay_days))


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def calendar_origin_frame(
    observations: Sequence[Mapping[str, Any]],
    horizon: int,
    start_date: date,
    end_date: date,
    *,
    availability_delay_days: int = AVAILABILITY_DELAY_DAYS,
) -> pd.DataFrame:
    """Build inclusive daily origins using strict as-of prices and exact targets.

    Only input observations are retained as prices. Missing observations are not
    filled; the latest previously available price is carried as an origin-time
    feature. Exact availability-day lags remain NaN and receive missing flags.
    """
    if horizon not in HORIZONS:
        raise ValueError(f"Supported calendar-day horizons: {HORIZONS}")
    start_date, end_date = _as_date(start_date), _as_date(end_date)
    if start_date > end_date:
        raise ValueError("Origin period start must not follow its end")
    if availability_delay_days < 0:
        raise ValueError("Availability delay must be nonnegative")

    price_by_observation_date: dict[date, float] = {}
    for row in observations:
        observation_date = _as_date(row.get("observation_date", row.get("date")))
        if observation_date in price_by_observation_date:
            raise ValueError(f"Duplicate observation date in one series: {observation_date}")
        price = float(row["modal_price"])
        if not np.isfinite(price):
            raise ValueError(f"Non-finite modal price on {observation_date}")
        price_by_observation_date[observation_date] = price

    releases: dict[date, tuple[date, float, datetime]] = {}
    for observed_on, price in price_by_observation_date.items():
        released_on = observed_on + timedelta(days=availability_delay_days)
        if released_on in releases:
            raise ValueError(f"Multiple prices become available on {released_on}; resolve source keys first")
        releases[released_on] = (observed_on, price, assumed_available_at(observed_on, availability_delay_days))

    ordered_release_dates = sorted(releases)
    observed_dates = set(price_by_observation_date)
    origins = []
    for origin_ts in pd.date_range(start_date, end_date, freq="D"):
        origin_date = origin_ts.date()
        origin_at = local_end(origin_date)
        available_release_dates = [released for released in ordered_release_dates
                                   if releases[released][2] <= origin_at]
        latest_release_date = available_release_dates[-1] if available_release_dates else None
        latest = releases[latest_release_date] if latest_release_date is not None else None

        # Exact lags refer to the calendar dates on the availability timeline.
        lag1_source = releases.get(origin_date - timedelta(days=1))
        lag7_source = releases.get(origin_date - timedelta(days=7))
        recent = [releases[d][1] for d in ordered_release_dates
                  if origin_date - timedelta(days=7) < d <= origin_date and d in available_release_dates]
        target_date = origin_date + timedelta(days=horizon)
        target_is_observed = target_date in observed_dates
        origins.append({
            "origin_id": origin_date.isoformat(),
            "origin_date": origin_date,
            "origin_at": origin_at,
            "target_id": target_date.isoformat(),
            "target_date": target_date,
            "target": price_by_observation_date.get(target_date, np.nan),
            "scored": bool(target_is_observed),
            "current": float(latest[1]) if latest else np.nan,
            "price": float(latest[1]) if latest else np.nan,
            "latest_observation_date": latest[0] if latest else None,
            "latest_available_at": latest[2] if latest else None,
            "latest_price_age_days": (origin_date - latest[0]).days if latest else np.nan,
            "days_since_price_became_available": (origin_date - latest_release_date).days if latest else np.nan,
            "lag1": float(lag1_source[1]) if lag1_source else np.nan,
            "lag1_missing": int(lag1_source is None),
            "lag7": float(lag7_source[1]) if lag7_source else np.nan,
            "lag7_missing": int(lag7_source is None),
            "mean7": float(np.mean(recent)) if recent else np.nan,
            "std7": float(np.std(recent, ddof=0)) if recent else np.nan,
            "change7": (float(latest[1] - lag7_source[1]) if latest and lag7_source else np.nan),
            "weekday": origin_date.weekday(),
            "month": origin_date.month,
        })
    return pd.DataFrame(origins)


def origin_count_summary(rows: pd.DataFrame) -> dict[str, int]:
    if "scored" not in rows:
        raise ValueError("Origin frame must contain scored")
    total = len(rows)
    scored = int(rows.scored.astype(bool).sum())
    return {"total_calendar_origins": total, "scored_origins": scored,
            "unscored_origins": total - scored}


def seasonal_naive_availability(
    observations: Sequence[Mapping[str, Any]], origins: pd.DataFrame, horizon: int,
    *, availability_delay_days: int = AVAILABILITY_DELAY_DAYS,
) -> dict[str, Any]:
    """Assess target-minus-seven inputs on the shared scored-origin set."""
    if horizon not in HORIZONS:
        raise ValueError(f"Supported calendar-day horizons: {HORIZONS}")
    prices = {_as_date(r.get("observation_date", r.get("date"))): float(r["modal_price"])
              for r in observations}
    shared = origins.loc[origins.scored.astype(bool)]
    eligible = 0
    for row in shared.itertuples():
        seasonal_date = row.target_date - timedelta(days=7)
        eligible += int(seasonal_date in prices and
                        assumed_available_at(seasonal_date, availability_delay_days) <= row.origin_at)
    return {"status": "available" if eligible == len(shared) and len(shared) else "unavailable",
            "eligible_origins": eligible, "shared_scored_origins": len(shared),
            "reason": (None if eligible == len(shared) and len(shared) else
                       "Seasonal inputs are absent or unavailable for at least one shared scored origin")}


def purge_training_rows(rows: pd.DataFrame, first_origin: date) -> pd.DataFrame:
    """Keep only labels strictly earlier and available by the prior local day."""
    required = {"origin_date", "target_date", "target_available_at"}
    if not required <= set(rows.columns):
        raise ValueError(f"Training rows missing {sorted(required - set(rows.columns))}")
    first_origin = _as_date(first_origin)
    cutoff = local_end(first_origin - timedelta(days=1))
    eligible = []
    for row in rows.itertuples():
        available = pd.Timestamp(row.target_available_at)
        if available.tzinfo is None:
            raise ValueError("Target availability must be timezone-aware")
        eligible.append(_as_date(row.origin_date) < first_origin and
                        _as_date(row.target_date) < first_origin and
                        available.to_pydatetime() <= cutoff)
    return rows.loc[np.asarray(eligible, dtype=bool)].reset_index(drop=True)


def assert_candidate_origins(candidate_rows: Mapping[str, pd.DataFrame]) -> tuple[tuple[Any, Any], ...]:
    """Independently compare each candidate's actual origin/target identifiers."""
    if not candidate_rows:
        raise ValueError("At least one candidate origin frame is required")
    expected = None
    expected_name = None
    for name, rows in candidate_rows.items():
        if not {"origin_id", "target_id"} <= set(rows.columns):
            raise ValueError(f"Candidate {name} lacks origin_id or target_id")
        pairs = tuple(zip(rows.origin_id.tolist(), rows.target_id.tolist()))
        if len(pairs) != len(set(pairs)):
            raise ValueError(f"Candidate {name} has duplicate origin/target identifiers")
        if expected is None:
            expected, expected_name = pairs, name
        elif pairs != expected:
            raise ValueError(f"Candidate {name} origins differ from {expected_name}")
    return expected or ()


def _direction_class(changes: np.ndarray, deadband: float) -> np.ndarray:
    result = np.full(len(changes), "no_change", dtype=object)
    result[changes > deadband] = "up"
    result[changes < -deadband] = "down"
    return result


def directional_diagnostics(actual, predicted, reference, *, deadband: float = 0.0) -> dict[str, Any]:
    """Return historical sign agreement plus explicit movement/no-change scores.

    At deadband zero, exact ties are no-change. A predicted no-change on a
    moving target is incorrect for up/down accuracy; it is reported separately.
    """
    if deadband < 0 or not np.isfinite(deadband):
        raise ValueError("Deadband must be finite and nonnegative")
    actual, predicted, reference = [np.asarray(v, dtype=float) for v in (actual, predicted, reference)]
    if not len(actual) or not (len(actual) == len(predicted) == len(reference)):
        raise ValueError("Directional inputs must have identical nonzero lengths")
    if not all(np.isfinite(v).all() for v in (actual, predicted, reference)):
        raise ValueError("Directional inputs must be finite")
    actual_change, predicted_change = actual - reference, predicted - reference
    actual_class = _direction_class(actual_change, deadband)
    predicted_class = _direction_class(predicted_change, deadband)
    moving = actual_class != "no_change"
    legacy = float(np.mean(np.sign(actual_change) == np.sign(predicted_change)))
    up_down_accuracy = (float(np.mean(actual_class[moving] == predicted_class[moving]))
                        if moving.any() else None)
    classes = ("up", "down", "no_change")
    actual_distribution = {k: int(np.sum(actual_class == k)) for k in classes}
    predicted_distribution = {k: int(np.sum(predicted_class == k)) for k in classes}
    return {
        "legacy_three_way_sign_agreement": legacy,
        "tie_rule": "exact equality to reference is no-change" if deadband == 0 else
                    f"absolute change <= {deadband:g} is no-change",
        "deadband": float(deadband),
        "up_down_accuracy_on_moving_targets": up_down_accuracy,
        "moving_target_count": int(moving.sum()),
        "no_change_prediction_behavior": {
            "predicted_no_change_count": predicted_distribution["no_change"],
            "predicted_no_change_rate": float(np.mean(predicted_class == "no_change")),
            "no_change_correct_count": int(np.sum((actual_class == "no_change") &
                                                    (predicted_class == "no_change"))),
            "no_change_predictions_on_moving_targets": int(np.sum(moving &
                                                                    (predicted_class == "no_change"))),
        },
        "actual_class_distribution": actual_distribution,
        "predicted_class_distribution": predicted_distribution,
    }


def finite_sample_residual_radius(residuals, nominal_coverage: float = 0.9) -> dict[str, Any]:
    """Split-conformal absolute-residual radius using the finite-sample rank."""
    residuals = np.asarray(residuals, dtype=float)
    if residuals.ndim != 1 or not len(residuals) or not np.isfinite(residuals).all():
        raise ValueError("Calibration residuals must be a nonempty finite vector")
    if (residuals < 0).any() or not 0 < nominal_coverage < 1:
        raise ValueError("Residuals must be nonnegative and nominal coverage in (0,1)")
    n = len(residuals)
    rank = math.ceil((n + 1) * nominal_coverage)
    if rank > n:
        radius = float("inf")
        finite_radius = False
    else:
        radius = float(np.sort(residuals)[rank - 1])
        finite_radius = True
    return {"radius": radius, "nominal_coverage": float(nominal_coverage),
            "calibration_sample_size": n, "finite_sample_rank_1_based": rank,
            "finite_radius_available": finite_radius,
            "method": "split conformal absolute residual, order statistic ceil((n+1)*coverage)",
            "assumptions": ["calibration and future residuals are exchangeable for finite-sample marginal coverage",
                            "temporal agricultural residuals may violate exchangeability; coverage is not guaranteed"]}


@dataclass
class ModelCalibration:
    """Calibration bound to the exact fitted model instance used for calibration."""
    model: Any
    model_fingerprint: str
    radius: float
    nominal_coverage: float
    calibration_sample_size: int
    rank: int
    finite_radius_available: bool
    method: str
    assumptions: tuple[str, ...]

    def intervals(self, model: Any, predictions) -> tuple[np.ndarray, np.ndarray]:
        if model is not self.model:
            raise ValueError("Interval model differs from the model used for calibration; recalibrate chronologically")
        if _model_fingerprint(model) != self.model_fingerprint:
            raise ValueError("Calibrated model state changed after calibration; recalibrate chronologically")
        predictions = np.asarray(predictions, dtype=float)
        if not np.isfinite(predictions).all():
            raise ValueError("Predictions must be finite")
        return np.maximum(0, predictions - self.radius), predictions + self.radius


def _model_fingerprint(model: Any) -> str:
    try:
        serialized = pickle.dumps(model, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception as exc:
        raise ValueError("Model must be serializable to bind interval calibration to its fitted state") from exc
    return hashlib.sha256(serialized).hexdigest()


def calibrate_model_intervals(
    model: Any, calibration_features: Any, calibration_targets, predict_fn: Callable,
    *, nominal_coverage: float = 0.9,
) -> ModelCalibration:
    """Calibrate using predictions from this exact model; this function never refits."""
    targets = np.asarray(calibration_targets, dtype=float)
    predictions = np.asarray(predict_fn(model, calibration_features), dtype=float)
    if targets.ndim != 1 or len(targets) != len(predictions) or not len(targets):
        raise ValueError("Calibration targets and model predictions must have matching nonzero lengths")
    if not np.isfinite(targets).all() or not np.isfinite(predictions).all():
        raise ValueError("Calibration inputs and predictions must be finite")
    result = finite_sample_residual_radius(np.abs(targets - predictions), nominal_coverage)
    return ModelCalibration(model=model, model_fingerprint=_model_fingerprint(model), radius=result["radius"],
                            nominal_coverage=result["nominal_coverage"],
                            calibration_sample_size=result["calibration_sample_size"],
                            rank=result["finite_sample_rank_1_based"],
                            finite_radius_available=result["finite_radius_available"],
                            method=result["method"], assumptions=tuple(result["assumptions"]))


def interval_diagnostics(actual, lower, upper, calibration: ModelCalibration) -> dict[str, Any]:
    """Report empirical interval performance with the calibration context."""
    actual, lower, upper = [np.asarray(v, dtype=float) for v in (actual, lower, upper)]
    if actual.ndim != 1 or not len(actual) or not (len(actual) == len(lower) == len(upper)):
        raise ValueError("Interval metric inputs must have matching nonzero lengths")
    if not np.isfinite(actual).all() or np.isnan(lower).any() or np.isnan(upper).any():
        raise ValueError("Interval metrics do not accept NaNs")
    if (lower > upper).any():
        raise ValueError("An interval lower bound exceeds its upper bound")
    return {
        "nominal_coverage": calibration.nominal_coverage,
        "empirical_coverage": float(np.mean((actual >= lower) & (actual <= upper))),
        "mean_interval_width": float(np.mean(upper - lower)),
        "evaluation_sample_size": len(actual),
        "calibration_sample_size": calibration.calibration_sample_size,
        "finite_sample_rank_1_based": calibration.rank,
        "finite_radius_available": calibration.finite_radius_available,
        "calibration_method": calibration.method,
        "assumptions": list(calibration.assumptions),
    }


def fresh_holdout_assessment(observation_dates, *, examined_target_end: date = PREVIOUSLY_EXAMINED_TARGET_END,
                             min_scored_origins: int = 21) -> dict[str, Any]:
    """Assess only whether exact-series observations exist after examined outcomes."""
    dates = sorted({_as_date(v) for v in observation_dates})
    latest = dates[-1] if dates else None
    fresh_dates = [d for d in dates if d > examined_target_end]
    return {
        "examined_target_end": examined_target_end.isoformat(),
        "latest_exact_series_observation": latest.isoformat() if latest else None,
        "fresh_observation_count": len(fresh_dates),
        "fresh_observation_start": fresh_dates[0].isoformat() if fresh_dates else None,
        "fresh_observation_end": fresh_dates[-1].isoformat() if fresh_dates else None,
        "minimum_scored_origins_required": min_scored_origins,
        "status": "fresh_observations_present" if fresh_dates else "no_fresh_holdout",
        "scored_origin_counts_by_horizon": {str(h): None for h in HORIZONS},
        "note": ("Freshness is checked by exact market/commodity/variety/grade identity; aliases and grades are not merged. "
                 "Observation counts do not establish the minimum scored-origin count; recompute exact targets by horizon."),
    }
