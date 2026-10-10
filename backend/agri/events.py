"""Append-only, source-attributed RSS capture and transparent event signals.

The included PIB adapter imports a locally saved official RSS XML file. It does
not fetch URLs, run on a schedule, or infer historical retrieval timestamps.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import argparse
import hashlib
from html.parser import HTMLParser
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
import sys
import uuid
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, urlsplit

from sqlalchemy import Column, Date, Integer, MetaData, String, Table, Text, UniqueConstraint, create_engine, or_, select, update

from .data import DataUnavailable
from .semantic import classify_onion_event, extract_event_intelligence

PIB_RSS_URL = "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=1"
PIB_ARTICLE_URL = "https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2114060&reg=48&lang=1"
PIB_PRID = "2114060"
metadata = MetaData()
capture_runs = Table(
    "agri_event_capture_runs", metadata,
    Column("run_id", String(36), primary_key=True),
    Column("source_url", Text, nullable=False),
    Column("retrieval_method", String(64), nullable=False),
    Column("retrieved_at_utc", String(40), nullable=False),
    Column("raw_sha256", String(64), nullable=False),
    Column("raw_payload", Text, nullable=False),
    Column("status", String(32), nullable=False),
    Column("item_count", Integer, nullable=False),
    Column("validation_errors_json", Text, nullable=False),
)
captures = Table(
    "agri_event_captures", metadata,
    Column("capture_id", String(36), primary_key=True),
    Column("run_id", String(36), nullable=False),
    Column("article_key", String(64), nullable=False),
    Column("deduplication_key", String(64), nullable=False),
    Column("first_seen_at_utc", String(40), nullable=False),
    Column("retrieved_at_utc", String(40), nullable=False),
    Column("source_url", Text, nullable=False),
    Column("article_url", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("summary_text", Text, nullable=False),
    Column("source_publication_at_utc", String(40), nullable=True),
    Column("publication_status", String(40), nullable=False),
    Column("raw_item_json", Text, nullable=False),
    Column("classification_json", Text, nullable=False),
    Column("raw_sha256", String(64), nullable=False),
)
representations = Table(
    "agri_event_source_representations", metadata,
    Column("representation_id", String(36), primary_key=True),
    Column("capture_id", String(36), nullable=False),
    Column("representation_type", String(32), nullable=False),
    Column("source_url", Text, nullable=False),
    Column("source_name", Text, nullable=False),
    Column("imported_at_utc", String(40), nullable=False),
    Column("raw_sha256", String(64), nullable=False),
    Column("content_sha256", String(64), nullable=False),
    Column("article_text", Text, nullable=False),
    Column("content_status", String(40), nullable=False),
    Column("extraction_method", String(80), nullable=False),
    Column("classification_json", Text, nullable=False),
    Column("metadata_json", Text, nullable=False),
)
text_normalizations = Table(
    "agri_event_text_normalizations", metadata,
    Column("normalization_id", String(36), primary_key=True),
    Column("capture_id", String(36), nullable=False),
    Column("representation_id", String(36), nullable=True),
    Column("source_content_sha256", String(64), nullable=False),
    Column("normalization_version", String(40), nullable=False),
    Column("normalized_text", Text, nullable=False),
    Column("normalized_sha256", String(64), nullable=False),
    Column("transformations_json", Text, nullable=False),
    Column("status", String(32), nullable=False),
    Column("created_at_utc", String(40), nullable=False),
    UniqueConstraint("capture_id", "representation_id", "source_content_sha256",
                     "normalization_version", "normalized_sha256",
                     name="uq_agri_event_text_normalization_revision"),
)
human_event_reviews = Table(
    "agri_event_human_reviews", metadata,
    Column("review_id", String(36), primary_key=True),
    Column("article_key", String(128), nullable=False),
    Column("capture_id", String(36), nullable=False),
    Column("source_content_sha256", String(64), nullable=False),
    Column("reviewer_id", String(120), nullable=False),
    Column("reviewed_at_utc", String(40), nullable=False),
    Column("status", String(24), nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("supersedes_review_id", String(36), nullable=True),
)


def migrate(engine):
    """Create only the new event-capture tables; existing tables are untouched."""
    metadata.create_all(engine)


def _local_name(tag):
    return tag.rsplit("}", 1)[-1].casefold()


def _child(item, name):
    return next((node.text or "" for node in item if _local_name(node.tag) == name), "").strip()


def _publication(value):
    if not value:
        return None, "missing"
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None, "invalid"
    if parsed.tzinfo is None:
        return None, "timezone_missing"
    return parsed.astimezone(timezone.utc).isoformat(), "source_timestamp"


def import_pib_rss_file(engine, path, *, source_url=PIB_RSS_URL, retrieved_at=None):
    """Capture a saved PIB RSS XML response with the actual local import time.

    The local import time is not represented as the feed download time. Use
    only primary PIB material; linked third-party content is not fetched.
    """
    path = Path(path)
    raw = path.read_bytes()
    return import_pib_rss_bytes(engine, raw, source_url=source_url, retrieved_at=retrieved_at,
                                retrieval_method=f"manual_rss_xml_import:{path.name}")


def import_pib_rss_bytes(engine, raw, *, source_url=PIB_RSS_URL, retrieved_at=None,
                         retrieval_method="official_rss_http_get"):
    """Persist response bytes with genuine local capture time and raw checksum."""
    if not raw or len(raw) > 5_000_000:
        raise DataUnavailable("RSS file must contain 1 byte to 5 MB")
    captured = retrieved_at or datetime.now(timezone.utc)
    if captured.tzinfo is None:
        raise DataUnavailable("RSS import time must be timezone-aware")
    captured = captured.astimezone(timezone.utc)
    if source_url != PIB_RSS_URL:
        raise DataUnavailable("RSS source must match the documented official PIB press-release feed")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        raise DataUnavailable("RSS file is not well-formed XML") from None
    items = [node for node in root.iter() if _local_name(node.tag) == "item"]
    if not items:
        raise DataUnavailable("RSS file contains no article items")
    parsed_items = []
    errors = []
    for index, item in enumerate(items, 1):
        title, url = _child(item, "title"), _child(item, "link")
        summary = _child(item, "description")
        published_at, publication_status = _publication(_child(item, "pubdate"))
        if not title or not url:
            errors.append({"item": index, "error": "missing article title or URL"})
            continue
        hostname = (urlsplit(url).hostname or "").casefold()
        if hostname != "pib.gov.in" and not hostname.endswith(".pib.gov.in"):
            errors.append({"item": index, "error": "non-PIB article link excluded; third-party content is not fetched"})
            continue
        try:
            signal = classify_onion_event({"title": title, "summary": summary,
                                           "url": url, "published_at": published_at},
                                          series_id="unassigned", retrieved_at=captured)
        except (ValueError, TypeError) as exc:
            errors.append({"item": index, "error": str(exc)[:160]})
            continue
        parsed_items.append({"title": title, "url": signal["url"], "summary": summary,
                             "published_at": published_at, "publication_status": publication_status,
                             "signal": signal,
                             "raw_item": {"title": title, "link": url, "description": summary,
                                          "pubDate": _child(item, "pubdate")}})
    if not parsed_items and errors:
        raise DataUnavailable("RSS file has no valid article items")
    migrate(engine)
    raw_hash = hashlib.sha256(raw).hexdigest()
    run_id = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(capture_runs.insert().values(
            run_id=run_id, source_url=source_url, retrieval_method=retrieval_method,
            retrieved_at_utc=captured.isoformat(), raw_sha256=raw_hash, raw_payload=raw.decode("utf-8", errors="replace"),
            status="partial" if errors else "success", item_count=len(items),
            validation_errors_json=json.dumps(errors, ensure_ascii=False, sort_keys=True)))
        for item in parsed_items:
            prior = conn.execute(select(captures.c.first_seen_at_utc)
                                 .where(captures.c.deduplication_key == item["signal"]["deduplication_key"])
                                 .order_by(captures.c.first_seen_at_utc).limit(1)).first()
            first_seen = prior[0] if prior else captured.isoformat()
            conn.execute(captures.insert().values(
                capture_id=str(uuid.uuid4()), run_id=run_id,
                article_key=item["signal"]["id"], deduplication_key=item["signal"]["deduplication_key"],
                first_seen_at_utc=first_seen, retrieved_at_utc=captured.isoformat(), source_url=source_url,
                article_url=item["url"], title=item["title"], summary_text=item["summary"],
                source_publication_at_utc=item["published_at"], publication_status=item["publication_status"],
                raw_item_json=json.dumps(item["raw_item"], ensure_ascii=False, sort_keys=True),
                classification_json=json.dumps(item["signal"], ensure_ascii=False, sort_keys=True),
                raw_sha256=raw_hash))
    return {"run_id": run_id, "status": "partial" if errors else "success",
            "items_seen": len(items), "items_captured": len(parsed_items), "validation_errors": errors,
            "retrieved_at_utc": captured.isoformat(), "raw_sha256": raw_hash,
            "note": "Local import time is first local capture, not original feed download time."}


def fetch_pib_rss(engine, *, timeout_seconds=10, retries=2, opener=None):
    """Fetch the fixed PIB RSS endpoint once with bounded retries and response size."""
    if not 1 <= timeout_seconds <= 30 or not 0 <= retries <= 3:
        raise ValueError("timeout_seconds must be 1..30 and retries must be 0..3")
    request = urllib.request.Request(PIB_RSS_URL, headers={
        "User-Agent": "Nexyra-Research-EventCollector/1.0",
        "Accept": "application/rss+xml, application/xml, text/xml;q=0.9",
    })
    open_url = opener or urllib.request.urlopen
    last_error = None
    for attempt in range(retries + 1):
        try:
            with open_url(request, timeout=timeout_seconds) as response:
                status = getattr(response, "status", 200)
                if status != 200:
                    raise DataUnavailable(f"PIB RSS returned HTTP {status}")
                raw = response.read(5_000_001)
                if len(raw) > 5_000_000:
                    raise DataUnavailable("PIB RSS response exceeds 5 MB limit")
            return import_pib_rss_bytes(engine, raw, retrieved_at=datetime.now(timezone.utc))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(min(0.25 * (2 ** attempt), 1.0))
    raise DataUnavailable(f"PIB RSS request failed after {retries + 1} bounded attempt(s): {type(last_error).__name__}")


def recent_captures(engine, *, limit=50):
    """Read persisted captures without creating tables on an API request."""
    if not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    from sqlalchemy import inspect
    inspector = inspect(engine)
    if not inspector.has_table(captures.name) or not inspector.has_table(capture_runs.name):
        return {"status": "unavailable", "events": [], "reason": "No official source capture has been stored"}
    with engine.connect() as conn:
        rows = conn.execute(select(captures).order_by(captures.c.retrieved_at_utc.desc())).mappings().all()
        rep_rows = (conn.execute(select(representations).order_by(representations.c.imported_at_utc.desc())).mappings().all()
                    if inspector.has_table(representations.name) else [])
        normalized_rows = (conn.execute(select(text_normalizations).order_by(text_normalizations.c.created_at_utc.desc())).mappings().all()
                           if inspector.has_table(text_normalizations.name) else [])
    reps_by_capture = {}
    for rep in rep_rows:
        reps_by_capture.setdefault(rep["capture_id"], []).append(rep)
    norm_by_source = {}
    for normalized in normalized_rows:
        norm_by_source.setdefault((normalized["capture_id"], normalized["representation_id"]), []).append(normalized)
    by_article = {}
    for row in rows:
        raw_metadata = json.loads(row["raw_item_json"])
        candidates = reps_by_capture.get(row["capture_id"], [])
        representation = max(candidates, key=lambda rep: (3 if rep["content_status"] in {"full_text_extracted", "full_body_verified"} else 2,
                                                           rep["imported_at_utc"])) if candidates else None
        signal = json.loads(representation["classification_json"]) if representation else json.loads(row["classification_json"])
        source_text = representation["article_text"] if representation else raw_metadata.get("article_text")
        source_content_hash = representation["content_sha256"] if representation else raw_metadata.get("content_sha256")
        normalization = next((item for item in norm_by_source.get((row["capture_id"], representation["representation_id"] if representation else None), [])
                              if item["source_content_sha256"] == source_content_hash), None)
        page_url = str(raw_metadata.get("source_page_url_as_saved") or "").strip()
        if page_url.casefold().startswith(("www.pib.gov.in/", "pib.gov.in/")):
            page_url = "https://" + page_url
        page_parsed = urlsplit(page_url)
        page_prids = parse_qs(page_parsed.query).get("PRID", []) + parse_qs(page_parsed.query).get("relid", [])
        verified_page_url = (page_url if page_parsed.scheme == "https" and page_parsed.hostname in {"pib.gov.in", "www.pib.gov.in"}
                             and raw_metadata.get("prid") in page_prids else row["article_url"])
        if not raw_metadata.get("prid") and raw_metadata.get("source_url_status") == "official_host_domain_checked":
            parsed_saved = urlsplit(str(raw_metadata.get("source_url") or ""))
            if parsed_saved.scheme == "https" and parsed_saved.hostname == (urlsplit(row["article_url"]).hostname):
                verified_page_url = str(raw_metadata["source_url"])
        article_identity = raw_metadata.get("article_identity") or (f"pib:{raw_metadata.get('prid')}" if raw_metadata.get("prid") else row["article_url"])
        event = {"id": row["capture_id"], "title": row["title"], "url": verified_page_url,
                       "source": raw_metadata.get("source_organization", "Press Information Bureau, Government of India"), "source_url": row["source_url"],
                       "published_at": row["source_publication_at_utc"], "publication_status": row["publication_status"],
                       "published_date": raw_metadata.get("published_date", raw_metadata.get("publication_date")),
                       "publication_precision": raw_metadata.get("publication_precision", "timestamp" if row["source_publication_at_utc"] else "unknown"),
                       "retrieved_at": row["retrieved_at_utc"], "first_seen_at": row["first_seen_at_utc"],
                       "available_at": row["first_seen_at_utc"], "availability_basis": "first_local_capture",
                       "category": signal.get("category") or (signal.get("events") or [{}])[0].get("category", "unclassified"),
                       "series_id": signal.get("series_id", "unassigned"),
                       "severity": signal.get("event_severity_heuristic"),
                       "event_classifications": signal.get("events", []),
                       "reported_facts": signal.get("reported_facts", []),
                       "date_mentions": signal.get("date_mentions", []),
                       "classification_method": signal.get("method", signal.get("classification_method")),
                       "classification_status": signal.get("classification_status", "unvalidated_research_signal"),
                       "geographic_relevance": signal.get("geographic_relevance_legacy", signal.get("geographic_relevance", "unknown")),
                       "commodity_relevance": signal.get("commodity_relevance_legacy", signal.get("commodity_relevance", "unknown")),
                       "relevance_status": signal.get("relevance_status", signal.get("classification_status", "review_required")),
                       "evidence": signal.get("extracted_evidence", [ev for item in signal.get("events", []) for ev in item.get("evidence", [])]),
                       "impact_hypothesis": signal.get("direction_hypothesis", signal.get("price_impact_hypothesis")),
                       "raw_sha256": row["raw_sha256"],
                       "article_text": normalization["normalized_text"] if normalization else source_text,
                       "original_article_text": source_text if normalization else None,
                       "text_representation_id": representation["representation_id"] if representation else None,
                       "normalization_id": normalization["normalization_id"] if normalization else None,
                       "normalization_status": normalization["status"] if normalization else None,
                       "normalization_changes": json.loads(normalization["transformations_json"]) if normalization else [],
                       "normalized_content_sha256": normalization["normalized_sha256"] if normalization else None,
                       "content_status": representation["content_status"] if representation else raw_metadata.get("content_status"),
                       "text_representation": representation["representation_type"] if representation else "html_capture",
                       "text_imported_at": representation["imported_at_utc"] if representation else None,
                       "text_raw_sha256": representation["raw_sha256"] if representation else row["raw_sha256"],
                       "text_content_sha256": representation["content_sha256"] if representation else raw_metadata.get("content_sha256"),
                       "article_identity": article_identity,
                       "issuing_ministry": raw_metadata.get("issuing_ministry"),
                       "published_time_source_text": raw_metadata.get("published_time_source_text"),
                       "title_status": raw_metadata.get("title_status", "source_capture"),
                       "publication_metadata_status": raw_metadata.get("publication_metadata_status"),
                       "source_url_status": raw_metadata.get("source_url_status"),
                       "metadata_verification": raw_metadata.get("metadata_verification"),
                       "prid": raw_metadata.get("prid"),
                       "source_page_url_as_saved": verified_page_url,
                       "source_relevance": raw_metadata.get("source_relevance", signal.get("source_relevance", "official_primary_source"))}
        prid = raw_metadata.get("prid")
        key = article_identity
        rank = 3 if event["content_status"] in {"full_text_extracted", "full_body_verified"} else 2 if event["content_status"] else 1
        prior = by_article.get(key)
        if prior is None or rank > prior[0] or (rank == prior[0] and event["retrieved_at"] > prior[1]["retrieved_at"]):
            by_article[key] = (rank, event)
    all_events = sorted((value[1] for value in by_article.values()), key=lambda item: item["retrieved_at"], reverse=True)
    events = all_events[:limit]
    review_count = 0
    if inspector.has_table(human_event_reviews.name):
        latest_by_article = {}
        with engine.connect() as conn:
            review_rows = conn.execute(select(human_event_reviews).order_by(
                human_event_reviews.c.reviewed_at_utc.desc())).mappings().all()
        for review in review_rows:
            latest_by_article.setdefault(review["article_key"], review)
        review_count = sum(row["status"] == "reviewed" for row in latest_by_article.values())
    full_body_count = sum(item.get("content_status") in {"full_text_extracted", "full_body_verified"} for item in all_events)
    return {"status": "ready" if events else "empty", "events": events,
            "classification_method": "transparent_keyword_rules_v1", "predictive_status": "not_validated",
            "dataset_health": {"unique_articles": len(all_events), "full_body_articles": full_body_count,
                               "source_diversity": len({item.get("source") for item in all_events if item.get("source")}),
                               "human_reviewed_articles": review_count,
                               "evaluation_status": "insufficient_labels" if review_count == 0 else "exploratory",
                               "accuracy_metrics_available": False if review_count == 0 else None}}


def _pib_2024_2025_signal(prid, title, body):
    """Keep the two additional full-text classifications tied to exact sentences."""
    import re
    signal = extract_event_intelligence(title, body, article_id=prid)
    content = f"{title}\n{body}".strip()

    def evidence(fragment, category):
        match = re.search(fragment, content, re.I)
        if not match:
            raise DataUnavailable(f"PRID {prid} source text no longer contains required evidence for {category}")
        left_boundaries = [item.end() for item in re.finditer(r"[.!?]\s+(?=[A-Z])|\n", content[:match.start()])]
        left = max(left_boundaries, default=0)
        right_match = re.search(r"[.!?](?=\s+[A-Z])|\n", content[match.end():])
        right = match.end() + right_match.end() if right_match else len(content)
        return {"text": content[left:right].strip(), "start": left, "end": right,
                "source_article_id": prid, "supports": category}

    def event(category, definition, *passages):
        return {"category": category, "definition": definition,
                "status": "experimental_rule_supported",
                "evidence": [evidence(fragment, category) for fragment in passages]}

    def exact_evidence(pattern, category):
        match = re.search(pattern, content, re.I)
        if not match:
            raise DataUnavailable(f"PRID {prid} source text no longer contains required evidence for {category}")
        return {"text": match.group().strip(), "start": match.start(), "end": match.end(),
                "source_article_id": prid, "supports": category}

    if prid == "2042765":
        export_evidence = evidence(r"2\.60 lakh tons of onion had been exported", "reported_export_volume")
        procurement_evidence = evidence(r"Government had procured 4\.68 lakh tons", "government_procurement")
        mandi_price_evidence = evidence(r"average monthly mandi modal prices of onion in Maharashtra between April and July, 2024", "market_price_report")
        procurement_price_evidence = evidence(r"average procurement price of onion for the buffer in current year was Rs\.2,833 per quintal", "buffer_procurement_price")
        signal["events"] = [
            event("reported_export_volume", "Reported historical onion export volume; not itself a new policy action.",
                  r"2\.60 lakh tons of onion had been exported"),
            event("government_procurement", "Reported government procurement for the price stabilisation buffer.",
                  r"Government had procured 4\.68 lakh tons"),
            event("market_price_report", "Reported historical wholesale market prices; not a causal price-effect estimate.",
                  r"average monthly mandi modal prices of onion in Maharashtra between April and July, 2024"),
        ]
        signal["reported_facts"] = [
            {"kind": "onion_export_volume", "value": "2.60 lakh tons",
             "period": "FY 2024-25 through 31 July 2024", "evidence": export_evidence},
            {"kind": "buffer_procurement", "value": "4.68 lakh tons",
             "period": "current year; article does not state a more precise period in this passage",
             "evidence": procurement_evidence},
            {"kind": "maharashtra_mandi_modal_price_range", "value": "Rs.1,230–2,578 per quintal vs Rs.693–1,205 per quintal",
             "period": "April–July 2024 vs corresponding period in 2023", "evidence": mandi_price_evidence},
            {"kind": "buffer_procurement_price", "value": "Rs.2,833 per quintal vs Rs.1,724 per quintal (64% higher)",
             "period": "current year vs last year; source passage does not name the years", "evidence": procurement_price_evidence},
        ]
        signal["classification_status"] = "experimental_rule_supported"
        signal["price_impact_hypothesis"] = "The release reports historical exports, procurement, and mandi prices; causal price effects are not established."
    else:
        duty_evidence = evidence(r"has withdrawn 20% duty on onion export, effective from 1st April, 2025", "export_duty_reduction")
        export_evidence = evidence(r"total onion export during FY 2023-24 was 17\.17 LMT", "reported_export_volume")
        arrivals_evidence = evidence(r"Onion arrival in benchmark markets Lasalgoan and Pimpalgaon have increased", "market_arrivals")
        production_evidence = evidence(r"rabi production this year at 227 lakh metric tonnes", "production_estimate")
        national_price_evidence = evidence(r"a decline of 39% is observed in the all-India weighted average modal prices", "market_price_report")
        benchmark_price_pattern = r"The modal prices in Lasalgaon and Pimpalgoan on 21st March, 2025 were Rs\.1330/qtl and Rs\.1325/qtl, respectively\."
        benchmark_price_evidence = exact_evidence(benchmark_price_pattern, "market_price_report")
        price_event = event("market_price_report", "Reported observed wholesale and retail prices; not a causal price-effect estimate.",
                            r"a decline of 39% is observed in the all-India weighted average modal prices")
        price_event["evidence"].append(benchmark_price_evidence)
        signal["events"] = [
            event("export_duty_reduction", "Explicit withdrawal of export duty; article states its implementation date.",
                  r"has withdrawn 20% duty on onion export, effective from 1st April, 2025"),
            event("reported_export_volume", "Reported historical onion export volume; not itself a new policy action.",
                  r"total onion export during FY 2023-24 was 17\.17 LMT"),
            event("market_arrivals", "Reported change in benchmark-market onion arrivals.",
                  r"Onion arrival in benchmark markets Lasalgoan and Pimpalgaon have increased"),
            event("production_estimate", "Officially attributed rabi onion production estimate.",
                  r"rabi production this year at 227 lakh metric tonnes"),
            price_event,
        ]
        signal["reported_facts"] = [
            {"kind": "export_duty", "value": "20% withdrawn", "period": "effective 1 April 2025",
             "announcement_date": "2025-03-22", "evidence": duty_evidence},
            {"kind": "onion_export_volume", "value": "17.17 LMT", "period": "FY 2023-24",
             "evidence": export_evidence},
            {"kind": "onion_export_volume", "value": "11.65 LMT", "period": "FY 2024-25 through 18 March (year not repeated in passage)",
             "evidence": evidence(r"FY 2024-25 \(till 18th March\) was 11\.65 LMT", "reported_export_volume")},
            {"kind": "monthly_onion_export_volume", "value": "0.72 LMT to 1.85 LMT",
             "period": "September 2024 to January 2025",
             "evidence": exact_evidence(r"Monthly onion export quantity had picked up from 0\.72 LMT in September, 2024 to 1\.85 LMT in January, 2025\.", "reported_export_volume")},
            {"kind": "rabi_onion_production_estimate", "value": "227 LMT vs 192 LMT",
             "period": "this year vs last year; exact crop year labels are not supplied in this passage",
             "evidence": production_evidence},
            {"kind": "benchmark_market_arrivals", "value": "increased",
             "period": "from March 2025; exact start day is not stated",
             "evidence": arrivals_evidence},
            {"kind": "all_india_modal_price_change", "value": "39% decline",
             "period": "relative period not stated in this passage", "evidence": national_price_evidence},
            {"kind": "all_india_retail_price_change", "value": "10% decline",
             "period": "over the past one month as of the 2025-03-22 publication", "evidence": exact_evidence(r"all-India average retail prices recorded declined of 10% over the past one month\.", "market_price_report")},
            {"kind": "benchmark_market_modal_price", "value": "Rs.1330/qtl and Rs.1325/qtl",
             "period": "21 March 2025; source spells market names Lasalgaon and Pimpalgoan",
             "evidence": benchmark_price_evidence},
        ]
        signal["price_impact_hypothesis"] = "The source reports a duty withdrawal, arrivals, and higher production estimates; actual causal effects and Nashik price direction remain unknown and unvalidated."
    signal.update({"commodity_relevance": "onion_direct", "geographic_relevance": "india_wide",
                   "series_id": "unassigned", "classification_method": "source_passage_rules_v1_manual_text",
                   "source_relevance": "official_primary_source", "price_impact_validation": "none"})
    return signal


def import_pib_text_file(engine, path, *, prid, source_url, imported_at=None):
    """Append a manually saved PIB text representation to its existing article capture."""
    import re
    path = Path(path)
    raw = path.read_bytes()
    if not raw or len(raw) > 2_000_000:
        raise DataUnavailable("PIB text file must contain 1 byte to 2 MB")
    try:
        text_value = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n").strip()
    except UnicodeDecodeError:
        raise DataUnavailable("PIB text file must be UTF-8 text") from None
    if not re.fullmatch(r"\d+", str(prid)):
        raise DataUnavailable("PIB release identifier must be numeric")
    parsed = urlsplit(source_url)
    query_id = re.search(r"(?:PRID|relid)=(\d+)", parsed.query, re.I)
    if parsed.scheme != "https" or (parsed.hostname or "").casefold() not in {"pib.gov.in", "www.pib.gov.in"} or not query_id or query_id.group(1) != str(prid):
        raise DataUnavailable("Source URL must be an HTTPS PIB release URL for the supplied PRID")
    date_line = re.search(r"^Posted On:[^\r\n]*(?:\r?\n|$)", text_value, re.I | re.M)
    body = text_value[date_line.end():].strip() if date_line else text_value
    if str(prid) == "1972618":
        required = (r"minimum export price.*?\b800\b", r"(?:with\s+effect\s+from|effective\s+from)\s+29th October,?\s+2023.*?31st December,?\s+2023",
                    r"procurement of additional\s+2\s+lakh tons?.*?buffer")
        if not all(re.search(pattern, body, re.I | re.S) for pattern in required):
            raise DataUnavailable("PRID 1972618 text is missing the source-supported MEP period or additional buffer procurement passage")
    elif str(prid) == "2042765":
        required = (r"2\.60 lakh tons of onion had been exported in current financial year 2024-25",
                    r"Government had procured 4\.68 lakh tons")
        if not all(re.search(pattern, body, re.I) for pattern in required):
            raise DataUnavailable("PRID 2042765 text is missing its reported export-volume or procurement passage")
    elif str(prid) == "2114060":
        required = (r"withdrawn 20% duty on onion export, effective from 1st April, 2025",
                    r"total onion export during FY 2023-24 was 17\.17 LMT")
        if not all(re.search(pattern, body, re.I) for pattern in required):
            raise DataUnavailable("PRID 2114060 text is missing its duty-withdrawal or historical export passage")
    elif not (re.search(r"\bonion", body, re.I) and len(body) >= 300):
        raise DataUnavailable("Manual PIB text is too short or does not identify onion article content")
    captured = imported_at or datetime.now(timezone.utc)
    if captured.tzinfo is None:
        raise DataUnavailable("Text import timestamp must be timezone-aware")
    captured = captured.astimezone(timezone.utc)
    canonical = f"https://www.pib.gov.in/PressReleaseDetail.aspx?PRID={prid}&reg=48&lang=1"
    raw_hash = hashlib.sha256(raw).hexdigest()
    content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    migrate(engine)
    with engine.begin() as conn:
        row = conn.execute(select(captures).where(captures.c.article_url == canonical).order_by(captures.c.retrieved_at_utc).limit(1)).mappings().first()
        if not row:
            raise DataUnavailable("No existing captured PIB article matches this PRID; text import will not create an unanchored article")
        metadata_value = json.loads(row["raw_item_json"])
        if metadata_value.get("published_date") != row["source_publication_at_utc"]:
            raise DataUnavailable("Existing verified publication date metadata is inconsistent; text import stopped")
        if str(prid) == "1972618" and (row["source_publication_at_utc"] != "2023-10-28" or
                "consumer affairs" not in (metadata_value.get("issuing_ministry") or "").casefold()):
            raise DataUnavailable("PRID 1972618 does not match the existing verified date/ministry metadata")
        expected_identity = {
            "2042765": ("2024-08-07", "consumer affairs"),
            "2114060": ("2025-03-22", "consumer affairs"),
        }.get(str(prid))
        if expected_identity and (row["source_publication_at_utc"] != expected_identity[0] or
                expected_identity[1] not in (metadata_value.get("issuing_ministry") or "").casefold()):
            raise DataUnavailable(f"PRID {prid} does not match its existing verified date/ministry metadata")
        same = conn.execute(select(representations).where(representations.c.capture_id == row["capture_id"])
                            .where(or_(representations.c.raw_sha256 == raw_hash,
                                       representations.c.content_sha256 == content_hash))).mappings().first()
        title = row["title"]
        signal = extract_event_intelligence(title, body, article_id=str(prid))
        if str(prid) == "1972618":
            wanted = {
                "mep_introduction": lambda ev: "with effect from 29th october, 2023, till 31st december, 2023" in ev["text"].casefold(),
                "government_procurement": lambda ev: "procurement of additional 2 lakh tons of onion for the buffer" in ev["text"].casefold(),
            }
            selected = []
            for category, predicate in wanted.items():
                event = next((item for item in signal["events"] if item["category"] == category), None)
                evidence = next((ev for ev in (event or {}).get("evidence", []) if predicate(ev)), None)
                if event and evidence:
                    selected.append({**event, "evidence": [evidence]})
            signal["events"] = selected
            if len(selected) != 2:
                raise DataUnavailable("Full text did not yield both required evidence-supported PRID 1972618 events")
        elif str(prid) in {"2042765", "2114060"}:
            signal = _pib_2024_2025_signal(str(prid), title, body)
        signal.update({"commodity_relevance": "onion_direct", "geographic_relevance": "india_wide"
                       if "all over the country" in body.casefold() else signal["geographic_relevance"],
                       "series_id": "unassigned", "classification_status": "experimental_rule_supported",
                       "classification_method": "explainable_multilabel_rules_v1_manual_text",
                       "source_relevance": "official_primary_source",
                       "price_impact_hypothesis": signal.get("price_impact_hypothesis") or "Export incentives and buffer procurement/disposal may affect domestic availability; net mandi-price effect and Nashik-specific impact are unknown and unvalidated.",
                       "price_impact_validation": "none"})
        representation_id = str(uuid.uuid4())
        metadata_json = {"prid": str(prid), "file_name": path.name, "availability_basis": "manual_local_import",
                         "publication_date_source": "existing_verified_capture_metadata",
                         "published_at_time_zone": "not_supplied_by_source"}
        if same:
            # Identical source bytes remain idempotent, while deterministic
            # classifier fixes can refresh derived fields without a revision.
            conn.execute(update(representations).where(representations.c.representation_id == same["representation_id"]).values(
                classification_json=json.dumps(signal, ensure_ascii=False, sort_keys=True)))
            return {"status": "duplicate", "capture_id": row["capture_id"], "representation_id": same["representation_id"],
                    "prid": str(prid), "raw_sha256": same["raw_sha256"],
                    "incoming_raw_sha256": raw_hash, "content_sha256": content_hash,
                    "matched_by": "raw_sha256" if same["raw_sha256"] == raw_hash else "content_sha256",
                    "events": signal["events"]}
        conn.execute(representations.insert().values(representation_id=representation_id,
            capture_id=row["capture_id"], representation_type="manual_txt", source_url=canonical,
            source_name="PIB article text manually saved from official page", imported_at_utc=captured.isoformat(),
            raw_sha256=raw_hash, content_sha256=content_hash, article_text=body,
            content_status="full_text_extracted", extraction_method="manual_official_page_text_v1",
            classification_json=json.dumps(signal, ensure_ascii=False, sort_keys=True),
            metadata_json=json.dumps(metadata_json, ensure_ascii=False, sort_keys=True)))
    return {"status": "success", "capture_id": row["capture_id"], "representation_id": representation_id,
            "prid": str(prid), "content_status": "full_text_extracted", "event_count": len(signal["events"]),
            "events": signal["events"], "commodity_relevance": signal["commodity_relevance"],
            "geographic_relevance": signal["geographic_relevance"], "published_date": row["source_publication_at_utc"],
            "issuing_ministry": metadata_value.get("issuing_ministry"), "imported_at_utc": captured.isoformat(),
            "raw_sha256": raw_hash, "content_sha256": content_hash,
            "note": "Manual text stored as a separate source representation; existing HTML capture and article first-seen time are unchanged."}


class _PIBHTMLText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.meta, self.links = [], {}, []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag.casefold() in {"script", "style", "noscript", "svg"}:
            self._skip += 1
        if tag.casefold() == "meta":
            key = values.get("property") or values.get("name")
            if key and values.get("content"):
                self.meta[key.casefold()] = values["content"].strip()
        if tag.casefold() == "a" and values.get("href"):
            self.links.append(values["href"])

    def handle_endtag(self, tag):
        if tag.casefold() in {"script", "style", "noscript", "svg"} and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.parts.append(" ".join(data.split()))


def import_pib_article_html(engine, path, *, retrieved_at=None):
    """Import HTML-only save of PIB PRID 2114060 with its actual local import time."""
    import re
    from datetime import date
    path = Path(path)
    raw = path.read_bytes()
    if not raw or len(raw) > 10_000_000:
        raise DataUnavailable("Saved PIB HTML must contain 1 byte to 10 MB")
    try:
        document = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        document = raw.decode("cp1252", errors="strict")
    parser = _PIBHTMLText()
    parser.feed(document)
    body_text = " ".join(parser.parts)
    if PIB_PRID not in (path.name + " " + " ".join(parser.links) + " " + document[:500_000]) or "pib.gov.in" not in document[:500_000].casefold():
        raise DataUnavailable("HTML does not verifiably identify official PIB release PRID 2114060")
    title = parser.meta.get("og:title") or parser.meta.get("twitter:title")
    if not title:
        title = next((part for part in parser.parts[:100]
                      if "onion" in part.casefold() and "export" in part.casefold()), "")
    if not title or "onion" not in title.casefold() or "export" not in title.casefold():
        raise DataUnavailable("Saved PIB headline does not identify the supplied onion export release")
    if len(body_text) < 300:
        raise DataUnavailable("Saved PIB page has insufficient extracted article text")
    date_value = None
    for match in re.finditer(r"(?:Date|Dated|Posted\s+On|Publication\s+Date)\s*[:\-]?\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})", body_text, re.I):
        for fmt in ("%d %B %Y", "%d %b %Y"):
            try:
                date_value = datetime.strptime(match.group(1), fmt).date().isoformat()
                break
            except ValueError:
                continue
        if date_value:
            break
    captured = retrieved_at or datetime.now(timezone.utc)
    if captured.tzinfo is None:
        raise DataUnavailable("HTML import time must be timezone-aware")
    captured = captured.astimezone(timezone.utc)
    canonical_url = PIB_ARTICLE_URL
    signal = classify_onion_event({"title": title, "summary": body_text, "url": canonical_url},
                                  series_id="unassigned", retrieved_at=captured)
    signal["category"] = "export_policy"
    signal["relevance_status"] = "relevant" if "onion" in body_text.casefold() else "review_required"
    signal["direction_hypothesis"] = "Policy change may affect export incentives and domestic supply; price direction is uncertain and unvalidated."
    signal["supply_pressure"] = 0.0
    signal["extracted_evidence"] = [word for word in ("onion", "export", "duty") if word in body_text.casefold()]
    signal["classification_method"] = "pib_article_html_keyword_rules_v1"
    signal["classification_status"] = "unvalidated_rule_signal_manual_source_capture"
    content_hash = hashlib.sha256(body_text.encode("utf-8")).hexdigest()
    raw_hash = hashlib.sha256(raw).hexdigest()
    ministry_terms = ("Ministry of Agriculture and Farmers Welfare", "Ministry of Consumer Affairs, Food and Public Distribution",
                      "Department of Consumer Affairs", "Ministry of Commerce and Industry")
    ministry = next((term for term in ministry_terms if term.casefold() in body_text.casefold()), None)
    metadata_json = {"prid": PIB_PRID, "article_text": body_text, "issuing_ministry": ministry,
                     "publication_date": date_value, "publication_precision": "date_only" if date_value else "unknown",
                     "content_sha256": content_hash}
    migrate(engine)
    run_id, capture_id = str(uuid.uuid4()), str(uuid.uuid4())
    with engine.begin() as conn:
        prior_rows = conn.execute(select(captures.c.capture_id, captures.c.raw_item_json, captures.c.first_seen_at_utc)
                                  .where(captures.c.article_url == canonical_url)).mappings().all()
        existing = next((row for row in prior_rows
                         if json.loads(row["raw_item_json"]).get("content_sha256") == content_hash), None)
        if existing:
            return {"status": "deduplicated", "capture_id": existing["capture_id"], "raw_sha256": raw_hash,
                    "content_sha256": content_hash, "retrieved_at_utc": captured.isoformat()}
        prior = conn.execute(select(captures.c.first_seen_at_utc).where(captures.c.article_url == canonical_url)
                             .order_by(captures.c.first_seen_at_utc).limit(1)).first()
        conn.execute(capture_runs.insert().values(run_id=run_id, source_url=canonical_url,
            retrieval_method=f"manual_pib_html_import:{path.name}", retrieved_at_utc=captured.isoformat(),
            raw_sha256=raw_hash, raw_payload=document, status="success", item_count=1,
            validation_errors_json="[]"))
        conn.execute(captures.insert().values(capture_id=capture_id, run_id=run_id,
            article_key=hashlib.sha256(f"{PIB_PRID}|{content_hash}".encode()).hexdigest(),
            deduplication_key=hashlib.sha256(PIB_PRID.encode()).hexdigest(),
            first_seen_at_utc=prior[0] if prior else captured.isoformat(), retrieved_at_utc=captured.isoformat(),
            source_url=canonical_url, article_url=canonical_url, title=title, summary_text=body_text,
            source_publication_at_utc=date_value,
            publication_status="source_date_only" if date_value else "missing",
            raw_item_json=json.dumps(metadata_json, ensure_ascii=False, sort_keys=True),
            classification_json=json.dumps(signal, ensure_ascii=False, sort_keys=True), raw_sha256=raw_hash))
    return {"status": "success", "run_id": run_id, "capture_id": capture_id, "prid": PIB_PRID,
            "title": title, "publication_date": date_value, "issuing_ministry": ministry,
            "retrieved_at_utc": captured.isoformat(), "raw_sha256": raw_hash,
            "content_sha256": content_hash, "classification": signal}


def import_pib_html_file(engine, path, *, retrieved_at=None, retrieval_method=None):
    """Import any PIB HTML-only release using its embedded official identity."""
    import re
    path = Path(path)
    raw = path.read_bytes()
    if not raw or len(raw) > 10_000_000:
        raise DataUnavailable("Saved PIB HTML must contain 1 byte to 10 MB")
    try:
        document = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        document = raw.decode("cp1252", errors="strict")
    parser = _PIBHTMLText()
    parser.feed(document)
    source_url = parser.meta.get("og:url", "")
    title = parser.meta.get("og:title") or parser.meta.get("twitter:title")
    description = parser.meta.get("og:description", "")
    # PIB has historically emitted a host-relative og:url (for example
    # ``www.pib.gov.in/Pressreleaseshare.aspx?...``). Accept that exact
    # official host form, while continuing to reject arbitrary hosts.
    normalized_source_url = source_url.strip()
    if normalized_source_url.casefold().startswith(("www.pib.gov.in/", "pib.gov.in/")):
        normalized_source_url = "https://" + normalized_source_url
    parsed_url = urlsplit(normalized_source_url)
    match = re.search(r"(?:PRID|relid)=(\d+)", normalized_source_url, re.I)
    if not match or (parsed_url.hostname or "").casefold() not in {"pib.gov.in", "www.pib.gov.in"}:
        raise DataUnavailable("HTML is missing an official PIB URL and release identifier")
    if not title or len(title.strip()) < 10 or len(description.strip()) < 35:
        raise DataUnavailable("HTML has no verifiable PIB headline and source article excerpt")
    prid = match.group(1)
    canonical_url = f"https://www.pib.gov.in/PressReleaseDetail.aspx?PRID={prid}&reg=48&lang=1"
    # Prefer a full article body only when meaningful non-chrome content exists.
    visible = " ".join(parser.parts)
    title_at = visible.casefold().find(title.casefold())
    article_region = visible[title_at + len(title):] if title_at >= 0 else ""
    # Full PIB pages put a publication heading before body text and duplicate
    # the content in desktop/mobile containers. Slice by visible PIB markers.
    header = re.search(r"Posted\s+On:.*?PIB\s+Delhi\s*", article_region, re.I)
    if header:
        article_region = article_region[header.end():]
    # PIB separates article copy from signature/footer with four asterisks.
    # If absent, fall back to the visible navigation marker.
    article_region = re.split(r"\s+\*{4}\s+", article_region, maxsplit=1)[0]
    article_region = re.split(r"\b(?:Read this release in:|Share Ministry of)", article_region, maxsplit=1, flags=re.I)[0]
    # Do not split a sentence inside numeric dates or before PIB's **** footer.
    body_candidates = [chunk.strip() for chunk in re.split(r"(?<=[!?])\s+|(?<=\.)\s+(?![\d*])", article_region)
                       if len(chunk.strip()) >= 45 and ("onion" in chunk.casefold() or "agricultur" in chunk.casefold())
                       and not re.search(r"(?:Release ID:|Visitor Counter:|Read this release in:|Share Ministry of)", chunk, re.I)]
    article_text = " ".join(body_candidates) if body_candidates else description.strip()
    content_status = "full_text_extracted" if body_candidates else "metadata_excerpt_only"
    captured = retrieved_at or datetime.now(timezone.utc)
    if captured.tzinfo is None:
        raise DataUnavailable("HTML import time must be timezone-aware")
    captured = captured.astimezone(timezone.utc)
    published_date = None
    published_time = None
    pub_match = re.search(r"Posted On:\s*(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})(?:\s+(\d{1,2}:\d{2}\s*[AP]M))?", visible, re.I)
    if pub_match:
        try:
            published_date = datetime.strptime(" ".join(pub_match.group(i) for i in (1,2,3)), "%d %b %Y").date().isoformat()
            published_time = pub_match.group(4)
        except ValueError:
            pass
    full_text = f"{title}\n{article_text}"
    signal = extract_event_intelligence(title, article_text, article_id=prid)
    signal.update({"category": signal["events"][0]["category"] if signal["events"] else "unclassified",
                   "relevance_status": "relevant" if signal["commodity_relevance"] == "onion_direct" else "review_required",
                   "geographic_relevance_legacy": "unverified" if signal["geographic_relevance"] == "unknown" else signal["geographic_relevance"],
                   "commodity_relevance_legacy": signal["commodity_relevance"],
                   "direction_hypothesis": signal["price_impact_hypothesis"],
                   "source_confidence": "not_scored",
                   "source_relevance": "official_primary_source"})
    # Metadata only supports the precisely captured description as evidence.
    raw_hash = hashlib.sha256(raw).hexdigest()
    content_hash = hashlib.sha256(article_text.encode("utf-8")).hexdigest()
    ministry = None
    article_head = visible[:max(0, visible.find(title))] if title in visible else ""
    ministry_match = re.search(r"(Ministry of [A-Za-z &,-]+|Department of [A-Za-z &,-]+)", article_head, re.I)
    if ministry_match:
        ministry = ministry_match.group(1).strip()
    item_meta = {"prid": prid, "article_text": article_text, "content_status": content_status,
                 "content_sha256": content_hash, "issuing_ministry": ministry,
                 "published_date": published_date, "published_time_source_text": published_time,
                 "publication_precision": "date_only" if published_date else "unknown",
                 "source_description": description, "original_language": parser.meta.get("og:locale") or "en",
                 "source_page_url_as_saved": source_url}
    migrate(engine)
    run_id, capture_id = str(uuid.uuid4()), str(uuid.uuid4())
    with engine.begin() as conn:
        same_identity = conn.execute(select(captures.c.capture_id, captures.c.raw_item_json,
                                           captures.c.first_seen_at_utc, captures.c.raw_sha256).where(captures.c.article_url == canonical_url)).mappings().all()
        duplicate = next((r for r in same_identity if json.loads(r["raw_item_json"]).get("content_sha256") == content_hash), None)
        if duplicate:
            # Identical extracted article text can arrive in a genuinely
            # fuller official page save. Preserve both raw responses and
            # upgrade only derived extraction metadata when it is stronger.
            existing_meta = json.loads(duplicate["raw_item_json"])
            merged_meta = {**item_meta, **{key: value for key, value in existing_meta.items()
                if key in {"metadata_verification", "metadata_verification_history", "published_date",
                           "publication_precision", "issuing_ministry", "published_time_source_text"} and value}}
            merged_date = existing_meta.get("published_date") or published_date
            incoming_rank = {"metadata_excerpt_only": 1, "full_text_extracted": 2}
            if (duplicate["raw_sha256"] == raw_hash or
                    incoming_rank.get(content_status, 0) > incoming_rank.get(existing_meta.get("content_status"), 0)):
                conn.execute(update(captures).where(captures.c.capture_id == duplicate["capture_id"]).values(
                    title=title, summary_text=article_text,
                    source_publication_at_utc=merged_date,
                    publication_status="source_date_only" if merged_date else "missing",
                    raw_item_json=json.dumps(merged_meta, ensure_ascii=False, sort_keys=True),
                    classification_json=json.dumps(signal, ensure_ascii=False, sort_keys=True)))
                return {"status": "enriched_existing", "capture_id": duplicate["capture_id"], "prid": prid,
                        "content_status": content_status, "event_count": len(signal["events"]),
                        "raw_sha256": raw_hash, "content_sha256": content_hash}
            return {"status": "duplicate", "capture_id": duplicate["capture_id"], "prid": prid,
                    "content_sha256": content_hash, "source_url": canonical_url}
        same_response = next((r for r in same_identity if r["raw_sha256"] == raw_hash), None)
        if same_response:
            # Same preserved source bytes; enrich only derived metadata/classification.
            existing_meta = json.loads(same_response["raw_item_json"])
            merged_meta = {**item_meta, **{key: value for key, value in existing_meta.items()
                if key in {"metadata_verification", "metadata_verification_history", "published_date",
                           "publication_precision", "issuing_ministry", "published_time_source_text"} and value}}
            merged_date = existing_meta.get("published_date") or published_date
            conn.execute(update(captures).where(captures.c.capture_id == same_response["capture_id"]).values(
                title=title, summary_text=article_text,
                source_publication_at_utc=merged_date,
                publication_status="source_date_only" if merged_date else "missing",
                raw_item_json=json.dumps(merged_meta, ensure_ascii=False, sort_keys=True),
                classification_json=json.dumps(signal, ensure_ascii=False, sort_keys=True)))
            return {"status": "enriched_existing", "capture_id": same_response["capture_id"], "prid": prid,
                    "content_status": content_status, "event_count": len(signal["events"]),
                    "raw_sha256": raw_hash}
        first_seen = same_identity[0]["first_seen_at_utc"] if same_identity else captured.isoformat()
        conn.execute(capture_runs.insert().values(run_id=run_id, source_url=canonical_url,
            retrieval_method=retrieval_method or f"manual_pib_html_import:{path.name}", retrieved_at_utc=captured.isoformat(),
            raw_sha256=raw_hash, raw_payload=document, status="success", item_count=1, validation_errors_json="[]"))
        conn.execute(captures.insert().values(capture_id=capture_id, run_id=run_id,
            article_key=hashlib.sha256(f"{prid}|{content_hash}".encode()).hexdigest(),
            deduplication_key=hashlib.sha256(f"pib|{prid}".encode()).hexdigest(),
            first_seen_at_utc=first_seen, retrieved_at_utc=captured.isoformat(), source_url=canonical_url,
            article_url=canonical_url, title=title, summary_text=article_text,
            source_publication_at_utc=published_date,
            publication_status="source_date_only" if published_date else "missing",
            raw_item_json=json.dumps(item_meta, ensure_ascii=False, sort_keys=True),
            classification_json=json.dumps(signal, ensure_ascii=False, sort_keys=True), raw_sha256=raw_hash))
    return {"status": "success" if signal["events"] else "review_required", "capture_id": capture_id,
            "run_id": run_id, "prid": prid, "source_url": canonical_url, "title": title,
            "publication_date": published_date, "issuing_ministry": ministry,
            "content_status": content_status, "content_sha256": content_hash, "raw_sha256": raw_hash,
            "event_count": len(signal["events"]), "classification_status": signal["classification_status"]}


def import_pib_html_directory(engine, directory, *, retrieved_at=None):
    directory = Path(directory)
    if not directory.is_dir():
        raise DataUnavailable("PIB import directory does not exist")
    files = sorted({*directory.glob("*.html"), *directory.glob("*.htm")})
    results = []
    for path in files:
        try:
            result = import_pib_html_file(engine, path, retrieved_at=retrieved_at)
            results.append({"file": path.name, **result})
        except (DataUnavailable, OSError, UnicodeError, ValueError) as exc:
            results.append({"file": path.name, "status": "failed", "error": str(exc)})
    return {"files_seen": len(files), "succeeded": sum(r["status"] in {"success", "enriched_existing"} for r in results),
            "duplicates": sum(r["status"] == "duplicate" for r in results),
            "enriched_existing": sum(r["status"] == "enriched_existing" for r in results),
            "review_required": sum(r["status"] == "review_required" for r in results),
            "failed": sum(r["status"] == "failed" for r in results), "results": results}


def enrich_verified_pib_metadata(engine, *, prid, published_date, ministry, source_evidence,
                                 verification_source_url, published_time_source_text=None, verified_at=None):
    """Append separately sourced official metadata without altering raw capture bytes."""
    import re
    from datetime import date
    from sqlalchemy import update
    if not re.fullmatch(r"\d+", str(prid)):
        raise DataUnavailable("PIB release identifier must be numeric")
    try:
        date.fromisoformat(published_date)
    except (TypeError, ValueError):
        raise DataUnavailable("Published date must be an actual ISO calendar date") from None
    host = (urlsplit(verification_source_url).hostname or "").casefold()
    if host not in {"pib.gov.in", "www.pib.gov.in"} or str(prid) not in verification_source_url:
        raise DataUnavailable("Metadata verification must link to the exact official PIB release")
    if not source_evidence or not ministry:
        raise DataUnavailable("Official page text supporting date and ministry is required")
    checked = verified_at or datetime.now(timezone.utc)
    if checked.tzinfo is None:
        raise DataUnavailable("Metadata verification time must be timezone-aware")
    canonical = f"https://www.pib.gov.in/PressReleaseDetail.aspx?PRID={prid}&reg=48&lang=1"
    with engine.begin() as conn:
        row = conn.execute(select(captures).where(captures.c.article_url == canonical).order_by(captures.c.retrieved_at_utc).limit(1)).mappings().first()
        if not row:
            raise DataUnavailable("No previously captured source article matches this PIB PRID")
        raw_meta = json.loads(row["raw_item_json"])
        existing_date = raw_meta.get("published_date", raw_meta.get("publication_date"))
        existing_ministry = raw_meta.get("issuing_ministry")
        if existing_date and existing_date != published_date:
            raise DataUnavailable("Conflicting verified publication date; original metadata was preserved")
        if existing_ministry and existing_ministry.casefold() != ministry.casefold():
            raise DataUnavailable("Conflicting verified issuing ministry; original metadata was preserved")
        raw_meta["published_date"] = published_date
        raw_meta["publication_precision"] = "date_only"
        raw_meta["issuing_ministry"] = ministry
        raw_meta["published_time_source_text"] = published_time_source_text
        verification = {"source_url": verification_source_url,
            "retrieved_at_utc": checked.astimezone(timezone.utc).isoformat(),
            "method": "official_pib_page_content_review", "source_evidence": source_evidence,
            "time_zone_status": "not_explicitly_supplied"}
        history = raw_meta.get("metadata_verification_history")
        if history is None:
            prior = raw_meta.get("metadata_verification")
            history = [prior] if prior else []
        history.append(verification)
        raw_meta["metadata_verification_history"] = history
        raw_meta["metadata_verification"] = verification
        conn.execute(update(captures).where(captures.c.capture_id == row["capture_id"]).values(
            source_publication_at_utc=published_date, publication_status="source_date_only",
            raw_item_json=json.dumps(raw_meta, ensure_ascii=False, sort_keys=True)))
    return {"capture_id": row["capture_id"], "prid": str(prid), "published_date": published_date,
            "publication_precision": "date_only", "issuing_ministry": ministry,
            "metadata_verified_at_utc": checked.astimezone(timezone.utc).isoformat(),
            "raw_capture_preserved": True}


def export_research_archive(engine, *, series_id):
    """Export events only when saved-feed polls prove gap-free daily coverage.

    This deliberately cannot establish pre-capture availability. Events with
    absent or timezone-ambiguous publication timestamps remain stored but are
    excluded from the model archive.
    """
    with engine.connect() as conn:
        runs = conn.execute(select(capture_runs).where(capture_runs.c.status == "success")
                            .order_by(capture_runs.c.retrieved_at_utc)).mappings().all()
        rows = conn.execute(select(captures).order_by(captures.c.first_seen_at_utc)).mappings().all()
    if not runs:
        raise DataUnavailable("No successful timestamped RSS captures exist")
    days = sorted({datetime.fromisoformat(row["retrieved_at_utc"]).date() for row in runs})
    start, end = days[0], days[-1]
    expected_days = (end - start).days + 1
    if len(days) != expected_days:
        raise DataUnavailable("RSS source monitoring has calendar gaps; no complete event archive can be asserted")
    events, seen = [], set()
    for row in rows:
        if not row["source_publication_at_utc"] or row["deduplication_key"] in seen:
            continue
        signal = json.loads(row["classification_json"])
        if signal["relevance_status"] != "relevant":
            continue
        seen.add(row["deduplication_key"])
        events.append({"id": row["article_key"], "series_id": series_id,
                       "title": row["title"], "url": row["article_url"],
                       "published_at": row["source_publication_at_utc"],
                       "available_at": row["first_seen_at_utc"],
                       "availability_basis": "first_local_capture",
                       "category": signal["category"], "supply_pressure": signal["supply_pressure"],
                       "direction_hypothesis": signal["direction_hypothesis"],
                       "event_severity_heuristic": signal["event_severity_heuristic"],
                       "extracted_evidence": signal["extracted_evidence"],
                       "classification_status": signal["classification_status"],
                       "source": "Press Information Bureau, Government of India"})
    return {"coverage": {series_id: {"start": start.isoformat(), "end": end.isoformat()}},
            "coverage_basis": "successful local RSS imports on every calendar date in interval",
            "events": events,
            "limitations": ["Local import is first known availability; no historic publication availability is inferred.",
                            "Rule-based categories and direction are unvalidated hypotheses.",
                            "Only PIR/PIB primary material should be used; linked third-party items require separate rights review."],
            "holdout_eligible": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Capture and export source-attributed agricultural news; no scheduler or model training")
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("import-pib-rss", help="Import a locally saved PIB RSS XML file")
    capture.add_argument("--file", required=True)
    capture.add_argument("--database-url", default=os.getenv("DATABASE_URL", "sqlite:///./nexyra.db"))
    live = commands.add_parser("fetch-pib-rss", help="Fetch the official PIB RSS feed once")
    live.add_argument("--database-url", default=os.getenv("DATABASE_URL", "sqlite:///./nexyra.db"))
    live.add_argument("--timeout", type=int, default=10)
    live.add_argument("--retries", type=int, default=2)
    article = commands.add_parser("import-pib-html", help="Import a saved official PIB release page")
    article.add_argument("--file", required=True)
    article.add_argument("--database-url", default=os.getenv("DATABASE_URL", "sqlite:///./nexyra.db"))
    batch = commands.add_parser("import-pib-directory", help="Batch import authentic PIB HTML/HTM files")
    batch.add_argument("--directory", default="data/pib")
    batch.add_argument("--database-url", default=os.getenv("DATABASE_URL", "sqlite:///./nexyra.db"))
    text_import = commands.add_parser("import-pib-text", help="Attach a manually saved full-text representation to an existing PIB capture")
    text_import.add_argument("--file", required=True)
    text_import.add_argument("--prid", required=True)
    text_import.add_argument("--source-url", required=True)
    text_import.add_argument("--database-url", default=os.getenv("DATABASE_URL", "sqlite:///./nexyra.db"))
    export = commands.add_parser("export-archive", help="Export only after successful daily RSS capture coverage")
    export.add_argument("--series-id", required=True, help="Exact selected price-series ID")
    export.add_argument("--output", required=True)
    export.add_argument("--database-url", default=os.getenv("DATABASE_URL", "sqlite:///./nexyra.db"))
    args = parser.parse_args(argv)
    engine = create_engine(args.database_url, future=True)
    try:
        if args.command == "import-pib-rss":
            result = import_pib_rss_file(engine, args.file)
        elif args.command == "fetch-pib-rss":
            result = fetch_pib_rss(engine, timeout_seconds=args.timeout, retries=args.retries)
        elif args.command == "import-pib-html":
            result = import_pib_html_file(engine, args.file)
        elif args.command == "import-pib-directory":
            result = import_pib_html_directory(engine, args.directory)
        elif args.command == "import-pib-text":
            result = import_pib_text_file(engine, args.file, prid=args.prid, source_url=args.source_url)
        else:
            result = export_research_archive(engine, series_id=args.series_id)
            Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            result = {"status": "exported", "output": str(Path(args.output)),
                      "event_count": len(result["events"]), "holdout_eligible": result["holdout_eligible"]}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (DataUnavailable, OSError, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}), file=sys.stderr)
        return 2
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
