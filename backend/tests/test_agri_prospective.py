import json
import hashlib
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy import create_engine, select

from backend.agri.prospective import (
    OGD_EXPECTED_FIELDS, OGD_RESOURCE_TITLE, PROTOCOL_ID, audit_calendar_gaps, audit_integrity, collect_datagov, freeze_protocol,
    import_manual_file, ingest_records,
    observations, protocols, revisions, runs,
)


def sample(**changes):
    value = {
        "market_id": "official-market-17", "market_label": "Sample Market",
        "commodity_id": "official-onion", "commodity": "Onion",
        "variety_id": "official-other", "variety": "Other",
        "grade_id": "official-local", "grade": "Local",
        "observation_date": "2026-10-08", "min_price": "1000",
        "max_price": "1400", "modal_price": "1200", "source_unit": "INR/quintal",
    }
    value.update(changes)
    return value


def capture(engine, records, when, raw=b"source-response"):
    return ingest_records(engine, records, source_kind="manual_file",
                          source_url="https://example.gov/data.csv",
                          retrieval_method="manual_csv_import:test.csv", raw_bytes=raw,
                          retrieved_at=when)


def test_initial_capture_keeps_retrieval_and_publication_distinct_and_persists_protocol():
    engine = create_engine("sqlite:///:memory:")
    when = datetime(2026, 10, 9, 4, 0, tzinfo=timezone.utc)
    result = capture(engine, [sample()], when)
    assert result["inserted"] == 1
    with engine.connect() as conn:
        row = conn.execute(select(observations)).mappings().one()
        rev = conn.execute(select(revisions)).mappings().one()
        protocol = conn.execute(select(protocols).where(protocols.c.protocol_id == PROTOCOL_ID)).mappings().one()
    assert row["first_seen_at_utc"] == when.isoformat()
    assert row["source_publication_at_utc"] is None
    assert rev["retrieved_at_utc"] == when.isoformat()
    assert json.loads(protocol["protocol_json"])["holdout_populated"] is False
    assert protocol["status"] == "frozen_before_future_targets"


def test_duplicate_poll_is_recorded_without_overwriting_first_seen():
    engine = create_engine("sqlite:///:memory:")
    first = datetime(2026, 10, 9, 4, 0, tzinfo=timezone.utc)
    second = datetime(2026, 10, 10, 4, 0, tzinfo=timezone.utc)
    capture(engine, [sample()], first, b"one")
    result = capture(engine, [sample()], second, b"two")
    with engine.connect() as conn:
        row = conn.execute(select(observations)).mappings().one()
        revs = conn.execute(select(revisions).order_by(revisions.c.revision_number)).mappings().all()
    assert result["duplicate"] == 1
    assert row["first_seen_at_utc"] == first.isoformat()
    assert row["latest_retrieved_at_utc"] == second.isoformat()
    assert [r["change_kind"] for r in revs] == ["initial", "duplicate"]
    assert revs[0]["raw_sha256"] != revs[1]["raw_sha256"]


def test_source_correction_appends_revision_and_preserves_original_raw_record():
    engine = create_engine("sqlite:///:memory:")
    first = datetime(2026, 10, 9, 4, 0, tzinfo=timezone.utc)
    second = datetime(2026, 10, 10, 4, 0, tzinfo=timezone.utc)
    capture(engine, [sample()], first, b"original")
    result = capture(engine, [sample(modal_price="1250")], second, b"corrected")
    with engine.connect() as conn:
        row = conn.execute(select(observations)).mappings().one()
        revs = conn.execute(select(revisions).order_by(revisions.c.revision_number)).mappings().all()
    assert result["revised"] == 1
    assert row["modal_price"] == 1250
    assert row["revision_count"] == 2
    assert row["first_seen_at_utc"] == first.isoformat()
    assert [r["change_kind"] for r in revs] == ["initial", "correction"]
    assert json.loads(revs[0]["raw_record_json"])["modal_price"] == "1200"


def test_correction_after_duplicate_poll_uses_monotonic_revision_numbers():
    engine = create_engine("sqlite:///:memory:")
    first = datetime(2026, 10, 9, 4, 0, tzinfo=timezone.utc)
    capture(engine, [sample()], first, b"initial")
    capture(engine, [sample()], datetime(2026, 10, 10, 4, 0, tzinfo=timezone.utc), b"duplicate")
    result = capture(engine, [sample(modal_price="1250")],
                     datetime(2026, 10, 11, 4, 0, tzinfo=timezone.utc), b"corrected")
    with engine.connect() as conn:
        numbers = [r[0] for r in conn.execute(select(revisions.c.revision_number).order_by(revisions.c.revision_number))]
        row = conn.execute(select(observations)).mappings().one()
    assert result["revised"] == 1
    assert numbers == [1, 2, 3]
    assert row["revision_count"] == 3


def test_invalid_order_and_identity_or_unit_changes_are_not_accepted():
    engine = create_engine("sqlite:///:memory:")
    first = datetime(2026, 10, 9, 4, 0, tzinfo=timezone.utc)
    capture(engine, [sample()], first)
    result = capture(engine, [
        sample(min_price="1300", max_price="1100"),
        sample(market_label="Renamed Market"),
        sample(source_unit="INR/kg"),
    ], datetime(2026, 10, 10, 4, 0, tzinfo=timezone.utc))
    with engine.connect() as conn:
        rows = conn.execute(select(observations)).mappings().all()
        run = conn.execute(select(runs).order_by(runs.c.retrieved_at_utc.desc())).mappings().first()
        revs = conn.execute(select(revisions)).mappings().all()
    assert len(result["validation_errors"]) == 3
    assert len(rows) == 1
    assert rows[0]["modal_price"] == 1200
    assert len(revs) == 1
    assert run["status"] == "failed"


def test_protocol_cannot_be_silently_replaced():
    engine = create_engine("sqlite:///:memory:")
    from backend.agri.prospective import migrate
    migrate(engine)
    freeze_protocol(engine)
    freeze_protocol(engine)
    with engine.connect() as conn:
        assert conn.execute(select(protocols.c.protocol_id)).scalar_one() == PROTOCOL_ID


def test_manual_import_uses_real_import_time_and_file_checksum(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    path = tmp_path / "official.csv"
    import csv
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(sample()))
        writer.writeheader()
        writer.writerow(sample())
    captured = datetime(2026, 10, 9, 5, 0, tzinfo=timezone.utc)
    result = import_manual_file(engine, path, source_url="https://example.gov/report.csv", retrieved_at=captured)
    with engine.connect() as conn:
        row = conn.execute(select(observations)).mappings().one()
        run = conn.execute(select(runs)).mappings().one()
    assert row["first_seen_at_utc"] == captured.isoformat()
    assert row["source_publication_at_utc"] is None
    assert run["raw_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result["inserted"] == 1


def test_official_api_adapter_paginates_real_responses_and_checksums_payload():
    engine = create_engine("sqlite:///:memory:")
    api_record = {"State": "Maharashtra", "District": "Nashik", "Market": "Exact Market",
                  "Commodity": "Onion", "Variety": "Other", "Grade": "Local",
                  "Arrival_Date": "08/10/2026", "Min_Price": "1000", "Max_Price": "1400",
                  "Modal_Price": "1200", "Commodity_Code": "ONION"}
    payloads = [
        {"title": OGD_RESOURCE_TITLE, "total": 1, "records": [api_record]},
    ]
    calls = []
    requests = []

    def handler(request):
        requests.append(request)
        calls.append(request.url.params.get("offset"))
        content = json.dumps(payloads.pop(0)).encode()
        return httpx.Response(200, content=content, headers={"content-type": "application/json"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = collect_datagov(engine, resource_id="9ef84268-d588-465a-a308-a864a43d0070", api_key="secret", client=client,
                             retrieved_at=datetime(2026, 10, 9, 5, 0, tzinfo=timezone.utc),
                             page_size=1, filters={"Market": "Exact Label"})
    assert result["status"] == "dry_run"
    assert result["resource_verified"] is True and result["schema_valid"] is True
    assert result["record_count"] == 1
    assert calls == ["0"]
    assert all(request.url.params.get("filters[Market]") == "Exact Label" for request in requests)
    assert "secret" not in result["raw_sha256"]
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").all() == []


def test_official_api_empty_response_is_a_valid_empty_capture():
    engine = create_engine("sqlite:///:memory:")
    client = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"title": OGD_RESOURCE_TITLE, "records": []})))
    result = collect_datagov(engine, resource_id="9ef84268-d588-465a-a308-a864a43d0070", api_key="secret", client=client)
    assert result["status"] == "unverified_schema"
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").all() == []


def test_official_api_rejects_non_object_records_without_crashing():
    engine = create_engine("sqlite:///:memory:")
    client = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"title": OGD_RESOURCE_TITLE, "records": [None]})))
    with pytest.raises(ValueError, match="non-object"):
        collect_datagov(engine, resource_id="9ef84268-d588-465a-a308-a864a43d0070", api_key="secret", client=client)
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").all() == []


def test_official_api_rate_limit_and_network_errors_are_sanitized():
    engine = create_engine("sqlite:///:memory:")

    def limited(request):
        return httpx.Response(429, headers={"Retry-After": "60"}, request=request)

    client = httpx.Client(transport=httpx.MockTransport(limited))
    with pytest.raises(ValueError, match="rate limit") as rate_error:
        collect_datagov(engine, resource_id="9ef84268-d588-465a-a308-a864a43d0070", api_key="private-secret", client=client, sleep_fn=lambda _: None)
    assert "private-secret" not in str(rate_error.value)
    assert "60" in str(rate_error.value)

    def unavailable(request):
        raise httpx.ConnectError("private-secret is never shown", request=request)

    client = httpx.Client(transport=httpx.MockTransport(unavailable))
    with pytest.raises(ValueError, match="network_failure") as network_error:
        collect_datagov(engine, resource_id="9ef84268-d588-465a-a308-a864a43d0070", api_key="private-secret", client=client, sleep_fn=lambda _: None)
    assert "private-secret" not in str(network_error.value)
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").all() == []


def test_ogd_credentials_load_from_env_file_with_environment_precedence(tmp_path):
    from backend.agri.prospective import load_ogd_credentials
    env = tmp_path / ".env"
    env.write_text("DATA_GOV_IN_API_KEY=file-secret\nDATA_GOV_IN_RESOURCE_ID=11111111-1111-1111-1111-111111111111\n", encoding="utf-8")
    assert load_ogd_credentials(env, environ={"DATA_GOV_IN_API_KEY": "process-secret"}) == {
        "DATA_GOV_IN_API_KEY": "process-secret",
        "DATA_GOV_IN_RESOURCE_ID": "11111111-1111-1111-1111-111111111111",
    }


def test_invalid_uuid_and_authentication_fail_without_database_writes():
    engine = create_engine("sqlite:///:memory:")
    with pytest.raises(ValueError, match="UUID"):
        collect_datagov(engine, resource_id="not-a-uuid", api_key="private")
    for status in (401, 403, 404):
        client = httpx.Client(transport=httpx.MockTransport(
            lambda request, status=status: httpx.Response(status, request=request)))
        with pytest.raises(ValueError):
            collect_datagov(engine, resource_id="9ef84268-d588-465a-a308-a864a43d0070",
                            api_key="private", client=client, sleep_fn=lambda _: None)
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").all() == []


def test_resource_title_and_complete_schema_are_required_before_ingest():
    engine = create_engine("sqlite:///:memory:")
    row = {name: "value" for name in OGD_EXPECTED_FIELDS}
    response_data = {"title": "Different resource", "records": [row]}
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response_data)))
    result = collect_datagov(engine, resource_id="9ef84268-d588-465a-a308-a864a43d0070",
                             api_key="private", client=client)
    assert result["status"] == "unverified_resource"
    assert result["ingest_requested"] is False
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").all() == []


def test_dry_run_never_requires_database_or_persists_and_raw_prices_are_not_returned():
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={
        "title": OGD_RESOURCE_TITLE,
        "records": [{name: ("1200" if name == "modal_price" else "value") for name in OGD_EXPECTED_FIELDS}],
    })))
    result = collect_datagov(resource_id="9ef84268-d588-465a-a308-a864a43d0070",
                             api_key="private", client=client)
    assert result["status"] == "dry_run"
    assert "1200" not in json.dumps(result)


def test_explicit_ingest_preserves_source_but_quarantines_missing_market_id_and_unit():
    engine = create_engine("sqlite:///:memory:")
    source = {"State": "Maharashtra", "District": "Nashik", "Market": "Lasalgaon(Niphad)",
              "Commodity": "Onion", "Variety": "Other", "Grade": "Local",
              "Arrival_Date": "08/10/2026", "Min_Price": "1000", "Max_Price": "1400",
              "Modal_Price": "1200", "Commodity_Code": "ONION"}
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={
        "title": OGD_RESOURCE_TITLE, "records": [source],
    })))
    result = collect_datagov(engine, resource_id="9ef84268-d588-465a-a308-a864a43d0070", api_key="private",
                             client=client, filters={"Market": "Lasalgaon(Niphad)"}, ingest=True)
    assert result["status"] == "failed"
    assert result["inserted"] == 0
    assert "market_id" in result["validation_errors"][0]["errors"][0]
    assert "source_unit" in result["validation_errors"][0]["errors"][0]
    with engine.connect() as conn:
        assert conn.execute(select(observations)).all() == []
        run = conn.execute(select(runs)).mappings().one()
        assert json.loads(run["raw_payload"])["records"][0] == source


def test_conflicting_duplicate_inside_one_capture_is_reported():
    engine = create_engine("sqlite:///:memory:")
    result = capture(engine, [sample(), sample(modal_price="1250")],
                     datetime(2026, 10, 9, 4, 0, tzinfo=timezone.utc))
    with engine.connect() as conn:
        rows = conn.execute(select(observations)).mappings().all()
        revs = conn.execute(select(revisions)).mappings().all()
    assert result["status"] == "partial"
    assert len(result["validation_errors"]) == 1
    assert len(rows) == 1
    assert len(revs) == 1


def test_timestamp_consistency_rejects_naive_or_future_publication_time():
    engine = create_engine("sqlite:///:memory:")
    captured = datetime(2026, 10, 9, 4, 0, tzinfo=timezone.utc)
    result = capture(engine, [
        sample(source_publication_at="2026-10-09T03:00:00"),
        sample(observation_date="2026-10-10", source_publication_at="2026-10-10T00:00:00Z"),
    ], captured)
    assert result["status"] == "failed"
    assert len(result["validation_errors"]) == 2


def test_integrity_and_calendar_gap_audits():
    engine = create_engine("sqlite:///:memory:")
    captured = datetime(2026, 10, 9, 4, 0, tzinfo=timezone.utc)
    capture(engine, [sample()], captured, b"first payload")
    capture(engine, [sample(observation_date="2026-10-11")], captured, b"second payload")
    gap = audit_calendar_gaps(engine, market_id="official-market-17", commodity_id="official-onion",
                              variety_id="official-other", grade_id="official-local")
    assert gap["missing_calendar_dates"] == ["2026-10-09", "2026-10-10"]
    assert gap["closure_status"].startswith("unknown")
    assert audit_integrity(engine)["ok"] is True


def test_raw_payload_tampering_is_detected():
    engine = create_engine("sqlite:///:memory:")
    capture(engine, [sample()], datetime(2026, 10, 9, 4, 0, tzinfo=timezone.utc), b"original")
    with engine.begin() as conn:
        conn.exec_driver_sql("UPDATE agri_prospective_ingestion_runs SET raw_payload='tampered'")
    audit = audit_integrity(engine)
    assert audit["ok"] is False
    assert audit["failures"][0]["kind"] == "raw_payload_checksum"
