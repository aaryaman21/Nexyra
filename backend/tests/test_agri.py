"""Synthetic fixtures validate mechanics only; never registered in production."""
import json
from datetime import date

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.agri.data import DataUnavailable, SEMANTIC, cutoff, make_features, read_prices, supervised
from backend.agri.evaluation import Protocol, choose, evaluate, metrics
from backend.agri.registry import load_registry
from backend.agri.train import train
from backend.app.main import app


@pytest.fixture
def prices(tmp_path):
    dates = pd.date_range("2022-01-01", periods=300)
    rng = np.random.default_rng(42)
    values = 1000+np.cumsum(rng.normal(0, 8, len(dates)))
    data = pd.DataFrame(dict(date=dates.strftime("%Y-%m-%d"), state="Maharashtra", district="Fixture",
                             market="Synthetic test only", commodity="Onion", variety="Fixture", grade="Test grade", unit="INR/quintal",
                             source="synthetic-unit-test", availability_basis="verified_source_timestamp",
                             min_price=values-10, max_price=values+10, modal_price=values,
                             available_at=[cutoff(d).isoformat() for d in dates]))
    path = tmp_path / "prices.csv"
    data.to_csv(path, index=False)
    return path


def test_calendar_targets_and_future_invariance(prices):
    series = read_prices(prices)
    features = make_features(series)
    changed = series.copy()
    changed.loc[changed.date > pd.Timestamp("2022-04-01"), "modal_price"] *= 10
    pd.testing.assert_frame_equal(features[features.origin <= "2022-04-01"],
                                  make_features(changed).query("origin <= '2022-04-01'"))
    rows = supervised(series, features, 7)
    assert ((rows.target_date-rows.origin).dt.days == 7).all()
    missing = series[series.date != pd.Timestamp("2022-04-08")]
    assert pd.Timestamp("2022-04-01") not in set(supervised(missing, make_features(missing), 7).origin)


def test_validation_only_selection_and_shared_test(prices):
    series = read_prices(prices)
    features = make_features(series)
    for i, name in enumerate(SEMANTIC):
        features[name] = np.sin(np.arange(len(features)) / (i+3))
    rows = supervised(series, features, 7)
    report, _ = evaluate(rows, "2022-05-15", "2022-08-15")
    changed = rows.copy()
    changed.loc[changed.origin >= "2022-08-15", "target"] *= 10
    second, _ = evaluate(changed, "2022-05-15", "2022-08-15")
    assert report["selected_model"] == second["selected_model"]
    assert {r["family"] for r in report["comparison"]} == {"A", "B", "C", "baseline"}
    assert len({r["test"]["n"] for r in report["comparison"]}) == 1
    assert len({json.dumps(r["folds"]) for r in report["comparison"]}) == 1
    for before, after in zip(report["comparison"], second["comparison"]):
        assert before["validation"] == after["validation"]
        for fold in before["folds"]:
            assert fold["train_target_end"] < fold["origin_start"]


def test_baseline_gate_does_not_prefer_complexity():
    def record(name, family, mae, fold):
        return dict(id=name, family=family, status="evaluated", validation={"mae": mae, "rmse": mae},
                    stability_mae_std=0, fold_metrics=[{"mae": x} for x in fold])
    reports = [record("naive", "baseline", 10, [10]*3), record("seasonal_naive", "baseline", 11, [11]*3),
               record("C", "C", 9, [5, 5, 17]), record("A", "A", 9.6, [9.6]*3)]
    assert choose(reports, Protocol())[0] == "naive"
    reports.append(record("B", "B", 8, [8]*3))
    assert choose(reports, Protocol())[0] == "B"


def test_metrics_zero_and_intervals():
    result = metrics([0, 10], [0, 8], [0, 9], 2)
    assert result["mae"] == 1
    assert result["interval_coverage"] == 1
    assert result["directional_accuracy"] == .5
    assert np.isfinite(result["smape"])


def test_reject_bad_data(prices):
    frame = pd.read_csv(prices)
    pd.concat([frame, frame.iloc[:1]]).to_csv(prices, index=False)
    with pytest.raises(DataUnavailable, match="Duplicate"):
        read_prices(prices)
    frame.loc[0, "unit"] = "INR/kg"
    frame.to_csv(prices, index=False)
    with pytest.raises(DataUnavailable, match="unit"):
        read_prices(prices)


def test_series_identity_preserves_exact_grade_and_source(prices, tmp_path):
    frame = pd.read_csv(prices).iloc[:2].copy()
    second = frame.iloc[[0]].copy()
    second["grade"] = "FAQ"
    third = frame.iloc[[1]].copy()
    third["source"] = "another-source"
    combined = pd.concat([frame, second, third], ignore_index=True)
    path = tmp_path / "distinct-series.csv"
    combined.to_csv(path, index=False)
    rows = read_prices(path)
    assert rows.series_id.nunique() == 3
    assert set(rows.grade) == {"Test grade", "FAQ"}
    assert set(rows.source) == {"synthetic-unit-test", "another-source"}


def test_retrospective_seven_day_basis_is_explicit_and_fixed(prices, tmp_path):
    frame = pd.read_csv(prices).iloc[:1].copy()
    frame["availability_basis"] = "retrospective_assumption_7d"
    frame["available_at"] = ""
    path = tmp_path / "assumed.csv"
    frame.to_csv(path, index=False)
    row = read_prices(path).iloc[0]
    expected = pd.Timestamp("2022-01-08 18:29:59+00:00")
    assert row.available_at == expected
    assert row.availability_basis == "retrospective_assumption_7d"
    frame["available_at"] = "2022-01-02T00:00:00Z"
    frame.to_csv(path, index=False)
    with pytest.raises(DataUnavailable, match="must match observation date"):
        read_prices(path)


def test_register_infer_and_fail_closed(prices, tmp_path, monkeypatch):
    from backend.agri.registry import load_bundle
    root = tmp_path / "registry"
    monkeypatch.setenv("AGRISENSE_REGISTRY", str(root))
    client = TestClient(app)
    assert client.get("/api/agri/models").json()["status"] == "unavailable"
    result = train(prices, None, "2022-05-15", "2022-08-15", root)
    assert len(result["registered"]) == 1
    manifest = load_registry(root)["markets"][0]
    for horizon in (1, 3, 7):
        response = client.get(f'/api/agri/forecast/{manifest["series_id"]}?horizon={horizon}')
        assert response.status_code == 200, response.text
        assert response.json()["selected_model"] == manifest["horizons"][str(horizon)]["selected_model"]
        assert response.json()["status"] == "research_only"
        assert response.json()["interval_status"] == "experimental_temporal_coverage_not_guaranteed"
        assert response.json()["calibration"]["predictor_refit_after_calibration"] is False
        _, bundle = load_bundle(manifest["series_id"], horizon, root)
        assert response.json()["calibration"]["predictor_fingerprint"] == bundle["model_fingerprint"]
    with pytest.raises(DataUnavailable, match="already reserved"):
        train(prices, None, "2022-05-15", "2022-08-15", root)
    (root / manifest["version"] / "h1.joblib").write_bytes(b"corrupt")
    assert client.get("/api/agri/models").status_code == 503
    assert client.get(f'/api/agri/forecast/{manifest["series_id"]}').status_code == 503


def test_observation_catalog_keeps_grade_source_and_unknown_availability(monkeypatch):
    from datetime import datetime, timezone
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool
    from backend.agri import api
    from backend.agri.storage import commodities, mandis, migrate, prices

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    migrate(engine)
    today = pd.Timestamp.now().date()
    with engine.begin() as conn:
        conn.execute(commodities.insert().values(id="onion", name="Onion"))
        conn.execute(mandis.insert().values(id="exact-local", market="Lasalgaon(Niphad)", district="Nashik", state="Maharashtra"))
        conn.execute(prices.insert().values(series_id="exact-local", commodity_id="onion", variety="Other", grade="Local",
            date=today, min_price=1000, max_price=1400, modal_price=1200, unit="INR/quintal", source="official-report.csv",
            available_at=datetime.now(timezone.utc), record_key="test-record"))
    monkeypatch.setattr(api, "observation_source", lambda: (engine, commodities, mandis, prices))
    monkeypatch.setattr(api, "safe_registry", lambda: {"status": "unavailable", "markets": []})
    client = TestClient(app)
    response = client.get("/api/agri/series")
    assert response.status_code == 200
    series = response.json()["series"][0]
    assert (series["market"], series["variety"], series["grade"], series["source"]) == (
        "Lasalgaon(Niphad)", "Other", "Local", "official-report.csv")
    assert series["availability_status"] == "unknown"
    observed = client.get("/api/agri/series/exact-local").json()
    assert observed["latest_observation"]["availability_status"] == "unknown"
    assert observed["latest_observation"]["source_available_at"] is None
    assert observed["forecast_status"] == "evaluation_blocked"


def test_news_availability_and_coverage(prices):
    from backend.agri.data import event_features
    day = pd.Timestamp("2022-04-01")
    event = dict(url="https://example.test/article", series_id="x", published_at=cutoff(day),
                 available_at=cutoff(day)+pd.Timedelta(days=1), category="policy", supply_pressure=1)
    archive = {"coverage": {"x": {"start": "2022-01-01", "end": "2022-05-01"}}, "events": [event]}
    assert event_features(archive, "x", day)["event_count"] == 0
    assert event_features(archive, "x", day+pd.Timedelta(days=1))["event_count"] == 1
    assert event_features(None, "x", day) is None


def test_short_history_never_registers(prices, tmp_path):
    frame = pd.read_csv(prices).head(40)
    frame.to_csv(prices, index=False)
    root = tmp_path / "short"
    result = train(prices, None, "2022-01-15", "2022-02-01", root)
    assert not result["registered"]
    assert result["limitations"]
    assert not load_registry(root)["markets"]


def test_additive_migration_idempotent_ingestion_and_conflicts(prices):
    from sqlalchemy import create_engine, inspect, select
    from backend.agri.storage import ingest_csv, logs, migrate
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE legacy (value TEXT)")
        conn.exec_driver_sql("INSERT INTO legacy VALUES ('preserved')")
    migrate(engine)
    migrate(engine)
    assert "legacy" in inspect(engine).get_table_names()
    assert ingest_csv(engine, prices)["inserted"] == 300
    assert ingest_csv(engine, prices)["inserted"] == 0
    frame = pd.read_csv(prices)
    frame.loc[0, "modal_price"] += 1
    frame.to_csv(prices, index=False)
    with pytest.raises(DataUnavailable, match="Conflicting"):
        ingest_csv(engine, prices)
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT value FROM legacy").scalar() == "preserved"
        assert conn.execute(select(logs.c.status).order_by(logs.c.id.desc())).first()[0] == "failed"


def test_agmarknet_daily_report_ingestion_is_idempotent_and_preserves_units():
    from pathlib import Path
    from sqlalchemy import create_engine, select
    from backend.agri.storage import (audit_agmarknet_daily, ingest_agmarknet_daily,
                                      prices as agri_prices, read_agmarknet_daily)

    source = Path(__file__).resolve().parents[2] / "data/raw/agri/Daily Price Arrival Report-07-11-2025 to 08-10-2026 for Maharashtra.csv"
    source_hash = __import__("hashlib").sha256(source.read_bytes()).hexdigest()
    records = read_agmarknet_daily(source)
    assert len(records) == 291
    assert {r["market"] for r in records} == {"Lasalgaon(Niphad)"}
    assert {r["price_unit"] for r in records} == {"INR/quintal"}
    assert {r["arrival_unit"] for r in records} == {"metric tonnes"}
    assert {r["price_date"] for r in records} == {r["arrival_date"] for r in records}

    engine = create_engine("sqlite:///:memory:")
    first = ingest_agmarknet_daily(engine, source)
    assert first == {"inserted": 291, "skipped": 0, "source_records": 291}
    second = ingest_agmarknet_daily(engine, source)
    assert second == {"inserted": 0, "skipped": 291, "source_records": 291}
    audit = audit_agmarknet_daily(engine)
    assert audit["database_rows"] == 291
    assert audit["date_start"].isoformat() == "2025-11-07"
    assert audit["date_end"].isoformat() == "2026-10-08"
    assert {k: v["count"] for k, v in audit["observations_per_variety"].items()} == {"Other": 74, "Red": 90, "Unhali": 127}
    with engine.connect() as conn:
        row = conn.execute(select(agri_prices).where(agri_prices.c.variety == "Unhali")).mappings().first()
        assert row["unit"] == "INR/quintal"
        assert row["arrival_unit"] == "metric tonnes"
        assert row["grade"] == "Local"
        assert row["arrival_quantity"] is not None
        assert row["price_date"] == row["arrival_date"]
    assert __import__("hashlib").sha256(source.read_bytes()).hexdigest() == source_hash


def test_historical_ingestion_isolated_quarantined_and_idempotent(tmp_path):
    import csv
    from sqlalchemy import create_engine, select, inspect
    from backend.agri.storage import (commodities, historical_prices, ingest_historical_nashik,
                                      mandis, migrate, prices)

    fields = ["State", "District", "Market", "Commodity", "Variety", "Grade", "Arrival_Date",
              "Min_Price", "Max_Price", "Modal_Price", "Commodity_Code"]
    path = tmp_path / "2025.csv"
    rows = [
        ["Maharashtra", "Nashik", "Lasalgaon (Niphad) APMC", "Onion", "Other", "Local", "2025-12-05", "1000", "1500", "1300", "23"],
        ["Maharashtra", "Nashik", "Lasalgaon", "Onion", "Other", "FAQ", "2025-12-05", "1100", "1600", "1400", "23"],
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(fields)
        writer.writerows(rows)
    engine = create_engine("sqlite:///:memory:")
    dry = ingest_historical_nashik(engine, [path])
    assert dry["source_rows"] == 2 and dry["inserted"] == 0
    assert "agri_historical_price_observations" not in inspect(engine).get_table_names()
    migrate(engine)
    with engine.begin() as conn:
        conn.execute(commodities.insert().values(id="onion", name="Onion"))
        conn.execute(mandis.insert().values(id="canonical", market="Lasalgaon(Niphad)", district="Nashik", state="Maharashtra"))
        conn.execute(prices.insert().values(series_id="canonical", commodity_id="onion", variety="Other",
            date=date(2025, 12, 5), min_price=1000, max_price=1500, modal_price=1300,
            unit="INR/quintal", source="canonical fixture", available_at=__import__("datetime").datetime(2025, 12, 6),
            record_key="canonical-key", grade="Local", price_date=date(2025, 12, 5)))
    first = ingest_historical_nashik(engine, [path], commit=True)
    second = ingest_historical_nashik(engine, [path], commit=True)
    assert first["inserted"] == 2 and first["eligible_rows"] == 1 and first["quarantined_rows"] == 1
    assert second["inserted"] == 0 and second["skipped"] == 2
    with engine.connect() as conn:
        records = conn.execute(select(historical_prices)).mappings().all()
    assert len(records) == 2
    assert {r["availability_status"] for r in records} == {"unknown"}
    assert all(r["verified_available_at"] is None for r in records)
    assert {r["grade"] for r in records} == {"Local", "FAQ"}
    assert {r["market_original"] for r in records} == {"Lasalgaon (Niphad) APMC", "Lasalgaon"}
    assert {r["review_status"] for r in records} == {"eligible_historical", "quarantined_alias_candidate"}


def test_retrospective_availability_policy_is_explicit_and_not_verified():
    from datetime import date, datetime, timezone
    from backend.agri.storage import retrospective_assumed_available_at
    assumed = retrospective_assumed_available_at(date(2025, 12, 5))
    assert assumed == datetime(2025, 12, 12, 18, 29, 59, 999999, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        retrospective_assumed_available_at(date(2025, 12, 5), delay_days=0)


def test_historical_import_rolls_back_on_source_duplicate(tmp_path):
    import csv
    from sqlalchemy import create_engine, select
    from backend.agri.data import DataUnavailable
    from backend.agri.storage import historical_prices, ingest_historical_nashik, migrate
    fields = ["State", "District", "Market", "Commodity", "Variety", "Grade", "Arrival_Date",
              "Min_Price", "Max_Price", "Modal_Price", "Commodity_Code"]
    row = ["Maharashtra", "Nashik", "Test Market", "Onion", "Other", "FAQ", "2025-01-02", "10", "20", "15", "23"]
    path = tmp_path / "2025.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle); writer.writerow(fields); writer.writerow(row); writer.writerow(row)
    engine = create_engine("sqlite:///:memory:")
    migrate(engine)
    with pytest.raises(DataUnavailable, match="Duplicate historical record key"):
        ingest_historical_nashik(engine, [path], commit=True)
    with engine.connect() as conn:
        assert conn.execute(select(historical_prices.c.id)).all() == []


def test_supervised_targets_survive_unavailable_seasonal_baseline():
    from backend.agri.data import supervised
    dates = pd.date_range("2024-01-01", periods=20)
    series = pd.DataFrame({"date": dates, "modal_price": np.arange(20, dtype=float) + 100,
                           "available_at": [cutoff(d + pd.Timedelta(days=7)) for d in dates]})
    features = pd.DataFrame({"origin": dates[:10], "current": np.arange(10, dtype=float) + 100,
                             "price": np.arange(10, dtype=float) + 100,
                             "lag1": np.arange(10, dtype=float) + 99,
                             "lag7": np.arange(10, dtype=float) + 93,
                             "mean7": np.arange(10, dtype=float) + 97,
                             "std7": np.ones(10), "change7": np.full(10, 7.),
                             "weekday": dates[:10].dayofweek, "month": dates[:10].month})
    rows = supervised(series, features, 1)
    assert len(rows) == 10
    assert rows.target.notna().all()
    assert rows.seasonal.isna().all()


def test_research_asof_features_respect_seven_day_availability_and_future_invariance():
    from backend.agri.research_phase3a import build_asof_features, forecast_origin
    dates = pd.date_range("2022-01-01", periods=45)
    records = [dict(observation_date=d.strftime("%Y-%m-%d"), modal_price=float(900+i))
               for i, d in enumerate(dates)]
    _, original_series, original = build_asof_features(records)
    changed_records = [dict(r, modal_price=(r["modal_price"] * 9 if
                       pd.Timestamp(r["observation_date"]) > pd.Timestamp("2022-01-20") else r["modal_price"]))
                       for r in records]
    _, _, changed = build_asof_features(changed_records)
    cutoff_origin = pd.Timestamp("2022-01-27")
    columns = ["origin", "current", "lag1", "lag7", "mean7", "std7", "change7"]
    pd.testing.assert_frame_equal(original.loc[original.origin <= cutoff_origin, columns].reset_index(drop=True),
                                  changed.loc[changed.origin <= cutoff_origin, columns].reset_index(drop=True))
    for origin in original.origin:
        known = original_series.loc[original_series.date <= origin]
        assert (known.date <= origin).all()
        assert (known.available_at <= forecast_origin(origin.date()).astimezone(__import__("datetime").timezone.utc)).all()


def test_research_split_purges_unavailable_targets_and_requires_common_origins():
    from backend.agri.research_phase3a import assert_identical_origins, research_eligible
    frame = pd.DataFrame({"origin_date": [date(2024, 1, 10)] * 3,
                          "target_date": [date(2024, 1, 8), date(2024, 1, 9), date(2024, 1, 10)],
                          "target_available_at": [
                              __import__("backend.agri.research_phase3a", fromlist=["assumed_available_at"]).assumed_available_at(date(2024, 1, 1)),
                              __import__("backend.agri.research_phase3a", fromlist=["local_end"]).local_end(date(2024, 1, 10)),
                              __import__("backend.agri.research_phase3a", fromlist=["assumed_available_at"]).assumed_available_at(date(2024, 1, 3))]})
    eligible_rows = research_eligible(frame, date(2024, 1, 10))
    assert eligible_rows.target_date.tolist() == [date(2024, 1, 8)]
    assert len(assert_identical_origins([eligible_rows, eligible_rows.copy()])) == 1
    with pytest.raises(ValueError, match="identical origins"):
        assert_identical_origins([eligible_rows, eligible_rows.iloc[:0]])


def test_research_artifacts_are_not_loadable_from_production_registry(tmp_path):
    from backend.agri.data import DataUnavailable
    from backend.agri.registry import load_bundle, load_registry
    production_registry = tmp_path / "production_registry"
    research = tmp_path / "ml" / "research_only" / "phase3a"
    research.mkdir(parents=True)
    (research / "manifest.json").write_text(json.dumps({"research_only": True}), encoding="utf-8")
    (research / "h1_A_ridge_1.joblib").write_bytes(b"research artifact")
    assert load_registry(production_registry)["status"] == "unavailable"
    with pytest.raises(DataUnavailable, match="No evaluated model"):
        load_bundle("research-only-lasalgaon-niphad-other-faq", 1, production_registry)


def test_historical_ingestion_isolated_quarantined_and_idempotent(tmp_path):
    import csv
    from datetime import date
    from sqlalchemy import create_engine, select
    from backend.agri.storage import historical_prices, ingest_historical_nashik, migrate

    fields = ["State", "District", "Market", "Commodity", "Variety", "Grade", "Arrival_Date",
              "Min_Price", "Max_Price", "Modal_Price", "Commodity_Code"]
    path = tmp_path / "2025.csv"
    rows = [
        ["Maharashtra", "Nashik", "Lasalgaon (Niphad) APMC", "Onion", "Other", "Local", "2025-12-05", "1000", "1500", "1300", "23"],
        ["Maharashtra", "Nashik", "Lasalgaon", "Onion", "Other", "FAQ", "2025-12-05", "1100", "1600", "1400", "23"],
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(fields)
        writer.writerows(rows)
    engine = create_engine("sqlite:///:memory:")
    dry = ingest_historical_nashik(engine, [path])
    assert dry["source_rows"] == 2 and dry["inserted"] == 0
    assert "agri_historical_price_observations" not in __import__("sqlalchemy").inspect(engine).get_table_names()
    migrate(engine)
    first = ingest_historical_nashik(engine, [path], commit=True)
    second = ingest_historical_nashik(engine, [path], commit=True)
    assert first["inserted"] == 2 and first["eligible_rows"] == 2
    assert second["inserted"] == 0 and second["skipped"] == 2
    with engine.connect() as conn:
        records = conn.execute(select(historical_prices)).mappings().all()
    assert len(records) == 2
    assert {r["availability_status"] for r in records} == {"unknown"}
    assert all(r["verified_available_at"] is None for r in records)
    assert {r["grade"] for r in records} == {"Local", "FAQ"}
    assert {r["market_original"] for r in records} == {"Lasalgaon (Niphad) APMC", "Lasalgaon"}


def test_source_failure_does_not_log_secrets(tmp_path):
    import httpx
    from backend.agri.sources import fetch_json
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(403)))
    with pytest.raises(DataUnavailable):
        fetch_json("https://example.test", {"api-key": "secret-value"}, tmp_path, client)
    assert "secret-value" not in (tmp_path / "ingestion.jsonl").read_text()
    assert json.loads((tmp_path / "ingestion.jsonl").read_text())["status"] == "failed"


def test_legacy_financial_api_is_retired():
    client = TestClient(app)
    for path, method in (("/api/models/status", "get"), ("/api/decision/predict", "post"),
                         ("/api/decision/simulate", "post"), ("/api/decision/explain", "post"),
                         ("/api/financial-state/validate", "post")):
        response = client.post(path, json={}) if method == "post" else client.get(path)
        assert response.status_code == 404


def test_semantic_retrieval_filters_and_preserves_sources():
    from backend.agri.semantic import retrieve
    day = pd.Timestamp("2022-01-10", tz="UTC")
    old = dict(id="1", url="https://example.test/1", title="Onion supply disruption", series_id="x",
               published_at=day-pd.Timedelta(days=1), available_at=day)
    future = dict(old, id="2", url="https://example.test/2", available_at=day+pd.Timedelta(days=1))
    result = retrieve({"events": [old, future]}, "onion", "x", day)
    assert [e["id"] for e in result] == ["1"]
    assert result[0]["url"] == old["url"]
    assert result[0]["retrieval"] == "keyword_only"


def test_linear_explanation_is_additive(prices):
    from backend.agri.evaluation import candidates, fit, predict
    from backend.agri.explain import explain
    series = read_prices(prices)
    rows = supervised(series, make_features(series), 1)
    spec = next(c for c in candidates(False) if c["id"] == "A_ridge_1")
    bundle = {"spec": spec, "model": fit(spec, rows.head(100))}
    sample = rows.tail(1)
    explanation = explain(bundle, sample)
    total = explanation["reference_prediction"] + explanation["clipping_adjustment"] + sum(f["contribution"] for f in explanation["features"])
    assert np.isclose(total, predict(spec, bundle["model"], sample)[0])


def test_browser_workspace_upload_check_evaluate(prices, tmp_path, monkeypatch):
    monkeypatch.setenv("AGRISENSE_WORKSPACE", str(tmp_path / "workspace"))
    monkeypatch.setenv("AGRISENSE_REGISTRY", str(tmp_path / "registry"))
    client = TestClient(app)
    response = client.post("/api/agri/workspace/datasets", json={"prices_csv": prices.read_text()})
    assert response.status_code == 201, response.text
    dataset = response.json()
    series = dataset["series"][0]
    assert series["rows"] == 300
    assert len(series["history"]) == 90
    assert not (tmp_path / "registry" / "active.json").exists()
    payload = {"dataset_id": dataset["dataset_id"], "series_id": series["series_id"],
               "validation_start": series["validation_start"], "test_start": series["test_start"]}
    ready = client.post("/api/agri/workspace/check", json=payload)
    assert ready.json()["ready"], ready.text
    assert all(not h["semantic_ready"] for h in ready.json()["horizons"])
    rejected = client.post("/api/agri/workspace/check", json={**payload, "test_start": "2022-06-02"})
    assert not rejected.json()["ready"]
    assert not (tmp_path / "registry" / "active.json").exists()
    started = client.post("/api/agri/workspace/evaluate", json=payload)
    assert started.status_code == 202, started.text
    job = client.get(f'/api/agri/workspace/jobs/{started.json()["job_id"]}').json()
    assert job["status"] == "completed", job
    assert client.get("/api/agri/models").json()["status"] == "research_only"
    for horizon in (1, 3, 7):
        assert client.get(f'/api/agri/forecast/{series["series_id"]}?horizon={horizon}').status_code == 200
    reused = client.post("/api/agri/workspace/evaluate", json=payload)
    assert reused.status_code == 422
    assert "reserved" in reused.json()["detail"]


def test_workspace_rejects_invalid_upload_and_foreign_origin(tmp_path, monkeypatch):
    monkeypatch.setenv("AGRISENSE_WORKSPACE", str(tmp_path / "workspace"))
    client = TestClient(app)
    assert client.post("/api/agri/workspace/datasets", json={"prices_csv": "hello"}).status_code == 422
    assert client.post("/api/agri/workspace/datasets", json={"prices_csv": "hello"}, headers={"origin": "https://example.test"}).status_code == 403
    assert client.post("/api/agri/workspace/datasets", json={"prices_csv": "hello"}, headers={"x-forwarded-for": "192.0.2.1"}).status_code == 403
    assert client.get("/api/agri/workspace/jobs/not-an-id").status_code == 422


def test_readiness_does_not_reserve_short_history(prices, tmp_path, monkeypatch):
    monkeypatch.setenv("AGRISENSE_WORKSPACE", str(tmp_path / "workspace"))
    monkeypatch.setenv("AGRISENSE_REGISTRY", str(tmp_path / "registry"))
    client = TestClient(app)
    short = pd.read_csv(prices).head(40).to_csv(index=False)
    data = client.post("/api/agri/workspace/datasets", json={"prices_csv": short}).json()
    series = data["series"][0]
    response = client.post("/api/agri/workspace/evaluate", json={"dataset_id": data["dataset_id"], "series_id": series["series_id"], "validation_start": series["validation_start"], "test_start": series["test_start"]})
    assert response.status_code == 422
    assert not (tmp_path / "registry").exists()


def test_research_calendar_origins_carry_forward_and_score_exact_targets():
    from backend.agri.research_evaluation import calendar_origin_frame, origin_count_summary
    observations = [
        {"observation_date": "2024-01-01", "modal_price": 100.0},
        {"observation_date": "2024-01-03", "modal_price": 120.0},
        {"observation_date": "2024-01-09", "modal_price": 150.0},
    ]
    rows = calendar_origin_frame(observations, 1, date(2024, 1, 8), date(2024, 1, 10))
    assert rows.origin_date.tolist() == [date(2024, 1, 8), date(2024, 1, 9), date(2024, 1, 10)]
    # Jan 9 has no newly published price; the Jan 1 price remains the as-of value.
    assert rows.current.tolist()[:2] == [100.0, 100.0]
    assert rows.latest_observation_date.tolist()[:2] == [date(2024, 1, 1), date(2024, 1, 1)]
    assert rows.latest_price_age_days.tolist()[:2] == [7, 8]
    # The origin on Jan 8 has a real Jan 9 target; later target dates are absent.
    assert rows.scored.tolist() == [True, False, False]
    assert origin_count_summary(rows) == {
        "total_calendar_origins": 3, "scored_origins": 1, "unscored_origins": 2}


def test_research_calendar_asof_strict_future_invariance_and_timezone_boundary():
    from backend.agri.research_evaluation import calendar_origin_frame, local_end
    from datetime import timezone
    source = [
        {"observation_date": "2024-01-01", "modal_price": 100.0},
        {"observation_date": "2024-01-03", "modal_price": 120.0},
    ]
    assert local_end(date(2024, 1, 8)).astimezone(timezone.utc).isoformat() == "2024-01-08T18:29:59+00:00"
    base = calendar_origin_frame(source, 3, date(2024, 1, 7), date(2024, 1, 9))
    changed = [dict(row, modal_price=(9999.0 if row["observation_date"] == "2024-01-03" else row["modal_price"]))
               for row in source]
    future_changed = calendar_origin_frame(changed, 3, date(2024, 1, 7), date(2024, 1, 9))
    assert pd.isna(base.current.iloc[0])  # release occurs after Jan 7 origin
    assert base.current.iloc[1] == 100.0  # available exactly at Jan 8 23:59:59
    pd.testing.assert_series_equal(base.loc[:1, "current"], future_changed.loc[:1, "current"])
    assert base.target_date.tolist() == [date(2024, 1, 10), date(2024, 1, 11), date(2024, 1, 12)]
    assert not base.scored.any()


def test_research_calendar_exact_lags_preserve_gaps_and_missing_indicators():
    from backend.agri.research_evaluation import calendar_origin_frame
    rows = calendar_origin_frame([
        {"date": "2024-01-01", "modal_price": 100.0},
        {"date": "2024-01-03", "modal_price": 120.0},
    ], 1, date(2024, 1, 10), date(2024, 1, 10))
    row = rows.iloc[0]
    assert row.current == 120.0
    assert row.lag1_missing == 1 and pd.isna(row.lag1)
    assert row.lag7_missing == 1 and pd.isna(row.lag7)
    assert pd.isna(row.change7)
    with pytest.raises(ValueError, match="Duplicate observation date"):
        calendar_origin_frame([
            {"date": "2024-01-01", "modal_price": 100.0},
            {"date": "2024-01-01", "modal_price": 101.0}],
            1, date(2024, 1, 8), date(2024, 1, 8))


def test_research_chronological_purge_and_candidate_origins_are_independent():
    from datetime import datetime
    from backend.agri.research_evaluation import assert_candidate_origins, local_end, purge_training_rows
    frame = pd.DataFrame({
        "origin_id": ["2024-01-01", "2024-01-02", "2024-01-03"],
        "target_id": ["2024-01-08", "2024-01-09", "2024-01-10"],
        "origin_date": [date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3)],
        "target_date": [date(2024, 1, 8), date(2024, 1, 9), date(2024, 1, 10)],
        "target_available_at": [local_end(date(2024, 1, 9)), local_end(date(2024, 1, 10)),
                                local_end(date(2024, 1, 11))],
    })
    eligible = purge_training_rows(frame, date(2024, 1, 10))
    assert eligible.origin_id.tolist() == ["2024-01-01"]
    assert len(assert_candidate_origins({"ridge": eligible, "baseline": eligible.copy()})) == 1
    with pytest.raises(ValueError, match="origins differ"):
        assert_candidate_origins({"ridge": eligible, "baseline": frame.iloc[1:]})
    bad = frame.iloc[:1].copy()
    bad["target_available_at"] = pd.Series([datetime(2024, 1, 9, 23, 59)], dtype=object)
    with pytest.raises(ValueError, match="timezone-aware"):
        purge_training_rows(bad, date(2024, 1, 10))


def test_research_directional_metrics_separate_movement_and_no_change():
    from backend.agri.research_evaluation import directional_diagnostics
    report = directional_diagnostics(
        actual=[100, 110, 90, 100], predicted=[100, 100, 110, 101], reference=[100, 100, 100, 100])
    assert report["legacy_three_way_sign_agreement"] == 0.25
    assert report["up_down_accuracy_on_moving_targets"] == 0.0
    assert report["actual_class_distribution"] == {"up": 1, "down": 1, "no_change": 2}
    assert report["predicted_class_distribution"] == {"up": 2, "down": 0, "no_change": 2}
    assert report["no_change_prediction_behavior"]["no_change_predictions_on_moving_targets"] == 1
    deadband = directional_diagnostics(actual=[100, 102], predicted=[100, 103], reference=[100, 100], deadband=2)
    assert deadband["tie_rule"] == "absolute change <= 2 is no-change"
    assert deadband["actual_class_distribution"]["no_change"] == 2


def test_research_finite_sample_interval_rank_and_model_identity():
    from backend.agri.research_evaluation import (
        calibrate_model_intervals, finite_sample_residual_radius, interval_diagnostics,
    )
    values = finite_sample_residual_radius(np.arange(1, 21, dtype=float), 0.9)
    assert values["calibration_sample_size"] == 20
    assert values["finite_sample_rank_1_based"] == 19
    assert values["radius"] == 19.0
    too_small = finite_sample_residual_radius(np.arange(1, 9, dtype=float), 0.9)
    assert not too_small["finite_radius_available"] and np.isinf(too_small["radius"])
    model = {"offset": 0.0}
    calibration = calibrate_model_intervals(model, [1, 2, 3], [2, 4, 6],
                                            lambda fitted, xs: np.asarray(xs, dtype=float) + fitted["offset"],
                                            nominal_coverage=0.5)
    lo, hi = calibration.intervals(model, [10.0])
    assert lo.tolist() == [8.0] and hi.tolist() == [12.0]
    interval_report = interval_diagnostics([10.0], lo, hi, calibration)
    assert interval_report["nominal_coverage"] == 0.5
    assert interval_report["empirical_coverage"] == 1.0
    assert interval_report["mean_interval_width"] == 4.0
    assert interval_report["calibration_sample_size"] == 3
    with pytest.raises(ValueError, match="differs from the model"):
        calibration.intervals(object(), [10.0])
    model["offset"] = 5.0
    with pytest.raises(ValueError, match="state changed"):
        calibration.intervals(model, [10.0])
    assert calibration.calibration_sample_size == 3
    assert "not guaranteed" in " ".join(calibration.assumptions)


def test_research_seasonal_naive_is_unavailable_under_seven_day_delay():
    from backend.agri.research_evaluation import calendar_origin_frame, seasonal_naive_availability
    observations = [{"date": f"2024-01-{day:02d}", "modal_price": 100.0 + day}
                    for day in range(1, 16)]
    origins = calendar_origin_frame(observations, 1, date(2024, 1, 8), date(2024, 1, 8))
    result = seasonal_naive_availability(observations, origins, 1)
    assert result["status"] == "unavailable"
    assert result["eligible_origins"] == 0


def test_research_fresh_holdout_and_production_isolation(tmp_path):
    from backend.agri.registry import load_registry
    from backend.agri.research_evaluation import fresh_holdout_assessment
    assessment = fresh_holdout_assessment(pd.date_range("2021-01-01", "2024-12-10"))
    assert assessment["status"] == "no_fresh_holdout"
    assert assessment["fresh_observation_count"] == 0
    production_registry = tmp_path / "production_registry"
    assert load_registry(production_registry)["status"] == "unavailable"
    assert not production_registry.exists()
