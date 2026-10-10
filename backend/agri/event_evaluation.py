"""Append-only human review and article/event/evidence/date evaluation for Model B."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import uuid
import hashlib

from sqlalchemy import create_engine, select

from .events import human_event_reviews, migrate, recent_captures
from .semantic import EVENT_TAXONOMY

TAXONOMY = set(EVENT_TAXONOMY)


def near_duplicate_groups(articles, *, threshold=0.90):
    """Cluster near-identical source bodies for temporal split grouping only."""
    rows = list(articles)
    parent = list(range(len(rows)))
    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index
    def union(left, right):
        left, right = find(left), find(right)
        if left != right:
            parent[max(left, right)] = min(left, right)
    shingles = []
    for row in rows:
        words = re.findall(r"[a-z0-9]+", (row.get("article_text") or "").casefold())
        shingles.append({" ".join(words[i:i + 5]) for i in range(max(1, len(words) - 4))} if len(words) >= 5 else set(words))
    for i in range(len(rows)):
        if not shingles[i]:
            continue
        for j in range(i + 1, len(rows)):
            if not shingles[j]:
                continue
            union_size = len(shingles[i] | shingles[j])
            if union_size and len(shingles[i] & shingles[j]) / union_size >= threshold:
                union(i, j)
    members = {}
    for index, row in enumerate(rows):
        members.setdefault(find(index), []).append(str(row.get("article_identity") or row.get("id")))
    output = {}
    for indices, identities in ((root, sorted(values)) for root, values in members.items()):
        group_id = "group:" + hashlib.sha256("|".join(identities).encode()).hexdigest()[:16]
        for identity in identities:
            output[identity] = group_id
    return output


def export_review_queue(engine, path):
    migrate(engine)
    feed = recent_captures(engine, limit=200)
    group_map = near_duplicate_groups(feed.get("events", []))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output:
        for item in feed.get("events", []):
            output.write(json.dumps({
                "capture_id": item["id"], "article_identity": item.get("article_identity"),
                "evaluation_group_key": group_map.get(item.get("article_identity")),
                "source_content_sha256": item.get("normalized_content_sha256") or item.get("text_content_sha256"),
                "source_url": item["url"], "headline": item["title"], "prid": item.get("prid"),
                "publication_date": item.get("published_date"), "publication_precision": item.get("publication_precision"),
                "publication_date_extraction": {"predicted_date": item.get("published_date"),
                    "source_time_text": item.get("published_time_source_text"),
                    "source_verification": item.get("metadata_verification"), "human_review_status": "pending"},
                "acquired_at_utc": item.get("first_seen_at"), "content_status": item.get("content_status"),
                "article_text": item.get("article_text"),
                "predictions_for_reference_only": {"relevance": item.get("relevance_status"),
                    "commodity": item.get("commodity_relevance"), "geography": item.get("geographic_relevance"),
                    "events": item.get("event_classifications", []), "dates": item.get("date_mentions", [])},
                "review": {"status": "pending", "reviewer_id": "", "reviewed_at_utc": "",
                    "relevance": "", "commodity_relevance": "", "geographic_relevance": "",
                    "publication_date_correctness": "", "corrected_publication_date": "",
                    "events": [], "notes": ""},
            }, ensure_ascii=False) + "\n")
    return {"status": "exported", "path": str(path), "articles": len(feed.get("events", [])),
            "all_rows_pending": True, "evaluation_partition": "development_reused"}


def _parse_utc(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("reviewed_at_utc must include an explicit timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def import_human_reviews(engine, path):
    migrate(engine)
    feed = recent_captures(engine, limit=200)
    current = {item["id"]: item for item in feed.get("events", [])}
    group_map = near_duplicate_groups(feed.get("events", []))
    review_rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    outcomes, skipped_duplicate = [], 0
    with engine.begin() as conn:
        existing = conn.execute(select(human_event_reviews)).mappings().all()
        latest = {}
        for record in sorted(existing, key=lambda row: row["reviewed_at_utc"]):
            latest[record["article_key"]] = record
        for envelope in review_rows:
            nested = envelope.get("review")
            review = nested if isinstance(nested, dict) else envelope
            capture_id = envelope.get("capture_id")
            article = current.get(capture_id)
            if not article:
                raise ValueError(f"unknown or stale capture_id: {capture_id}")
            expected_hash = article.get("normalized_content_sha256") or article.get("text_content_sha256")
            if envelope.get("article_identity") != article.get("article_identity") or envelope.get("source_content_sha256") != expected_hash:
                raise ValueError(f"article identity or source checksum mismatch for capture {capture_id}")
            expected_group = group_map.get(article.get("article_identity"))
            if envelope.get("evaluation_group_key") not in {None, expected_group}:
                raise ValueError(f"near-duplicate evaluation group mismatch for capture {capture_id}")
            status = review.get("status")
            if status != "reviewed":
                raise ValueError("only completed human reviews can be imported")
            reviewer = str(review.get("reviewer_id", "")).strip()
            if not reviewer:
                raise ValueError("reviewer_id is required")
            reviewed_at = _parse_utc(review.get("reviewed_at_utc", ""))
            relevance = review.get("relevance")
            if relevance not in {"relevant", "irrelevant", "uncertain"}:
                raise ValueError("relevance must be relevant, irrelevant, or uncertain")
            publication_date_correctness = review.get("publication_date_correctness")
            if publication_date_correctness not in {"correct", "incorrect", "uncertain"}:
                raise ValueError("publication_date_correctness must be correct, incorrect, or uncertain")
            corrected_publication_date = review.get("corrected_publication_date") or None
            if corrected_publication_date:
                datetime.strptime(corrected_publication_date, "%Y-%m-%d")
            if publication_date_correctness == "incorrect" and not corrected_publication_date:
                raise ValueError("incorrect publication date requires corrected_publication_date when the source supports one")
            if publication_date_correctness == "correct" and not article.get("published_date"):
                raise ValueError("a missing predicted publication date cannot be marked correct")
            body = article.get("article_text") or ""
            events = review.get("events") or []
            for event in events:
                if event.get("category") not in TAXONOMY:
                    raise ValueError(f"unknown event category: {event.get('category')}")
                for evidence in event.get("evidence", []):
                    quote = evidence.get("quote", "")
                    if not quote or quote not in body:
                        raise ValueError(f"evidence quote is not an exact span in source text for {capture_id}")
                for date in event.get("dates", []):
                    if date.get("date"):
                        datetime.strptime(date["date"], "%Y-%m-%d")
                    if not date.get("role"):
                        raise ValueError("date mention requires a temporal role")
            key = article["article_identity"]
            prior = latest.get(key)
            supersedes = review.get("supersedes_review_id") or (prior["review_id"] if prior else None)
            review_id = str(uuid.uuid4())
            payload = {"relevance": relevance, "commodity_relevance": review.get("commodity_relevance"),
                "geographic_relevance": review.get("geographic_relevance"), "events": events,
                "classification_decisions": review.get("classification_decisions", []),
                "publication_date_review": {"correctness": publication_date_correctness,
                    "predicted_date": article.get("published_date"),
                    "gold_date": corrected_publication_date if publication_date_correctness == "incorrect" else article.get("published_date") if publication_date_correctness == "correct" else None},
                "notes": review.get("notes", ""), "source_content_sha256": expected_hash,
                "evaluation_group_key": expected_group,
                "publication_date": article.get("published_date"), "acquired_at_utc": article.get("first_seen_at"),
                "evaluation_partition": "development_reused"}
            duplicate = next((record for record in existing if record["article_key"] == key
                and record["capture_id"] == capture_id and record["source_content_sha256"] == expected_hash
                and record["reviewer_id"] == reviewer and record["reviewed_at_utc"] == reviewed_at
                and record["payload_json"] == json.dumps(payload, ensure_ascii=False)), None)
            if duplicate:
                skipped_duplicate += 1
                continue
            conn.execute(human_event_reviews.insert().values(review_id=review_id, article_key=key,
                capture_id=capture_id, source_content_sha256=expected_hash, reviewer_id=reviewer,
                reviewed_at_utc=reviewed_at, status="reviewed", payload_json=json.dumps(payload, ensure_ascii=False),
                supersedes_review_id=supersedes))
            latest[key] = {"review_id": review_id, "reviewed_at_utc": reviewed_at}
            existing.append({"article_key": key, "capture_id": capture_id, "source_content_sha256": expected_hash,
                "reviewer_id": reviewer, "reviewed_at_utc": reviewed_at,
                "payload_json": json.dumps(payload, ensure_ascii=False), "review_id": review_id})
            outcomes.append({"review_id": review_id, "capture_id": capture_id, "article_identity": key,
                             "supersedes_review_id": supersedes})
    return {"status": "imported", "review_count": len(outcomes), "duplicates_skipped": skipped_duplicate,
            "append_only": True, "reviews": outcomes}


def _scores(tp, fp, fn):
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else None
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1,
            "gold_denominator": tp + fn, "prediction_denominator": tp + fp}


def _sets_metric(predicted, actual):
    return _scores(len(predicted & actual), len(predicted - actual), len(actual - predicted))


def evaluate_reviews(engine, *, markdown_path=None):
    feed = recent_captures(engine, limit=200)
    current = {item.get("article_identity"): item for item in feed.get("events", [])}
    migrate(engine)
    with engine.connect() as conn:
        records = conn.execute(select(human_event_reviews).order_by(human_event_reviews.c.reviewed_at_utc)).mappings().all()
    latest = {}
    for row in records:
        latest[row["article_key"]] = row
    exclusions = {"unreviewed": 0, "uncertain": 0, "identity_or_checksum_mismatch": 0,
                  "not_relevant": 0, "development_reused": 0, "current_eligible": 0}
    exclusions["unreviewed"] = max(0, len(current) - len(latest))
    selected = []
    for key, row in latest.items():
        item = current.get(key)
        payload = json.loads(row["payload_json"])
        if not item or payload.get("source_content_sha256") != (item.get("normalized_content_sha256") or item.get("text_content_sha256")):
            exclusions["identity_or_checksum_mismatch"] += 1; continue
        if row["status"] != "reviewed":
            exclusions["unreviewed"] += 1; continue
        if payload.get("relevance") == "uncertain":
            exclusions["uncertain"] += 1; continue
        if payload.get("relevance") == "irrelevant":
            exclusions["not_relevant"] += 1
        exclusions["development_reused"] += 1
        selected.append((item, payload))
    exclusions["current_eligible"] = len(selected)
    if not selected:
        result = {"status": "insufficient_labels", "review_history_records": len(records), "reviewed_article_count": len(latest),
            "eligible_article_count": 0, "near_duplicate_group_count": len(set(near_duplicate_groups(feed.get("events", [])).values())), "exclusions": exclusions,
            "publication_date_extraction": {"reviewed_denominator": 0, "correct": 0, "accuracy": None, "uncertain_excluded": 0},
            "metrics": None, "message": "No eligible reviewed labels match current source revisions; no scores calculated."}
        if markdown_path: Path(markdown_path).write_text(_markdown(result), encoding="utf-8")
        return result

    relevance_pairs = [(item.get("relevance_status") == "relevant", payload.get("relevance") == "relevant") for item, payload in selected]
    relevance = _scores(sum(p and g for p, g in relevance_pairs), sum(p and not g for p, g in relevance_pairs), sum(not p and g for p, g in relevance_pairs))
    reviewed_publication_dates = [payload.get("publication_date_review", {}) for _, payload in selected
                                  if payload.get("publication_date_review", {}).get("correctness") in {"correct", "incorrect"}]
    publication_date_correct = sum(review.get("predicted_date") == review.get("gold_date") for review in reviewed_publication_dates)
    event_pairs, pred_spans, gold_spans, pred_dates, gold_dates = [], set(), set(), set(), set()
    per_category = {}
    for item, payload in selected:
        gold_events = payload.get("events", [])
        # If the reviewed article is irrelevant, event and span labels are omitted, not negative labels.
        if payload.get("relevance") != "relevant":
            continue
        gold_categories = {ev["category"] for ev in gold_events}
        pred_categories = {ev.get("category") for ev in item.get("event_classifications", [])}
        event_pairs.append((pred_categories, gold_categories))
        for category in pred_categories | gold_categories:
            stats = per_category.setdefault(category, [0, 0, 0])
            stats[0] += len(pred_categories & gold_categories & {category})
            stats[1] += len((pred_categories - gold_categories) & {category})
            stats[2] += len((gold_categories - pred_categories) & {category})
        for ev in item.get("event_classifications", []):
            for evidence in ev.get("evidence", []): pred_spans.add((item["article_identity"], ev.get("category"), evidence.get("text", "")))
        for ev in gold_events:
            for evidence in ev.get("evidence", []): gold_spans.add((item["article_identity"], ev["category"], evidence.get("quote", "")))
        for date in item.get("date_mentions", []):
            if date.get("normalized_date"): pred_dates.add((item["article_identity"], date.get("role"), date["normalized_date"]))
        for ev in gold_events:
            for date in ev.get("dates", []):
                if date.get("date"): gold_dates.add((item["article_identity"], date.get("role"), date["date"]))
    # Labels are scored per article and category, so identical labels on distinct articles count separately.
    predicted_pairs = {(item["article_identity"], category) for item, payload in selected if payload.get("relevance") == "relevant" for category in {e.get("category") for e in item.get("event_classifications", [])}}
    gold_pairs = {(item["article_identity"], ev["category"]) for item, payload in selected if payload.get("relevance") == "relevant" for ev in payload.get("events", [])}
    event_metric = _sets_metric(predicted_pairs, gold_pairs)
    category_metrics = {category: _scores(*counts) for category, counts in per_category.items()}
    macro_categories = [metric for metric in category_metrics.values() if metric["f1"] is not None]
    event_macro = {"category_count": len(macro_categories),
                   "precision": sum(item["precision"] for item in macro_categories) / len(macro_categories) if macro_categories else None,
                   "recall": sum(item["recall"] for item in macro_categories) / len(macro_categories) if macro_categories else None,
                   "f1": sum(item["f1"] for item in macro_categories) / len(macro_categories) if macro_categories else None}
    span_metric = _sets_metric(pred_spans, gold_spans)
    date_metric = _sets_metric(pred_dates, gold_dates)
    correct_dates = len(pred_dates & gold_dates)
    missing_evidence_articles = sum(
        payload.get("relevance") == "relevant" and not any(ev.get("evidence") for ev in payload.get("events", []))
        for _, payload in selected)
    result = {"status": "exploratory_development_reused", "review_history_records": len(records),
        "reviewed_article_count": len(latest), "eligible_article_count": len(selected),
        "near_duplicate_group_count": len(set(near_duplicate_groups([item for item, _ in selected]).values())),
        "relevance_denominator": len(relevance_pairs), "event_article_count": len(event_pairs),
        "evidence_span_denominator": len(gold_spans), "date_mention_denominator": len(gold_dates),
        "relevance": relevance, "events_micro": event_metric, "events_macro": event_macro,
        "events_per_category": category_metrics,
        "publication_date_extraction": {"reviewed_denominator": len(reviewed_publication_dates),
            "correct": publication_date_correct,
            "accuracy": publication_date_correct / len(reviewed_publication_dates) if reviewed_publication_dates else None,
            "uncertain_excluded": sum(payload.get("publication_date_review", {}).get("correctness") == "uncertain" for _, payload in selected)},
        "evidence_exact_span": span_metric, "dates_exact_value_and_role": {**date_metric,
            "correct": correct_dates, "gold_date_count": len(gold_dates)},
        "missing_evidence": {"relevant_reviewed_articles": sum(payload.get("relevance") == "relevant" for _, payload in selected),
            "articles_without_supported_evidence": missing_evidence_articles,
            "rate": missing_evidence_articles / sum(payload.get("relevance") == "relevant" for _, payload in selected)
                if any(payload.get("relevance") == "relevant" for _, payload in selected) else None},
        "exclusions": exclusions, "partition_counts": {"development_reused": len(selected), "independent_test": 0},
        "warning": "All current articles and predictions informed development. This is descriptive only, not an independent test or generalizable accuracy claim."}
    if markdown_path: Path(markdown_path).write_text(_markdown(result), encoding="utf-8")
    return result


def _markdown(result):
    if result["status"] == "insufficient_labels":
        return ("# Model B semantic evaluation\n\nStatus: insufficient human-reviewed labels. No metrics were computed.\n\n"
                f"Review-history records: {result['review_history_records']}\n\nExclusions: `{json.dumps(result['exclusions'])}`\n")
    return ("# Model B semantic evaluation\n\n"
        f"Status: {result['status']}\n\nReviewed articles: {result['reviewed_article_count']} · eligible descriptive labels: {result['eligible_article_count']}\n\n"
        f"Relevance (n={result['relevance_denominator']}): `{json.dumps(result['relevance'])}`\n\n"
        f"Events micro (n={result['event_article_count']}): `{json.dumps(result['events_micro'])}`\n\n"
        f"Events macro: `{json.dumps(result['events_macro'])}`\n\n"
        f"Per category: `{json.dumps(result['events_per_category'])}`\n\n"
        f"Publication-date extraction: `{json.dumps(result['publication_date_extraction'])}`\n\n"
        f"Exact evidence spans (gold n={result['evidence_span_denominator']}): `{json.dumps(result['evidence_exact_span'])}`\n\n"
        f"Exact dates and roles (gold n={result['date_mention_denominator']}): `{json.dumps(result['dates_exact_value_and_role'])}`\n\n"
        f"Missing evidence: `{json.dumps(result['missing_evidence'])}`\n\n"
        f"Exclusions: `{json.dumps(result['exclusions'])}`\n\nWarning: {result['warning']}\n")


# Retain the earlier CSV export/evaluate API for reproducibility of historical reports.
def export_annotations(engine, path):
    feed = recent_captures(engine, limit=200)
    fields = ["capture_id", "prid", "headline", "published_date", "predicted_categories", "predicted_commodity_relevance", "predicted_geographic_relevance", "evidence", "evaluation_partition", "human_reviewed", "human_categories", "human_commodity_relevance", "human_geographic_relevance", "reviewer_provenance", "reviewed_at_utc", "review_notes"]
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as output:
        writer = csv.DictWriter(output, fieldnames=fields); writer.writeheader()
        for item in feed.get("events", []):
            writer.writerow({"capture_id": item["id"], "prid": item.get("prid", ""), "headline": item["title"],
                "published_date": item.get("published_date", ""), "predicted_categories": ";".join(x["category"] for x in item.get("event_classifications", [])),
                "predicted_commodity_relevance": item.get("commodity_relevance"), "predicted_geographic_relevance": item.get("geographic_relevance"),
                "evidence": json.dumps(item.get("evidence", []), ensure_ascii=False), "evaluation_partition": "development_reused",
                "human_reviewed": "false", "human_categories": "", "human_commodity_relevance": "", "human_geographic_relevance": "", "reviewer_provenance": "", "reviewed_at_utc": "", "review_notes": ""})
    return {"path": str(path), "genuine_captures_exported": len(feed.get("events", [])), "reviewed_labels": 0}


def evaluate_annotations(path):
    rows = list(csv.DictReader(Path(path).open(newline="", encoding="utf-8-sig")))
    return {"status": "insufficient_labels", "annotation_rows": len(rows),
            "reviewed_rows": sum(row.get("human_reviewed", "").casefold() == "true" for row in rows),
            "metrics": None, "message": "Use the append-only JSON review workflow; no unreviewed row is treated as gold."}


def main(argv=None):
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("--output", default="data/pib/annotations.csv")
    export.add_argument("--database-url", default=os.getenv("DATABASE_URL", "sqlite:///./nexyra.db"))
    queue = commands.add_parser("export-review")
    queue.add_argument("--output", default="data/pib/review_queue.jsonl")
    queue.add_argument("--database-url", default=os.getenv("DATABASE_URL", "sqlite:///./nexyra.db"))
    imp = commands.add_parser("import-reviews")
    imp.add_argument("--file", required=True)
    imp.add_argument("--database-url", default=os.getenv("DATABASE_URL", "sqlite:///./nexyra.db"))
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--database-url", default=os.getenv("DATABASE_URL", "sqlite:///./nexyra.db"))
    evaluate.add_argument("--json-output", default="data/pib/evaluation.json")
    evaluate.add_argument("--markdown-output", default="data/pib/evaluation.md")
    legacy = commands.add_parser("evaluate-csv")
    legacy.add_argument("--file", default="data/pib/annotations.csv")
    args = parser.parse_args(argv)
    if args.command == "evaluate-csv":
        result = evaluate_annotations(args.file)
    else:
        engine = create_engine(args.database_url, future=True)
        try:
            if args.command == "export": result = export_annotations(engine, args.output)
            elif args.command == "export-review": result = export_review_queue(engine, args.output)
            elif args.command == "import-reviews": result = import_human_reviews(engine, args.file)
            else:
                result = evaluate_reviews(engine, markdown_path=args.markdown_output)
                Path(args.json_output).parent.mkdir(parents=True, exist_ok=True)
                Path(args.json_output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        finally: engine.dispose()
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
