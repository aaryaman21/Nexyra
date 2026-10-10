"""Exact additive Ridge decomposition relative to training feature means."""
import numpy as np


def explain(bundle, features):
    spec = bundle["spec"]
    if spec["family"] == "baseline":
        return {"method": "naive_reference", "features": [],
                "description": "Uses the last observed price or target-weekday price from seven days earlier."}
    if spec["algorithm"] != "ridge":
        return {"method": "unavailable", "features": [],
                "description": "Feature contributions for the boosting configuration are not integrated."}
    scaler = bundle["model"].named_steps["standardscaler"]
    regressor = bundle["model"].named_steps["ridge"]
    transformed = scaler.transform(features[spec["features"]])[0]
    values = transformed * regressor.coef_
    raw = float(regressor.intercept_+values.sum())
    return {"method": "linear_training_mean_reference", "reference_prediction": float(regressor.intercept_),
            "clipping_adjustment": float(max(0, raw)-raw),
            "features": sorted([{"feature": name, "contribution": float(value)} for name, value in zip(spec["features"], values)],
                               key=lambda item: abs(item["contribution"]), reverse=True),
            "description": "Exact linear contributions in INR/quintal relative to training feature means. Explains model behavior, not causation."}
