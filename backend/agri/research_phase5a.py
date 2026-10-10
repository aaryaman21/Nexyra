"""Phase 5A exact-series Model A training and historical replay.

Reads the historical SQLite table in read-only mode. Writes only a separate
research artifact directory; it never modifies source observations or the
active production/research registry.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

import joblib
import numpy as np
import pandas as pd
import sklearn

from .data import HORIZONS, NUMERICAL, SEMANTIC, DataUnavailable
from .evaluation import Protocol, candidates, calibrated_fit, evaluate, eligible, predict
from .registry import ROOT, digest
from .research_evaluation import (AVAILABILITY_DELAY_DAYS, AVAILABILITY_POLICY,
                                  assumed_available_at, calendar_origin_frame,
                                  seasonal_naive_availability)

SERIES = {"state": "Maharashtra", "district": "Nashik", "market": "Lasalgaon (Niphad)",
          "commodity": "Onion", "variety": "Other", "grade": "FAQ"}
VALIDATION_START = date(2023, 6, 1)
REUSED_TEST_START = date(2024, 8, 1)
PREVIOUSLY_EXAMINED_TARGET_END = date(2024, 12, 10)
STALE_AFTER_DAYS = 7
ZONE = ZoneInfo("Asia/Kolkata")
DEFAULT_ARTIFACTS = ROOT / "ml" / "research_only"


def load_exact_series_read_only(db_path: str | Path) -> list[dict]:
    """Load only the exact eligible FAQ identity, preserving source metadata."""
    db_path = Path(db_path).resolve()
    connection = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """SELECT record_key, source_file, source_row_number, source_sha256,
                      source_url, source_publisher, source_attribution_claim,
                      state, district, market_original, commodity, variety, grade,
                      observation_date, min_price, max_price, modal_price,
                      price_unit, price_unit_status, verified_available_at,
                      availability_status, review_status
               FROM agri_historical_price_observations
               WHERE state=? AND district=? AND market_original=? AND commodity=?
                 AND variety=? AND grade=? AND review_status='eligible_historical'
               ORDER BY observation_date, source_file, source_row_number""",
            (SERIES["state"], SERIES["district"], SERIES["market"], SERIES["commodity"],
             SERIES["variety"], SERIES["grade"]),
        ).fetchall()
        result = [dict(row) for row in rows]
    finally:
        connection.close()
    if not result:
        raise DataUnavailable("Exact Lasalgaon (Niphad) / Onion / Other / FAQ series is unavailable")
    dates = [date.fromisoformat(row["observation_date"]) for row in result]
    if len(dates) != len(set(dates)):
        raise DataUnavailable("Exact historical series has duplicate dates; refusing to resolve them implicitly")
    if any(row["availability_status"] != "unknown" or row["verified_available_at"] is not None
           for row in result):
        raise DataUnavailable("Historical availability is not uniformly unknown; review source timestamps first")
    if any(row["review_status"] != "eligible_historical" for row in result):
        raise DataUnavailable("Historical series includes rows outside eligible_historical")
    for key in ("source_url", "source_publisher", "source_attribution_claim", "price_unit", "price_unit_status"):
        if len({row[key] for row in result}) != 1:
            raise DataUnavailable(f"Exact pilot has inconsistent {key}; refusing to merge source identities")
    if {row["price_unit"] for row in result} != {"INR/quintal"}:
        raise DataUnavailable("The historical unit differs from the recorded provisional INR/quintal label")
    for row in result:
        low, high, modal = (float(row[name]) for name in ("min_price", "max_price", "modal_price"))
        if not np.isfinite([low, high, modal]).all() or low < 0 or not low <= modal <= high:
            raise DataUnavailable(f"Invalid historical price ordering on {row['observation_date']}")
    return result


def model_input_frame(observations: list[dict]) -> pd.DataFrame:
    """Map recorded rows to the existing strict feature/evaluation contract."""
    rows = []
    for row in observations:
        rows.append({
            "date": row["observation_date"], "state": row["state"], "district": row["district"],
            "market": row["market_original"], "commodity": row["commodity"],
            "variety": row["variety"], "grade": row["grade"],
            "min_price": row["min_price"], "max_price": row["max_price"],
            "modal_price": row["modal_price"], "unit": row["price_unit"],
            "source": row["source_url"], "availability_basis": "retrospective_assumption_7d",
            "available_at": "", "source_file": row["source_file"],
            "source_publisher": row["source_publisher"],
            "source_attribution_claim": row["source_attribution_claim"],
            "source_row_number": row["source_row_number"], "source_sha256": row["source_sha256"],
            "record_key": row["record_key"],
        })
    return pd.DataFrame(rows)


def build_origin_rows(observations: list[dict], horizon: int) -> tuple[pd.DataFrame, dict]:
    """Create daily origins; score only exact observed targets and complete features."""
    if horizon not in HORIZONS:
        raise DataUnavailable("Supported calendar-day horizons: 1, 3, 7")
    dates = [date.fromisoformat(row["observation_date"]) for row in observations]
    daily = calendar_origin_frame(observations, horizon, min(dates), max(dates))
    daily["origin"] = pd.to_datetime(daily["origin_date"])
    daily["target_date"] = pd.to_datetime(daily["target_date"])
    daily["target_available_at"] = pd.to_datetime(
        [assumed_available_at(value.date()).astimezone(timezone.utc) for value in daily["target_date"]], utc=True)
    raw_by_date = {date.fromisoformat(row["observation_date"]): row for row in observations}
    seasonal_status = seasonal_naive_availability(observations, daily, horizon)
    seasonal_values = []
    for row in daily.itertuples():
        source_date = row.target_date.date() - timedelta(days=7)
        source = raw_by_date.get(source_date)
        available = source is not None and assumed_available_at(source_date) <= row.origin_at
        seasonal_values.append(float(source["modal_price"]) if available else np.nan)
    daily["seasonal"] = seasonal_values
    scored = daily.loc[daily.scored.astype(bool) & daily.current.notna()].copy()
    complete_mask = np.isfinite(scored[NUMERICAL].to_numpy(float)).all(axis=1)
    feature_ineligible = int((~complete_mask).sum())
    rows = scored.loc[complete_mask].reset_index(drop=True)
    for name in SEMANTIC:
        rows[name] = np.nan
    counts = {
        "calendar_origins": int(len(daily)),
        "exact_target_origins": int(daily.scored.astype(bool).sum()),
        "targets_with_asof_price": int(len(scored)),
        "feature_eligible_scored_origins": int(len(rows)),
        "incomplete_feature_origins_excluded_from_comparison": feature_ineligible,
        "unscored_exact_target_origins": int(len(daily) - daily.scored.astype(bool).sum()),
        "seasonal_naive": seasonal_status,
    }
    if rows.empty:
        raise DataUnavailable(f"No eligible exact-target origins for horizon {horizon}")
    return rows, counts


def _json_safe(value):
    if isinstance(value, (date, datetime, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def training_report(observations: list[dict], protocol: Protocol = Protocol(), *,
                    artifact_root: str | Path | None = None) -> dict:
    """Train/evaluate all horizons and persist a distinct research-only bundle."""
    protocol.validate()
    frames, counts, summaries, selected_artifacts, candidate_artifacts = {}, {}, {}, {}, {}
    numerical_specs = [item for item in candidates(semantic=False)
                       if item["id"] in {"naive", "seasonal_naive", "A_ridge_1", "A_ridge_10", "A_boosting"}]
    for horizon in HORIZONS:
        rows, row_counts = build_origin_rows(observations, horizon)
        summary, artifact = evaluate(rows, VALIDATION_START.isoformat(), REUSED_TEST_START.isoformat(), protocol)
        summary["origin_coverage"] = row_counts
        summary["test_status"] = "previously_examined_historical_diagnostic_not_fresh_holdout"
        summary["previously_examined_target_end"] = PREVIOUSLY_EXAMINED_TARGET_END.isoformat()
        summary["holdout_eligible"] = False
        frames[horizon], counts[horizon], summaries[horizon] = rows, row_counts, summary
        selected_artifacts[horizon] = artifact
        pretest = eligible(rows, pd.Timestamp(REUSED_TEST_START))
        persisted = {}
        for report in summary["comparison"]:
            if report["status"] != "evaluated":
                continue
            spec = next(item for item in numerical_specs if item["id"] == report["id"])
            model, radius = calibrated_fit(spec, pretest, protocol)
            # Preserve candidate model states as research artifacts; none is activated.
            from .evaluation import predictor_fingerprint
            fingerprint = predictor_fingerprint(spec, model)
            persisted[spec["id"]] = {
                "spec": spec, "model": model, "radius": radius,
                "model_fingerprint": fingerprint,
                "calibration": {"predictor_fingerprint": fingerprint,
                                "predictor_refit_after_calibration": False,
                                "nominal_coverage": protocol.coverage,
                                "sample_size": protocol.calibration,
                                "method": "past_only_split_conformal_absolute_residual",
                                "coverage_guarantee": "not guaranteed under temporal dependence"},
            }
        candidate_artifacts[horizon] = persisted

    model_input = model_input_frame(observations)
    observations_csv = model_input.to_csv(index=False)
    identity_fields = ["state", "district", "market", "commodity", "variety", "grade", "unit", "source"]
    identity = model_input.iloc[0]
    series_id = hashlib.sha256(json.dumps([str(identity[name]) for name in identity_fields],
                                         ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()[:20]
    input_hash = hashlib.sha256(observations_csv.encode("utf-8")).hexdigest()
    record_hash = hashlib.sha256("\n".join(row["record_key"] for row in observations).encode("ascii")).hexdigest()
    target = Path(artifact_root or (DEFAULT_ARTIFACTS /
                                   f"phase5a_lasalgaon_niphad_other_faq_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}")).resolve()
    if target.exists():
        raise DataUnavailable(f"Research artifact path already exists; refusing to overwrite: {target}")
    target.mkdir(parents=True, exist_ok=False)
    (target / "input_series.csv").write_text(observations_csv, encoding="utf-8")
    hashes = {"input_series.csv": digest(target / "input_series.csv")}
    for horizon in HORIZONS:
        name = f"h{horizon}.joblib"
        joblib.dump(selected_artifacts[horizon], target / name)
        hashes[name] = digest(target / name)
        candidate_dir = target / "candidates"
        candidate_dir.mkdir(exist_ok=True)
        for candidate_id, bundle in candidate_artifacts[horizon].items():
            candidate_path = candidate_dir / f"h{horizon}_{candidate_id}.joblib"
            joblib.dump(bundle, candidate_path)
            hashes[str(candidate_path.relative_to(target))] = digest(candidate_path)

    # Find a single replay origin in the reused diagnostic period that has exact
    # observed targets at all three horizons. Test outcomes are displayed only
    # after prediction and are not used in fitting or validation selection.
    common = set(frames[1].loc[(frames[1].origin_date >= REUSED_TEST_START) &
                               (frames[1].origin_date <= PREVIOUSLY_EXAMINED_TARGET_END), "origin_date"])
    for horizon in HORIZONS[1:]:
        common &= set(frames[horizon].loc[frames[horizon].origin_date >= REUSED_TEST_START, "origin_date"])
    if not common:
        raise DataUnavailable("No shared test-period origin has exact targets at all three horizons")
    replay_origin = max(common).date() if isinstance(max(common), pd.Timestamp) else max(common)
    manifest = {
        "protocol_id": "phase5a-numerical-historical-replay-v1",
        "series_id": series_id,
        "identity": {**SERIES, "source_url": observations[0]["source_url"],
                     "source_publisher": observations[0]["source_publisher"],
                     "source_attribution_claim": observations[0]["source_attribution_claim"],
                     "unit": observations[0]["price_unit"],
                     "unit_status": observations[0]["price_unit_status"]},
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "release_status": "research_only",
        "production_authorized": False,
        "database_source": str(Path("nexyra.db")),
        "input_fingerprint_sha256": input_hash,
        "record_keys_fingerprint_sha256": record_hash,
        "observation_count": len(observations),
        "observation_start": min(date.fromisoformat(r["observation_date"]) for r in observations).isoformat(),
        "observation_end": max(date.fromisoformat(r["observation_date"]) for r in observations).isoformat(),
        "source_files": sorted({r["source_file"] for r in observations}),
        "source_file_hashes": sorted({r["source_sha256"] for r in observations}),
        "availability_policy": AVAILABILITY_POLICY,
        "availability_verified": False,
        "feature_schema": NUMERICAL,
        "protocol": {**protocol.__dict__, "validation_start": VALIDATION_START.isoformat(),
                     "reused_test_start": REUSED_TEST_START.isoformat(),
                     "test_status": "previously_examined_not_fresh"},
        "software": {"scikit_learn": sklearn.__version__, "pandas": pd.__version__},
        "horizons": {str(h): summaries[h] for h in HORIZONS},
        "selected_candidate_artifacts": {str(h): f"h{h}.joblib" for h in HORIZONS},
        "candidate_artifacts": {str(h): sorted(candidate_artifacts[h]) for h in HORIZONS},
        "historical_replay_demo_origin": replay_origin.isoformat(),
        "test_period": {"start": REUSED_TEST_START.isoformat(),
                        "target_end": PREVIOUSLY_EXAMINED_TARGET_END.isoformat(),
                        "fresh_untouched": False,
                        "status": "previously_examined_historical_diagnostic"},
        "staleness_threshold_days": STALE_AFTER_DAYS,
        "artifact_files_sha256": hashes,
    }
    evaluation_path = target / "evaluation.json"
    evaluation_path.write_text(json.dumps(_json_safe({str(h): summaries[h] for h in HORIZONS}),
                                          indent=2, allow_nan=False), encoding="utf-8")
    replay_rows = {str(h): replay_forecast(target, selected_artifacts[h], observations, h, replay_origin,
                                            series_id=series_id)
                   for h in HORIZONS}
    replay_path = target / "replay_examples.json"
    replay_path.write_text(json.dumps(_json_safe(replay_rows), indent=2, allow_nan=False), encoding="utf-8")
    hashes["evaluation.json"] = digest(evaluation_path)
    hashes["replay_examples.json"] = digest(replay_path)
    manifest["artifact_files_sha256"] = hashes
    manifest_path = target / "manifest.json"
    manifest_path.write_text(json.dumps(_json_safe(manifest), indent=2, allow_nan=False), encoding="utf-8")
    manifest_hash = digest(manifest_path)
    (target / "manifest.sha256").write_text(manifest_hash + "  manifest.json\n", encoding="ascii")
    return {"artifact_root": str(target), "manifest": manifest, "replay_examples": replay_rows}


def _load_snapshot(artifact_root: str | Path) -> list[dict]:
    frame = pd.read_csv(Path(artifact_root) / "input_series.csv", dtype={"date": str})
    required = {"date", "modal_price", "record_key", "source_file", "source_sha256"}
    if not required <= set(frame.columns):
        raise DataUnavailable("Research snapshot is incomplete")
    return [{"observation_date": str(row.date), "modal_price": float(row.modal_price),
             "record_key": str(row.record_key), "source_file": str(row.source_file),
             "source_sha256": str(row.source_sha256), "source_url": str(row.source),
             "source_publisher": str(row.source_publisher) if hasattr(row, "source_publisher") else "",
             "source_attribution_claim": str(row.source_attribution_claim)
             if hasattr(row, "source_attribution_claim") else ""} for row in frame.itertuples()]


def replay_forecast(artifact_root: str | Path, artifact: dict, observations: list[dict],
                    horizon: int, origin: date, *, series_id: str | None = None) -> dict:
    """Generate one as-of historical prediction and reveal the target separately."""
    if horizon not in HORIZONS:
        raise DataUnavailable("Supported calendar-day horizons: 1, 3, 7")
    dates = [date.fromisoformat(row["observation_date"]) for row in observations]
    features = calendar_origin_frame(observations, horizon, origin, origin)
    features["origin"] = pd.to_datetime(features["origin_date"])
    features["target_date"] = pd.to_datetime(features["target_date"])
    features["target_available_at"] = pd.to_datetime(
        [assumed_available_at(value.date()).astimezone(timezone.utc) for value in features["target_date"]], utc=True)
    for name in SEMANTIC:
        features[name] = np.nan
    if features.empty or not np.isfinite(features[NUMERICAL].to_numpy(float)).all():
        raise DataUnavailable(f"No feature-complete as-of inputs for replay origin {origin}")
    fingerprint = artifact.get("model_fingerprint")
    from .evaluation import predictor_fingerprint
    if fingerprint != predictor_fingerprint(artifact["spec"], artifact["model"]):
        raise DataUnavailable("Research model fingerprint does not match the persisted predictor")
    prediction = float(predict(artifact["spec"], artifact["model"], features)[0])
    row = features.iloc[0]
    target_date = origin + timedelta(days=horizon)
    source_by_date = {date.fromisoformat(item["observation_date"]): item for item in observations}
    outcome = source_by_date.get(target_date)
    radius = float(artifact["radius"])
    return {
        "mode": "historical_replay", "status": "research_only",
        "series_id": series_id, "identity": SERIES,
        "origin": origin.isoformat(), "origin_cutoff": "23:59:59 Asia/Kolkata",
        "horizon_days": horizon, "target_date": target_date.isoformat(),
        "prediction": prediction, "lower": max(0.0, prediction - radius), "upper": prediction + radius,
        "interval_status": "experimental_temporal_coverage_not_guaranteed",
        "selected_model": artifact["spec"]["id"], "model_family": artifact["spec"]["family"],
        "model_fingerprint": fingerprint,
        "latest_available_observation_date": row.latest_observation_date.isoformat()
            if row.latest_observation_date else None,
        "latest_available_price": float(row.current) if np.isfinite(row.current) else None,
        "latest_price_age_days": int(row.latest_price_age_days) if np.isfinite(row.latest_price_age_days) else None,
        "unit": "INR/quintal", "unit_status": "provisional_unverified",
        "source_url": observations[0].get("source_url"),
        "availability_policy": AVAILABILITY_POLICY,
        "availability_verified": False,
        "stale": None,
        "outcome": ({"status": "observed_after_origin_for_historical_diagnostic_only",
                     "modal_price": float(outcome["modal_price"]),
                     "forecast_error_prediction_minus_actual": prediction - float(outcome["modal_price"])}
                    if outcome else {"status": "target_not_observed_in_snapshot", "modal_price": None,
                                     "forecast_error_prediction_minus_actual": None}),
        "test_period_status": "previously_examined_not_fresh_holdout",
    }


def locate_artifact(series_id: str, root: str | Path | None = None) -> Path:
    root = artifact_base(root)
    matches = []
    for path in root.glob("phase5a_*/manifest.json"):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("series_id") == series_id and manifest.get("protocol_id") == "phase5a-numerical-historical-replay-v1":
            folder = path.parent
            checksum_path = folder / "manifest.sha256"
            if not checksum_path.exists() or checksum_path.read_text(encoding="ascii").split()[0] != digest(path):
                raise DataUnavailable("Research manifest integrity check failed")
            for relative, expected in manifest["artifact_files_sha256"].items():
                if digest(folder / relative) != expected:
                    raise DataUnavailable(f"Research artifact integrity check failed: {relative}")
            matches.append((manifest.get("created_at_utc", ""), folder))
    if matches:
        return max(matches, key=lambda item: item[0])[1]
    raise DataUnavailable("No Phase 5A research artifact for this exact series")


def artifact_base(root: str | Path | None = None) -> Path:
    return Path(root or os.getenv("AGRISENSE_RESEARCH_ARTIFACTS", ROOT / "ml" / "research_only"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default=str(ROOT / "nexyra.db"))
    parser.add_argument("--artifact-root", help="New, unused research artifact directory (defaults to a timestamped run)")
    args = parser.parse_args(argv)
    try:
        observations = load_exact_series_read_only(args.database)
        result = training_report(observations, artifact_root=args.artifact_root)
        print(json.dumps(_json_safe({"artifact_root": result["artifact_root"],
                                     "series": result["manifest"]["identity"],
                                     "observation_count": result["manifest"]["observation_count"],
                                     "training_period": result["manifest"]["horizons"]["1"]["training_period"],
                                     "validation_period": result["manifest"]["horizons"]["1"]["validation_period"],
                                     "test_period": result["manifest"]["test_period"],
                                      "horizons": {h: {"selected_model": v["selected_model"],
                                                      "validation": next(r["validation"] for r in v["comparison"] if r["id"] == v["selected_model"]),
                                                      "historical_replay": result["replay_examples"][h]}
                                                  for h, v in result["manifest"]["horizons"].items()}}),
                                    indent=2, allow_nan=False))
    except (DataUnavailable, FileNotFoundError, FileExistsError, ValueError) as exc:
        parser.exit(2, f"Phase 5A training unavailable: {exc}\n")


if __name__ == "__main__":
    main()
