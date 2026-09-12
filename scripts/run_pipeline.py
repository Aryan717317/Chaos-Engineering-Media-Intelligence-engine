"""Crawl configured URLs, extract a graph and write SQLite evidence."""

import argparse
import asyncio
import json
import logging
import os
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timezone

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import load_config
from app.crawler import CrawlReport, crawl, save_crawl
from app.entities import load_aliases
from app.extract import load_nlp, load_topics
from app.pipeline import process_pages
from app.storage import connect


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/sources.yaml")
    parser.add_argument("--db", default=os.getenv("MEDIA_DB_PATH", "data/graph.db"))
    parser.add_argument("--model", default="en_core_web_sm")
    parser.add_argument("--topics", default="config/topics.yaml")
    parser.add_argument("--aliases", default="config/aliases.yaml")
    parser.add_argument("--from-crawl", help="Replay a saved Crawl4AI result, preserving observation times")
    parser.add_argument("--crawl-output", help="Optionally retain raw HTML/results locally")
    parser.add_argument("--report", default="data/run-summary.json")
    parser.add_argument("--strict", action="store_true", help="Return failure if any page fails")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        config = load_config(args.config)
        topics = load_topics(args.topics)
        aliases = load_aliases(args.aliases)
        nlp = load_nlp(args.model)
        if args.from_crawl:
            report = CrawlReport.model_validate_json(Path(args.from_crawl).read_text(encoding="utf-8"))
        else:
            report = asyncio.run(crawl(config))
        if args.crawl_output:
            save_crawl(report, args.crawl_output)
        summary = process_pages(report.pages, config, args.db, nlp, topics, aliases)
        expected = {seed.source_type or config.rule_for(seed.url).source_type for seed in config.seeds}
        missing = sorted(expected - summary.source_types.keys())
        with connect(args.db) as connection:
            totals = {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                      for table in ("sources", "nodes", "edges", "edge_evidence")}
        success = bool(summary.processed) and not missing
        if args.strict and (summary.failures or report.failures):
            success = False
        run_report = {"completed_at": datetime.now(timezone.utc).isoformat(),
            "mode": "replay" if args.from_crawl else "live", "success": success,
            "discovered": report.discovered, "crawled": len(report.pages),
            "crawl_failures": [failure.model_dump() for failure in report.failures],
            **summary.model_dump(), "missing_source_types": missing, "database_counts": totals}
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(run_report, indent=2), encoding="utf-8")
        logging.info("queued=%d crawled=%d crawl_failures=%d processed=%d processing_failures=%d new_evidence=%d types=%s",
                     report.discovered, len(report.pages), len(report.failures), summary.processed,
                     len(summary.failures), summary.evidence_added, summary.source_types)
        if missing:
            logging.error("No content processed for configured source types: %s", missing)
        return 0 if success else 1
    except (OSError, ValueError, RuntimeError, sqlite3.Error, yaml.YAMLError) as exc:
        logging.error("Pipeline failed: %s", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
