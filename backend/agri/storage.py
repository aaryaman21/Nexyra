"""Additive SQLAlchemy migration and parameterized agricultural CSV ingestion."""
from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path

from sqlalchemy import (Column, Date, DateTime, Float, ForeignKey, Integer, MetaData,
                        String, Table, Text, UniqueConstraint, select, inspect, Boolean)

from .data import DataUnavailable, read_prices
from .registry import digest

metadata = MetaData()
migrations = Table("agri_schema_versions", metadata, Column("version", Integer, primary_key=True))
commodities = Table("agri_commodities", metadata, Column("id", String, primary_key=True), Column("name", String, nullable=False))
mandis = Table("agri_mandis", metadata, Column("id", String, primary_key=True), Column("market", String, nullable=False),
               Column("district", String, nullable=False), Column("state", String, nullable=False))
prices = Table("agri_daily_prices", metadata, Column("id", Integer, primary_key=True),
               Column("series_id", String, ForeignKey("agri_mandis.id"), nullable=False, index=True),
               Column("commodity_id", String, ForeignKey("agri_commodities.id"), nullable=False),
               Column("variety", String, nullable=False), Column("date", Date, nullable=False, index=True),
               Column("min_price", Float, nullable=False), Column("max_price", Float, nullable=False),
               Column("modal_price", Float, nullable=False), Column("unit", String, nullable=False),
               Column("source", String, nullable=False), Column("available_at", DateTime(timezone=True), nullable=False),
               Column("record_key", String, nullable=True, unique=True),
               Column("grade", String, nullable=True), Column("price_date", Date, nullable=True),
               Column("arrival_date", Date, nullable=True), Column("arrival_quantity", Float, nullable=True),
               Column("arrival_unit", String, nullable=True), Column("source_record", Text, nullable=True),
               UniqueConstraint("series_id", "date", name="uq_agri_series_date"))
weather = Table("agri_weather_daily", metadata, Column("id", Integer, primary_key=True),
                Column("mandi_id", String, ForeignKey("agri_mandis.id"), nullable=False), Column("date", Date, nullable=False),
                Column("available_at", DateTime(timezone=True), nullable=False), Column("source", String, nullable=False),
                Column("payload", Text, nullable=False), UniqueConstraint("mandi_id", "date", "source"))
articles = Table("agri_news_articles", metadata, Column("id", String, primary_key=True),
                 Column("url", Text, nullable=False), Column("title", Text, nullable=False),
                 Column("published_at", DateTime(timezone=True), nullable=False, index=True),
                 Column("available_at", DateTime(timezone=True), nullable=False), Column("metadata_json", Text))
events = Table("agri_news_events", metadata, Column("id", String, primary_key=True),
               Column("article_id", String, ForeignKey("agri_news_articles.id"), nullable=False),
               Column("series_id", String, ForeignKey("agri_mandis.id"), nullable=False, index=True),
               Column("category", String, nullable=False), Column("payload", Text, nullable=False))
runs = Table("agri_forecast_runs", metadata, Column("id", String, primary_key=True),
             Column("version", String, nullable=False), Column("created_at", DateTime(timezone=True), nullable=False))
predictions = Table("agri_predictions", metadata, Column("id", Integer, primary_key=True),
                    Column("run_id", String, ForeignKey("agri_forecast_runs.id"), nullable=False),
                    Column("horizon", Integer, nullable=False), Column("target_date", Date, nullable=False),
                    Column("prediction", Float, nullable=False), Column("lower", Float), Column("upper", Float),
                    UniqueConstraint("run_id", "horizon"))
evaluations = Table("agri_model_evaluations", metadata, Column("version", String, primary_key=True),
                    Column("horizon", Integer, primary_key=True), Column("payload", Text, nullable=False))
logs = Table("agri_ingestion_logs", metadata, Column("id", Integer, primary_key=True),
             Column("created_at", DateTime(timezone=True), nullable=False), Column("status", String, nullable=False),
             Column("source_sha256", String), Column("details", Text, nullable=False))

# Historical Kaggle observations are intentionally isolated from the canonical
# inference/training table because source availability timestamps are unknown.
historical_prices = Table(
    "agri_historical_price_observations", metadata,
    Column("id", Integer, primary_key=True),
    Column("record_key", String(64), nullable=False, unique=True),
    Column("source_file", String(255), nullable=False),
    Column("source_row_number", Integer, nullable=False),
    Column("source_sha256", String(64), nullable=False),
    Column("source_url", Text, nullable=False),
    Column("source_publisher", String(255), nullable=False),
    Column("source_attribution_claim", String(255), nullable=False),
    Column("state", String(255), nullable=False),
    Column("district", String(255), nullable=False),
    Column("market_original", String(512), nullable=False),
    Column("market_normalized", String(512), nullable=False),
    Column("commodity", String(255), nullable=False),
    Column("commodity_code", String(64), nullable=False),
    Column("variety", String(255), nullable=False),
    Column("grade", String(255), nullable=False),
    Column("observation_date", Date, nullable=False),
    Column("min_price", Float, nullable=False),
    Column("max_price", Float, nullable=False),
    Column("modal_price", Float, nullable=False),
    Column("price_unit", String(64), nullable=False),
    Column("price_unit_status", String(64), nullable=False),
    Column("verified_available_at", DateTime(timezone=True), nullable=True),
    Column("availability_status", String(64), nullable=False),
    Column("retrospective_policy", String(255), nullable=True),
    Column("review_status", String(64), nullable=False),
    Column("quarantine_reason", Text, nullable=True),
    Column("source_record", Text, nullable=False),
    Column("ingested_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("state", "district", "market_original", "commodity", "variety", "grade",
                     "observation_date", name="uq_agri_historical_exact_source_series_date"),
)

HISTORICAL_SOURCE_URL = "https://www.kaggle.com/datasets/khandelwalmanas/daily-commodity-prices-india"
HISTORICAL_PUBLISHER = "khandelwalmanas (Kaggle)"


def migrate(engine):
    metadata.create_all(engine)
    existing = {column["name"] for column in inspect(engine).get_columns("agri_daily_prices")}
    additions = {
        "record_key": "VARCHAR(64)", "grade": "VARCHAR(255)", "price_date": "DATE",
        "arrival_date": "DATE", "arrival_quantity": "FLOAT", "arrival_unit": "VARCHAR(64)",
        "source_record": "TEXT",
    }
    with engine.begin() as conn:
        for name, sql_type in additions.items():
            if name not in existing:
                conn.exec_driver_sql(f"ALTER TABLE agri_daily_prices ADD COLUMN {name} {sql_type}")
    with engine.begin() as conn:
        for version in (1, 2, 3):
            if conn.execute(select(migrations.c.version).where(migrations.c.version == version)).first() is None:
                conn.execute(migrations.insert().values(version=version))


def _historical_record_key(record):
    identity = "|".join((record["state"].casefold(), record["district"].casefold(),
                         record["market_original"], record["commodity"].casefold(),
                         record["variety"], record["grade"], record["observation_date"].isoformat()))
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def normalize_market_label(value):
    """Normalize whitespace only; preserve suffixes, punctuation and market identity."""
    return " ".join(value.split())


def retrospective_assumed_available_at(observation_date, delay_days=7):
    """Research-only availability proxy; never a verified timestamp or stored value."""
    from datetime import date, time, timedelta
    from zoneinfo import ZoneInfo

    if not isinstance(delay_days, int) or delay_days < 1:
        raise ValueError("Research availability delay must be a positive whole number of days")
    if isinstance(observation_date, str):
        observation_date = date.fromisoformat(observation_date)
    assumed_day = observation_date + timedelta(days=delay_days)
    return datetime.combine(assumed_day, time.max, tzinfo=ZoneInfo("Asia/Kolkata")).astimezone(timezone.utc)


def _alias_candidate_label(value):
    """Diagnostic-only alias key; it never changes or joins stored market labels."""
    import re
    without_apmc = re.sub(r"\s+APMC\s*$", "", value, flags=re.IGNORECASE)
    return re.sub(r"[^a-z0-9]", "", without_apmc.casefold())


def ingest_historical_nashik(engine, paths, *, commit=False, chunk_size=100_000,
                              retrospective_policy=None, expected_sha256=None):
    """Chunked dry-run/import for the Kaggle historical CSV collection.

    Dry-run performs no migration or database writes. A commit uses one SQL
    transaction and imports only to the isolated historical table.
    """
    import math
    from datetime import date
    import pandas as pd

    paths = [Path(path) for path in paths]
    file_meta = {}
    for path in paths:
        hasher = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
                hasher.update(block)
        file_meta[path.name] = {"sha256": hasher.hexdigest(), "bytes": path.stat().st_size}
        if expected_sha256 and expected_sha256.get(path.name) != file_meta[path.name]["sha256"]:
            raise DataUnavailable(f"Historical source checksum differs from approved provenance manifest: {path.name}")

    summary = {"source_rows": 0, "eligible_rows": 0, "quarantined_rows": 0,
               "inserted": 0, "skipped": 0, "duplicates": 0, "conflicts": 0,
               "rows_by_year_market_variety_grade": {}, "file_summary": {},
               "dry_run": not commit,
               "retrospective_availability_policy": retrospective_policy or
               "None: availability remains unknown; no retrospective timestamp assigned"}
    seen = set()
    exact_existing = {}
    canonical_signatures = {}
    if "agri_daily_prices" in inspect(engine).get_table_names():
        with engine.connect() as read_conn:
            rows = read_conn.execute(select(prices, mandis.c.market, mandis.c.district,
                                           mandis.c.state, commodities.c.name.label("commodity_name"))
                                     .join(mandis, prices.c.series_id == mandis.c.id)
                                     .join(commodities, prices.c.commodity_id == commodities.c.id)
                                     .where(prices.c.record_key.is_not(None))).mappings()
            for canonical in rows:
                sig = (canonical["state"].casefold(), canonical["district"].casefold(),
                       canonical["commodity_name"].casefold(), canonical["variety"], canonical["grade"] or "",
                       canonical["price_date"] or canonical["date"],
                       _alias_candidate_label(canonical["market"]))
                canonical_signatures.setdefault(sig, []).append(canonical)
    if commit and "agri_historical_price_observations" in inspect(engine).get_table_names():
        migrate(engine)
        with engine.connect() as conn:
            exact_existing = {row["record_key"]: row for row in conn.execute(select(historical_prices)).mappings()}
    elif commit:
        migrate(engine)
    transaction = engine.begin() if commit else None
    try:
        conn = transaction.__enter__() if transaction else None
        for path in paths:
            file_rows = 0
            eligible_rows = quarantined_rows = 0
            date_min, date_max = None, None
            file_date_min, file_date_max = None, None
            expected = ["State", "District", "Market", "Commodity", "Variety", "Grade",
                        "Arrival_Date", "Min_Price", "Max_Price", "Modal_Price", "Commodity_Code"]
            row_offset = 2
            for chunk in pd.read_csv(path, dtype=str, keep_default_na=False, chunksize=chunk_size,
                                     encoding="utf-8-sig"):
                if list(chunk.columns) != expected:
                    raise DataUnavailable(f"Unexpected header in {path.name}: {list(chunk.columns)}")
                file_rows += len(chunk)
                parsed_dates = pd.to_datetime(chunk["Arrival_Date"], format="%Y-%m-%d", errors="coerce")
                valid_dates = parsed_dates.dropna()
                if not valid_dates.empty:
                    chunk_min, chunk_max = valid_dates.min().date(), valid_dates.max().date()
                    file_date_min = min(file_date_min, chunk_min) if file_date_min else chunk_min
                    file_date_max = max(file_date_max, chunk_max) if file_date_max else chunk_max
                eligible_mask = (chunk["State"].str.strip().str.casefold().eq("maharashtra") &
                                 chunk["District"].str.strip().str.casefold().eq("nashik") &
                                 chunk["Commodity"].str.strip().str.casefold().eq("onion"))
                eligible_chunk = chunk.loc[eligible_mask]
                for source_index, values in eligible_chunk.iterrows():
                    chunk_row_index = int(source_index - chunk.index[0])
                    row_number = row_offset + chunk_row_index
                    row = values
                    state, district = row["State"].strip(), row["District"].strip()
                    commodity = row["Commodity"].strip()
                    market_original = row["Market"]
                    market_normalized = normalize_market_label(market_original)
                    if not market_original.strip():
                        raise DataUnavailable(f"Empty source market in {path.name}:{row_number}")
                    variety, grade = row["Variety"].strip(), row["Grade"].strip()
                    commodity_code = row["Commodity_Code"].strip()
                    if not variety or not grade or not commodity_code:
                        raise DataUnavailable(f"Missing series field in {path.name}:{row_number}")
                    try:
                        observation_date = date.fromisoformat(row["Arrival_Date"].strip())
                        min_price, max_price, modal_price = (float(row[c].strip()) for c in
                                                              ("Min_Price", "Max_Price", "Modal_Price"))
                    except (ValueError, TypeError, AttributeError):
                        raise DataUnavailable(f"Invalid date/price in {path.name}:{row_number}") from None
                    if not all(math.isfinite(v) and v >= 0 for v in (min_price, max_price, modal_price)) or not min_price <= modal_price <= max_price:
                        raise DataUnavailable(f"Invalid price range in {path.name}:{row_number}")
                    record = {
                        "source_file": path.name, "source_row_number": row_number,
                        "source_sha256": file_meta[path.name]["sha256"], "source_url": HISTORICAL_SOURCE_URL,
                        "source_publisher": HISTORICAL_PUBLISHER,
                        "source_attribution_claim": "AGMARKNET (publisher claim; not independently verified)",
                        "state": state, "district": district, "market_original": market_original,
                        "market_normalized": market_normalized, "commodity": commodity,
                        "commodity_code": commodity_code, "variety": variety, "grade": grade,
                        "observation_date": observation_date, "min_price": min_price,
                        "max_price": max_price, "modal_price": modal_price,
                        "price_unit": "INR/quintal", "price_unit_status": "provisional",
                        "verified_available_at": None, "availability_status": "unknown",
                        "retrospective_policy": retrospective_policy,
                        "review_status": "eligible_historical",
                        "quarantine_reason": None,
                        "source_record": json.dumps({name: str(value) for name, value in row.items()},
                                                    ensure_ascii=False, sort_keys=True),
                    }
                    key = _historical_record_key(record)
                    record["record_key"] = key
                    sig = (state.casefold(), district.casefold(), commodity.casefold(), variety, grade,
                           observation_date, _alias_candidate_label(market_original))
                    candidates = canonical_signatures.get(sig, [])
                    is_quarantined = bool(candidates and any(c["market"] != market_original for c in candidates))
                    for candidate in candidates:
                        if any(float(candidate[col]) != record[field] for col, field in
                               (("min_price", "min_price"), ("max_price", "max_price"), ("modal_price", "modal_price"))):
                            summary["conflicts"] += 1
                            raise DataUnavailable(f"Conflicting canonical overlap for {market_original} on {observation_date}")
                    if is_quarantined:
                        record["review_status"] = "quarantined_alias_candidate"
                        record["quarantine_reason"] = "Candidate overlaps canonical Lasalgaon observation under an unresolved market-label alias"
                        summary["quarantined_rows"] += 1
                        quarantined_rows += 1
                    else:
                        record["review_status"] = "eligible_historical"
                        summary["eligible_rows"] += 1
                        eligible_rows += 1
                    summary["source_rows"] += 1
                    year_key = f"{observation_date.year}|{market_original}|{variety}|{grade}"
                    summary["rows_by_year_market_variety_grade"][year_key] = summary["rows_by_year_market_variety_grade"].get(year_key, 0) + 1
                    date_min = min(date_min, observation_date) if date_min else observation_date
                    date_max = max(date_max, observation_date) if date_max else observation_date
                    if key in seen:
                        summary["duplicates"] += 1
                        raise DataUnavailable(f"Duplicate historical record key in source: {path.name}:{row_number}")
                    seen.add(key)
                    existing = exact_existing.get(key)
                    if existing:
                        comparable = ("source_sha256", "state", "district", "market_original", "commodity", "commodity_code",
                                      "market_normalized", "variety", "grade", "observation_date", "min_price", "max_price",
                                      "modal_price", "price_unit", "price_unit_status", "availability_status",
                                      "review_status", "quarantine_reason", "retrospective_policy", "source_record")
                        if any(existing[name] != record[name] for name in comparable):
                            summary["conflicts"] += 1
                            raise DataUnavailable(f"Conflicting existing historical key {key}")
                        summary["skipped"] += 1
                        continue
                    if conn is not None:
                        record["ingested_at"] = datetime.now(timezone.utc)
                        conn.execute(historical_prices.insert().values(**record))
                        summary["inserted"] += 1
                row_offset += len(chunk)
            summary["file_summary"][path.name] = {**file_meta[path.name], "rows": file_rows,
                "eligible_rows": eligible_rows, "quarantined_rows": quarantined_rows,
                "eligible_date_range": [date_min.isoformat(), date_max.isoformat()] if date_min else None,
                "file_date_range": [file_date_min.isoformat(), file_date_max.isoformat()] if file_date_min else None}
        if commit:
            transaction.__exit__(None, None, None)
            transaction = None
    except Exception as exc:
        if transaction:
            transaction.__exit__(type(exc), exc, exc.__traceback__)
        raise
    return summary


def read_agmarknet_daily(path):
    """Parse the source's title + column-header + data-row CSV export."""
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 3:
        raise DataUnavailable("Daily AGMARKNET report must include title, header, and data rows")
    title_row, header, *body = rows
    if len(header) != 14 or header != [
        "State/UT", "District", "Market", "Commodity Group", "Commodity", "Variety", "Grade",
        "Min Price", "Max Price", "Modal Price", "Price Unit", "Arrival Quantity", "Arrival Unit", "Arrival Date",
    ]:
        raise DataUnavailable("Unexpected AGMARKNET daily report header")
    title = next((value.strip() for value in title_row if value.strip()), "")
    records = []
    for line, values in enumerate(body, start=3):
        if not values or all(not value.strip() for value in values):
            continue
        if len(values) != 14:
            raise DataUnavailable(f"Expected 14 columns on report row {line}")
        source = dict(zip(header, values))
        for name in ("State/UT", "District", "Market", "Commodity Group", "Commodity", "Variety", "Grade", "Price Unit", "Arrival Unit"):
            source[name] = source[name].strip()
            if not source[name]:
                raise DataUnavailable(f"Missing {name} on report row {line}")
        date = datetime.strptime(source["Arrival Date"].strip(), "%d-%m-%Y").date()
        numbers = {}
        for name in ("Min Price", "Max Price", "Modal Price", "Arrival Quantity"):
            try:
                numbers[name] = float(source[name].replace(",", "").strip())
            except (ValueError, AttributeError):
                raise DataUnavailable(f"Invalid {name} on report row {line}") from None
        if source["Price Unit"].lower() not in {"rs./quintal", "inr/quintal"}:
            raise DataUnavailable(f"Unexpected price unit on report row {line}")
        if source["Arrival Unit"].lower() not in {"metric tonnes", "metric tons"}:
            raise DataUnavailable(f"Unexpected arrival unit on report row {line}")
        if numbers["Min Price"] < 0 or not numbers["Min Price"] <= numbers["Modal Price"] <= numbers["Max Price"] or numbers["Arrival Quantity"] < 0:
            raise DataUnavailable(f"Invalid price range or arrival quantity on report row {line}")
        # The export supplies one Arrival Date for each daily price/arrival record.
        # If a future export provides a distinct Price Date, parse and retain it separately.
        price_date = datetime.strptime(source.get("Price Date", source["Arrival Date"]).strip(), "%d-%m-%Y").date()
        normalized_market = source["Market"]
        identity = "|".join((source["State/UT"].casefold(), source["District"].casefold(), normalized_market.casefold(), source["Commodity"].casefold(), source["Variety"].casefold(), source["Grade"].casefold()))
        series_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
        key_text = "|".join((normalized_market.casefold(), source["Commodity"].casefold(), source["Variety"].casefold(), source["Grade"].casefold(), price_date.isoformat()))
        record_key = hashlib.sha256(key_text.encode("utf-8")).hexdigest()
        records.append({
            "series_id": series_id, "market": normalized_market, "district": source["District"],
            "state": source["State/UT"], "commodity": source["Commodity"], "variety": source["Variety"],
            "grade": source["Grade"], "price_date": price_date, "arrival_date": date,
            "min_price": numbers["Min Price"], "max_price": numbers["Max Price"],
            "modal_price": numbers["Modal Price"], "price_unit": "INR/quintal",
            "arrival_quantity": numbers["Arrival Quantity"], "arrival_unit": "metric tonnes",
            "source": title or Path(path).name, "source_record": json.dumps(source, ensure_ascii=False, sort_keys=True),
            "record_key": record_key,
        })
    keys = [record["record_key"] for record in records]
    if len(keys) != len(set(keys)):
        raise DataUnavailable("Duplicate market/commodity/variety/grade/price-date records in source")
    return records


def ingest_agmarknet_daily(engine, path):
    migrate(engine)
    records = read_agmarknet_daily(path)
    inserted = skipped = 0
    source_hash = digest(path)
    try:
        with engine.begin() as conn:
            for record in records:
                if not conn.execute(select(commodities.c.id).where(commodities.c.id == record["commodity"].casefold())).first():
                    conn.execute(commodities.insert().values(id=record["commodity"].casefold(), name=record["commodity"]))
                if not conn.execute(select(mandis.c.id).where(mandis.c.id == record["series_id"])).first():
                    conn.execute(mandis.insert().values(id=record["series_id"], market=record["market"], district=record["district"], state=record["state"]))
                existing = conn.execute(select(prices).where(prices.c.record_key == record["record_key"])).mappings().first()
                values = {
                    "series_id": record["series_id"], "commodity_id": record["commodity"].casefold(),
                    "variety": record["variety"], "date": record["price_date"],
                    "min_price": record["min_price"], "max_price": record["max_price"],
                    "modal_price": record["modal_price"], "unit": record["price_unit"],
                    "source": record["source"], "available_at": datetime.combine(record["arrival_date"], datetime.max.time(), tzinfo=timezone.utc),
                    "record_key": record["record_key"], "grade": record["grade"],
                    "price_date": record["price_date"], "arrival_date": record["arrival_date"],
                    "arrival_quantity": record["arrival_quantity"], "arrival_unit": record["arrival_unit"],
                    "source_record": record["source_record"],
                }
                if existing:
                    if any(existing[key] != value for key, value in values.items() if key not in {"available_at", "source_record"}):
                        raise DataUnavailable(f"Conflicting stored observation for {record['record_key']}")
                    skipped += 1
                    continue
                conn.execute(prices.insert().values(**values))
                inserted += 1
            conn.execute(logs.insert().values(created_at=datetime.now(timezone.utc), status="success", source_sha256=source_hash,
                                               details=json.dumps({"inserted": inserted, "skipped": skipped, "source": str(path)})))
    except (ValueError, OSError) as exc:
        with engine.begin() as conn:
            conn.execute(logs.insert().values(created_at=datetime.now(timezone.utc), status="failed", source_sha256=source_hash, details=str(exc)))
        raise
    return {"inserted": inserted, "skipped": skipped, "source_records": len(records)}


def audit_agmarknet_daily(engine):
    with engine.connect() as conn:
        total = conn.execute(select(prices.c.id).where(prices.c.record_key.is_not(None))).all()
        rows = conn.execute(select(prices, mandis.c.market, commodities.c.name.label("commodity_name"))
                            .join(mandis, prices.c.series_id == mandis.c.id)
                            .join(commodities, prices.c.commodity_id == commodities.c.id)
                            .where(prices.c.record_key.is_not(None))).mappings().all()
        per_variety = {}
        for row in rows:
            item = per_variety.setdefault(row["variety"], {"count": 0, "start": row["price_date"].isoformat(), "end": row["price_date"].isoformat()})
            item["count"] += 1
            item["start"] = min(item["start"], row["price_date"].isoformat())
            item["end"] = max(item["end"], row["price_date"].isoformat())
        return {"database_rows": len(total), "date_start": min((r["price_date"] for r in rows), default=None),
                "date_end": max((r["price_date"] for r in rows), default=None), "observations_per_variety": per_variety}


def ingest_csv(engine, path):
    migrate(engine)
    inserted = 0
    try:
        frame = read_prices(path)
        with engine.begin() as conn:
            if not conn.execute(select(commodities.c.id).where(commodities.c.id == "onion")).first():
                conn.execute(commodities.insert().values(id="onion", name="Onion"))
            for sid, group in frame.groupby("series_id"):
                first = group.iloc[0]
                if not conn.execute(select(mandis.c.id).where(mandis.c.id == sid)).first():
                    conn.execute(mandis.insert().values(id=sid, market=first.market, district=first.district, state=first.state))
                for row in group.itertuples():
                    existing = conn.execute(select(prices).where(prices.c.series_id == sid, prices.c.date == row.date.date())).mappings().first()
                    if existing:
                        if any(existing[key] != getattr(row, key) for key in ("min_price", "max_price", "modal_price", "source", "unit", "variety")):
                            raise DataUnavailable("Conflicting stored observation; corrections require explicit review")
                        continue
                    conn.execute(prices.insert().values(series_id=sid, commodity_id="onion", variety=row.variety,
                                 date=row.date.date(), min_price=row.min_price, max_price=row.max_price,
                                 modal_price=row.modal_price, unit=row.unit, source=row.source,
                                 available_at=row.available_at.ceil("us").to_pydatetime()))
                    inserted += 1
            conn.execute(logs.insert().values(created_at=datetime.now(timezone.utc), status="success", source_sha256=digest(path), details=json.dumps({"inserted": inserted})))
        return {"inserted": inserted, "series": int(frame.series_id.nunique())}
    except (ValueError, OSError) as exc:
        with engine.begin() as conn:
            conn.execute(logs.insert().values(created_at=datetime.now(timezone.utc), status="failed", details=str(exc)))
        raise


if __name__ == "__main__":
    import argparse
    from backend.app.models.database import engine
    parser = argparse.ArgumentParser()
    parser.add_argument("--prices")
    parser.add_argument("--agmarknet-daily")
    parser.add_argument("--historical-dir")
    parser.add_argument("--historical-manifest")
    parser.add_argument("--historical-dry-run", action="store_true")
    parser.add_argument("--historical-import", action="store_true")
    args = parser.parse_args()
    if args.historical_dir:
        paths = sorted(Path(args.historical_dir).glob("20[0-9][0-9].csv"))
        if len(paths) != 5:
            parser.error(f"Expected five annual CSVs, found {len(paths)}")
        manifest_path = Path(args.historical_manifest) if args.historical_manifest else Path(__file__).resolve().parents[2] / "docs" / "agri_historical_provenance_manifest.json"
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        expected_hashes = {entry["filename"]: entry["sha256"] for entry in manifest_data["files"]}
        result = ingest_historical_nashik(engine, paths, commit=args.historical_import,
                                          expected_sha256=expected_hashes)
        print(json.dumps(result, indent=2, default=str))
    elif args.agmarknet_daily:
        result = ingest_agmarknet_daily(engine, args.agmarknet_daily)
        result["audit"] = audit_agmarknet_daily(engine)
        print(json.dumps(result, indent=2, default=str))
    elif args.prices:
        print(json.dumps(ingest_csv(engine, args.prices)))
    else:
        migrate(engine)
        print("Applied additive agricultural schema version 1")
