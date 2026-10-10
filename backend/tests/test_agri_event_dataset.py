import hashlib
import json
from io import BytesIO

from sqlalchemy import create_engine, select

from backend.agri import event_evaluation as evaluation
from backend.agri.event_dataset import normalize_article_text, normalize_captures
from backend.agri.events import (captures, capture_runs, human_event_reviews, migrate,
                                 representations, text_normalizations)


def test_normalization_is_derived_and_idempotent_for_existing_genuine_articles():
    text, changes, status = normalize_article_text("A&nbsp;B\u00a0  C\n\n\nD", "x")
    assert text == "A B C\n\nD"
    assert any(item["kind"] == "html_whitespace_and_zero_width_cleanup" for item in changes)
    assert status == "normalized"
    repaired, changes, status = normalize_article_text("Itâ€™s tested", "2114060")
    assert repaired == "It’s tested"
    assert changes[0]["kind"] == "known_reversible_mojibake_repair"
    assert status == "normalized"
    unchanged, changes, _ = normalize_article_text("Itâ€™s tested", "other")
    assert unchanged != repaired


def test_near_duplicate_grouping_is_source_split_only_and_stable():
    from backend.agri.event_evaluation import near_duplicate_groups
    body = "A source article about onion procurement and market arrivals reported in Maharashtra. " * 8
    articles = [{"id": "a", "article_identity": "pib:1", "article_text": body},
                {"id": "b", "article_identity": "pib:2", "article_text": body},
                {"id": "c", "article_identity": "pib:3", "article_text": "A separate unrelated source body."}]
    first = near_duplicate_groups(articles)
    second = near_duplicate_groups(articles)
    assert first == second
    assert first["pib:1"] == first["pib:2"]
    assert first["pib:3"] != first["pib:1"]


def test_review_import_is_identity_and_exact_span_checked_append_only(tmp_path, monkeypatch):
    from sqlalchemy.pool import StaticPool
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    migrate(engine)
    text = "The Government procured onions for the buffer."
    digest = hashlib.sha256(text.encode()).hexdigest()
    article = {"id": "capture-1", "article_identity": "pib:999", "text_content_sha256": digest,
        "normalized_content_sha256": None, "url": "https://www.pib.gov.in/PressReleasePage.aspx?PRID=999",
        "title": "Onion buffer procurement", "published_date": "2026-01-01", "published_at": "2026-01-01",
        "first_seen_at": "2026-01-02T00:00:00+00:00", "content_status": "full_text_extracted",
        "article_text": text, "relevance_status": "relevant", "commodity_relevance": "onion_direct",
        "geographic_relevance": "india_wide", "event_classifications": [{"category": "government_procurement", "evidence": [{"text": "The Government procured onions for the buffer."}]}],
        "date_mentions": [{"normalized_date": "2026-01-01", "role": "publication_date"}]}
    monkeypatch.setattr(evaluation, "recent_captures", lambda *a, **k: {"events": [article]})
    path = tmp_path / "reviews.jsonl"
    entry = {"capture_id": article["id"], "article_identity": article["article_identity"], "source_content_sha256": digest,
        "review": {"status": "reviewed", "reviewer_id": "reviewer-a", "reviewed_at_utc": "2026-02-01T00:00:00Z",
            "relevance": "relevant", "commodity_relevance": "onion_direct", "geographic_relevance": "india_wide",
                "publication_date_correctness": "correct", "corrected_publication_date": "",
            "events": [{"category": "government_procurement", "evidence": [{"quote": text}],
                        "dates": [{"date": "2026-01-01", "role": "publication_date"}]}]}}
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    first = evaluation.import_human_reviews(engine, path)
    assert first["review_count"] == 1
    entry["review"]["reviewed_at_utc"] = "2026-02-02T00:00:00Z"
    entry["review"]["notes"] = "human correction"
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    second = evaluation.import_human_reviews(engine, path)
    assert second["review_count"] == 1
    duplicate = evaluation.import_human_reviews(engine, path)
    assert duplicate["review_count"] == 0
    assert duplicate["duplicates_skipped"] == 1
    with engine.connect() as conn:
        rows = conn.execute(select(human_event_reviews)).mappings().all()
    assert len(rows) == 2
    assert rows[1]["supersedes_review_id"] == rows[0]["review_id"]
    result = evaluation.evaluate_reviews(engine)
    assert result["status"] == "exploratory_development_reused"
    assert result["relevance"]["tp"] == 1
    assert result["events_micro"]["tp"] == 1
    assert result["events_macro"]["f1"] == 1
    assert result["evidence_exact_span"]["tp"] == 1
    assert result["dates_exact_value_and_role"]["tp"] == 1
    assert result["partition_counts"]["independent_test"] == 0
    assert result["missing_evidence"]["rate"] == 0


def test_local_review_api_preserves_predictions_and_appends_corrected_review_history(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.agri import review_api, event_evaluation

    from sqlalchemy.pool import StaticPool
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    migrate(engine)
    text = "The Government procured onion for the buffer on 1 October 2026."
    digest = hashlib.sha256(text.encode()).hexdigest()
    article = {"id": "capture-review", "article_identity": "pib:review", "title": "Onion procurement",
        "url": "https://www.pib.gov.in/PressReleasePage.aspx?PRID=999", "published_date": "2026-10-02",
        "published_at": "2026-10-02", "first_seen_at": "2026-10-03T00:00:00+00:00",
        "content_status": "full_text_extracted", "article_text": text,
        "text_content_sha256": digest, "normalized_content_sha256": None,
        "relevance_status": "relevant", "commodity_relevance": "onion_direct",
        "geographic_relevance": "india_wide", "event_classifications": [
            {"category": "government_procurement", "evidence": [{"text": text}]}], "date_mentions": []}
    later_article = {**article, "id": "capture-review-later", "article_identity": "pib:review-later",
        "title": "Later onion procurement", "published_date": "2026-10-04"}
    # Deliberately provide reverse chronological input; review queue order must
    # remain stable and put the oldest current unreviewed article first.
    feed = {"status": "ready", "events": [later_article, article], "dataset_health": {"unique_articles": 2}}
    monkeypatch.setattr(review_api, "_engine", lambda: engine)
    monkeypatch.setattr(review_api, "recent_captures", lambda *a, **k: feed)
    monkeypatch.setattr(event_evaluation, "recent_captures", lambda *a, **k: feed)
    client = TestClient(app)
    queued = client.get("/api/agri/review/queue")
    assert queued.status_code == 200
    assert queued.json()["events"][0]["review_status"] == "pending"
    assert [row["id"] for row in queued.json()["events"]] == ["capture-review", "capture-review-later"]
    response = client.post("/api/agri/review/articles/capture-review", json={
        "reviewer_id": "human-reviewer-1", "relevance": "relevant",
        "commodity_relevance": "onion_direct", "geographic_relevance": "india_wide",
        "publication_date_correctness": "correct",
        "classification_decisions": [{"prediction_category": "government_procurement", "decision": "approved"}],
        "events": [{"category": "government_procurement", "decision": "approved",
            "source_prediction_category": "government_procurement", "evidence": [{"quote": text}],
            "dates": [{"date": "2026-10-02", "role": "publication_date"}]}]})
    assert response.status_code == 200, response.text
    assert response.json()["review_count"] == 1
    history = client.get("/api/agri/review/articles/capture-review/history").json()["reviews"]
    assert len(history) == 1
    assert history[0]["payload"]["classification_decisions"][0]["decision"] == "approved"
    assert history[0]["payload"]["events"][0]["evidence"][0]["quote"] == text
    revised_text = text + " The new source revision changes this article body."
    article.update({"id": "capture-review-v2", "article_text": revised_text,
        "text_content_sha256": hashlib.sha256(revised_text.encode()).hexdigest(),
        "event_classifications": [{"category": "government_procurement", "evidence": [{"text": revised_text}]}]})
    revised_queue = client.get("/api/agri/review/queue").json()["events"][0]
    assert revised_queue["review_status"] == "pending"
    assert len(revised_queue["review_history"]) == 1


def test_local_review_api_reports_unavailable_archive_as_error_not_empty_queue(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.agri import review_api
    from sqlalchemy.pool import StaticPool

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    migrate(engine)
    monkeypatch.setattr(review_api, "_engine", lambda: engine)
    monkeypatch.setattr(review_api, "recent_captures", lambda *a, **k: {
        "status": "unavailable", "events": [], "reason": "Capture tables are unavailable"})
    response = TestClient(app).get("/api/agri/review/queue")
    assert response.status_code == 503
    assert response.json()["detail"] == "Capture tables are unavailable"


def test_local_review_api_rejects_non_exact_evidence_and_incomplete_decisions(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.agri import review_api, event_evaluation
    from sqlalchemy.pool import StaticPool

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    migrate(engine)
    text = "Official source sentence about onion procurement."
    digest = hashlib.sha256(text.encode()).hexdigest()
    article = {"id": "c", "article_identity": "pib:100", "content_status": "full_text_extracted",
        "article_text": text, "text_content_sha256": digest, "normalized_content_sha256": None,
        "event_classifications": [{"category": "government_procurement"}]}
    feed = {"events": [article]}
    monkeypatch.setattr(review_api, "_engine", lambda: engine)
    monkeypatch.setattr(review_api, "recent_captures", lambda *a, **k: feed)
    monkeypatch.setattr(event_evaluation, "recent_captures", lambda *a, **k: feed)
    client = TestClient(app)
    base = {"reviewer_id": "reviewer", "relevance": "relevant", "commodity_relevance": "onion_direct",
        "geographic_relevance": "india_wide", "publication_date_correctness": "uncertain"}
    incomplete = client.post("/api/agri/review/articles/c", json=base)
    assert incomplete.status_code == 422
    cross_site = client.post("/api/agri/review/articles/c", json=base,
        headers={"Origin": "https://untrusted.example"})
    assert cross_site.status_code == 403
    base["classification_decisions"] = [{"prediction_category": "government_procurement", "decision": "approved"}]
    base["events"] = [{"category": "government_procurement", "evidence": [{"quote": "not in source"}]}]
    invalid = client.post("/api/agri/review/articles/c", json=base)
    assert invalid.status_code == 422
    assert engine.connect().execute(select(human_event_reviews)).all() == []


def test_local_review_api_accepts_approved_prediction_with_body_evidence_only(monkeypatch):
    """Headline evidence is not a body span; exact body evidence persists once."""
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.agri import review_api, event_evaluation
    from sqlalchemy.pool import StaticPool

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    migrate(engine)
    headline = "Prohibition removed from Onion Export"
    body = "Central Government removes prohibition for the export of all varieties of Onions with effect from 01.01.2021"
    digest = hashlib.sha256(body.encode()).hexdigest()
    article = {"id": "pib-1684194-capture", "article_identity": "pib:1684194", "title": headline,
        "url": "https://www.pib.gov.in/Pressreleaseshare.aspx?PRID=1684194", "published_date": "2020-12-28",
        "first_seen_at": "2026-10-09T00:00:00+00:00", "content_status": "full_text_extracted",
        "article_text": body, "text_content_sha256": digest, "normalized_content_sha256": None,
        "event_classifications": [{"category": "export_restriction_removal", "evidence": [
            {"text": headline}, {"text": body}]}], "date_mentions": []}
    feed = {"status": "ready", "events": [article], "dataset_health": {"unique_articles": 1}}
    monkeypatch.setattr(review_api, "_engine", lambda: engine)
    monkeypatch.setattr(review_api, "recent_captures", lambda *a, **k: feed)
    monkeypatch.setattr(event_evaluation, "recent_captures", lambda *a, **k: feed)
    client = TestClient(app)
    base = {"reviewer_id": "reviewer_01", "relevance": "relevant", "commodity_relevance": "onion_direct",
        "geographic_relevance": "India-wide", "publication_date_correctness": "correct",
        "classification_decisions": [{"prediction_category": "export_restriction_removal", "decision": "approved"}],
        "events": [{"category": "export_restriction_removal", "decision": "approved",
            "source_prediction_category": "export_restriction_removal",
            "evidence": [{"quote": headline}, {"quote": body}],
            "dates": [{"date": "2021-01-01", "role": "Effective date"}]}],
        "notes": "The automatic date extraction missed the effective date of 1 January 2021"}
    rejected = client.post("/api/agri/review/articles/pib-1684194-capture", json=base)
    assert rejected.status_code == 422
    assert "exact contiguous passage" in rejected.json()["detail"]
    assert engine.connect().execute(select(human_event_reviews)).all() == []

    base["events"][0]["evidence"] = [{"quote": body}]
    saved = client.post("/api/agri/review/articles/pib-1684194-capture", json=base)
    assert saved.status_code == 200, saved.text
    assert saved.json()["review_count"] == 1
    queue = client.get("/api/agri/review/queue").json()
    assert queue["events"][0]["review_status"] == "reviewed"
    assert len(queue["events"][0]["review_history"]) == 1
    review = queue["events"][0]["review_history"][0]["payload"]
    assert review["events"][0]["evidence"] == [{"quote": body}]
    assert review["events"][0]["dates"] == [{"date": "2021-01-01", "role": "Effective date"}]
    assert review["notes"] == base["notes"]
    assert len(engine.connect().execute(select(human_event_reviews)).all()) == 1


def test_model_c_excludes_late_and_unverified_context_without_modifying_forecast():
    from backend.agri.model_c import build_combined_context
    series = {"series_id": "s", "market": "Lasalgaon", "district": "Nashik", "state": "Maharashtra",
        "commodity": "Onion"}
    forecast = {"origin": "2026-10-10", "prediction": 100.0, "status": "research_only"}
    base_review = {"article_identity": "pib:1", "first_seen_at": "2026-10-09T00:00:00Z",
        "source_url": "https://pib.gov.in/release", "title": "Test", "status": "reviewed",
        "identity_matches": True, "source_checksum_matches": True,
        "review": {"relevance": "relevant", "commodity_relevance": "onion_direct",
            "geographic_relevance": "Maharashtra", "events": [{"category": "export_duty_reduction",
            "evidence": [{"quote": "Exact source evidence."}]}]}}
    late = {**base_review, "article_identity": "pib:2", "first_seen_at": "2026-10-11T00:00:00Z"}
    unverified = {**base_review, "article_identity": "pib:3", "source_checksum_matches": False}
    result = build_combined_context(series_identity=series, forecast=forecast,
        forecast_origin_at="2026-10-10T18:29:59Z", reviews=[base_review, late, unverified])
    assert len(result["events"]) == 1
    assert result["events"][0]["article_identity"] == "pib:1"
    assert result["forecast"] == forecast
    assert result["numerical_adjustment"] is None
    assert result["measured_price_impact"] is None
    assert result["excluded_review_count_by_reason"]["after_forecast_origin"] == 1
    assert result["excluded_review_count_by_reason"]["identity_or_revision_unverified"] == 1


def test_model_c_blocks_all_news_when_forecast_missing():
    from backend.agri.model_c import build_combined_context
    result = build_combined_context(series_identity={"series_id": "s"}, forecast=None,
        forecast_origin_at="2026-10-10T00:00:00Z", reviews=[])
    assert result["status"] == "forecast_unavailable"
    assert result["events"] == []
    assert result["numerical_adjustment"] is None


def test_review_import_rejects_inexact_evidence_and_unknown_capture(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    migrate(engine)
    text = "Only this source sentence."
    digest = hashlib.sha256(text.encode()).hexdigest()
    article = {"id": "c1", "article_identity": "pib:1", "text_content_sha256": digest,
        "normalized_content_sha256": None, "article_text": text}
    monkeypatch.setattr(evaluation, "recent_captures", lambda *a, **k: {"events": [article]})
    entry = {"capture_id": "c1", "article_identity": "pib:1", "source_content_sha256": digest,
        "review": {"status": "reviewed", "reviewer_id": "r", "reviewed_at_utc": "2026-01-01T00:00:00Z",
            "relevance": "relevant", "publication_date_correctness": "uncertain",
            "events": [{"category": "market_price_report", "evidence": [{"quote": "invented sentence"}]}]}}
    path = tmp_path / "reviews.jsonl"; path.write_text(json.dumps(entry), encoding="utf-8")
    try:
        evaluation.import_human_reviews(engine, path)
    except ValueError as exc:
        assert "exact span" in str(exc)
    else:
        raise AssertionError("inexact supporting evidence was accepted")
    assert engine.connect().execute(select(human_event_reviews)).all() == []


def test_evaluation_without_review_labels_returns_null_metrics(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    monkeypatch.setattr(evaluation, "recent_captures", lambda *a, **k: {"events": []})
    migrate(engine)
    result = evaluation.evaluate_reviews(engine, markdown_path=tmp_path / "evaluation.md")
    assert result["status"] == "insufficient_labels"
    assert result["metrics"] is None
    assert "No metrics were computed" in (tmp_path / "evaluation.md").read_text(encoding="utf-8")


def test_manifest_collector_bounds_identity_preserves_raw_html_and_actual_retrieval_time(tmp_path, monkeypatch):
    from backend.agri import event_dataset
    engine = create_engine("sqlite:///:memory:")
    body = b'''<!doctype html><html><head>
      <meta property="og:url" content="https://www.pib.gov.in/PressReleasePage.aspx?PRID=501&amp;lang=1&amp;reg=48">
      <meta property="og:title" content="Government reports onion procurement activity">
      <meta property="og:description" content="The Government procured onions for the buffer this season, according to the official release.">
      </head><body><h1>Government reports onion procurement activity</h1>
      <p>Ministry of Consumer Affairs, Food &amp; Public Distribution</p>
      <p>Posted On: 09 OCT 2026 2:00PM by PIB Delhi</p>
      <p>The Government procured onions for the buffer this season to maintain supply and support farmers.</p></body></html>'''
    calls = []

    class Response(BytesIO):
        status = 200
        def geturl(self): return "https://www.pib.gov.in/PressReleasePage.aspx?PRID=501&lang=1&reg=48"
        def __enter__(self): return self
        def __exit__(self, *args): self.close()

    def opener(request, timeout):
        calls.append((request.full_url, timeout))
        return Response(body)

    monkeypatch.setattr(event_dataset.urllib.request, "urlopen", opener)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"articles": [
        {"prid": "501", "url": "https://www.pib.gov.in/PressReleasePage.aspx?PRID=501&lang=1", "status": "collect"},
        {"prid": "502", "url": "https://example.test/PressReleasePage.aspx?PRID=502", "status": "collect"},
    ]}), encoding="utf-8")
    before = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    result = event_dataset.import_manifest(engine, manifest, fetch=True, timeout=7, raw_dir=tmp_path / "raw")
    assert result["captured"] == 1, result
    assert [item["status"] for item in result["outcomes"]] == ["captured", "rejected"]
    assert calls == [("https://www.pib.gov.in/PressReleasePage.aspx?PRID=501&lang=1", 7)]
    capture = engine.connect().execute(select(captures)).mappings().one()
    run = engine.connect().execute(select(capture_runs)).mappings().one()
    assert capture["retrieved_at_utc"] >= before.isoformat()
    assert capture["first_seen_at_utc"] == capture["retrieved_at_utc"]
    assert run["retrieval_method"] == "official_pib_http_get"
    raw_path = __import__("pathlib").Path(result["outcomes"][0]["file"])
    assert raw_path.read_bytes() == body
    assert hashlib.sha256(raw_path.read_bytes()).hexdigest() == capture["raw_sha256"]
    second = event_dataset.import_manifest(engine, manifest, fetch=True, timeout=7, raw_dir=tmp_path / "raw")
    assert second["captured"] == 0
    assert second["outcomes"][0]["status"] == "already_captured"
    assert len(calls) == 1


def test_real_saved_article_normalization_preserves_capture_and_reuses_same_revision():
    from datetime import datetime, timezone
    from pathlib import Path
    from backend.agri.events import import_pib_html_file
    source = (Path(__file__).resolve().parents[2] / "data" / "pib" /
              "Press Release_ Press Information Bureau_files" / "PressReleasePage.html")
    if not source.exists():
        return
    engine = create_engine("sqlite:///:memory:")
    imported = import_pib_html_file(engine, source,
        retrieved_at=datetime(2026, 10, 9, 12, tzinfo=timezone.utc))
    before = engine.connect().execute(select(captures)).mappings().one()
    first = normalize_captures(engine)
    second = normalize_captures(engine)
    after = engine.connect().execute(select(captures)).mappings().one()
    norms = engine.connect().execute(select(text_normalizations)).mappings().all()
    assert imported["prid"] == "1684194"
    assert first["created"] == 1 and second["reused"] == 1
    assert len(norms) == 1
    assert before["capture_id"] == after["capture_id"]
    assert before["raw_sha256"] == after["raw_sha256"]
    assert before["first_seen_at_utc"] == after["first_seen_at_utc"]
