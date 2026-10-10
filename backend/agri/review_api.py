"""Loopback-only browser workflow for append-only Model B article reviews."""
from __future__ import annotations

from datetime import datetime, timezone
import ipaddress
import json
import tempfile
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from .event_evaluation import import_human_reviews, near_duplicate_groups
from .events import human_event_reviews, migrate, recent_captures
from .semantic import EVENT_TAXONOMY

router = APIRouter(prefix="/agri/review", tags=["Local Model B review"])
TAXONOMY = set(EVENT_TAXONOMY)


def _engine():
    from backend.app.models.database import engine
    return engine


def _require_local(request: Request):
    """Guard both reads and writes; deployment must bind Uvicorn to loopback."""
    client = request.client.host if request.client else ""
    try:
        if not ipaddress.ip_address(client).is_loopback:
            raise HTTPException(403, "The review workspace is available only from this computer")
    except ValueError:
        # Starlette's in-process TestClient uses this non-network sentinel.
        if client != "testclient":
            raise HTTPException(403, "The review workspace is available only from this computer")
    host = (request.headers.get("host", "").split(":", 1)[0].strip("[]").casefold())
    if host and host not in {"localhost", "127.0.0.1", "::1", "testserver", "testclient"}:
        raise HTTPException(403, "The review workspace requires a loopback Host")
    origin = request.headers.get("origin")
    if origin:
        from urllib.parse import urlsplit
        parsed = urlsplit(origin)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise HTTPException(403, "The review workspace accepts same-computer browser origins only")


class Evidence(BaseModel):
    quote: str = Field(min_length=1, max_length=4000)


class ReviewedDate(BaseModel):
    date: str = Field(min_length=10, max_length=10)
    role: str = Field(min_length=1, max_length=80)


class ReviewedEvent(BaseModel):
    category: str = Field(min_length=1, max_length=80)
    evidence: list[Evidence] = Field(default_factory=list, max_length=30)
    dates: list[ReviewedDate] = Field(default_factory=list, max_length=30)
    decision: Literal["approved", "corrected", "added"] = "approved"
    source_prediction_category: str | None = Field(default=None, max_length=80)


class ClassificationDecision(BaseModel):
    prediction_category: str = Field(min_length=1, max_length=80)
    decision: Literal["approved", "rejected", "corrected", "unsupported"]
    corrected_category: str | None = Field(default=None, max_length=80)


class ReviewSubmission(BaseModel):
    reviewer_id: str = Field(min_length=1, max_length=120)
    relevance: Literal["relevant", "irrelevant", "uncertain"]
    commodity_relevance: str = Field(min_length=1, max_length=80)
    geographic_relevance: str = Field(min_length=1, max_length=80)
    publication_date_correctness: Literal["correct", "incorrect", "uncertain"]
    corrected_publication_date: str | None = Field(default=None, max_length=10)
    classification_decisions: list[ClassificationDecision] = Field(default_factory=list, max_length=80)
    events: list[ReviewedEvent] = Field(default_factory=list, max_length=80)
    notes: str = Field(default="", max_length=4000)


@router.get("/queue")
def review_queue(request: Request, limit: int = 200):
    _require_local(request)
    if limit < 1 or limit > 200:
        raise HTTPException(422, "limit must be between 1 and 200")
    engine = _engine()
    try:
        migrate(engine)
        feed = recent_captures(engine, limit=limit)
        if feed.get("status") == "unavailable":
            raise HTTPException(503, feed.get("reason") or "Saved source article archive is unavailable")
        groups = near_duplicate_groups(feed.get("events", []))
        with engine.connect() as conn:
            history = conn.execute(select(human_event_reviews).order_by(
                human_event_reviews.c.reviewed_at_utc.desc())).mappings().all()
        by_article: dict[str, list[dict]] = {}
        for row in history:
            by_article.setdefault(row["article_key"], []).append({
                "review_id": row["review_id"], "capture_id": row["capture_id"], "reviewer_id": row["reviewer_id"],
                "reviewed_at_utc": row["reviewed_at_utc"], "status": row["status"],
                "supersedes_review_id": row["supersedes_review_id"],
                "payload": json.loads(row["payload_json"]),
            })
        for article in feed.get("events", []):
            article["evaluation_group_key"] = groups.get(article.get("article_identity"))
            article["review_history"] = by_article.get(article.get("article_identity"), [])
            current_hash = article.get("normalized_content_sha256") or article.get("text_content_sha256")
            article["review_status"] = "reviewed" if any(
                review.get("capture_id") == article.get("id")
                and review.get("payload", {}).get("source_content_sha256") == current_hash
                for review in article["review_history"]) else "pending"
        # Deterministic session order: unreviewed current revisions first,
        # oldest publication date first, then immutable identity and capture ID.
        feed["events"].sort(key=lambda article: (
            article.get("review_status") != "pending",
            article.get("published_date") is None,
            article.get("published_date") or "9999-12-31",
            article.get("article_identity") or "",
            article.get("id") or "",
        ))
        return {**feed, "review_mode": "local_loopback_append_only", "human_reviews_are_explicit": True}
    except (ValueError, OSError, SQLAlchemyError) as exc:
        raise HTTPException(503, "Local review queue is unavailable") from exc


@router.get("/evaluation")
def review_evaluation(request: Request):
    _require_local(request)
    from .event_evaluation import evaluate_reviews
    try:
        return evaluate_reviews(_engine())
    except (ValueError, OSError, SQLAlchemyError) as exc:
        raise HTTPException(503, "Human-review evaluation is unavailable") from exc


@router.post("/articles/{capture_id}")
def submit_review(capture_id: str, body: ReviewSubmission, request: Request):
    _require_local(request)
    engine = _engine()
    try:
        feed = recent_captures(engine, limit=200)
        item = next((row for row in feed.get("events", []) if row.get("id") == capture_id), None)
        if not item:
            raise HTTPException(404, "Capture is not present in the current source archive")
        if not item.get("article_text") or item.get("content_status") not in {
                "full_text_extracted", "full_body_verified", "manual_text_import_candidate"}:
            raise HTTPException(422, "A saved full-text representation is required for review")
        for decision in body.classification_decisions:
            if decision.prediction_category not in TAXONOMY:
                raise HTTPException(422, "Unknown predicted event category")
            if decision.corrected_category and decision.corrected_category not in TAXONOMY:
                raise HTTPException(422, "Unknown corrected event category")
        predicted = {row.get("category") for row in item.get("event_classifications", []) if row.get("category") in TAXONOMY}
        decisions = {row.prediction_category for row in body.classification_decisions}
        if predicted != decisions or len(decisions) != len(body.classification_decisions):
            raise HTTPException(422, "Every predicted category needs one explicit approve, reject, correction, or unsupported decision")
        for decision in body.classification_decisions:
            linked = [event for event in body.events if event.source_prediction_category == decision.prediction_category]
            if decision.decision in {"approved", "corrected"} and not linked:
                raise HTTPException(422, "Approved or corrected predictions need a reviewed event and exact evidence")
            if decision.decision in {"rejected", "unsupported"} and linked:
                raise HTTPException(422, "Rejected or unsupported predictions cannot remain in the reviewed event set")
            if decision.decision == "approved" and any(event.category != decision.prediction_category for event in linked):
                raise HTTPException(422, "Approved predictions must retain their original category")
            if decision.decision == "corrected" and (not decision.corrected_category
                    or any(event.category != decision.corrected_category for event in linked)):
                raise HTTPException(422, "Corrected predictions must retain the reviewer-selected corrected category")
        for event in body.events:
            if event.category not in TAXONOMY:
                raise HTTPException(422, "Unknown reviewed event category")
            if event.source_prediction_category and event.source_prediction_category not in TAXONOMY:
                raise HTTPException(422, "Unknown source prediction category")
            if event.decision == "corrected" and not event.source_prediction_category:
                raise HTTPException(422, "A corrected event must identify the prediction it corrects")
            for evidence in event.evidence:
                if evidence.quote not in item["article_text"]:
                    raise HTTPException(422, "Evidence must be an exact contiguous passage in the saved source text")
            for date in event.dates:
                try:
                    datetime.strptime(date.date, "%Y-%m-%d")
                except ValueError as exc:
                    raise HTTPException(422, "Event dates must use YYYY-MM-DD") from exc
        if body.corrected_publication_date:
            try:
                datetime.strptime(body.corrected_publication_date, "%Y-%m-%d")
            except ValueError as exc:
                raise HTTPException(422, "Corrected publication date must use YYYY-MM-DD") from exc
        if body.relevance == "relevant" and any(not event.evidence for event in body.events):
            raise HTTPException(422, "Each reviewed event needs at least one exact supporting passage")
        groups = near_duplicate_groups(feed.get("events", []))
        reviewed_at = datetime.now(timezone.utc).isoformat()
        envelope = {
            "capture_id": capture_id, "article_identity": item["article_identity"],
            "evaluation_group_key": groups.get(item.get("article_identity")),
            "source_content_sha256": item.get("normalized_content_sha256") or item.get("text_content_sha256"),
            "review": {**body.model_dump(), "status": "reviewed", "reviewed_at_utc": reviewed_at},
        }
        with tempfile.TemporaryDirectory(prefix="nexyra-review-") as folder:
            path = Path(folder) / "review.jsonl"
            path.write_text(json.dumps(envelope, ensure_ascii=False) + "\n", encoding="utf-8")
            result = import_human_reviews(engine, path)
        result["reviewed_at_utc"] = reviewed_at
        result["article_identity"] = item["article_identity"]
        return result
    except HTTPException:
        raise
    except (ValueError, OSError, SQLAlchemyError) as exc:
        raise HTTPException(422, str(exc)[:300]) from exc


@router.get("/articles/{capture_id}/history")
def review_history(capture_id: str, request: Request):
    _require_local(request)
    engine = _engine()
    try:
        feed = recent_captures(engine, limit=200)
        item = next((row for row in feed.get("events", []) if row.get("id") == capture_id), None)
        if not item:
            raise HTTPException(404, "Capture is not present in the current source archive")
        migrate(engine)
        with engine.connect() as conn:
            rows = conn.execute(select(human_event_reviews).where(
                human_event_reviews.c.article_key == item["article_identity"]).order_by(
                human_event_reviews.c.reviewed_at_utc)).mappings().all()
        return {"article_identity": item["article_identity"], "reviews": [{
            "review_id": row["review_id"], "capture_id": row["capture_id"],
            "source_content_sha256": row["source_content_sha256"], "reviewer_id": row["reviewer_id"],
            "reviewed_at_utc": row["reviewed_at_utc"], "status": row["status"],
            "supersedes_review_id": row["supersedes_review_id"], "payload": json.loads(row["payload_json"]),
        } for row in rows]}
    except HTTPException:
        raise
    except (ValueError, OSError, SQLAlchemyError) as exc:
        raise HTTPException(503, "Review history is unavailable") from exc
