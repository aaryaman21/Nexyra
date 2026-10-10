"""Manual, provenance-preserving import for saved official agricultural text.

This adapter never fetches a URL and never treats a local import time as a source
publication time. Imported text remains a candidate until a human checks it
against the original official page.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import uuid
from urllib.parse import urlsplit

from sqlalchemy import create_engine, select

from .data import DataUnavailable
from .events import capture_runs, captures, migrate, representations
from .semantic import extract_event_intelligence

MAX_TEXT_BYTES = 5_000_000
OFFICIAL_DOMAINS = {
    "mausam.imd.gov.in": "India Meteorological Department",
    "agromet.imd.gov.in": "India Meteorological Department",
    "agmarknet.gov.in": "AGMARKNET",
    "data.gov.in": "Open Government Data Platform India",
}


def _official_source(url: str) -> tuple[str, str]:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443) or parsed.fragment:
        raise DataUnavailable("Source URL must be an HTTPS URL without credentials, a nonstandard port, or a fragment")
    hostname = (parsed.hostname or "").casefold()
    for domain, organization in OFFICIAL_DOMAINS.items():
        if hostname == domain or hostname.endswith("." + domain):
            return hostname, organization
    raise DataUnavailable("Source URL host is not in the allowlist of official IMD, AGMARKNET, or data.gov.in domains")


def import_official_text_file(engine, path, *, source_url: str, title: str,
                              reported_publication_date: str | None = None,
                              archive_dir="data/official_sources"):
    """Archive an operator-saved text file from a verified official host.

    Publication date supplied by the operator is retained as an unverified
    claim. The importer does not assert the text is complete or authentic.
    """
    path = Path(path)
    raw = path.read_bytes()
    if not raw or len(raw) > MAX_TEXT_BYTES:
        raise DataUnavailable("Saved source text must contain 1 byte to 5 MB")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise DataUnavailable("Saved text must be UTF-8 (with or without a BOM)") from None
    if len(text.strip()) < 100:
        raise DataUnavailable("Text is too short to be reviewed as an article body")
    title = str(title).strip()
    if not title or len(title) > 500:
        raise DataUnavailable("A source headline between 1 and 500 characters is required")
    hostname, organization = _official_source(source_url)
    if reported_publication_date:
        try:
            datetime.strptime(reported_publication_date, "%Y-%m-%d")
        except ValueError:
            raise DataUnavailable("Reported publication date must use YYYY-MM-DD") from None

    raw_hash = hashlib.sha256(raw).hexdigest()
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    article_identity = "official-source:" + hashlib.sha256(source_url.encode("utf-8")).hexdigest()
    article_key = hashlib.sha256(article_identity.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    signal = extract_event_intelligence("", text, article_id=article_identity)
    signal.update({"method": "transparent_keyword_rules_v1", "classification_status": "experimental_unvalidated",
                   "relevance_status": "review_required", "source_relevance": "official_host_domain_checked_body_unverified"})
    metadata = {
        "article_identity": article_identity, "source_url": source_url,
        "source_url_status": "official_host_domain_checked", "source_host": hostname,
        "source_organization": organization, "source_organization_basis": "official_domain_only",
        "title_status": "operator_supplied_unverified", "content_status": "manual_text_import_candidate",
        "content_sha256": content_hash, "reported_publication_date": reported_publication_date,
        "publication_metadata_status": "operator_supplied_unverified" if reported_publication_date else "not_supplied",
        "publication_precision": "date_only_operator_unverified" if reported_publication_date else "unknown",
    }
    archive = Path(archive_dir)
    archive.mkdir(parents=True, exist_ok=True)
    safe_stem = re.sub(r"[^A-Za-z0-9_-]+", "_", path.stem).strip("_")[:60] or "document"
    archived_file = archive / f"{article_key[:12]}_{raw_hash[:12]}_{safe_stem}.txt"
    if archived_file.exists():
        if hashlib.sha256(archived_file.read_bytes()).hexdigest() != raw_hash:
            raise DataUnavailable("Archive path already exists with different bytes; refusing to overwrite")
    else:
        with archived_file.open("xb") as output:
            output.write(raw)

    migrate(engine)
    with engine.begin() as conn:
        existing = conn.execute(select(captures).where(
            captures.c.article_key == article_key, captures.c.raw_sha256 == raw_hash)).mappings().first()
        if existing:
            return {"status": "duplicate_reused", "capture_id": existing["capture_id"],
                    "article_identity": article_identity, "raw_sha256": raw_hash,
                    "content_sha256": content_hash, "database_rows_created": 0,
                    "archived_file": str(archived_file)}
        run_id, capture_id, representation_id = (str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4()))
        raw_metadata = {**metadata, "archived_file": str(archived_file),
                        "captured_at_utc": now, "retrieval_method": "manual_saved_text_import"}
        conn.execute(capture_runs.insert().values(
            run_id=run_id, source_url=source_url, retrieval_method="manual_saved_text_import",
            retrieved_at_utc=now, raw_sha256=raw_hash,
            raw_payload=json.dumps({"archived_file": str(archived_file), "raw_sha256": raw_hash,
                                    "content_sha256": content_hash}, ensure_ascii=False),
            status="success", item_count=1, validation_errors_json="[]"))
        conn.execute(captures.insert().values(
            capture_id=capture_id, run_id=run_id, article_key=article_key,
            deduplication_key=hashlib.sha256((article_identity + raw_hash + content_hash).encode()).hexdigest(),
            first_seen_at_utc=now, retrieved_at_utc=now, source_url=source_url,
            article_url=source_url, title=title, summary_text=text[:1000],
            source_publication_at_utc=None,
            publication_status="operator_reported_unverified" if reported_publication_date else "missing",
            raw_item_json=json.dumps({**raw_metadata, "published_date": reported_publication_date,
                                      "prid": None}, ensure_ascii=False),
            classification_json=json.dumps(signal, ensure_ascii=False), raw_sha256=raw_hash))
        conn.execute(representations.insert().values(
            representation_id=representation_id, capture_id=capture_id,
            representation_type="manual_txt", source_url=source_url,
            source_name=organization, imported_at_utc=now,
            raw_sha256=raw_hash, content_sha256=content_hash, article_text=text,
            content_status="manual_text_import_candidate", extraction_method="operator_saved_text_utf8",
            classification_json=json.dumps(signal, ensure_ascii=False),
            metadata_json=json.dumps(metadata, ensure_ascii=False)))
    return {"status": "captured_candidate", "capture_id": capture_id,
            "representation_id": representation_id, "article_identity": article_identity,
            "source_organization": organization, "source_url": source_url,
            "retrieved_at_utc": now, "publication_status": metadata["publication_metadata_status"],
            "raw_sha256": raw_hash, "content_sha256": content_hash,
            "content_status": "manual_text_import_candidate", "classification_status": "experimental_unvalidated",
            "database_rows_created": 3, "archived_file": str(archived_file),
            "limitations": ["Source text completeness and authenticity have not been verified against the original document.",
                            "The timestamp is the genuine local import/first-seen time; no HTTP retrieval timestamp is claimed.",
                            "Operator-supplied publication dates remain unverified and timezone-free."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    imp = commands.add_parser("import-text", help="Archive text manually saved from an official IMD/AGMARKNET/OGD document")
    imp.add_argument("--file", required=True)
    imp.add_argument("--source-url", required=True)
    imp.add_argument("--title", required=True)
    imp.add_argument("--reported-publication-date")
    imp.add_argument("--archive-dir", default="data/official_sources")
    imp.add_argument("--database-url", default=os.getenv("DATABASE_URL", "sqlite:///./nexyra.db"))
    args = parser.parse_args(argv)
    engine = create_engine(args.database_url, future=True)
    try:
        result = import_official_text_file(engine, args.file, source_url=args.source_url,
            title=args.title, reported_publication_date=args.reported_publication_date,
            archive_dir=args.archive_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (DataUnavailable, OSError, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
