import sqlite3
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from backend.agri.data import NUMERICAL, read_prices
from backend.agri.evaluation import predictor_fingerprint
from backend.agri.research_phase5a import (SERIES, build_origin_rows,
                                           load_exact_series_read_only,
                                           model_input_frame, replay_forecast)


def _db(path, *, duplicate=False):
    connection = sqlite3.connect(path)
    connection.execute("""create table agri_historical_price_observations (
        record_key text, source_file text, source_row_number integer, source_sha256 text,
        source_url text, source_publisher text, source_attribution_claim text,
        state text, district text, market_original text, commodity text, variety text,
        grade text, observation_date text, min_price real, max_price real,
        modal_price real, price_unit text, price_unit_status text,
        verified_available_at text, availability_status text, review_status text)""")
    values = []
    for i in range(80):
        day = date(2020, 1, 1) + timedelta(days=i)
        values.append((f"key-{i}", "2020.csv", i, "f" * 64,
                       "https://example.test/data", "test-publisher", "unverified claim",
                       "Maharashtra", "Nashik", SERIES["market"], "Onion", "Other", "FAQ",
                       day.isoformat(), 90 + i, 110 + i, 100 + i, "INR/quintal", "provisional",
                       None, "unknown", "eligible_historical"))
    # Similar market text is kept as an independent identity and excluded.
    values.append(("other-market", "2020.csv", 81, "a" * 64,
                   "https://example.test/data", "test-publisher", "unverified claim",
                   "Maharashtra", "Nashik", "Lasalgaon", "Onion", "Other", "FAQ",
                   "2020-03-21", 1, 3, 2, "INR/quintal", "provisional", None, "unknown", "eligible_historical"))
    if duplicate:
        values.append(values[0])
    connection.executemany("insert into agri_historical_price_observations values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", values)
    connection.commit()
    connection.close()


def _observations(n=100):
    start = date(2020, 1, 1)
    return [{"observation_date": (start + timedelta(days=i)).isoformat(),
             "modal_price": float(1000 + 3 * i), "source_url": "https://example.test/data"}
            for i in range(n)]


def test_exact_read_only_loader_keeps_similar_market_separate(tmp_path):
    db = tmp_path / "historical.db"
    _db(db)
    rows = load_exact_series_read_only(db)
    assert len(rows) == 80
    assert {row["market_original"] for row in rows} == {SERIES["market"]}
    assert all(row["verified_available_at"] is None for row in rows)


def test_exact_loader_rejects_duplicate_dates_instead_of_deduplicating(tmp_path):
    db = tmp_path / "historical.db"
    _db(db, duplicate=True)
    with pytest.raises(ValueError, match="duplicate dates"):
        load_exact_series_read_only(db)


def test_research_csv_keeps_availability_assumption_explicit(tmp_path):
    db = tmp_path / "historical.db"
    _db(db)
    frame = model_input_frame(load_exact_series_read_only(db))
    path = tmp_path / "series.csv"
    frame.to_csv(path, index=False)
    parsed = read_prices(path)
    assert len(parsed) == 80
    assert set(parsed.availability_basis) == {"retrospective_assumption_7d"}
    assert parsed.iloc[0].available_at == pd.Timestamp("2020-01-08 18:29:59+00:00")
    assert parsed.series_id.nunique() == 1


def test_calendar_origins_score_only_exact_observed_targets():
    observations = _observations(100)
    observations = [row for index, row in enumerate(observations) if index != 45]
    rows, counts = build_origin_rows(observations, 1)
    assert counts["calendar_origins"] == 100
    assert counts["exact_target_origins"] < counts["calendar_origins"]
    assert counts["feature_eligible_scored_origins"] == len(rows)
    assert rows[NUMERICAL].notna().all().all()
    assert 46 not in rows.target_date.dt.dayofyear.values


def test_naive_replay_does_not_use_future_target_as_input():
    observations = _observations(100)
    origin = date(2020, 3, 10)
    spec = {"id": "naive", "family": "baseline", "algorithm": "last_observation", "features": [], "params": {}}
    artifact = {"spec": spec, "model": None, "radius": 10.0,
                "model_fingerprint": predictor_fingerprint(spec, None)}
    before = replay_forecast(".", artifact, observations, 3, origin, series_id="exact-series")
    target_date = origin + timedelta(days=3)
    changed = [dict(row) for row in observations]
    target = next(row for row in changed if row["observation_date"] == target_date.isoformat())
    target["modal_price"] = 90000.0
    after = replay_forecast(".", artifact, changed, 3, origin, series_id="exact-series")
    assert before["prediction"] == after["prediction"]
    assert before["outcome"]["modal_price"] != after["outcome"]["modal_price"]
    assert before["latest_available_observation_date"] == (origin - timedelta(days=7)).isoformat()
