"""Fetch configured pages and save raw results for inspection."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import load_config
from app.crawler import crawl, save_crawl


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/sources.yaml")
    parser.add_argument("--output", default="data/crawl.json")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        report = asyncio.run(crawl(load_config(args.config)))
        save_crawl(report, args.output)
    except (OSError, ValueError, RuntimeError, yaml.YAMLError) as exc:
        logging.error("Crawl failed: %s", exc)
        return 2
    logging.info("discovered=%d crawled=%d failed=%d output=%s", report.discovered,
                 len(report.pages), len(report.failures), args.output)
    return 0 if report.pages else 1


if __name__ == "__main__":
    raise SystemExit(main())
