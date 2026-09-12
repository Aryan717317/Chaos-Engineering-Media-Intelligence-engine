import json
from datetime import datetime, timezone

import pytest
import spacy
import yaml

from app.config import CrawlConfig
from app.crawler import CrawlReport, RawPage
from app.pipeline import process_pages
from app.storage import connect
from scripts import run_pipeline


@pytest.fixture
def small_nlp():
    nlp = spacy.blank("en")
    nlp.add_pipe("sentencizer")
    nlp.add_pipe("entity_ruler").add_patterns([
        {"label": "PERSON", "pattern": "Alice"}, {"label": "ORG", "pattern": "Acme"}])
    return nlp


def raw(kind, index=0, html=None):
    url = f"https://example.org/{kind}/{index}"
    return RawPage(source_url=url, requested_url=url, source_type=kind, depth=0,
        scraped_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        html=html if html is not None else '<article><div class="commtext"><p>Alice works for Acme.</p></div></article>')


def test_all_source_types_share_one_pipeline_and_reruns_add_no_evidence(tmp_path, small_nlp):
    config = CrawlConfig(seeds=["https://example.org"], allowed_domains=["example.org"])
    pages = [raw(kind) for kind in ("news", "discussion", "blog")]
    path = str(tmp_path / "graph.db")
    summary = process_pages(pages, config, path, small_nlp, {}, [])
    assert summary.source_types == {"blog": 1, "discussion": 1, "news": 1}
    assert summary.evidence_added == 3
    assert process_pages(pages, config, path, small_nlp, {}, []).evidence_added == 0
    with connect(path) as connection:
        assert connection.execute("SELECT weight FROM edges").fetchone()[0] == 3


@pytest.mark.parametrize("strict,expected", [(False, 0), (True, 1)])
def test_cli_reports_failed_pages_and_strict_exit_status(tmp_path, monkeypatch, small_nlp, strict, expected):
    monkeypatch.setattr(run_pipeline, "load_nlp", lambda model: small_nlp)
    config_path = tmp_path / "sources.yaml"
    config_path.write_text(yaml.safe_dump({"seeds": [{"url": "https://example.org/news/0", "source_type": "news"}],
                                          "allowed_domains": ["example.org"]}), encoding="utf-8")
    crawl_path = tmp_path / "crawl.json"
    crawl_path.write_text(CrawlReport(pages=[raw("news"), raw("news", 1, "")]).model_dump_json(), encoding="utf-8")
    report_path = tmp_path / "report.json"
    args = ["--config", str(config_path), "--from-crawl", str(crawl_path), "--db", str(tmp_path / "graph.db"),
            "--report", str(report_path)] + (["--strict"] if strict else [])
    assert run_pipeline.main(args) == expected
    report = json.loads(report_path.read_text())
    assert report["processed"] == 1 and report["failures"][0]["stage"] == "normalization"
    assert report["mode"] == "replay"


def test_cli_fails_when_a_configured_source_type_is_missing(tmp_path, monkeypatch, small_nlp):
    monkeypatch.setattr(run_pipeline, "load_nlp", lambda model: small_nlp)
    config_path = tmp_path / "sources.yaml"
    config_path.write_text(yaml.safe_dump({"seeds": [
        {"url": "https://example.org/news", "source_type": "news"},
        {"url": "https://example.org/blog", "source_type": "blog"}], "allowed_domains": ["example.org"]}), encoding="utf-8")
    crawl_path = tmp_path / "crawl.json"
    crawl_path.write_text(CrawlReport(pages=[raw("news")]).model_dump_json(), encoding="utf-8")
    report_path = tmp_path / "report.json"
    assert run_pipeline.main(["--config", str(config_path), "--from-crawl", str(crawl_path),
        "--db", str(tmp_path / "graph.db"), "--report", str(report_path)]) == 1
    assert json.loads(report_path.read_text())["missing_source_types"] == ["blog"]
