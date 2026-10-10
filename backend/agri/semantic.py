"""Local headline search and an explicit, optional collaborator/embedding contract.

No guessed eleven-dimensional vector ordering or invented classifier confidence.
"""
from typing import Protocol
from datetime import datetime, timezone
import hashlib
import html
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import numpy as np
import pandas as pd


class EmbeddingProvider(Protocol):
    def encode(self, texts: list[str]) -> np.ndarray: ...


class StrategicFactorAdapter(Protocol):
    """Implement only after the collaborator supplies the vector schema."""
    def factors(self, article: dict) -> dict: ...


EVENT_RULES = {
    "weather_disruption": ("heavy rain", "extreme rainfall", "flood", "drought", "hailstorm", "unseasonal rain"),
    "crop_damage": ("crop damage", "crop loss", "onion damage", "crop destroyed"),
    "disease": ("crop disease", "fungal disease", "pest attack", "onion disease"),
    "harvest_supply": ("harvest", "kharif crop", "rabi crop", "sowing", "onion production"),
    "mandi_arrivals": ("mandi arrivals", "market arrivals", "onion arrivals", "arrivals increased"),
    "export_policy": ("onion export", "export ban", "export duty", "minimum export price", "mep on onion"),
    "storage_disruption": ("cold storage", "storage loss", "stored onion", "warehouse"),
    "transport_disruption": ("transport disruption", "road closure", "rail disruption", "logistics disruption"),
    "demand_shift": ("demand for onion", "onion demand", "consumer demand"),
}
SEVERITY_TERMS = {"severe": 1.0, "widespread": 0.9, "major": 0.8, "significant": 0.7,
                  "moderate": 0.5, "localized": 0.3, "minor": 0.2}

EVENT_TAXONOMY = {
    "export_duty_reduction": "Explicit reduction, withdrawal, or removal of export duty.",
    "export_duty_increase": "Explicit increase or imposition of export duty.",
    "export_restriction_removal": "Explicit lifting of an export ban, prohibition, or restriction.",
    "export_restriction_introduction": "New export ban, prohibition, or restriction.",
    "mep_introduction": "New minimum export price notification or imposition.",
    "mep_revision": "Explicit revision of an existing minimum export price.",
    "government_procurement": "Government procurement or buffer purchase.",
    "buffer_stock_release": "Government buffer-stock release or disposal.",
    "market_arrivals": "Reported change in mandi or market arrivals.",
    "market_price_report": "Reported observed wholesale or retail market prices; not a causal price-effect estimate.",
    "production_estimate": "Production, harvest, or sowing estimate.",
    "crop_damage": "Crop loss, damage, or disease.",
    "extreme_weather": "Extreme rainfall, flood, drought, or hail affecting agriculture.",
    "storage_logistics_disruption": "Storage, transport, or logistics disruption.",
    "supply_shortage": "Explicit commodity shortage or constrained supply.",
    "demand_event": "Explicit demand or consumption change.",
    "reported_export_volume": "Reported historical onion export volume; not itself a new policy action.",
}


def extract_event_intelligence(title, text, *, article_id):
    """Multi-label phrase rules with exact evidence spans; outputs stay experimental."""
    content = f"{title}\n{text}".strip()
    low = content.casefold()
    patterns = {
        "reported_export_volume": (r"\b\d[\d.,]*\s*(?:lakh|million|thousand)?\s*(?:tons?|tonnes?|metric tons?|mt)\b.{0,50}\bonions?\b.{0,35}\bexported\b",
                                    r"\bonions?\b.{0,35}\bexported\b.{0,50}\b\d[\d.,]*\s*(?:lakh|million|thousand)?\s*(?:tons?|tonnes?|metric tons?|mt)\b"),
        "export_duty_reduction": (r"(?:withdraw|remov|reduc|abolish)[a-z]*\s+(?:the\s+)?(?:\d+%\s+)?(?:export\s+)?duty", r"duty.{0,40}(?:withdrawn|removed|reduced)"),
        "export_duty_increase": (r"(?:impos|rais|increas)[a-z]*\s+(?:a\s+)?(?:\d+%\s+)?(?:export\s+)?duty", r"export duty.{0,40}(?:increased|raised)"),
        "export_restriction_removal": (r"(?:prohibition|ban|restriction).{0,35}(?:removed|lifted|withdrawn|ended)", r"(?:remov|lift|withdraw)[a-z]*.{0,35}(?:export )?(?:prohibition|ban|restriction)"),
        "export_restriction_introduction": (r"(?:impos|introduc|announc)[a-z]*.{0,35}(?:export )?(?:ban|prohibition|restriction)", r"prohibition on.{0,30}export"),
        "mep_introduction": (r"(?:notifi|impos|introduc)[a-z]*.{0,60}(?:minimum export price|\bmep\b)",),
        "mep_revision": (r"(?:revis|rais|reduc|chang)[a-z]*.{0,60}(?:minimum export price|\bmep\b)",),
        "government_procurement": (r"(?:government|buffer).{0,50}(?:procure|purchase)[a-z]*", r"procure[a-z]*.{0,50}buffer"),
        "buffer_stock_release": (r"buffer.{0,50}(?:release|disposed|disposal|sell)[a-z]*",),
        "market_arrivals": (r"(?:mandi|market) arrivals?", r"arrivals?.{0,25}(?:increased|declined|rose|fell)"),
        "market_price_report": (r"(?:mandi|market|modal|retail) prices?",),
        "production_estimate": (r"(?:production|harvest|sowing).{0,50}(?:estimate|forecast|expected|lakh|million)", r"onion production"),
        "crop_damage": (r"(?:crop|onion).{0,35}(?:damage|loss|destroyed|disease)",),
        "extreme_weather": (r"(?:extreme|heavy|excess|unseasonal).{0,25}(?:rain|rainfall)", r"\b(?:flood|drought|hailstorm)\b"),
        "storage_logistics_disruption": (r"(?:storage|transport|logistics|road).{0,40}(?:disrupt|damage|shortage|closure)",),
        "supply_shortage": (r"(?:shortage|shortfall|scarcity) of (?:onions?|the crop)", r"(?:supply|availability) of onions? (?:is|was|has been) (?:low|short|limited)"),
        "demand_event": (r"(?:demand|consumption) for onions?",),
    }
    events = []
    for category, alternatives in patterns.items():
        evidence = []
        for pattern in alternatives:
            for match in re.finditer(pattern, content, re.I):
                # Sentence boundaries require punctuation followed by
                # whitespace and an uppercase sentence start. This keeps
                # decimal dates (01.01.2021) inside their evidence passage.
                left_boundaries = [m.end() for m in re.finditer(r"[.!?]\s+(?=[A-Z])|\n", content[:match.start()])]
                left = max(left_boundaries, default=0)
                right_match = re.search(r"[.!?](?=\s+[A-Z])|\n", content[match.end():])
                right = match.end() + right_match.end() if right_match else len(content)
                passage = content[left:right].strip()
                if passage and not any(x["text"] == passage for x in evidence):
                    evidence.append({"text": passage, "start": left, "end": right,
                                     "source_article_id": article_id, "supports": category})
        # Do not interpret a quoted historical ban as a new ban.
        if category == "export_restriction_removal" and re.search(r"\bexported\b", title, re.I) and not re.search(r"\b(?:removed|lifted|withdrawn)\b", title, re.I):
            evidence = []
        if category == "export_restriction_introduction" and re.search(r"(?:removed|lifted|withdrawn).{0,60}(?:ban|prohibition)|(?:ban|prohibition).{0,60}(?:removed|lifted|withdrawn)", low):
            evidence = []
        if evidence:
            events.append({"category": category, "definition": EVENT_TAXONOMY[category],
                           "status": "experimental_rule_supported", "evidence": evidence})
    commodity = "onion_direct" if re.search(r"\bonions?\b", low) else ("other_agricultural" if re.search(r"\b(?:crop|harvest|mandi|farmers?)\b", low) else "unrelated")
    geography = "nashik_specific" if "nashik" in low else ("maharashtra_specific" if "maharashtra" in low else ("india_wide" if any(s in low for s in ("government of india", "central government", "all india", "all over the country")) else "unknown"))
    mechanisms = sorted({"export_incentives" for e in events if e["category"].startswith(("export_", "mep_"))} |
                       {"domestic_supply" for e in events if e["category"] in {"government_procurement", "buffer_stock_release", "supply_shortage"}})
    month = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    date_pattern = rf"\b(?:\d{{1,2}}(?:st|nd|rd|th)?\s+{month}|{month}\s+\d{{1,2}}(?:st|nd|rd|th)?),?\s+\d{{4}}\b"
    dates = []
    for m in re.finditer(date_pattern, content, re.I):
        context = content[max(0,m.start()-40):m.end()+30].casefold()
        preceding = content[max(0,m.start()-24):m.start()].casefold()
        role = ("effective_end_date" if any(k in preceding for k in ("till", "until", "through")) else
                "effective_date" if any(k in context for k in ("effective from", "with effect from", "effective on")) else
                "mentioned_date")
        value = None
        normalized = re.sub(r"(\d)(st|nd|rd|th)", r"\1", m.group(), flags=re.I).replace(",", "")
        for fmt in ("%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y"):
            try:
                value = datetime.strptime(normalized, fmt).date().isoformat()
                break
            except ValueError:
                continue
        dates.append({"text": m.group(), "normalized_date": value, "start": m.start(), "end": m.end(), "role": role})
    policy = any(e["category"].startswith(("export_", "mep_")) for e in events)
    return {"events": events, "classification_status": "experimental_rule_supported" if events else "insufficient_evidence",
            "commodity_relevance": commodity, "geographic_relevance": geography,
            "market_mechanisms": mechanisms, "series_id": "unassigned",
            "date_mentions": dates,
            "price_impact_hypothesis": "Possible export incentive and domestic availability effects; net mandi-price direction is uncertain." if policy else None,
            "price_impact_validation": "none", "method": "explainable_multilabel_rules_v1"}


def canonical_article_url(value):
    """Remove fragments and common tracking parameters without merging hostnames."""
    parts = urlsplit(str(value).strip())
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("Article URL must be an absolute HTTP(S) URL")
    query = [(key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True)
             if not key.casefold().startswith("utm_") and key.casefold() not in {"fbclid", "gclid"}]
    return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold(), parts.path or "/",
                       urlencode(query), ""))


def classify_onion_event(article, *, series_id, retrieved_at=None):
    """Extract an auditable, explicitly unvalidated keyword-rule signal.

    retrieved_at is the genuine local capture time. It never substitutes for
    publication time and therefore cannot backfill historical availability.
    """
    title = html.unescape(str(article.get("title", ""))).strip()
    text = html.unescape(str(article.get("summary", article.get("description", "")))).strip()
    if not title or not article.get("url") or not series_id:
        raise ValueError("Article title, source URL and exact series ID are required")
    url = canonical_article_url(article["url"])
    captured = retrieved_at or datetime.now(timezone.utc)
    if captured.tzinfo is None:
        raise ValueError("retrieved_at must be timezone-aware")
    captured = captured.astimezone(timezone.utc)
    published = article.get("published_at")
    if published:
        published = pd.Timestamp(published)
        if published.tzinfo is None:
            raise ValueError("Source publication timestamp must include a timezone")
        published = published.tz_convert("UTC")
        if published.to_pydatetime() > captured:
            raise ValueError("Source publication time cannot follow actual retrieval time")
    normalized = f"{title} {text}".casefold()
    terms = re.findall(r"[a-z0-9]+", normalized)
    lower = " ".join(terms)
    matches = {category: [phrase for phrase in phrases if phrase in lower]
               for category, phrases in EVENT_RULES.items()}
    matches = {category: phrases for category, phrases in matches.items() if phrases}
    category = max(matches, key=lambda key: len(matches[key])) if matches else "unclassified"
    geo_terms = [term for term in ("nashik", "maharashtra") if term in terms]
    onion_terms = [term for term in ("onion", "onions") if term in terms]
    severity = max((score for term, score in SEVERITY_TERMS.items() if term in terms), default=None)
    upward = {"weather_disruption", "crop_damage", "disease", "transport_disruption"}
    downward = {"harvest_supply", "mandi_arrivals"}
    if category in upward:
        direction = "possible upward price pressure if supply is disrupted"
        signal = 1.0
    elif category in downward:
        direction = "possible downward price pressure if supply increases"
        signal = -1.0
    elif category == "export_policy":
        direction = "direction depends on the specific policy; no directional signal assigned"
        signal = 0.0
    elif category == "demand_shift":
        direction = "possible upward price pressure if demand increases"
        signal = 1.0
    else:
        direction = None
        signal = 0.0
    normalized_title = " ".join(re.findall(r"\w+", title.casefold()))
    pub_day = published.date().isoformat() if published is not None else "publication-unknown"
    dedupe_key = hashlib.sha256(f"{normalized_title}|{pub_day}".encode()).hexdigest()
    relevance = "relevant" if geo_terms and onion_terms else "review_required"
    return {
        "id": hashlib.sha256(f"{url}|{dedupe_key}".encode()).hexdigest(),
        "series_id": series_id, "title": title, "url": url,
        "published_at": published.isoformat() if published is not None else None,
        "available_at": captured.isoformat(), "availability_basis": "first_local_capture",
        "category": category, "event_severity_heuristic": severity,
        "geographic_relevance": "matched:" + ",".join(geo_terms) if geo_terms else "unverified",
        "commodity_relevance": "matched:onion" if onion_terms else "unverified",
        "relevance_status": relevance,
        "extracted_evidence": sorted({phrase for values in matches.values() for phrase in values}),
        "direction_hypothesis": direction, "supply_pressure": signal,
        "source_confidence": "not_assessed",
        "classification_method": "transparent_keyword_rules_v1",
        "classification_status": "unvalidated_research_signal",
        "deduplication_key": dedupe_key,
    }


def retrieve(archive, query, series_id, as_of, encoder: EmbeddingProvider | None = None, limit=10):
    end = pd.Timestamp(as_of)
    if end.tzinfo is None:
        raise ValueError("Retrieval cutoff must include timezone")
    keywords = set(re.findall(r"\w+", query.lower()))
    eligible = {event["url"]: event for event in archive["events"]
                if event["series_id"] == series_id and event["published_at"] <= end
                and event["available_at"] <= end and event["published_at"] > end-pd.Timedelta(days=30)}
    events = list(eligible.values())
    if not events:
        return []
    scores = np.asarray([len(keywords & set(re.findall(r"\w+", e["title"].lower()))) / max(1, len(keywords)) for e in events])
    if encoder:
        vectors = np.asarray(encoder.encode([query]+[e["title"] for e in events]), dtype=float)
        if vectors.ndim != 2 or len(vectors) != len(events)+1 or not np.isfinite(vectors).all():
            raise ValueError("Invalid embedding provider output")
        vectors /= np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12)
        scores = .5*scores + .5*np.maximum(0, vectors[1:] @ vectors[0])
    order = sorted(range(len(events)), key=lambda i: (scores[i], events[i]["published_at"]), reverse=True)
    return [dict(events[i], relevance=float(scores[i]), retrieval="hybrid" if encoder else "keyword_only")
            for i in order[:limit] if scores[i] > 0]
