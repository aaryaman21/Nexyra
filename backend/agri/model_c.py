"""Temporal-safe, context-only Model C contract (no news-to-price arithmetic)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

PROTOCOL_ID = "model-c-context-only-v1"


def _instant(value: str | datetime) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Model C timestamps require an explicit timezone")
    return parsed.astimezone(timezone.utc)


def build_combined_context(*, series_identity: dict[str, Any], forecast: dict[str, Any] | None,
                           forecast_origin_at: str | datetime, reviews: list[dict[str, Any]],
                           protocol_id: str = PROTOCOL_ID) -> dict[str, Any]:
    """Pair an existing forecast with reviewed, exact-identity evidence available by its origin.

    This function intentionally emits no adjusted price or impact coefficient. It
    fails closed when source identity or review lineage cannot be established.
    """
    context, excluded = [], {"after_forecast_origin": 0, "not_relevant": 0,
                             "commodity_unverified": 0, "geography_unverified": 0,
                             "identity_or_revision_unverified": 0, "no_supported_events": 0}
    if not forecast:
        return {"status": "forecast_unavailable", "protocol_id": protocol_id,
                "forecast": None, "forecast_origin_at": None, "events": [],
                "numerical_adjustment": None, "predictive_status": "not_validated",
                "limitations": ["Model A forecast is unavailable; no combined output is emitted."]}
    origin = _instant(forecast_origin_at)
    series_market = str(series_identity.get("market", "")).casefold()
    series_district = str(series_identity.get("district", "")).casefold()
    for review in reviews:
        try:
            first_seen = _instant(review["first_seen_at"])
        except (KeyError, ValueError, TypeError):
            excluded["identity_or_revision_unverified"] += 1
            continue
        if first_seen > origin:
            excluded["after_forecast_origin"] += 1
            continue
        payload = review.get("review") or {}
        if (review.get("status") != "reviewed" or not review.get("source_checksum_matches")
                or not review.get("identity_matches")):
            excluded["identity_or_revision_unverified"] += 1
            continue
        if payload.get("relevance") != "relevant":
            excluded["not_relevant"] += 1
            continue
        commodity = payload.get("commodity_relevance")
        if commodity not in {"onion_direct", "onion_related"}:
            excluded["commodity_unverified"] += 1
            continue
        geography = str(payload.get("geographic_relevance") or "").casefold()
        geography_is_exact = (
            geography in {"nashik", "nashik_district", "nashik_region", "maharashtra"}
            and ("nashik" in series_district or "maharashtra" in series_identity.get("state", "").casefold()
                 or "nashik" in series_market)
        )
        if not geography_is_exact:
            excluded["geography_unverified"] += 1
            continue
        events = [event for event in payload.get("events", [])
                  if event.get("category") and event.get("evidence")]
        if not events:
            excluded["no_supported_events"] += 1
            continue
        context.append({"article_identity": review["article_identity"],
            "source_url": review.get("source_url"), "title": review.get("title"),
            "published_date": review.get("published_date"),
            "publication_precision": review.get("publication_precision"),
            "first_seen_at": first_seen.isoformat(), "events": events,
            "evidence_status": "human_reviewed_exact_source_spans"})
    return {"status": "experimental_context_only", "protocol_id": protocol_id,
            "series_identity": series_identity, "forecast_origin_at": origin.isoformat(),
            "forecast": forecast, "events": context, "excluded_review_count_by_reason": excluded,
            "numerical_adjustment": None, "measured_price_impact": None,
            "predictive_status": "not_validated",
            "limitations": ["News context does not alter Model A's numeric forecast.",
                "Only human-reviewed, checksum-matched, exact-series relevant evidence available by the forecast origin is shown.",
                "No combined-model accuracy or causal price effect has been measured."]}
