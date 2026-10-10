from datetime import date, datetime, timezone
import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
import joblib
import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from .data import DataUnavailable, cutoff, make_features, read_events, read_prices
from .evaluation import predict, predictor_fingerprint
from .explain import explain
from .registry import digest, load_bundle, load_registry, registry_root
from .research_phase5a import (PREVIOUSLY_EXAMINED_TARGET_END, REUSED_TEST_START,
                               STALE_AFTER_DAYS, _load_snapshot, artifact_base,
                               locate_artifact, replay_forecast)

router = APIRouter(prefix="/agri", tags=["AgriSense"])
logger = logging.getLogger(__name__)


@router.get("/events/recent")
def recent_events(limit: int = Query(50, ge=1, le=200)):
    """Return source-attributed, locally captured PIB items with separate timestamps."""
    from backend.app.models.database import engine
    from .events import human_event_reviews, recent_captures
    try:
        result = recent_captures(engine, limit=limit)
        if "dataset_health" not in result:
            # Keep the public response contract resilient when serving against
            # an older event-capture schema/code path; counts remain derived
            # only from distinct source identities and the append-only review table.
            all_events = recent_captures(engine, limit=200).get("events", [])
            from sqlalchemy import inspect
            review_count = 0
            if inspect(engine).has_table(human_event_reviews.name):
                with engine.connect() as conn:
                    rows = conn.execute(select(human_event_reviews).order_by(
                        human_event_reviews.c.reviewed_at_utc.desc())).mappings().all()
                latest = {}
                for row in rows:
                    latest.setdefault(row["article_key"], row)
                review_count = sum(row["status"] == "reviewed" for row in latest.values())
            result["dataset_health"] = {"unique_articles": len(all_events),
                "full_body_articles": sum(item.get("content_status") in {"full_text_extracted", "full_body_verified"} for item in all_events),
                "human_reviewed_articles": review_count, "source_diversity": len({item.get("source") for item in all_events if item.get("source")}),
                "evaluation_status": "insufficient_labels" if review_count == 0 else "exploratory",
                "accuracy_metrics_available": False if review_count == 0 else None}
        return result
    except (ValueError, OSError, SQLAlchemyError):
        logger.exception("Agricultural event capture lookup failed")
        raise HTTPException(503, "Official event captures are unavailable")


@router.get("/combined/{series_id}")
def combined_context(series_id: str, horizon: int = Query(1, ge=1, le=7)):
    """Guarded Model C: show a valid Model A forecast with prior, reviewed evidence only."""
    if horizon not in (1, 3, 7):
        raise HTTPException(422, "Supported calendar-day horizons: 1, 3, 7")
    from .model_c import build_combined_context
    try:
        try:
            model_a = forecast(series_id, horizon)
        except HTTPException:
            return build_combined_context(series_identity={"series_id": series_id}, forecast=None,
                forecast_origin_at=datetime.now(timezone.utc), reviews=[])
        from backend.app.models.database import engine
        from .events import human_event_reviews, recent_captures
        from .research_phase3a import forecast_origin
        from .storage import commodities, mandis, prices
        identity_query = (select(mandis.c.market, mandis.c.district, mandis.c.state,
            commodities.c.name.label("commodity"), prices.c.variety, prices.c.grade, prices.c.unit)
            .join(prices, prices.c.series_id == mandis.c.id)
            .join(commodities, prices.c.commodity_id == commodities.c.id)
            .where(prices.c.series_id == series_id).limit(1))
        with engine.connect() as conn:
            identity = dict(conn.execute(identity_query).mappings().first() or {})
            review_rows = conn.execute(select(human_event_reviews).order_by(
                human_event_reviews.c.reviewed_at_utc.desc())).mappings().all()
        feed = recent_captures(engine, limit=200)
        current = {item.get("article_identity"): item for item in feed.get("events", [])}
        latest_reviews = {}
        for row in review_rows:
            latest_reviews.setdefault(row["article_key"], row)
        reviews = []
        for article_key, row in latest_reviews.items():
            article = current.get(article_key)
            if not article:
                continue
            payload = json.loads(row["payload_json"])
            expected_hash = article.get("normalized_content_sha256") or article.get("text_content_sha256")
            reviews.append({"article_identity": article_key, "title": article.get("title"),
                "source_url": article.get("source_page_url_as_saved") or article.get("url"),
                "published_date": article.get("published_date"),
                "publication_precision": article.get("publication_precision"),
                "first_seen_at": article.get("first_seen_at"), "status": row["status"],
                "review": payload, "identity_matches": row["capture_id"] == article.get("id"),
                "source_checksum_matches": row["source_content_sha256"] == expected_hash})
        origin_at = forecast_origin(date.fromisoformat(model_a["origin"]))
        return build_combined_context(series_identity={"series_id": series_id, **identity},
            forecast=model_a, forecast_origin_at=origin_at, reviews=reviews)
    except HTTPException:
        raise
    except (ValueError, OSError, KeyError, SQLAlchemyError):
        logger.exception("Guarded combined context unavailable")
        raise HTTPException(503, "Combined context is unavailable")


def safe_registry():
    try:
        return load_registry()
    except (ValueError, OSError, KeyError, StopIteration, SQLAlchemyError):
        logger.exception("Agricultural registry validation failed")
        raise HTTPException(503, "Agricultural registry unavailable or invalid")


@router.get("/models")
def models():
    return safe_registry()


def _evaluated_series():
    try:
        return {item["series_id"]: item for item in safe_registry().get("markets", [])}
    except HTTPException:
        # Observation inspection remains available if an unrelated model
        # artifact is invalid; forecast routes continue to fail closed.
        return {}


def observation_source():
    from backend.app.models.database import engine
    from .storage import commodities, mandis, prices
    return engine, commodities, mandis, prices


@router.get("/series")
def series_catalog():
    """List exact canonical identities, separately from evaluated model availability."""
    try:
        engine, commodities, mandis, prices = observation_source()
        statement = (select(prices.c.series_id, mandis.c.market, mandis.c.district, mandis.c.state,
                            commodities.c.name.label("commodity"), prices.c.variety, prices.c.grade,
                            prices.c.unit, prices.c.source, func.count().label("observations"),
                            func.min(prices.c.date).label("first_date"), func.max(prices.c.date).label("last_date"))
                     .join(mandis, prices.c.series_id == mandis.c.id)
                     .join(commodities, prices.c.commodity_id == commodities.c.id)
                     .group_by(prices.c.series_id, mandis.c.market, mandis.c.district, mandis.c.state,
                               commodities.c.name, prices.c.variety, prices.c.grade, prices.c.unit, prices.c.source)
                     .order_by(mandis.c.market, prices.c.variety, prices.c.grade))
        with engine.connect() as conn:
            rows = conn.execute(statement).mappings().all()
        evaluated = _evaluated_series()
        records = []
        for row in rows:
            manifest = evaluated.get(row["series_id"])
            records.append({"series_id": row["series_id"], "market": row["market"],
                            "district": row["district"], "state": row["state"],
                            "commodity": row["commodity"], "variety": row["variety"],
                            "grade": row["grade"], "unit": row["unit"], "source": row["source"],
                            "observations": row["observations"],
                            "first_date": row["first_date"].isoformat(), "last_date": row["last_date"].isoformat(),
                            "availability_status": "unknown",
                            "model_status": "evaluated_research_bundle" if manifest else "unavailable",
                            "forecast_status": "research_only" if manifest else "evaluation_blocked"})
        return {"status": "ready" if records else "unavailable", "series": records,
                "reason": None if records else "No canonical agricultural observations are registered"}
    except (ValueError, OSError, KeyError, StopIteration, SQLAlchemyError):
        logger.exception("Agricultural series discovery failed")
        raise HTTPException(503, "Agricultural series discovery unavailable")


@router.get("/series/{series_id}")
def observed_series(series_id: str):
    """Return observed prices with explicit unknown source availability status."""
    try:
        engine, commodities, mandis, prices = observation_source()
        statement = (select(prices, mandis.c.market, mandis.c.district, mandis.c.state,
                            commodities.c.name.label("commodity"))
                     .join(mandis, prices.c.series_id == mandis.c.id)
                     .join(commodities, prices.c.commodity_id == commodities.c.id)
                     .where(prices.c.series_id == series_id).order_by(prices.c.date))
        with engine.connect() as conn:
            rows = conn.execute(statement).mappings().all()
        if not rows:
            raise HTTPException(404, "No exact canonical observation series found")
        last = rows[-1]
        dates = [row["date"] for row in rows[-90:]]
        history = [{"date": row["date"].isoformat(), "price": float(row["modal_price"])} for row in rows[-90:]]
        model_ready = series_id in _evaluated_series()
        today = datetime.now(timezone.utc).date()
        age_days = max(0, (today - last["date"]).days)
        return {"series_id": series_id, "market": last["market"], "district": last["district"],
                "state": last["state"], "commodity": last["commodity"], "variety": last["variety"],
                "grade": last["grade"], "unit": last["unit"], "source": last["source"],
                "availability_status": "unknown",
                "latest_price": float(last["modal_price"]),
                "latest_observation": {"date": last["date"].isoformat(), "modal_price": float(last["modal_price"]),
                                       "min_price": float(last["min_price"]), "max_price": float(last["max_price"]),
                                       "availability_status": "unknown", "source_available_at": None},
                "observation_age_days": age_days, "stale": age_days > 7,
                "change": float(last["modal_price"]-rows[-2]["modal_price"]) if len(rows)>1 else None,
                "volatility": float(pd.Series([x["price"] for x in history]).pct_change().dropna().std(ddof=0)) if len(history)>1 else None,
                "as_of": last["date"].isoformat(), "history": history, "news": [],
                "forecast_status": "research_only" if model_ready else "evaluation_blocked",
                "limitations": ["Observation date is known; publication/availability timestamp is unverified.",
                                "Internal series identity is based on stored exact labels, not an official market identifier.",
                                "News archive and event evaluation are unavailable."]}
    except HTTPException:
        raise
    except (ValueError, OSError, KeyError, SQLAlchemyError):
        raise HTTPException(503, "Observed agricultural series unavailable")


def _phase5a_manifest(folder: Path):
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("protocol_id") != "phase5a-numerical-historical-replay-v1"
            or manifest.get("release_status") != "research_only"
            or manifest.get("production_authorized") is not False):
        raise DataUnavailable("Research artifact status or protocol is invalid")
    return manifest


@router.get("/research/series")
def research_series_catalog():
    """Discover separately persisted Phase 5A research identities."""
    root = artifact_base()
    if not root.exists():
        return {"status": "unavailable", "series": [], "reason": "No historical research artifacts are saved"}
    records = []
    seen_ids = set()
    try:
        for path in sorted(root.glob("phase5a_*/manifest.json")):
            manifest = json.loads(path.read_text(encoding="utf-8"))
            if (manifest.get("protocol_id") != "phase5a-numerical-historical-replay-v1"
                    or not manifest.get("series_id") or manifest["series_id"] in seen_ids):
                continue
            folder = locate_artifact(manifest["series_id"], root)
            manifest = _phase5a_manifest(folder)
            records.append({"series_id": manifest["series_id"], **manifest["identity"],
                            "observations": manifest["observation_count"],
                            "first_date": manifest["observation_start"], "last_date": manifest["observation_end"],
                            "source": manifest["identity"]["source_url"],
                            "availability_status": "retrospective_assumption_not_verified",
                            "unit_status": manifest["identity"]["unit_status"],
                            "status": "research_only", "forecast_status": "historical_replay_available",
                            "forecast_mode": "historical_replay",
                            "horizons": manifest["horizons"],
                            "training_period": manifest["horizons"]["1"]["training_period"],
                            "validation_period": manifest["horizons"]["1"]["validation_period"],
                            "test_period": manifest["test_period"],
                            "replay_origin": manifest["historical_replay_demo_origin"],
                            "test_status": manifest["test_period"]["status"]})
            seen_ids.add(manifest["series_id"])
        return {"status": "ready" if records else "unavailable", "series": records,
                "reason": None if records else "No Phase 5A historical research series is saved"}
    except (ValueError, OSError, KeyError, StopIteration, SQLAlchemyError) as exc:
        logger.exception("Historical research series discovery failed")
        raise HTTPException(503, "Historical research artifact unavailable") from exc


@router.get("/research/series/{series_id}")
def research_observed_series(series_id: str):
    try:
        folder = locate_artifact(series_id)
        manifest = _phase5a_manifest(folder)
        rows = _load_snapshot(folder)
        latest = max(rows, key=lambda row: row["observation_date"])
        age = max(0, (datetime.now(timezone.utc).date() - date.fromisoformat(latest["observation_date"])).days)
        prices = pd.Series([row["modal_price"] for row in rows[-90:]], dtype=float)
        return {"series_id": series_id, "status": "research_only", **manifest["identity"],
                "observations": manifest["observation_count"], "first_date": manifest["observation_start"],
                "last_date": manifest["observation_end"], "availability_status": "retrospective_assumption_not_verified",
                "latest_price": latest["modal_price"], "latest_observation_date": latest["observation_date"],
                "as_of": latest["observation_date"],
                "change": latest["modal_price"] - rows[-2]["modal_price"] if len(rows) > 1 else None,
                "volatility": float(prices.pct_change().dropna().std(ddof=0)) if len(prices) > 1 else None,
                "news": [],
                "observation_age_days": age, "stale": age > STALE_AFTER_DAYS,
                "history": [{"date": row["observation_date"], "price": row["modal_price"]} for row in rows[-90:]],
                "source": manifest["identity"]["source_url"],
                "source_url": manifest["identity"]["source_url"],
                "availability_policy": manifest["availability_policy"],
                "limitations": ["Historical availability is assumed at seven days and not source-verified.",
                                "Stored unit is provisional and not independently verified.",
                                "This series is stale and cannot support a current market forecast."]}
    except DataUnavailable as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, OSError, KeyError, SQLAlchemyError) as exc:
        logger.exception("Historical research observation lookup failed")
        raise HTTPException(503, "Historical research series unavailable") from exc


@router.get("/research/replay/{series_id}")
def historical_replay(series_id: str, origin: date = Query(...),
                      horizon: int = Query(..., ge=1, le=7)):
    if horizon not in (1, 3, 7):
        raise HTTPException(422, "Supported calendar-day horizons: 1, 3, 7")
    try:
        folder = locate_artifact(series_id)
        manifest = _phase5a_manifest(folder)
        if not REUSED_TEST_START <= origin <= PREVIOUSLY_EXAMINED_TARGET_END:
            raise HTTPException(422, "Historical replay origin must be inside the saved, previously examined test period")
        artifact = joblib.load(folder / f"h{horizon}.joblib")
        observations = _load_snapshot(folder)
        result = replay_forecast(folder, artifact, observations, horizon, origin, series_id=series_id)
        result["series_staleness_days"] = max(0, (datetime.now(timezone.utc).date()
                                                   - date.fromisoformat(manifest["observation_end"])).days)
        result["current_market_forecast"] = False
        result["stale_warning"] = "Historical replay only; this series is stale relative to today."
        result["source_publisher"] = manifest["identity"]["source_publisher"]
        result["source_attribution_claim"] = manifest["identity"]["source_attribution_claim"]
        return result
    except HTTPException:
        raise
    except DataUnavailable as exc:
        raise HTTPException(422, str(exc)) from exc
    except (ValueError, OSError, KeyError, SQLAlchemyError) as exc:
        logger.exception("Historical replay failed")
        raise HTTPException(503, "Historical replay artifact unavailable") from exc


@router.get("/research/latest/{series_id}")
def latest_research_forecast(series_id: str, horizon: int = Query(..., ge=1, le=7)):
    if horizon not in (1, 3, 7):
        raise HTTPException(422, "Supported calendar-day horizons: 1, 3, 7")
    try:
        folder = locate_artifact(series_id)
        manifest = _phase5a_manifest(folder)
        latest_date = date.fromisoformat(manifest["observation_end"])
        age = max(0, (datetime.now(timezone.utc).date() - latest_date).days)
        if age > STALE_AFTER_DAYS:
            raise HTTPException(409, detail={"status": "unavailable_stale",
                                             "message": "Latest-origin forecast blocked because this exact historical series is stale.",
                                             "latest_observation_date": latest_date.isoformat(),
                                             "observation_age_days": age,
                                             "stale_after_days": STALE_AFTER_DAYS,
                                             "research_only": True})
        observations = _load_snapshot(folder)
        artifact = joblib.load(folder / f"h{horizon}.joblib")
        result = replay_forecast(folder, artifact, observations, horizon, datetime.now(timezone.utc).date(),
                                 series_id=series_id)
        result["mode"] = "latest_origin_experimental"
        result["series_staleness_days"] = age
        result["current_market_forecast"] = True
        result["source_publisher"] = manifest["identity"]["source_publisher"]
        result["source_attribution_claim"] = manifest["identity"]["source_attribution_claim"]
        return result
    except HTTPException:
        raise
    except DataUnavailable as exc:
        raise HTTPException(422, str(exc)) from exc
    except (ValueError, OSError, KeyError, SQLAlchemyError) as exc:
        logger.exception("Latest research forecast failed")
        raise HTTPException(503, "Latest research forecast unavailable") from exc


@router.get("/markets")
def markets():
    registry = safe_registry()
    return {"status": registry["status"], "reason": registry.get("reason"),
            "markets": [{k: m[k] for k in ("series_id", "market", "district", "state", "commodity", "variety", "version")}
                        for m in registry["markets"]]}


def inputs(series_id, horizon):
    manifest, bundle = load_bundle(series_id, horizon)
    folder = registry_root() / manifest["version"]
    if digest(folder / "prices.csv") != manifest["prices_snapshot_sha256"]:
        raise DataUnavailable("Price snapshot integrity failed")
    prices = read_prices(folder / "prices.csv")
    event_path = folder / "events.json"
    if manifest["events_snapshot_sha256"] and digest(event_path) != manifest["events_snapshot_sha256"]:
        raise DataUnavailable("News snapshot integrity failed")
    events = read_events(event_path if manifest["events_snapshot_sha256"] else None)
    return manifest, bundle, prices, events


@router.get("/market/{series_id}")
def market(series_id: str):
    try:
        manifest, _, prices, events = inputs(series_id, 1)
        recent = prices.tail(90)
        changes = recent.modal_price.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
        news = [] if events is None else [dict(e, published_at=e["published_at"].isoformat(), available_at=e["available_at"].isoformat())
                                        for e in events["events"] if e["series_id"] == series_id
                                        and e["available_at"] <= pd.Timestamp.now(tz="UTC")]
        return {"status": manifest.get("release_status", "research_only"),
                "series_id": series_id, "market": manifest["market"], "district": manifest["district"],
                "state": manifest["state"], "commodity": manifest["commodity"],
                "variety": manifest["variety"], "grade": manifest["grade"],
                "unit": manifest["unit"], "source": manifest["source"],
                "latest_price": float(prices.modal_price.iloc[-1]),
                "latest_observation_date": str(prices.date.iloc[-1].date()),
                "availability_basis": manifest["availability_basis"],
                "availability_status": "uploader_declared_not_source_verified",
                "change": float(prices.modal_price.iloc[-1]-prices.modal_price.iloc[-2]) if len(prices)>1 else None,
                "volatility": float(changes.std(ddof=0)) if len(changes) else None,
                "as_of": str(prices.date.max().date()),
                "history": [{"date": str(r.date.date()), "price": r.modal_price} for r in recent.itertuples()],
                "news": sorted(news, key=lambda e: e["published_at"], reverse=True)[:20],
                "limitations": ["Availability basis is uploader-declared and has not been independently source-verified.",
                                "Weather and arrivals are not integrated", "News/event intelligence lacks source coverage and independent evaluation"]}
    except (ValueError, OSError, KeyError, SQLAlchemyError):
        raise HTTPException(503, "Validated market history is unavailable")


@router.get("/forecast/{series_id}")
def forecast(series_id: str, horizon: int = Query(1, ge=1, le=7)):
    if horizon not in (1, 3, 7):
        raise HTTPException(422, "Supported calendar-day horizons: 1, 3, 7")
    try:
        manifest, bundle, prices, events = inputs(series_id, horizon)
        fingerprint = predictor_fingerprint(bundle["spec"], bundle["model"])
        calibration = bundle.get("calibration", {})
        if (bundle.get("model_fingerprint") != fingerprint
                or calibration.get("predictor_fingerprint") != fingerprint
                or calibration.get("predictor_refit_after_calibration") is not False):
            raise DataUnavailable("Predictor and interval calibration fingerprints do not match")
        features = make_features(prices, events).tail(1).copy()
        origin = features.origin.iloc[0]
        if origin != prices.date.max():
            raise DataUnavailable("Latest observation lacks valid lag features")
        day = origin + pd.Timedelta(days=horizon-7)
        known = prices[prices.date == day]
        if known.empty or known.available_at.iloc[0] > cutoff(origin):
            raise DataUnavailable("Seasonal reference unavailable")
        features["seasonal"] = float(known.modal_price.iloc[0])
        if features[bundle["spec"]["features"]].isna().any().any():
            raise DataUnavailable("Selected model features unavailable at cutoff")
        value = float(predict(bundle["spec"], bundle["model"], features)[0])
        if not np.isfinite(value):
            raise DataUnavailable("Non-finite forecast")
        target = origin + pd.Timedelta(days=horizon)
        return {"status": "research_only", "series_id": series_id, "horizon": horizon, "horizon_definition": "calendar_days",
                "origin": str(origin.date()), "target_date": str(target.date()), "prediction": value,
                "lower": max(0, value-bundle["radius"]), "upper": value+bundle["radius"],
                "market": manifest["market"], "district": manifest["district"], "state": manifest["state"],
                "commodity": manifest["commodity"], "variety": manifest["variety"],
                "grade": manifest["grade"], "unit": manifest["unit"], "source": manifest["source"],
                "latest_observation_date": str(prices.date.max().date()),
                "latest_price_age_days": int((origin-prices.date.max()).days),
                "availability_basis": manifest["availability_basis"],
                "interval_status": "experimental_temporal_coverage_not_guaranteed",
                "calibration": calibration,
                "selected_model": bundle["spec"]["id"], "version": manifest["version"],
                "stale": target.date() < datetime.now(timezone.utc).date(),
                "explanation": explain(bundle, features)}
    except (ValueError, OSError, KeyError, SQLAlchemyError):
        raise HTTPException(503, "Forecast unavailable: evaluated model or as-of features are missing")
