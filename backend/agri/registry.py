"""Atomic, versioned registry. Only local CLI-produced evaluated bundles are served."""
import hashlib
import json
import os
from pathlib import Path

import joblib

from .data import DataUnavailable, HORIZONS

ROOT = Path(__file__).resolve().parents[2]


def registry_root():
    return Path(os.getenv("AGRISENSE_REGISTRY", str(ROOT / "ml" / "agri_artifacts")))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_registry(root=None):
    root = Path(root or registry_root())
    pointer = root / "active.json"
    if not pointer.exists():
        return {"status": "unavailable", "reason": "No agricultural models have been successfully trained and evaluated", "markets": []}
    active = json.loads(pointer.read_text())
    markets = []
    for series_id, version in active.items():
        if not all(v.isalnum() for v in (series_id, version)):
            raise DataUnavailable("Invalid registry identifiers")
        manifest = json.loads((root / version / "manifest.json").read_text())
        if manifest.get("status") != "evaluated" or manifest["series_id"] != series_id:
            raise DataUnavailable("Unevaluated registry entry")
        if manifest.get("release_status") != "research_only":
            raise DataUnavailable("Model release status must be explicitly research_only")
        if set(manifest["horizons"]) != {str(h) for h in HORIZONS}:
            raise DataUnavailable("Incomplete horizon evaluation")
        for h in HORIZONS:
            item = manifest["horizons"][str(h)]
            if item.get("selection_basis") != "rolling_validation_only":
                raise DataUnavailable("Invalid model selection basis")
            winner = next((r for r in item["comparison"] if r["id"] == item["selected_model"]), None)
            if not winner or winner.get("status") != "evaluated" or not winner.get("test", {}).get("n"):
                raise DataUnavailable("Winner has not completed test evaluation")
            if digest(root / version / f"h{h}.joblib") != item["artifact_sha256"]:
                raise DataUnavailable("Model artifact integrity check failed")
        markets.append(manifest)
    return {"status": "research_only" if markets else "unavailable",
            "release_status": "research_only" if markets else "unavailable", "markets": markets,
            "reason": "Evaluation artifacts are research-only and are not production-authorized" if markets
            else "No agricultural models have completed evaluation"}


def load_bundle(series_id, horizon, root=None):
    root = Path(root or registry_root())
    registry = load_registry(root)
    manifest = next((m for m in registry["markets"] if m["series_id"] == series_id), None)
    if manifest is None:
        raise DataUnavailable("No evaluated model for this market and variety")
    # joblib is trusted local storage only; no API accepts artifact uploads or paths.
    return manifest, joblib.load(root / manifest["version"] / f"h{horizon}.joblib")
