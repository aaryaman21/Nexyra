"""Ephemeral browser-test API backed by a temporary SQLite database."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
import uvicorn

from backend.app.main import app
from backend.agri import event_evaluation, review_api
from backend.agri.events import migrate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--fixture", required=True)
    args = parser.parse_args()
    engine = create_engine(f"sqlite:///{args.database.replace(chr(92), '/')}", connect_args={"check_same_thread": False})
    migrate(engine)
    article = json.load(open(args.fixture, encoding="utf-8"))
    feed = {"status": "ready", "events": [article], "dataset_health": {
        "unique_articles": 1, "human_reviewed_articles": 0}}
    review_api._engine = lambda: engine
    review_api.recent_captures = lambda *a, **k: feed
    event_evaluation.recent_captures = lambda *a, **k: feed
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="error")


if __name__ == "__main__":
    main()
