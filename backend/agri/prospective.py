"""Append-only prospective price capture, isolated from canonical observations."""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import uuid
from uuid import UUID
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from dotenv import dotenv_values
from sqlalchemy import (Column, Date, Float, Integer, MetaData, String,
                        Table, Text, UniqueConstraint, create_engine, inspect, select)

from .data import DataUnavailable

metadata = MetaData()
runs = Table(
    "agri_prospective_ingestion_runs", metadata,
    Column("run_id", String(36), primary_key=True),
    Column("source_kind", String(32), nullable=False),
    Column("source_url", Text, nullable=False),
    Column("retrieval_method", String(64), nullable=False),
    Column("retrieved_at_utc", String(40), nullable=False),
    Column("raw_sha256", String(64), nullable=False),
    Column("raw_payload", Text, nullable=False),
    Column("status", String(32), nullable=False),
    Column("record_count", Integer, nullable=False),
    Column("validation_errors_json", Text, nullable=False),
)
observations = Table(
    "agri_prospective_observations", metadata,
    Column("observation_id", String(64), primary_key=True),
    Column("market_id", String(255), nullable=False),
    Column("market_label", String(512), nullable=False),
    Column("commodity_id", String(255), nullable=False),
    Column("commodity", String(255), nullable=False),
    Column("variety_id", String(255), nullable=True),
    Column("variety", String(255), nullable=False),
    Column("grade_id", String(255), nullable=True),
    Column("grade", String(255), nullable=False),
    Column("observation_date", Date, nullable=False),
    Column("modal_price", Float, nullable=False),
    Column("min_price", Float, nullable=False),
    Column("max_price", Float, nullable=False),
    Column("source_unit", String(128), nullable=False),
    Column("source_publication_at_utc", String(40), nullable=True),
    Column("first_seen_at_utc", String(40), nullable=False),
    Column("latest_retrieved_at_utc", String(40), nullable=False),
    Column("latest_run_id", String(36), nullable=False),
    Column("revision_count", Integer, nullable=False),
    Column("status", String(32), nullable=False),
    UniqueConstraint("market_id", "commodity_id", "variety_id", "grade_id", "observation_date",
                     name="uq_agri_prospective_exact_identity_date"),
)
revisions = Table(
    "agri_prospective_revisions", metadata,
    Column("revision_id", String(64), primary_key=True),
    Column("observation_id", String(64), nullable=False),
    Column("revision_number", Integer, nullable=False),
    Column("run_id", String(36), nullable=False),
    Column("source_url", Text, nullable=False),
    Column("retrieval_method", String(64), nullable=False),
    Column("retrieved_at_utc", String(40), nullable=False),
    Column("source_publication_at_utc", String(40), nullable=True),
    Column("raw_sha256", String(64), nullable=False),
    Column("raw_record_json", Text, nullable=False),
    Column("record_sha256", String(64), nullable=False),
    Column("change_kind", String(32), nullable=False),
    Column("validation_errors_json", Text, nullable=False),
    UniqueConstraint("observation_id", "revision_number", name="uq_agri_prospective_revision_no"),
)
protocols = Table(
    "agri_prospective_protocols", metadata,
    Column("protocol_id", String(64), primary_key=True),
    Column("protocol_json", Text, nullable=False),
    Column("protocol_sha256", String(64), nullable=False),
    Column("frozen_at_utc", String(40), nullable=False),
    Column("status", String(32), nullable=False),
)

REQUIRED = ("market_id", "market_label", "commodity_id", "commodity", "variety", "grade",
            "observation_date", "min_price", "max_price", "modal_price", "source_unit")
IDENTITY = ("market_id", "commodity_id", "variety_id", "grade_id", "observation_date")
PROTOCOL_ID = "phase3e-prospective-v1"
OGD_RESOURCE_TITLE = "Variety-wise Daily Market Prices Data of Commodity"
OGD_EXPECTED_FIELDS = {
    "state", "district", "market", "commodity", "variety", "grade",
    "arrival_date", "min_price", "max_price", "modal_price", "commodity_code",
}
PROTOCOL = {
    "protocol_id": PROTOCOL_ID,
    "status": "frozen_before_future_targets",
    "series": {"market_label": "Lasalgaon (Niphad)", "commodity": "Onion",
               "variety": "Other", "grade": "FAQ",
               "market_source_id": None, "identity_note": "Exact pilot spelling only; source identifier must be verified before eligibility. No aliases or grade mappings."},
    "forecast_origins": "Every calendar day at 23:59:59 Asia/Kolkata",
    "horizons_calendar_days": [1, 3, 7],
    "targets": "Exact observation on origin + horizon; no interpolated prices; preserve unscored origins.",
    "feature_availability": "Only records with genuine source publication timestamp or prospective first_seen_at_utc no later than origin. Retrieval time is not source publication time. No seven-day retrospective proxy for prospective claims.",
    "splits": {"minimum_proper_training_rows": 60, "calibration_rows": 20,
               "validation": "Three chronological folds of 21 scored origins each",
               "test": "At least 21 scored origins per horizon; choose a future test boundary before its target outcomes are observed; targets strictly after 2024-12-10; require a new prospective holdout boundary once evaluation starts."},
    "revision_policy": "Append every retrieval to revision history. First-seen immutable. Corrections arriving after an origin are unavailable at that origin. Freeze the evaluated revision snapshot and report sensitivity to later corrections; never rewrite earlier as-of views.",
    "late_arrival_policy": "A record is eligible only from first_seen_at_utc unless an authoritative source publication timestamp is available and preserved; do not backdate retrieval.",
    "validation_policy": "No model training/selection in collection phase. Preserve raw payload, checksum, exact identifiers, source URL, retrieval method, unit, and all validation errors.",
    "holdout_populated": False,
}


def migrate(engine):
    """Create only new prospective tables; never alters existing agricultural tables."""
    metadata.create_all(engine)
    run_columns = {item["name"] for item in inspect(engine).get_columns(runs.name)}
    if "raw_payload" not in run_columns:
        with engine.begin() as conn:
            conn.exec_driver_sql(f"ALTER TABLE {runs.name} ADD COLUMN raw_payload TEXT")
    freeze_protocol(engine)


def freeze_protocol(engine):
    """Persist the protocol once; refuse silent edits to an established protocol."""
    text = _json(PROTOCOL)
    checksum = _sha(text)
    with engine.begin() as conn:
        existing = conn.execute(select(protocols).where(protocols.c.protocol_id == PROTOCOL_ID)).mappings().first()
        if existing and existing["protocol_sha256"] != checksum:
            raise DataUnavailable("Frozen prospective protocol differs from the persisted copy")
        if not existing:
            conn.execute(protocols.insert().values(
                protocol_id=PROTOCOL_ID, protocol_json=text, protocol_sha256=checksum,
                frozen_at_utc=datetime.now(timezone.utc).isoformat(), status="frozen_before_future_targets"))


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      default=lambda item: item.isoformat() if hasattr(item, "isoformat") else str(item))


def _sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode("utf-8")).hexdigest()


def _safe_source_url(value):
    parts = urlsplit(value)
    secret_names = {"api-key", "api_key", "apikey", "key", "token", "access_token"}
    query = [(name, item) for name, item in parse_qsl(parts.query, keep_blank_values=True)
             if name.casefold() not in secret_names]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def load_ogd_credentials(env_file=None, *, environ=None):
    """Read local OGD credentials without logging or printing their values."""
    path = Path(env_file) if env_file else Path(__file__).resolve().parents[2] / ".env"
    file_values = dotenv_values(path, encoding="utf-8")
    environment = os.environ if environ is None else environ
    return {
        name: environment.get(name) or file_values.get(name)
        for name in ("DATA_GOV_IN_API_KEY", "DATA_GOV_IN_RESOURCE_ID")
    }


def _validate_resource_id(resource_id):
    try:
        UUID(str(resource_id))
    except (ValueError, TypeError, AttributeError):
        raise DataUnavailable("Invalid OGD resource UUID") from None


def _transport_category(exc):
    if isinstance(exc, (httpx.TimeoutException,)):
        return "timeout"
    message = str(exc).casefold()
    if any(value in message for value in ("certificate verify failed", "ssl", "tls")):
        return "tls_failure"
    if any(value in message for value in ("name or service not known", "getaddrinfo failed",
                                           "nodename nor servname", "name resolution")):
        return "dns_failure"
    if "refused" in message:
        return "connection_refused"
    return "network_failure"


def _retry_delay(response, attempt, backoff_seconds):
    value = response.headers.get("Retry-After", "")
    try:
        return min(10.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return min(5.0, backoff_seconds * (2 ** attempt))


def _get_json(client, url, params, *, retries=2, backoff_seconds=0.5, sleep_fn=time.sleep):
    if not 0 <= retries <= 3 or backoff_seconds < 0:
        raise ValueError("Retries must be 0..3 and backoff must be non-negative")
    for attempt in range(retries + 1):
        try:
            response = client.get(url, params=params)
        except httpx.TransportError as exc:
            category = _transport_category(exc)
            if attempt < retries:
                sleep_fn(min(5.0, backoff_seconds * (2 ** attempt)))
                continue
            raise DataUnavailable(f"OGD {category}; no records were ingested") from None
        status = response.status_code
        if status == 429 or status >= 500:
            if attempt < retries:
                sleep_fn(_retry_delay(response, attempt, backoff_seconds))
                continue
            if status == 429:
                retry_after = response.headers.get("Retry-After", "")
                try:
                    retry_note = f"; Retry-After={min(3600, max(0, int(retry_after)))}s" if retry_after else ""
                except ValueError:
                    retry_note = ""
                raise DataUnavailable("OGD rate limit (HTTP 429); no records were ingested" + retry_note) from None
            raise DataUnavailable(f"OGD server error (HTTP {status}); no records were ingested") from None
        if status in (401, 403):
            raise DataUnavailable(f"OGD authentication/authorization failure (HTTP {status})") from None
        if status == 404:
            raise DataUnavailable("OGD resource not found (HTTP 404); verify the resource UUID") from None
        if status < 200 or status >= 300:
            raise DataUnavailable(f"OGD HTTP failure (HTTP {status}); no records were ingested") from None
        try:
            return response, response.json()
        except ValueError:
            raise DataUnavailable("OGD returned invalid JSON") from None
    raise DataUnavailable("OGD request failed; no records were ingested")


def _utc(value):
    if value in (None, ""):
        return None
    stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("source publication timestamp must include a timezone")
    return stamp.astimezone(timezone.utc)


def _parse_record(raw, capture_time=None):
    if not isinstance(raw, dict):
        return None, ["record must be a JSON object"]
    record = dict(raw)
    errors = []
    missing = [key for key in REQUIRED if record.get(key) in (None, "")]
    if missing:
        errors.append("missing required fields: " + ", ".join(missing))
    if errors:
        return None, errors
    try:
        raw_date = str(record["observation_date"]).strip()
        try:
            record["observation_date"] = date.fromisoformat(raw_date[:10])
        except ValueError:
            record["observation_date"] = datetime.strptime(raw_date, "%d/%m/%Y").date()
        for name in ("min_price", "max_price", "modal_price"):
            record[name] = float(str(record[name]).replace(",", ""))
            if not math.isfinite(record[name]) or record[name] < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if not record["min_price"] <= record["modal_price"] <= record["max_price"]:
            errors.append("invalid price ordering: require min_price <= modal_price <= max_price")
        for key in REQUIRED:
            if key not in {"observation_date", "min_price", "max_price", "modal_price"}:
                record[key] = str(record[key]).strip()
                if not record[key]:
                    errors.append(f"{key} cannot be blank")
        for key in ("variety_id", "grade_id"):
            record[key] = str(record[key]).strip() if record.get(key) not in (None, "") else None
        record["source_publication_at_utc"] = _utc(record.get("source_publication_at"))
        if record["source_publication_at_utc"] and record["source_publication_at_utc"] > (capture_time or datetime.now(timezone.utc)):
            errors.append("source publication timestamp is in the future relative to capture")
    except (ValueError, TypeError) as exc:
        errors.append(str(exc))
    return (record if not errors else None), errors


def ingest_records(engine, raw_records, *, source_kind, source_url, retrieval_method,
                   raw_bytes, retrieved_at=None):
    """Capture genuinely retrieved records, keeping duplicate polls and revisions auditable."""
    if source_kind not in {"official_api", "manual_file"}:
        raise ValueError("source_kind must be official_api or manual_file")
    if not source_url or not retrieval_method:
        raise ValueError("source_url and retrieval_method are required")
    captured = retrieved_at or datetime.now(timezone.utc)
    if captured.tzinfo is None:
        raise ValueError("retrieved_at must be timezone-aware UTC capture time")
    captured = captured.astimezone(timezone.utc)
    run_id = str(uuid.uuid4())
    raw_hash = _sha(raw_bytes)
    try:
        raw_payload = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise DataUnavailable("Raw source payload must be UTF-8 to preserve and audit it") from None
    errors = []
    parsed = []
    for index, raw in enumerate(raw_records, 1):
        record, row_errors = _parse_record(raw, captured)
        if row_errors:
            errors.append({"row": index, "errors": row_errors, "record": raw})
        else:
            parsed.append((index, raw, record))
    migrate(engine)
    inserted = revised = duplicate = 0
    batch_keys = {}
    with engine.begin() as conn:
        conn.execute(runs.insert().values(
            run_id=run_id, source_kind=source_kind, source_url=_safe_source_url(source_url),
            retrieval_method=retrieval_method, retrieved_at_utc=captured.isoformat(), raw_sha256=raw_hash,
            raw_payload=raw_payload,
            status="partial" if errors else "success", record_count=len(raw_records),
            validation_errors_json=_json(errors)))
        for index, raw, record in parsed:
            key_values = {name: record.get(name) for name in IDENTITY}
            row = conn.execute(select(observations).where(
                observations.c.market_id == key_values["market_id"],
                observations.c.commodity_id == key_values["commodity_id"],
                observations.c.variety_id.is_(None) if key_values["variety_id"] is None else observations.c.variety_id == key_values["variety_id"],
                observations.c.grade_id.is_(None) if key_values["grade_id"] is None else observations.c.grade_id == key_values["grade_id"],
                observations.c.observation_date == key_values["observation_date"])).mappings().first()
            content = {name: record.get(name) for name in (
                "market_id", "market_label", "commodity_id", "commodity", "variety_id", "variety",
                "grade_id", "grade", "observation_date", "modal_price", "min_price", "max_price", "source_unit")}
            record_hash = _sha(_json(content))
            batch_key = tuple(key_values[name] for name in IDENTITY)
            if batch_key in batch_keys and batch_keys[batch_key] != record_hash:
                errors.append({"row": index, "errors": ["conflicting duplicate identity/date within one capture; quarantined"]})
                continue
            batch_keys[batch_key] = record_hash
            if row and row["status"] == "identity_change":
                errors.append({"row": index, "errors": ["market/commodity/variety/grade label or unit changed for stable source IDs; quarantined"]})
                continue
            same_publication = (row and row["source_publication_at_utc"] ==
                                (record["source_publication_at_utc"].isoformat()
                                 if record["source_publication_at_utc"] else None))
            if row and all(row[name] == content[name] for name in content) and same_publication:
                duplicate += 1
                change_kind = "duplicate"
            elif row and (row["market_label"] != content["market_label"] or row["commodity"] != content["commodity"] or row["variety"] != content["variety"] or row["grade"] != content["grade"] or row["source_unit"] != content["source_unit"]):
                errors.append({"row": index, "errors": ["identity label or unit changed for stable source IDs; quarantined"]})
                continue
            elif row:
                revised += 1
                change_kind = "correction"
            else:
                inserted += 1
                change_kind = "initial"
            observation_id = row["observation_id"] if row else _sha(_json(key_values))
            revision_number = row["revision_count"] + 1 if row else 1
            revision_id = _sha(f"{observation_id}|{revision_number}|{run_id}")
            raw_record = _json(raw)
            if row is None:
                conn.execute(observations.insert().values(
                    observation_id=observation_id, **content,
                    source_publication_at_utc=record["source_publication_at_utc"].isoformat() if record["source_publication_at_utc"] else None,
                    first_seen_at_utc=captured.isoformat(), latest_retrieved_at_utc=captured.isoformat(),
                    latest_run_id=run_id, revision_count=1, status="valid"))
            elif change_kind == "correction":
                conn.execute(observations.update().where(observations.c.observation_id == observation_id).values(
                    **content, source_publication_at_utc=record["source_publication_at_utc"].isoformat() if record["source_publication_at_utc"] else None,
                    latest_retrieved_at_utc=captured.isoformat(), latest_run_id=run_id, revision_count=revision_number))
            else:
                conn.execute(observations.update().where(observations.c.observation_id == observation_id).values(
                    latest_retrieved_at_utc=captured.isoformat(), latest_run_id=run_id,
                    revision_count=revision_number))
            conn.execute(revisions.insert().values(
                revision_id=revision_id, observation_id=observation_id,
                revision_number=revision_number, run_id=run_id, source_url=_safe_source_url(source_url),
                retrieval_method=retrieval_method, retrieved_at_utc=captured.isoformat(),
                source_publication_at_utc=record["source_publication_at_utc"].isoformat() if record["source_publication_at_utc"] else None,
                raw_sha256=raw_hash, raw_record_json=raw_record, record_sha256=record_hash,
                change_kind=change_kind, validation_errors_json="[]"))
        if errors:
            conn.execute(runs.update().where(runs.c.run_id == run_id).values(
                status="partial" if inserted or revised or duplicate else "failed",
                validation_errors_json=_json(errors)))
    final_status = ("failed" if errors and not (inserted or revised or duplicate)
                    else "partial" if errors else "success")
    return {"run_id": run_id, "status": final_status,
            "inserted": inserted, "revised": revised, "duplicate": duplicate,
            "validation_errors": errors, "raw_sha256": raw_hash, "retrieved_at_utc": captured.isoformat()}


def import_manual_file(engine, path, *, source_url, retrieved_at=None):
    """Import a source export using the real capture time of this import, never observation dates."""
    path = Path(path)
    raw_bytes = path.read_bytes()
    captured = retrieved_at or datetime.now(timezone.utc)
    text = raw_bytes.decode("utf-8-sig")
    records = list(csv.DictReader(text.splitlines()))
    if not records:
        raise DataUnavailable("Manual source file has no data records")
    return ingest_records(engine, records, source_kind="manual_file", source_url=source_url,
                          retrieval_method=f"manual_csv_import:{path.name}", raw_bytes=raw_bytes,
                          retrieved_at=captured)


def _normalise_ogd_field(name):
    return "_".join(str(name).strip().casefold().replace("-", " ").split())


def _ogd_schema(payload):
    """Check API metadata and row field names against the catalog's expected shape."""
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        raise DataUnavailable("OGD response has no records array")
    title = payload.get("title") or payload.get("resource_title")
    if title != OGD_RESOURCE_TITLE:
        return False, False, title, []
    rows = payload["records"]
    if not rows:
        # An empty result has no row keys; the title alone cannot prove schema.
        return True, False, title, []
    if not all(isinstance(row, dict) for row in rows):
        raise DataUnavailable("OGD records contain a non-object row")
    fields = sorted({_normalise_ogd_field(key) for row in rows for key in row})
    return True, OGD_EXPECTED_FIELDS.issubset(fields), title, fields


def _map_ogd_record(raw):
    """Map only documented value fields; do not synthesize missing source IDs or units."""
    values = {_normalise_ogd_field(key): value for key, value in raw.items()}
    return {
        "market_label": values.get("market"),
        "commodity": values.get("commodity"),
        "commodity_id": values.get("commodity_code"),
        "variety": values.get("variety"),
        "grade": values.get("grade"),
        "observation_date": values.get("arrival_date"),
        "min_price": values.get("min_price"),
        "max_price": values.get("max_price"),
        "modal_price": values.get("modal_price"),
        "_source_record": raw,
    }


def collect_datagov(engine=None, *, resource_id, api_key, source_url=None, client=None,
                    retrieved_at=None, page_size=10, max_pages=1, filters=None,
                    ingest=False, sleep_fn=time.sleep):
    """Dry-run a bounded official OGD request; persist only with explicit ingest=True."""
    if not resource_id or not api_key:
        raise DataUnavailable("Provide a verified OGD resource ID and DATA_GOV_IN_API_KEY")
    _validate_resource_id(resource_id)
    if not 1 <= page_size <= 1000 or not 1 <= max_pages <= 100:
        raise DataUnavailable("page_size must be 1..1000 and max_pages must be 1..100")
    if ingest and (not filters or any(not str(k).strip() or not str(v).strip() for k, v in filters.items())):
        raise DataUnavailable("Ingestion requires at least one verified exact source filter")
    url = source_url or f"https://api.data.gov.in/resource/{resource_id}"
    own_client = client is None
    client = client or httpx.Client(timeout=45)
    try:
        all_records, raw_pages, field_names = [], [], []
        title = None
        title_verified = schema_valid = False
        expected_total = None
        for page in range(max_pages):
            params = {"api-key": api_key, "format": "json", "limit": page_size, "offset": page * page_size}
            params.update({f"filters[{name}]": value for name, value in (filters or {}).items()})
            response, payload = _get_json(client, url, params, sleep_fn=sleep_fn)
            raw_pages.append(response.content)
            page_title_ok, page_schema_ok, page_title, page_fields = _ogd_schema(payload)
            if page == 0:
                title_verified, schema_valid, title = page_title_ok, page_schema_ok, page_title
            elif (not page_title_ok or page_title != title or not page_schema_ok):
                raise DataUnavailable("OGD resource metadata or schema changed during pagination")
            field_names = sorted(set(field_names) | set(page_fields))
            batch = payload["records"]
            all_records.extend(batch)
            try:
                if payload.get("total") is not None:
                    expected_total = int(payload["total"])
            except (ValueError, TypeError):
                raise DataUnavailable("OGD total field is malformed") from None
            if len(batch) < page_size or (expected_total is not None and len(all_records) >= expected_total):
                break
        else:
            raise DataUnavailable("OGD pagination limit reached; incomplete capture rejected")
        payload_bytes = b"\n".join(raw_pages)
    finally:
        if own_client:
            client.close()
    verified = title_verified and schema_valid
    summary = {
        "status": "dry_run", "resource_title": title, "resource_verified": title_verified,
        "schema_valid": schema_valid, "record_count": len(all_records), "pages": len(raw_pages),
        "fields": field_names, "raw_sha256": _sha(payload_bytes),
        "expected_total": expected_total, "ingest_requested": bool(ingest),
    }
    if not verified:
        summary["status"] = "unverified_resource" if not title_verified else "unverified_schema"
        summary["detail"] = "No database write occurred; verify the official resource title and complete field schema."
        return summary
    if not ingest:
        return summary
    mapped = [_map_ogd_record(row) for row in all_records]
    return ingest_records(engine, mapped, source_kind="official_api", source_url=url,
                          retrieval_method="data.gov.in JSON resource API", raw_bytes=payload_bytes,
                          retrieved_at=retrieved_at)


def audit_integrity(engine):
    """Verify saved response bytes and each normalized revision against its checksum."""
    failures = []
    with engine.connect() as conn:
        for run in conn.execute(select(runs)).mappings():
            if run["raw_payload"] is None or _sha(run["raw_payload"].encode("utf-8")) != run["raw_sha256"]:
                failures.append({"kind": "raw_payload_checksum", "run_id": run["run_id"]})
        for revision in conn.execute(select(revisions)).mappings():
            try:
                raw = json.loads(revision["raw_record_json"])
                record, errors = _parse_record(raw, datetime.fromisoformat(revision["retrieved_at_utc"]))
                if errors or record is None:
                    raise ValueError("raw record no longer validates")
                content = {name: record.get(name) for name in (
                    "market_id", "market_label", "commodity_id", "commodity", "variety_id", "variety",
                    "grade_id", "grade", "observation_date", "modal_price", "min_price", "max_price", "source_unit")}
                if _sha(_json(content)) != revision["record_sha256"]:
                    raise ValueError("record checksum differs")
            except (ValueError, TypeError, json.JSONDecodeError):
                failures.append({"kind": "raw_record_checksum", "revision_id": revision["revision_id"]})
    return {"ok": not failures, "failures": failures}


def audit_calendar_gaps(engine, *, market_id, commodity_id, variety_id, grade_id):
    """Report unobserved calendar dates without calling them market closures."""
    clauses = [observations.c.market_id == market_id,
               observations.c.commodity_id == commodity_id,
               observations.c.observation_date.is_not(None)]
    clauses.append(observations.c.variety_id.is_(None) if variety_id is None else observations.c.variety_id == variety_id)
    clauses.append(observations.c.grade_id.is_(None) if grade_id is None else observations.c.grade_id == grade_id)
    with engine.connect() as conn:
        dates = [row[0] for row in conn.execute(select(observations.c.observation_date)
                                               .where(*clauses).distinct()
                                               .order_by(observations.c.observation_date))]
    if not dates:
        return {"observations": 0, "first_date": None, "last_date": None,
                "missing_calendar_dates": [], "closure_status": "unknown"}
    present = set(dates)
    cursor = dates[0]
    missing = []
    from datetime import timedelta
    while cursor < dates[-1]:
        cursor += timedelta(days=1)
        if cursor not in present:
            missing.append(cursor.isoformat())
    return {"observations": len(dates), "first_date": dates[0].isoformat(),
            "last_date": dates[-1].isoformat(), "missing_calendar_dates": missing,
            "closure_status": "unknown; gaps are not classified as closures"}


def _engine(database_url):
    return create_engine(database_url, future=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Capture prospective agricultural observations (no model training)")
    subs = parser.add_subparsers(dest="command", required=True)
    initialize = subs.add_parser("initialize", help="Create isolated prospective tables and freeze protocol")
    initialize.add_argument("--database-url", default=os.getenv("DATABASE_URL", "sqlite:///./nexyra.db"))
    manual = subs.add_parser("import-csv")
    manual.add_argument("--file", required=True)
    manual.add_argument("--source-url", required=True)
    manual.add_argument("--database-url", default=os.getenv("DATABASE_URL", "sqlite:///./nexyra.db"))
    api = subs.add_parser("collect-datagov")
    api.add_argument("--resource-id")
    api.add_argument("--database-url", default=os.getenv("DATABASE_URL", "sqlite:///./nexyra.db"))
    api.add_argument("--filter", action="append", default=[],
                     help="Exact source field filter field=value; repeat after verifying field names")
    api.add_argument("--page-size", type=int, default=10)
    api.add_argument("--max-pages", type=int, default=1)
    api.add_argument("--ingest", action="store_true",
                     help="Persist only after resource title/schema verification; dry-run is the default")
    integrity = subs.add_parser("audit-integrity")
    integrity.add_argument("--database-url", default=os.getenv("DATABASE_URL", "sqlite:///./nexyra.db"))
    gaps = subs.add_parser("audit-gaps")
    gaps.add_argument("--database-url", default=os.getenv("DATABASE_URL", "sqlite:///./nexyra.db"))
    gaps.add_argument("--market-id", required=True)
    gaps.add_argument("--commodity-id", required=True)
    gaps.add_argument("--variety-id")
    gaps.add_argument("--grade-id")
    args = parser.parse_args(argv)
    try:
        engine = _engine(args.database_url)
        if args.command == "initialize":
            migrate(engine)
            with engine.connect() as conn:
                record = conn.execute(select(protocols).where(protocols.c.protocol_id == PROTOCOL_ID)).mappings().one()
            result = {"status": "initialized", "protocol_id": PROTOCOL_ID,
                      "protocol_sha256": record["protocol_sha256"], "holdout_populated": False}
        elif args.command == "import-csv":
            result = import_manual_file(engine, args.file, source_url=args.source_url)
        elif args.command == "audit-integrity":
            result = audit_integrity(engine)
        elif args.command == "audit-gaps":
            result = audit_calendar_gaps(engine, market_id=args.market_id, commodity_id=args.commodity_id,
                                         variety_id=args.variety_id, grade_id=args.grade_id)
        else:
            credentials = load_ogd_credentials()
            resource_id = args.resource_id or credentials.get("DATA_GOV_IN_RESOURCE_ID")
            api_key = credentials.get("DATA_GOV_IN_API_KEY")
            if not api_key:
                raise DataUnavailable("Missing DATA_GOV_IN_API_KEY in .env or environment")
            if not resource_id:
                raise DataUnavailable("Missing DATA_GOV_IN_RESOURCE_ID; configure only after verifying the official UUID")
            filters = {}
            for expression in args.filter:
                if "=" not in expression:
                    raise ValueError("Each --filter must use field=value")
                name, value = expression.split("=", 1)
                if not name.strip() or not value.strip():
                    raise ValueError("Each --filter must include a field and exact value")
                filters[name.strip()] = value.strip()
            if args.ingest and not filters:
                raise ValueError("At least one verified exact --filter is required for ingestion")
            result = collect_datagov(engine, resource_id=resource_id, api_key=api_key,
                                     filters=filters, page_size=args.page_size, max_pages=args.max_pages,
                                     ingest=args.ingest, **({"engine": engine} if args.ingest else {}))
        print(json.dumps(result, indent=2, default=str))
        return 1 if result.get("ok") is False else 2 if result.get("status") == "failed" else 0
    except (DataUnavailable, OSError, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
