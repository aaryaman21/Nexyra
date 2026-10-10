import hashlib
import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select

from backend.agri.data import DataUnavailable, read_events
from backend.agri.events import (PIB_RSS_URL, capture_runs, captures, representations, export_research_archive,
                                 fetch_pib_rss, import_pib_article_html, import_pib_rss_file, recent_captures,
                                 import_pib_text_file, enrich_verified_pib_metadata)
from backend.agri.semantic import classify_onion_event
from backend.agri.semantic import extract_event_intelligence
from backend.agri.events import import_pib_html_file


def test_keyword_classifier_is_explicitly_heuristic_and_keeps_timestamps_distinct():
    captured = datetime(2026, 10, 8, 10, 0, tzinfo=timezone.utc)
    event = classify_onion_event({
        "title": "Severe heavy rainfall disrupts onion transport in Nashik, Maharashtra",
        "url": "https://www.pib.gov.in/release?utm_source=rss&id=12#top",
        "published_at": "2026-10-08T09:00:00+00:00",
    }, series_id="exact-series", retrieved_at=captured)
    assert event["category"] == "weather_disruption"
    assert event["relevance_status"] == "relevant"
    assert event["availability_basis"] == "first_local_capture"
    assert event["available_at"] == captured.isoformat()
    assert event["published_at"] == "2026-10-08T09:00:00+00:00"
    assert event["classification_status"] == "unvalidated_research_signal"
    assert event["source_confidence"] == "not_assessed"
    assert event["direction_hypothesis"].startswith("possible")
    assert event["url"] == "https://www.pib.gov.in/release?id=12"


def test_classifier_does_not_invent_publication_timestamp_and_rejects_naive_time():
    event = classify_onion_event({"title": "Onion harvest report", "url": "https://pib.gov.in/a"},
                                 series_id="x", retrieved_at=datetime(2026, 10, 8, tzinfo=timezone.utc))
    assert event["published_at"] is None
    assert event["availability_basis"] == "first_local_capture"
    with pytest.raises(ValueError, match="timezone-aware"):
        classify_onion_event({"title": "Onion", "url": "https://pib.gov.in/a"},
                             series_id="x", retrieved_at=datetime(2026, 10, 8))


def test_local_rss_capture_preserves_each_poll_and_exports_only_gap_free_coverage(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    feed = tmp_path / "pib.xml"
    xml = b'''<?xml version="1.0" encoding="UTF-8"?>
      <rss version="2.0"><channel><title>PIB RSS</title><item>
      <title>Severe heavy rainfall disrupts onion supply in Nashik Maharashtra</title>
      <link>https://www.pib.gov.in/PressReleasePage.aspx?PRID=123</link>
      <description>Severe rainfall conditions disrupt supply.</description>
      <pubDate>Thu, 08 Oct 2026 09:00:00 +0000</pubDate>
      </item></channel></rss>'''
    feed.write_bytes(xml)
    first_time = datetime(2026, 10, 8, 10, 0, tzinfo=timezone.utc)
    gap_time = datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc)
    first = import_pib_rss_file(engine, feed, retrieved_at=first_time)
    assert first["status"] == "success"
    assert first["raw_sha256"] == hashlib.sha256(xml).hexdigest()
    import_pib_rss_file(engine, feed, retrieved_at=gap_time)
    with pytest.raises(DataUnavailable, match="calendar gaps"):
        export_research_archive(engine, series_id="exact-series")
    second_time = datetime(2026, 10, 9, 10, 0, tzinfo=timezone.utc)
    second = import_pib_rss_file(engine, feed, retrieved_at=second_time)
    assert second["status"] == "success"
    with engine.connect() as conn:
        run_rows = conn.execute(select(capture_runs)).mappings().all()
        capture_rows = conn.execute(select(captures).order_by(captures.c.retrieved_at_utc)).mappings().all()
    assert len(run_rows) == 3
    assert len(capture_rows) == 3
    assert capture_rows[0]["first_seen_at_utc"] == first_time.isoformat()
    assert capture_rows[1]["first_seen_at_utc"] == first_time.isoformat()
    assert capture_rows[0]["source_publication_at_utc"] == "2026-10-08T09:00:00+00:00"
    assert run_rows[0]["raw_payload"].encode("utf-8") == xml
    archive = export_research_archive(engine, series_id="exact-series")
    assert archive["holdout_eligible"] is False
    assert archive["coverage"]["exact-series"] == {"start": "2026-10-08", "end": "2026-10-10"}
    assert len(archive["events"]) == 1
    assert archive["events"][0]["available_at"] == first_time.isoformat()
    archive_file = tmp_path / "events.json"
    archive_file.write_text(json.dumps(archive), encoding="utf-8")
    parsed = read_events(archive_file)
    assert parsed["events"][0]["category"] == "weather_disruption"


def test_rss_import_rejects_non_official_feed_and_does_not_capture_third_party_links(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    feed = tmp_path / "pib.xml"
    feed.write_text("<rss><channel><item><title>Onion Nashik</title><link>https://news.example/article</link></item></channel></rss>", encoding="utf-8")
    captured = datetime(2026, 10, 8, 10, 0, tzinfo=timezone.utc)
    with pytest.raises(DataUnavailable, match="no valid article items"):
        import_pib_rss_file(engine, feed, retrieved_at=captured)
    with pytest.raises(DataUnavailable, match="official PIB"):
        import_pib_rss_file(engine, feed, source_url="https://example.test/rss", retrieved_at=captured)
    from sqlalchemy import inspect
    assert inspect(engine).get_table_names() == []


def test_manual_import_timestamp_cannot_precede_publication(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    feed = tmp_path / "pib.xml"
    feed.write_text("""<rss><channel><item><title>Onion Nashik</title>
      <link>https://pib.gov.in/a</link><pubDate>Fri, 09 Oct 2026 10:00:00 +0000</pubDate>
      </item></channel></rss>""", encoding="utf-8")
    with pytest.raises(DataUnavailable, match="no valid article items"):
        import_pib_rss_file(engine, feed, retrieved_at=datetime(2026, 10, 8, 10, tzinfo=timezone.utc))


def test_live_adapter_fetches_only_official_feed_and_reports_genuine_capture(tmp_path):
    from io import BytesIO
    from sqlalchemy import create_engine
    import json

    engine = create_engine("sqlite:///:memory:")
    xml = b'''<rss><channel><item><title>Onion arrivals change in Nashik Maharashtra</title>
      <link>https://pib.gov.in/release?id=123</link><pubDate>Thu, 08 Oct 2026 09:00:00 +0000</pubDate>
      </item></channel></rss>'''
    calls = []

    class Response(BytesIO):
        status = 200

        def __enter__(self): return self
        def __exit__(self, *args): self.close()

    def opener(request, timeout):
        calls.append((request.full_url, timeout, request.get_header("User-agent")))
        return Response(xml)

    result = fetch_pib_rss(engine, timeout_seconds=3, retries=0, opener=opener)
    assert result["status"] == "success"
    assert calls[0][0] == PIB_RSS_URL
    assert calls[0][1] == 3
    assert result["raw_sha256"] == hashlib.sha256(xml).hexdigest()
    stored = recent_captures(engine)
    assert stored["status"] == "ready"
    assert stored["events"][0]["published_at"] == "2026-10-08T09:00:00+00:00"
    assert stored["events"][0]["retrieved_at"] == result["retrieved_at_utc"]
    assert stored["events"][0]["classification_status"] == "unvalidated_research_signal"


def test_live_adapter_bounds_retry_and_network_error_has_no_tables():
    from sqlalchemy import create_engine, inspect
    from urllib.error import URLError

    engine = create_engine("sqlite:///:memory:")
    calls = []

    def opener(request, timeout):
        calls.append(request.full_url)
        raise URLError("secret query parameters must not be echoed")

    with pytest.raises(DataUnavailable, match="after 2 bounded attempt"):
        fetch_pib_rss(engine, retries=1, opener=opener)
    assert len(calls) == 2
    assert inspect(engine).get_table_names() == []
    assert recent_captures(engine)["status"] == "unavailable"


def test_manual_html_import_preserves_date_revision_and_deduplicates(tmp_path):
    from sqlalchemy import create_engine, select

    engine = create_engine("sqlite:///:memory:")
    article = tmp_path / "pib_2114060.html"
    title = "Centre withdraws 20% duty on Onion Export effective from April 1st, 2025"

    def page(body):
        return f'''<!doctype html><html><head><meta property="og:title" content="{title}">
          <meta property="og:url" content="https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2114060"></head>
          <body><a href="PressReleaseDetail.aspx?PRID=2114060">official release</a>
          <h1>{title}</h1><p>Date: 22 March 2025</p><p>{body}</p></body></html>'''

    article.write_text(page("The Government announced withdrawal of export duty on onion effective April 1st, 2025. " * 8), encoding="utf-8")
    first = import_pib_article_html(engine, article, retrieved_at=datetime(2026, 10, 9, 10, tzinfo=timezone.utc))
    assert first["status"] == "success"
    assert first["publication_date"] == "2025-03-22"
    assert first["classification"]["category"] == "export_policy"
    assert first["classification"]["classification_status"] == "unvalidated_rule_signal_manual_source_capture"
    assert import_pib_article_html(engine, article)["status"] == "deduplicated"
    article.write_text(page("The Government announced withdrawal of export duty on onion effective April 1st, 2025. " * 9), encoding="utf-8")
    revised = import_pib_article_html(engine, article)
    assert revised["status"] == "success"
    assert revised["content_sha256"] != first["content_sha256"]
    with engine.connect() as conn:
        rows = conn.execute(select(captures)).mappings().all()
    assert len(rows) == 2
    assert all(row["publication_status"] == "source_date_only" for row in rows)
    assert recent_captures(engine)["events"][0]["article_text"]


def test_manual_html_import_rejects_wrong_release(tmp_path):
    from sqlalchemy import create_engine, inspect
    from backend.agri.data import DataUnavailable

    engine = create_engine("sqlite:///:memory:")
    article = tmp_path / "wrong.html"
    article.write_text("<html><head><meta property='og:title' content='Other release'></head><body>pib.gov.in</body></html>", encoding="utf-8")
    with pytest.raises(DataUnavailable, match="PRID 2114060"):
        import_pib_article_html(engine, article)
    assert inspect(engine).get_table_names() == []


def test_multilabel_rules_distinguish_reduction_from_ban_removal_and_get_effective_date():
    duty = extract_event_intelligence("Centre withdraws 20% duty on onion export effective from April 1st, 2025",
                                      "The export duty is withdrawn.", article_id="a")
    assert [x["category"] for x in duty["events"]] == ["export_duty_reduction"]
    assert duty["date_mentions"][0]["role"] == "effective_date"
    assert duty["date_mentions"][0]["normalized_date"] == "2025-04-01"
    lift = extract_event_intelligence("Prohibition removed from Onion Export",
                                      "The central government removes prohibition for onion export.", article_id="b")
    labels = {x["category"] for x in lift["events"]}
    assert "export_restriction_removal" in labels
    assert "export_restriction_introduction" not in labels


def test_checked_in_official_pib_html_imports_genuine_metadata_excerpt_only(tmp_path):
    from pathlib import Path
    from sqlalchemy import create_engine, select
    source = Path(__file__).resolve().parents[2] / "data" / "pib" / "2114060.html"
    if not source.exists():
        pytest.skip("genuine saved PIB page is not present")
    engine = create_engine("sqlite:///:memory:")
    imported = import_pib_html_file(engine, source,
        retrieved_at=datetime(2026, 10, 9, 12, tzinfo=timezone.utc))
    assert imported["prid"] == "2114060"
    assert imported["content_status"] == "metadata_excerpt_only"
    assert imported["publication_date"] is None
    row = engine.connect().execute(select(captures)).mappings().one()
    assert "withdrawn 20% duty" in row["summary_text"].casefold()
    assert row["publication_status"] == "missing"
    assert json.loads(row["classification_json"])["events"][0]["category"] == "export_duty_reduction"


def test_checked_in_full_pib_page_extracts_article_and_published_date(tmp_path):
    from pathlib import Path
    from sqlalchemy import create_engine, select
    source = (Path(__file__).resolve().parents[2] / "data" / "pib" /
              "Press Release_ Press Information Bureau_files" / "PressReleasePage.html")
    if not source.exists():
        pytest.skip("genuine saved PIB full page is not present")
    engine = create_engine("sqlite:///:memory:")
    imported = import_pib_html_file(engine, source,
        retrieved_at=datetime(2026, 10, 9, 12, tzinfo=timezone.utc))
    assert imported["prid"] == "1684194"
    assert imported["content_status"] == "full_text_extracted"
    assert imported["publication_date"] == "2020-12-28"
    assert imported["issuing_ministry"] == "Ministry of Commerce & Industry"
    row = engine.connect().execute(select(captures)).mappings().one()
    metadata = json.loads(row["raw_item_json"])
    assert "01.01.2021" in row["summary_text"]
    assert metadata["published_time_source_text"] == "8:03PM"
    assert row["publication_status"] == "source_date_only"


def test_metadata_verification_preserves_history_and_rejects_conflicts():
    from backend.agri.events import enrich_verified_pib_metadata
    from sqlalchemy import create_engine, select
    engine = create_engine("sqlite:///:memory:")
    from backend.agri.events import migrate
    migrate(engine)
    now = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
    xml = b'''<rss><channel><item><title>Onion policy report</title>
      <link>https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=999&amp;reg=48&amp;lang=1</link></item></channel></rss>'''
    from backend.agri.events import import_pib_rss_bytes
    import_pib_rss_bytes(engine, xml, retrieved_at=now)
    result = enrich_verified_pib_metadata(engine, prid="999", published_date="2020-12-28",
        ministry="Ministry of Commerce &amp; Industry",
        source_evidence="Official page heading: 28 DEC 2020; Ministry of Commerce & Industry.",
        verification_source_url="https://www.pib.gov.in/PressReleasePage.aspx?PRID=999", verified_at=now)
    row = engine.connect().execute(select(captures)).mappings().one()
    metadata = json.loads(row["raw_item_json"])
    assert metadata["metadata_verification_history"][-1]["source_url"].endswith("PRID=999")
    assert row["source_publication_at_utc"] == "2020-12-28"
    with pytest.raises(DataUnavailable, match="Conflicting verified publication date"):
        enrich_verified_pib_metadata(engine, prid="999", published_date="2020-12-29",
            ministry="Ministry of Commerce & Industry", source_evidence="conflicting official evidence",
            verification_source_url="https://www.pib.gov.in/PressReleasePage.aspx?PRID=999", verified_at=now)
    row2 = engine.connect().execute(select(captures)).mappings().one()
    assert row2["source_publication_at_utc"] == "2020-12-28"


def test_manual_full_text_representation_adds_two_evidenced_events_without_capture_duplicate(tmp_path):
    from pathlib import Path
    from sqlalchemy import create_engine, select, func
    engine = create_engine("sqlite:///:memory:")
    source_html = Path(__file__).resolve().parents[2] / "data" / "pib" / "1972618.html"
    text_source = Path(__file__).resolve().parents[2] / "data" / "pib" / "1972618_full.txt"
    if not source_html.exists() or not text_source.exists():
        pytest.skip("genuine PIB HTML/TXT files are not present")
    original = import_pib_html_file(engine, source_html,
        retrieved_at=datetime(2026, 10, 9, 10, tzinfo=timezone.utc))
    enrich_verified_pib_metadata(engine, prid="1972618", published_date="2023-10-28",
        ministry="Ministry of Consumer Affairs, Food & Public Distribution",
        source_evidence="Official PIB heading: 28 OCT 2023; Ministry of Consumer Affairs, Food & Public Distribution.",
        verification_source_url="https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=1972618&reg=48&lang=1",
        published_time_source_text="28 OCT 2023 7:03PM by PIB Delhi; timezone not stated",
        verified_at=datetime(2026, 10, 9, 10, tzinfo=timezone.utc))
    before = engine.connect().execute(select(captures)).mappings().one()
    imported = import_pib_text_file(engine, text_source, prid="1972618",
        source_url="https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=1972618&reg=48&lang=1",
        imported_at=datetime(2026, 10, 9, 11, tzinfo=timezone.utc))
    assert imported["status"] == "success"
    assert [item["category"] for item in imported["events"]] == ["mep_introduction", "government_procurement"]
    evidence = {item["category"]: item["evidence"][0]["text"] for item in imported["events"]}
    assert "with effect from 29th October, 2023, till 31st December, 2023" in evidence["mep_introduction"]
    assert "procurement of additional 2 lakh tons of onion for the buffer" in evidence["government_procurement"]
    assert imported["published_date"] == "2023-10-28"
    assert imported["issuing_ministry"] == "Ministry of Consumer Affairs, Food & Public Distribution"
    assert imported["raw_sha256"] == hashlib.sha256(text_source.read_bytes()).hexdigest()
    with engine.connect() as conn:
        after = conn.execute(select(captures)).mappings().one()
        assert conn.execute(select(func.count()).select_from(captures)).scalar_one() == 1
    assert after["capture_id"] == before["capture_id"]
    assert after["raw_sha256"] == before["raw_sha256"]
    assert after["first_seen_at_utc"] == before["first_seen_at_utc"]
    assert after["source_publication_at_utc"] == "2023-10-28"
    feed = recent_captures(engine)
    assert len(feed["events"]) == 1
    assert feed["events"][0]["text_representation"] == "manual_txt"
    assert len(feed["events"][0]["event_classifications"]) == 2
    assert feed["events"][0]["geographic_relevance"] == "india_wide"
    duplicate = import_pib_text_file(engine, text_source, prid="1972618",
        source_url="https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=1972618&reg=48&lang=1",
        imported_at=datetime(2026, 10, 9, 12, tzinfo=timezone.utc))
    assert duplicate["status"] == "duplicate"


@pytest.mark.parametrize(("prid", "published_date", "expected_categories", "fact_value"), [
    ("2042765", "2024-08-07", ["reported_export_volume", "government_procurement", "market_price_report"], "2.60 lakh tons"),
    ("2114060", "2025-03-22", ["export_duty_reduction", "reported_export_volume", "market_arrivals", "production_estimate", "market_price_report"], "20% withdrawn"),
])
def test_manual_full_text_representations_for_additional_real_pib_articles(tmp_path, prid, published_date, expected_categories, fact_value):
    from pathlib import Path
    from sqlalchemy import create_engine, select, func
    engine = create_engine("sqlite:///:memory:")
    root = Path(__file__).resolve().parents[2] / "data" / "pib"
    source_html = root / f"{prid}.html"
    text_source = root / f"{prid}_full.txt"
    if not source_html.exists() or not text_source.exists():
        pytest.skip("genuine PIB HTML/TXT files are not present")
    before_import = import_pib_html_file(engine, source_html,
        retrieved_at=datetime(2026, 10, 9, 10, tzinfo=timezone.utc))
    url = f"https://www.pib.gov.in/PressReleaseDetail.aspx?PRID={prid}&reg=48&lang=1"
    enrich_verified_pib_metadata(engine, prid=prid, published_date=published_date,
        ministry="Ministry of Consumer Affairs, Food & Public Distribution",
        source_evidence=f"Official PIB page metadata for PRID {prid}.",
        verification_source_url=url,
        verified_at=datetime(2026, 10, 9, 10, tzinfo=timezone.utc))
    with engine.connect() as conn:
        before = conn.execute(select(captures).where(captures.c.capture_id == before_import["capture_id"])).mappings().one()
        original_run_count = conn.execute(select(func.count()).select_from(capture_runs)).scalar_one()
    imported = import_pib_text_file(engine, text_source, prid=prid, source_url=url,
        imported_at=datetime(2026, 10, 9, 11, tzinfo=timezone.utc))
    assert imported["status"] == "success"
    assert [item["category"] for item in imported["events"]] == expected_categories
    assert imported["published_date"] == published_date
    assert imported["issuing_ministry"] == "Ministry of Consumer Affairs, Food & Public Distribution"
    assert imported["raw_sha256"] == hashlib.sha256(text_source.read_bytes()).hexdigest()
    feed = recent_captures(engine)
    assert len(feed["events"]) == 1
    assert feed["events"][0]["text_representation"] == "manual_txt"
    assert any(item["value"] == fact_value for item in feed["events"][0]["reported_facts"])
    if prid == "2042765":
        assert "through 31 July 2024" in feed["events"][0]["reported_facts"][0]["period"]
        assert "Till 31st July, 2024" in feed["events"][0]["event_classifications"][0]["evidence"][0]["text"]
        assert "export_restriction_removal" not in [item["category"] for item in feed["events"][0]["event_classifications"]]
        price_fact = next(item for item in feed["events"][0]["reported_facts"] if item["kind"] == "maharashtra_mandi_modal_price_range")
        assert "April–July 2024" in price_fact["period"]
        assert "Rs.1,230 to Rs.2,578 per quintal" in price_fact["evidence"]["text"]
    else:
        facts = feed["events"][0]["reported_facts"]
        duty = next(item for item in facts if item["kind"] == "export_duty")
        assert duty["announcement_date"] == "2025-03-22"
        assert duty["period"] == "effective 1 April 2025"
        assert "effective from 1st April, 2025" in duty["evidence"]["text"]
        benchmark = next(item for item in facts if item["kind"] == "benchmark_market_modal_price")
        assert "21st March, 2025" in benchmark["evidence"]["text"]
        assert "Pimpalgoan" in benchmark["evidence"]["text"]
        market_event = next(item for item in feed["events"][0]["event_classifications"] if item["category"] == "market_price_report")
        assert market_event["evidence"][-1]["text"] == benchmark["evidence"]["text"]
    with engine.connect() as conn:
        after = conn.execute(select(captures).where(captures.c.capture_id == before["capture_id"])).mappings().one()
        assert conn.execute(select(func.count()).select_from(captures)).scalar_one() == 1
        assert conn.execute(select(func.count()).select_from(capture_runs)).scalar_one() == original_run_count
        assert conn.execute(select(func.count()).select_from(representations)).scalar_one() == 1
    assert after["capture_id"] == before["capture_id"]
    assert after["raw_sha256"] == before["raw_sha256"]
    assert after["first_seen_at_utc"] == before["first_seen_at_utc"]
    assert after["source_publication_at_utc"] == published_date
    duplicate = import_pib_text_file(engine, text_source, prid=prid, source_url=url,
        imported_at=datetime(2026, 10, 9, 12, tzinfo=timezone.utc))
    assert duplicate["status"] == "duplicate"
    reformatted = tmp_path / f"{prid}_same_body.txt"
    reformatted.write_bytes(text_source.read_bytes() + b"\n")
    same_content = import_pib_text_file(engine, reformatted, prid=prid, source_url=url,
        imported_at=datetime(2026, 10, 9, 13, tzinfo=timezone.utc))
    assert same_content["status"] == "duplicate"
    assert same_content["matched_by"] == "content_sha256"
    assert same_content["incoming_raw_sha256"] != same_content["raw_sha256"]
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(representations)).scalar_one() == 1
    if prid == "2114060":
        monthly = next(item for item in feed["events"][0]["reported_facts"] if item["kind"] == "monthly_onion_export_volume")
        assert monthly["evidence"]["text"] == "Monthly onion export quantity had picked up from 0.72 LMT in September, 2024 to 1.85 LMT in January, 2025."
