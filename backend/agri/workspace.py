"""Local dataset upload, readiness checks and background evaluation jobs."""
from datetime import date
import json
import logging
import os
from pathlib import Path
import threading
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field
import pandas as pd

from .data import DataUnavailable, HORIZONS, SEMANTIC, make_features, read_events, read_prices, supervised
from .evaluation import Protocol, eligible
from .registry import ROOT, registry_root
from .train import train

logger = logging.getLogger(__name__)
busy = threading.Lock()


def local_access(request: Request):
    # Training is a local workstation operation, not an unauthenticated public API.
    if request.client and request.client.host not in {"127.0.0.1", "::1", "testclient"}:
        raise HTTPException(403, "Dataset management is available on this computer only")
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded and any(host.strip() not in {"127.0.0.1", "::1", "::ffff:127.0.0.1"} for host in forwarded.split(",")):
        raise HTTPException(403, "Open Nexyra on localhost to manage datasets")
    origin = request.headers.get("origin")
    if origin and origin not in {"http://localhost:3000", "http://127.0.0.1:3000"}:
        raise HTTPException(403, "Unsupported workspace origin")


router = APIRouter(prefix="/agri/workspace", tags=["Local agricultural workspace"], dependencies=[Depends(local_access)])


def workspace():
    root = Path(os.getenv("AGRISENSE_WORKSPACE", str(ROOT / "ml" / "agri_workspace")))
    root.mkdir(parents=True, exist_ok=True)
    return root


def identifier(value):
    try:
        return uuid.UUID(value).hex
    except ValueError:
        raise HTTPException(422, "Invalid workspace identifier")


def write_json(path, data):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, allow_nan=False), encoding="utf-8")
    os.replace(temporary, path)


class Upload(BaseModel):
    prices_csv: str = Field(min_length=1, max_length=5_000_000)
    events_json: str | None = Field(default=None, max_length=5_000_000)


class EvaluationRequest(BaseModel):
    dataset_id: str
    series_id: str = Field(pattern=r"^[a-f0-9]{20}$")
    validation_start: date
    test_start: date


def load_dataset(dataset_id):
    folder = workspace() / identifier(dataset_id)
    if not (folder / "dataset.json").exists():
        raise HTTPException(404, "Validated dataset not found; upload a CSV first")
    return folder


@router.post("/datasets", status_code=201)
def upload(payload: Upload):
    dataset_id = uuid.uuid4().hex
    folder = workspace() / dataset_id
    folder.mkdir()
    price_path = folder / "prices.csv"
    price_path.write_text(payload.prices_csv, encoding="utf-8")
    event_path = None
    if payload.events_json:
        event_path = folder / "events.json"
        event_path.write_text(payload.events_json, encoding="utf-8")
    try:
        prices, archive = read_prices(price_path), read_events(event_path)
        if len(prices) > 20000 or prices.series_id.nunique() > 20:
            raise DataUnavailable("Upload at most 20,000 rows and 20 market/variety combinations at a time")
        summaries = []
        for sid, rows in prices.groupby("series_id"):
            days = int((rows.date.max()-rows.date.min()).days)+1
            recent = rows.tail(90)
            summaries.append({"series_id": sid, "market": rows.market.iloc[0], "variety": rows.variety.iloc[0],
                              "grade": rows.grade.iloc[0], "unit": rows.unit.iloc[0], "source": rows.source.iloc[0],
                              "availability_basis": {str(key): int(value) for key, value in rows.availability_basis.value_counts().items()},
                              "district": rows.district.iloc[0], "rows": len(rows),
                              "start": str(rows.date.min().date()), "end": str(rows.date.max().date()),
                              "missing_days": days-len(rows), "coverage": len(rows)/days,
                              "validation_start": str(rows.date.iloc[int(len(rows)*.5)].date()),
                              "test_start": str(rows.date.iloc[int(len(rows)*.8)].date()),
                              "history": [{"date": str(row.date.date()), "price": row.modal_price} for row in recent.itertuples()],
                              "semantic_archive": archive is not None and sid in archive["coverage"]})
        result = {"dataset_id": dataset_id, "series": summaries, "status": "validated_research_input",
                  "availability_note": "Source availability timestamps are supplied by the uploader; only their declared basis is validated."}
        write_json(folder / "dataset.json", result)
        return result
    except (ValueError, KeyError, TypeError, OverflowError) as exc:
        write_json(folder / "rejected.json", {"status": "rejected"})
        raise HTTPException(422, f"Data validation failed: {str(exc)[:300]}")


def preflight(payload):
    folder = load_dataset(payload.dataset_id)
    price_frame = read_prices(folder / "prices.csv")
    series = price_frame[price_frame.series_id == payload.series_id]
    if series.empty:
        raise DataUnavailable("Market/variety not found in this dataset")
    archive = read_events(folder / "events.json" if (folder / "events.json").exists() else None)
    features = make_features(series, archive)
    validation, test = pd.Timestamp(payload.validation_start), pd.Timestamp(payload.test_start)
    if validation >= test:
        raise DataUnavailable("Validation start must be earlier than test start")
    reservation = registry_root() / f"test-reservation-{payload.series_id}.json"
    if reservation.exists() and payload.test_start.isoformat() <= json.loads(reservation.read_text())["test_end"]:
        raise DataUnavailable("This test history has already been reserved. Upload newer untouched history for another evaluation")
    protocol = Protocol()
    counts = []
    for horizon in HORIZONS:
        rows = supervised(series, features, horizon)
        pretest = eligible(rows, test)
        valid = pretest[pretest.origin >= validation]
        test_rows = rows[rows.origin >= test]
        if len(valid) < protocol.folds*protocol.fold_size:
            raise DataUnavailable(f"{horizon}-day horizon needs 63 validation origins before test; found {len(valid)}. Move validation earlier or test later, or add history")
        training = eligible(pretest, valid.origin.iloc[0])
        calibration = training.tail(protocol.calibration)
        proper = eligible(training.iloc[:-protocol.calibration], calibration.origin.iloc[0]) if len(calibration) else training
        if len(proper) < protocol.min_train or len(calibration) < protocol.calibration:
            raise DataUnavailable(f"{horizon}-day horizon needs at least 60 training and 20 calibration rows after purging. Move validation later or add earlier history")
        if len(test_rows) < protocol.min_test:
            raise DataUnavailable(f"{horizon}-day horizon needs 21 untouched test origins; found {len(test_rows)}. Add later observations or move test earlier")
        semantic = not pretest[SEMANTIC].isna().any().any()
        if semantic and test_rows[SEMANTIC].isna().any().any():
            raise DataUnavailable("Semantic archive coverage must include the complete test period")
        counts.append({"horizon": horizon, "training": len(proper), "validation": 63, "test": len(test_rows), "semantic_ready": semantic})
    return folder, series, counts


@router.post("/check")
def check(payload: EvaluationRequest):
    try:
        _, _, counts = preflight(payload)
        return {"ready": True, "horizons": counts, "message": "All three horizons have sufficient chronological history. No model has been trained by this check."}
    except (ValueError, KeyError, OSError) as exc:
        return {"ready": False, "horizons": [], "message": str(exc)[:350]}


def execute_job(job_id, folder, selected_path, validation, test):
    path = workspace() / f"job-{job_id}.json"
    try:
        write_json(path, {"job_id": job_id, "status": "running", "message": "Training and backtesting 1-, 3- and 7-day configurations. Please keep the backend running."})
        events_path = folder / "events.json"
        result = train(selected_path, events_path if events_path.exists() else None, validation, test)
        write_json(path, {"job_id": job_id, "status": "completed" if result["registered"] else "failed",
                          "message": "Research evaluation completed; selected artifacts remain research-only." if result["registered"] else "No model could be registered.", **result})
    except (ValueError, FileExistsError) as exc:
        write_json(path, {"job_id": job_id, "status": "failed", "message": str(exc)[:350]})
    except Exception:
        logger.exception("Local agricultural training failed")
        write_json(path, {"job_id": job_id, "status": "failed", "message": "Evaluation failed. Check backend logs; no unevaluated model was activated."})
    finally:
        busy.release()


@router.post("/evaluate", status_code=202)
def evaluate_upload(payload: EvaluationRequest, tasks: BackgroundTasks):
    if not busy.acquire(blocking=False):
        raise HTTPException(409, "An evaluation is already running")
    try:
        if (registry_root() / "training.lock").exists():
            raise HTTPException(409, "Training is already running or an interrupted training lock needs inspection")
        folder, series, _ = preflight(payload)
        job_id = uuid.uuid4().hex
        selected_path = folder / f"selection-{job_id}.csv"
        series.to_csv(selected_path, index=False)
        write_json(workspace() / f"job-{job_id}.json", {"job_id": job_id, "status": "queued", "message": "Evaluation queued"})
        tasks.add_task(execute_job, job_id, folder, selected_path, payload.validation_start.isoformat(), payload.test_start.isoformat())
        return {"job_id": job_id, "status": "queued"}
    except Exception as exc:
        busy.release()
        if isinstance(exc, (ValueError, KeyError)):
            raise HTTPException(422, str(exc)[:350])
        raise


@router.get("/jobs/{job_id}")
def job_status(job_id: str):
    path = workspace() / f"job-{identifier(job_id)}.json"
    if not path.exists():
        raise HTTPException(404, "Evaluation job not found")
    result = json.loads(path.read_text())
    if result["status"] in {"queued", "running"} and not busy.locked() and not (registry_root() / "training.lock").exists():
        return {"job_id": job_id, "status": "interrupted", "message": "The backend restarted during evaluation. Check the registry and logs before using newer untouched history."}
    return result
