"""Strict, reproducible as-of features. Prices are never interpolated."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

HORIZONS = (1, 3, 7)
NUMERICAL = ["price", "lag1", "lag7", "mean7", "std7", "change7", "weekday", "month"]
SEMANTIC = ["event_count", "supply_pressure", "disruption_count", "policy_count"]


class DataUnavailable(ValueError):
    pass


def cutoff(day):
    return (pd.Timestamp(day).normalize().tz_localize("Asia/Kolkata")
            + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)).tz_convert("UTC")


def read_prices(path):
    frame = pd.read_csv(path)
    required = {"date", "state", "district", "market", "commodity", "variety", "grade",
                "min_price", "max_price", "modal_price", "unit", "source",
                "availability_basis", "available_at"}
    if not required <= set(frame):
        raise DataUnavailable(f"Missing price columns: {sorted(required - set(frame))}")
    if frame[[name for name in required if name != "available_at"]].isna().any().any():
        raise DataUnavailable("Required price fields cannot be missing")
    for name in ["state", "district", "market", "commodity", "variety", "grade", "unit", "source"]:
        frame[name] = frame[name].astype(str)
        if frame[name].str.strip().eq("").any():
            raise DataUnavailable(f"Empty {name}")
    if set(frame.commodity.str.casefold()) != {"onion"} or set(frame.state.str.casefold()) != {"maharashtra"}:
        raise DataUnavailable("This MVP accepts Maharashtra onion wholesale series only")
    if set(frame.unit) != {"INR/quintal"}:
        raise DataUnavailable("Expected wholesale price unit INR/quintal")
    frame["date"] = pd.to_datetime(frame.date, format="%Y-%m-%d", errors="raise")
    allowed_basis = {"verified_source_timestamp", "retrospective_assumption_7d"}
    frame["availability_basis"] = frame.availability_basis.astype(str).str.strip()
    frame["available_at"] = frame.available_at.astype("object")
    if not set(frame.availability_basis) <= allowed_basis:
        raise DataUnavailable("availability_basis must be verified_source_timestamp or retrospective_assumption_7d")
    missing_timestamp = frame.available_at.isna() | frame.available_at.astype(str).str.strip().isin({"", "NaT", "nan"})
    assumed = frame.availability_basis == "retrospective_assumption_7d"
    if (missing_timestamp & ~assumed).any():
        raise DataUnavailable("Verified source availability timestamps cannot be missing")
    assumed_dates = frame.loc[assumed, "date"]
    assumed_at = (assumed_dates.dt.tz_localize("Asia/Kolkata")
                  + pd.Timedelta(days=7, hours=23, minutes=59, seconds=59)).dt.tz_convert("UTC")
    supplied_assumed = frame.loc[assumed & ~missing_timestamp, "available_at"]
    if len(supplied_assumed):
        supplied = pd.to_datetime(supplied_assumed, utc=True, errors="raise")
        if not np.array_equal(supplied.to_numpy(), assumed_at.loc[supplied.index].to_numpy()):
            raise DataUnavailable("Retrospective availability must match observation date + 7 days at local day end")
    frame.loc[assumed, "available_at"] = assumed_at
    verified = ~assumed
    if any(pd.Timestamp(value).tzinfo is None for value in frame.loc[verified, "available_at"]):
        raise DataUnavailable("Verified price availability timestamps must include timezone")
    frame["available_at"] = pd.to_datetime(frame.available_at, utc=True, errors="raise")
    starts = frame.date.dt.tz_localize("Asia/Kolkata").dt.tz_convert("UTC")
    if (frame.available_at < starts).any():
        raise DataUnavailable("Price cannot be available before its observation date")
    if (frame.available_at > pd.Timestamp.now(tz="UTC")).any():
        raise DataUnavailable("Future availability timestamps are invalid")
    for name in ["min_price", "max_price", "modal_price"]:
        frame[name] = pd.to_numeric(frame[name], errors="raise")
        if not np.isfinite(frame[name]).all() or (frame[name] < 0).any():
            raise DataUnavailable("Prices must be finite and nonnegative")
    if ((frame.modal_price < frame.min_price) | (frame.modal_price > frame.max_price)).any():
        raise DataUnavailable("Modal price must lie between minimum and maximum")
    keys = ["state", "district", "market", "commodity", "variety", "grade", "unit", "source", "date"]
    if frame.duplicated(keys).any():
        raise DataUnavailable("Duplicate series/date; resolve conflicting observations at ingestion")
    identity = keys[:-1]
    frame["series_id"] = frame.apply(lambda r: hashlib.sha256(
        json.dumps([str(r[k]) for k in identity], ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()[:20], axis=1)
    return frame.sort_values(["series_id", "date"]).reset_index(drop=True)


def read_events(path):
    if path is None:
        return None
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    # Coverage attests actual archived monitoring, not inferred from article count.
    if not isinstance(payload.get("coverage"), dict) or not isinstance(payload.get("events"), list):
        raise DataUnavailable("News archive requires explicit coverage and events")
    for bounds in payload["coverage"].values():
        if pd.Timestamp(bounds["start"]) > pd.Timestamp(bounds["end"]):
            raise DataUnavailable("Invalid semantic coverage")
    seen = set()
    for event in payload["events"]:
        for name in ["id", "series_id", "title", "url", "published_at", "available_at", "category"]:
            if not event.get(name):
                raise DataUnavailable(f"Event missing {name}")
        if not event["url"].startswith(("https://", "http://")):
            raise DataUnavailable("Invalid article URL")
        if event["id"] in seen:
            raise DataUnavailable("Duplicate article ID")
        seen.add(event["id"])
        for name in ["published_at", "available_at"]:
            stamp = pd.Timestamp(event[name])
            if stamp.tzinfo is None:
                raise DataUnavailable("News timestamps must include timezone")
            event[name] = stamp.tz_convert("UTC")
        if event["available_at"] < event["published_at"]:
            raise DataUnavailable("News cannot be available before publication")
        pressure = float(event.get("supply_pressure", 0))
        if not np.isfinite(pressure) or not -1 <= pressure <= 1:
            raise DataUnavailable("Supply pressure must be in [-1, 1]")
        event["supply_pressure"] = pressure
    return payload


def event_features(archive, series_id, day):
    if archive is None or series_id not in archive["coverage"]:
        return None
    bounds = archive["coverage"][series_id]
    if not pd.Timestamp(bounds["start"]) <= day - pd.Timedelta(days=6) <= day <= pd.Timestamp(bounds["end"]):
        return None
    end = cutoff(day)
    start = end - pd.Timedelta(days=7)
    eligible = [e for e in archive["events"] if e["series_id"] == series_id
                and start < e["published_at"] <= end and e["available_at"] <= end]
    events = {}
    for event in eligible:
        key = event.get("deduplication_key") or event["url"]
        current = events.get(key)
        if current is None or event["available_at"] < current["available_at"]:
            events[key] = event
    values = list(events.values())
    return dict(zip(SEMANTIC, [len(values), sum(e["supply_pressure"] for e in values),
                              sum(e["category"] == "transport_disruption" for e in values),
                              sum(e["category"] in {"policy", "export_policy"} for e in values)]))


def make_features(series, archive=None):
    if series.series_id.nunique() != 1:
        raise DataUnavailable("Feature engineering requires one market/variety series")
    series = series.sort_values("date")
    rows = []
    for row in series.itertuples():
        day = row.date
        history = series[(series.date <= day) & (series.available_at <= cutoff(day))].set_index("date")
        if day not in history.index or len(history) < 8:
            continue
        prices = history.modal_price
        # Exact calendar lags: missing observations stay unavailable.
        if any(day - pd.Timedelta(days=n) not in prices for n in (1, 7)):
            continue
        recent = prices[prices.index > day - pd.Timedelta(days=7)]
        features = dict(origin=day, current=float(prices.loc[day]), price=float(prices.loc[day]),
                        lag1=float(prices.loc[day-pd.Timedelta(days=1)]),
                        lag7=float(prices.loc[day-pd.Timedelta(days=7)]),
                        mean7=float(recent.mean()), std7=float(recent.std(ddof=0)),
                        change7=float(prices.loc[day]-prices.loc[day-pd.Timedelta(days=7)]),
                        weekday=day.dayofweek, month=day.month)
        semantic = event_features(archive, row.series_id, day)
        features.update(semantic or {name: np.nan for name in SEMANTIC})
        rows.append(features)
    if not rows:
        raise DataUnavailable("Insufficient as-of price history for calendar-day lag features")
    return pd.DataFrame(rows)


def supervised(series, features, horizon):
    if horizon not in HORIZONS:
        raise DataUnavailable("Unsupported horizon")
    rows = features.copy()
    rows["target_date"] = rows.origin + pd.Timedelta(days=horizon)
    targets = series.set_index("date")
    rows["target"] = rows.target_date.map(targets.modal_price)
    rows["target_available_at"] = rows.target_date.map(targets.available_at)
    # Seasonal naive at target minus seven days, always at/before origin.
    known_date = rows.target_date - pd.Timedelta(days=7)
    rows["seasonal"] = known_date.map(targets.modal_price)
    availability = known_date.map(targets.available_at)
    rows.loc[availability > rows.origin.map(cutoff), "seasonal"] = np.nan
    # A missing baseline must not erase an otherwise observable supervised target.
    # The evaluator marks that baseline unavailable on the common origin set.
    return rows.dropna(subset=["target"]).reset_index(drop=True)
