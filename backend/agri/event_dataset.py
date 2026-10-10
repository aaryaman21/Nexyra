"""Source-preserving text normalization and bounded PIB manifest collection."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlsplit
import unicodedata

from sqlalchemy import create_engine, inspect, select

from .data import DataUnavailable
from .events import (captures, human_event_reviews, migrate, recent_captures,
                     representations, text_normalizations, import_pib_html_file)

NORMALIZATION_VERSION = "pib-text-nfc-clean-v1"
MAX_PAGE_BYTES = 10_000_000
PIB_HOSTS = {"pib.gov.in", "www.pib.gov.in"}
_KNOWN_MOJIBAKE = {"Ã¢â‚¬â„¢": "’", "â€™": "’"}


def normalize_article_text(text: str, prid: str | None = None):
    """Return a derived display/evaluation form plus an auditable change list."""
    original = text
    text = unicodedata.normalize("NFC", text)
    changes = []
    if text != original:
        changes.append({"kind": "unicode_nfc"})
    decoded = text.replace("&nbsp;", " ").replace("&#160;", " ").replace("\u00a0", " ")
    decoded = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", decoded)
    if decoded != text:
        changes.append({"kind": "html_whitespace_and_zero_width_cleanup"})
    text = decoded
    if prid == "2114060":
        for broken, repaired in _KNOWN_MOJIBAKE.items():
            if broken in text:
                text = text.replace(broken, repaired)
                changes.append({"kind": "known_reversible_mojibake_repair", "from": broken, "to": repaired})
    # Collapse layout-only spacing while retaining article paragraph boundaries.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    text = re.sub(r"\n?Posted On:.*?PIB Delhi\s*", "\n", text, flags=re.I | re.S, count=1)
    if text != decoded:
        changes.append({"kind": "layout_whitespace_and_pib_header_cleanup"})
    suspicious = bool(re.search(r"(?:Ã.|â€|â€™|â€œ|â€|ï»¿)", text))
    return text, changes, "review_required" if suspicious else "normalized"


def normalize_captures(engine):
    """Append one derived normalization per best full-body source revision."""
    migrate(engine)
    feed = recent_captures(engine, limit=200)
    report = {"status": "complete", "created": 0, "reused": 0, "skipped": 0, "articles": []}
    with engine.begin() as conn:
        for item in feed["events"]:
            rep_id = item.get("text_representation_id")
            source_hash = item.get("text_content_sha256")
            source_text = item.get("original_article_text") or item.get("article_text") or ""
            if not source_hash or not source_text or item.get("content_status") not in {"full_text_extracted", "full_body_verified"}:
                report["skipped"] += 1
                continue
            prior = conn.execute(select(text_normalizations).where(
                text_normalizations.c.capture_id == item["id"],
                text_normalizations.c.representation_id == rep_id,
                text_normalizations.c.source_content_sha256 == source_hash,
                text_normalizations.c.normalization_version == NORMALIZATION_VERSION
            ).order_by(text_normalizations.c.created_at_utc.desc()).limit(1)).mappings().first()
            if prior:
                report["reused"] += 1
                continue
            normalized, changes, status = normalize_article_text(source_text, item.get("prid"))
            now = datetime.now(timezone.utc).isoformat()
            normal_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            conn.execute(text_normalizations.insert().values(
                normalization_id=__import__("uuid").uuid4().hex, capture_id=item["id"],
                representation_id=rep_id, source_content_sha256=source_hash,
                normalization_version=NORMALIZATION_VERSION, normalized_text=normalized,
                normalized_sha256=normal_hash, transformations_json=json.dumps(changes, ensure_ascii=False),
                status=status, created_at_utc=now))
            report["created"] += 1
            report["articles"].append({"prid": item.get("prid"), "capture_id": item["id"],
                                       "source_sha256": source_hash, "normalized_sha256": normal_hash,
                                       "status": status, "transformations": changes})
    return report


def classification_inventory(engine):
    """Summarize stored experimental predictions without touching source or labels."""
    feed = recent_captures(engine, limit=200)
    articles, categories = [], {}
    for item in feed.get("events", []):
        labels = sorted({entry.get("category", "unclassified") for entry in item.get("event_classifications", [])})
        for label in labels:
            categories[label] = categories.get(label, 0) + 1
        articles.append({"article_identity": item.get("article_identity"), "capture_id": item.get("id"),
            "prid": item.get("prid"), "classification_status": item.get("classification_status"),
            "categories": labels})
    return {"status": "ready" if articles else "empty", "unique_articles": len(articles),
            "category_article_counts": categories, "articles": articles,
            "accuracy_status": "not_evaluated_without_human_review"}


def import_manifest(engine, manifest_path, *, fetch=False, timeout=15, raw_dir="data/pib/phase5b6_raw", refresh=False):
    """Collect only candidate rows marked collect, from exact official PIB URLs."""
    if not 1 <= timeout <= 30:
        raise ValueError("timeout must be 1..30 seconds")
    path = Path(manifest_path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    articles = manifest.get("articles")
    if not isinstance(articles, list):
        raise DataUnavailable("Manifest must contain an articles array")
    outcomes = []
    captured_prids = set()
    if inspect(engine).has_table(captures.name):
        with engine.connect() as conn:
            prior_rows = conn.execute(select(captures.c.raw_item_json)).all()
        captured_prids = {str(json.loads(row[0]).get("prid")) for row in prior_rows if json.loads(row[0]).get("prid")}
    for entry in articles:
        prid, url = str(entry.get("prid", "")), str(entry.get("url", ""))
        parsed = urlsplit(url)
        query_prid = parse_qs(parsed.query).get("PRID", [""])[0]
        if not prid.isdigit() or query_prid != prid or parsed.scheme != "https" or parsed.hostname not in PIB_HOSTS:
            outcomes.append({"prid": prid, "status": "rejected", "reason": "URL must be an exact official PIB URL whose PRID matches"})
            continue
        if entry.get("status") != "collect":
            outcomes.append({"prid": prid, "status": "not_collected", "reason": "manifest row not explicitly marked collect"})
            continue
        if fetch and prid in captured_prids and not refresh:
            outcomes.append({"prid": prid, "status": "already_captured", "reason": "PRID has a stored capture; use --refresh only to poll for a source revision"})
            continue
        if not fetch:
            outcomes.append({"prid": prid, "status": "verified_manifest_candidate", "url": url})
            continue
        req = urllib.request.Request(url, headers={"User-Agent": "Nexyra-Research-EventCollector/1.0", "Accept": "text/html"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                final = urlsplit(response.geturl())
                if response.status != 200 or final.scheme != "https" or final.hostname not in PIB_HOSTS:
                    raise DataUnavailable("request returned non-200 status or redirected outside PIB")
                raw = response.read(MAX_PAGE_BYTES + 1)
            if len(raw) > MAX_PAGE_BYTES:
                raise DataUnavailable("PIB response exceeded 10 MB limit")
            fetched_at = datetime.now(timezone.utc)
            raw_hash = hashlib.sha256(raw).hexdigest()
            root = Path(raw_dir)
            root.mkdir(parents=True, exist_ok=True)
            target = root / f"PRID_{prid}_{fetched_at.strftime('%Y%m%dT%H%M%S%fZ')}_{raw_hash[:10]}.html"
            # Exclusive creation guarantees an existing raw capture is never overwritten.
            with target.open("xb") as output:
                output.write(raw)
            result = import_pib_html_file(engine, target, retrieved_at=fetched_at,
                                          retrieval_method="official_pib_http_get")
            receipt = {"prid": prid, "source_url_requested": url, "raw_file": str(target),
                "raw_sha256": raw_hash, "retrieved_at_utc": fetched_at.isoformat(),
                "capture_id": result.get("capture_id"), "import_status": result.get("status"),
                "content_status": result.get("content_status")}
            receipt_path = Path(raw_dir).parent / "phase5b6_collection_receipts.jsonl"
            with receipt_path.open("a", encoding="utf-8") as receipt_file:
                receipt_file.write(json.dumps(receipt, ensure_ascii=False) + "\n")
            outcomes.append({**result, "prid": prid, "status": "captured",
                             "import_status": result.get("status"), "file": str(target),
                             "raw_sha256": raw_hash, "retrieved_at_utc": fetched_at.isoformat()})
        except (urllib.error.URLError, TimeoutError, OSError, DataUnavailable, ValueError) as exc:
            # Never echo URL query strings or exception detail that could contain secrets.
            outcomes.append({"prid": prid, "status": "failed", "error_type": type(exc).__name__})
        time.sleep(0.2)
    return {"status": "complete", "fetch_enabled": fetch,
            "captured": sum(row["status"] == "captured" for row in outcomes), "outcomes": outcomes}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    norm = subs.add_parser("normalize", help="append derived normalized full-text representations")
    norm.add_argument("--database-url", default=os.getenv("DATABASE_URL", "sqlite:///./nexyra.db"))
    classify = subs.add_parser("classify", help="report stored experimental event classifications")
    classify.add_argument("--database-url", default=os.getenv("DATABASE_URL", "sqlite:///./nexyra.db"))
    manifest = subs.add_parser("manifest", help="validate or fetch official PIB manifest rows")
    manifest.add_argument("--file", default="data/pib/phase5b6_collection_manifest.json")
    manifest.add_argument("--fetch", action="store_true", help="perform bounded HTTP requests and write captures")
    manifest.add_argument("--refresh", action="store_true", help="poll already captured PRIDs for source revisions")
    manifest.add_argument("--timeout", type=int, default=15)
    manifest.add_argument("--raw-dir", default="data/pib/phase5b6_raw")
    manifest.add_argument("--database-url", default=os.getenv("DATABASE_URL", "sqlite:///./nexyra.db"))
    args = parser.parse_args(argv)
    engine = create_engine(args.database_url, future=True)
    try:
        if args.command == "normalize":
            result = normalize_captures(engine)
        elif args.command == "classify":
            result = classification_inventory(engine)
        else:
            result = import_manifest(engine, args.file, fetch=args.fetch, timeout=args.timeout,
                                     raw_dir=args.raw_dir, refresh=args.refresh)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    except (DataUnavailable, OSError, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=__import__("sys").stderr)
        return 2
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
