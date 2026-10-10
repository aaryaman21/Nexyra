import hashlib
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select

from backend.agri.data import DataUnavailable
from backend.agri.events import capture_runs, captures, migrate, recent_captures, representations
from backend.agri.official_documents import import_official_text_file


def test_saved_official_text_import_preserves_manual_provenance_and_source_revisions(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    migrate(engine)
    source_url = "https://mausam.imd.gov.in/responsive/advisory/PRID-like-identity.pdf"
    first_text = ("India Meteorological Department advisory for Nashik, Maharashtra. "
        "Heavy rainfall is forecast across the district during the next two days. "
        "Farmers should drain water from vegetable fields and protect harvested produce. " * 4)
    first_file = tmp_path / "bulletin.txt"
    first_file.write_text(first_text, encoding="utf-8")
    first = import_official_text_file(engine, first_file, source_url=source_url,
        title="Nashik agricultural weather advisory", reported_publication_date="2026-10-08",
        archive_dir=tmp_path / "archive")
    assert first["status"] == "captured_candidate"
    assert first["content_status"] == "manual_text_import_candidate"
    assert first["publication_status"] == "operator_supplied_unverified"
    assert first["retrieved_at_utc"].endswith("+00:00")
    assert hashlib.sha256(first_file.read_bytes()).hexdigest() == first["raw_sha256"]
    archived = tmp_path / "archive" / __import__("pathlib").Path(first["archived_file"]).name
    assert archived.read_bytes() == first_file.read_bytes()

    feed = recent_captures(engine, limit=50)
    assert len(feed["events"]) == 1
    item = feed["events"][0]
    assert item["article_identity"] == first["article_identity"]
    assert item["source"] == "India Meteorological Department"
    assert item["published_at"] is None
    assert item["published_date"] == "2026-10-08"
    assert item["publication_precision"] == "date_only_operator_unverified"
    assert item["content_status"] == "manual_text_import_candidate"
    assert item["article_text"] == first_text

    duplicate = import_official_text_file(engine, first_file, source_url=source_url,
        title="Nashik agricultural weather advisory", archive_dir=tmp_path / "archive")
    assert duplicate["status"] == "duplicate_reused"
    with engine.connect() as conn:
        assert len(conn.execute(select(captures)).all()) == 1
        assert len(conn.execute(select(capture_runs)).all()) == 1
        assert len(conn.execute(select(representations)).all()) == 1

    second_text = first_text + " Follow-up advice: use field drainage channels."
    second_file = tmp_path / "bulletin_revised.txt"
    second_file.write_text(second_text, encoding="utf-8")
    revision = import_official_text_file(engine, second_file, source_url=source_url,
        title="Nashik agricultural weather advisory", archive_dir=tmp_path / "archive")
    assert revision["status"] == "captured_candidate"
    assert revision["article_identity"] == first["article_identity"]
    with engine.connect() as conn:
        assert len(conn.execute(select(captures)).all()) == 2
        assert len(conn.execute(select(capture_runs)).all()) == 2
        assert len(conn.execute(select(representations)).all()) == 2
    revised_item = recent_captures(engine, limit=50)["events"][0]
    assert revised_item["id"] == revision["capture_id"]
    assert revised_item["article_text"] == second_text


@pytest.mark.parametrize("url", [
    "http://mausam.imd.gov.in/advisory.pdf",
    "https://mausam.imd.gov.in.evil.example/advisory.pdf",
    "https://user@mausam.imd.gov.in/advisory.pdf",
    "https://example.gov.in/advisory.pdf",
])
def test_manual_official_text_import_rejects_unverified_hosts_and_urls(tmp_path, url):
    engine = create_engine("sqlite:///:memory:")
    text_file = tmp_path / "advisory.txt"
    text_file.write_text("A sufficiently long test source document. " * 8, encoding="utf-8")
    with pytest.raises(DataUnavailable):
        import_official_text_file(engine, text_file, source_url=url, title="Source document",
            archive_dir=tmp_path / "archive")
    from sqlalchemy import inspect
    assert not inspect(engine).has_table(captures.name)
