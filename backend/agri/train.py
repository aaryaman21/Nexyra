"""python -m backend.agri.train --prices ... --validation-start ... --test-start ..."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid

import joblib
import sklearn
import pandas as pd

from .data import HORIZONS, DataUnavailable, make_features, read_events, read_prices, supervised
from .evaluation import Protocol, evaluate
from .registry import digest, registry_root


def train(prices_path, events_path, validation_start, test_start, root=None, protocol=Protocol()):
    validation_start = pd.Timestamp(validation_start).date().isoformat()
    test_start = pd.Timestamp(test_start).date().isoformat()
    if validation_start >= test_start:
        raise DataUnavailable("Validation must precede test")
    prices = read_prices(prices_path)
    events = read_events(events_path)
    root = Path(root or registry_root())
    root.mkdir(parents=True, exist_ok=True)
    # Single-writer lock protects both evaluation reservations and the active pointer.
    lock = root / "training.lock"
    with lock.open("x"):
        pass
    try:
        pointer = root / "active.json"
        active = json.loads(pointer.read_text()) if pointer.exists() else {}
        completed, limitations = [], []
        for series_id, series in prices.groupby("series_id", sort=True):
            reservation = root / f"test-reservation-{series_id}.json"
            if reservation.exists():
                previous = json.loads(reservation.read_text())
                if test_start <= previous["test_end"]:
                    raise DataUnavailable("Test period already reserved/evaluated; use genuinely newer untouched history")
            features = make_features(series, events)
            prepared = {h: supervised(series, features, h) for h in HORIZONS}
            # Reserve before any test access; failed runs are also not silently retuned.
            reservation.write_text(json.dumps({"test_start": test_start, "test_end": str(series.date.max().date())}))
            version = uuid.uuid4().hex
            folder = root / version
            folder.mkdir()
            metadata = series.iloc[0]
            manifest = dict(status="evaluated", series_id=series_id, version=version,
                            release_status="research_only",
                            created_at=datetime.now(timezone.utc).isoformat(),
                            market=metadata.market, district=metadata.district, state=metadata.state,
                            commodity=metadata.commodity, variety=metadata.variety, grade=metadata.grade,
                            unit=metadata.unit, source=metadata.source,
                            availability_basis={str(key): int(value) for key, value in series.availability_basis.value_counts().items()},
                            dataset_sha256=digest(prices_path), events_sha256=digest(events_path) if events_path else None,
                            software={"scikit_learn": sklearn.__version__}, horizons={})
            try:
                for horizon, rows in prepared.items():
                    summary, artifact = evaluate(rows, validation_start, test_start, protocol)
                    joblib.dump(artifact, folder / f"h{horizon}.joblib")
                    summary["artifact_sha256"] = digest(folder / f"h{horizon}.joblib")
                    manifest["horizons"][str(horizon)] = summary
                # Snapshot price/news inputs for reproducibility and inference.
                series.to_csv(folder / "prices.csv", index=False)
                if events_path:
                    (folder / "events.json").write_bytes(Path(events_path).read_bytes())
                manifest["prices_snapshot_sha256"] = digest(folder / "prices.csv")
                manifest["events_snapshot_sha256"] = digest(folder / "events.json") if events_path else None
                (folder / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False))
                active[series_id] = version
                completed.append({"series_id": series_id, "version": version})
            except DataUnavailable as exc:
                limitations.append({"series_id": series_id, "reason": str(exc)})
                (folder / "failure.json").write_text(json.dumps(limitations[-1]))
        temp = root / "active.tmp"
        temp.write_text(json.dumps(active, indent=2))
        os.replace(temp, pointer)
        return {"registered": completed, "limitations": limitations}
    finally:
        lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prices", required=True)
    parser.add_argument("--events")
    parser.add_argument("--validation-start", required=True)
    parser.add_argument("--test-start", required=True)
    args = parser.parse_args()
    try:
        result = train(args.prices, args.events, args.validation_start, args.test_start)
        print(json.dumps(result, indent=2))
        if not result["registered"]:
            raise SystemExit(2)
    except (DataUnavailable, FileNotFoundError, FileExistsError) as exc:
        parser.exit(2, f"Training unavailable: {exc}\n")


if __name__ == "__main__":
    main()
