import asyncio
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.config import CrawlConfig, canonical_url, domain_allowed, load_config
from app.crawler import crawl


def test_url_cleanup_keeps_content_query_and_drops_tracking():
    assert canonical_url("https://EXAMPLE.org:443/item?id=1&utm_source=x#comment") == "https://example.org/item?id=1"
    assert canonical_url("https://example.org/item?id=2") != canonical_url("https://example.org/item?id=1")


@pytest.mark.parametrize("url,expected", [
    ("https://example.org", True), ("https://news.example.org/a", True),
    ("https://notexample.org", False), ("https://example.org.evil.net", False),
    ("javascript:alert(1)", False), ("https://example.org@evil.net", False),
])
def test_domain_boundary(url, expected):
    assert domain_allowed(url, ["example.org"]) is expected


def test_configuration_accepts_changed_plain_seeds(tmp_path):
    path = tmp_path / "sources.yaml"
    path.write_text("seeds: [https://different.org/story]\nallowed_domains: [different.org]\nmax_depth: 0")
    config = load_config(path)
    assert config.seeds[0].url == "https://different.org/story"
    assert config.max_depth == 0
    with pytest.raises(ValidationError, match="allowed_domains"):
        CrawlConfig(seeds=["https://outside.org"], allowed_domains=["different.org"])


@pytest.mark.parametrize("depth,expected", [(0, ["/a"]), (1, ["/a", "/b", "/bad"]), (2, ["/a", "/b", "/bad", "/c"])])
def test_depth_duplicates_cycles_and_failed_pages(depth, expected):
    called = []
    async def fetch(url):
        path = url.removeprefix("https://example.org")
        called.append(path)
        if path == "/bad":
            raise TimeoutError("page timed out")
        targets = {"/a": ["/a#anchor", "/b", "/bad", "https://outside.org/"], "/b": ["/c"], "/c": []}
        return SimpleNamespace(success=True, url=url, html="<p>content</p>", status_code=200,
                               links={"internal": [{"href": v} for v in targets[path]]})
    config = CrawlConfig(seeds=["https://example.org/a"], allowed_domains=["example.org"],
                         max_depth=depth, delay_seconds=0)
    report = asyncio.run(crawl(config, fetch=fetch))
    assert called == expected
    assert len(report.failures) == (1 if depth else 0)


def test_page_limit_and_redirect_boundary():
    async def fetch(url):
        return SimpleNamespace(success=True, url=url, redirected_url="https://outside.org/",
                               html="<p>x</p>", status_code=200, links={})
    config = CrawlConfig(seeds=["https://example.org"], allowed_domains=["example.org"], max_pages=1)
    report = asyncio.run(crawl(config, fetch=fetch))
    assert not report.pages
    assert "Redirect" in report.failures[0].error


def test_page_budget_and_configured_link_filter():
    called = []
    async def fetch(url):
        called.append(url)
        return SimpleNamespace(success=True, url=url, html="<p>x</p>", status_code=200,
            links={"internal": [{"href": "/account"}, {"href": "/story/1"}, {"href": "/story/2"}]})
    config = CrawlConfig(seeds=["https://example.org"], allowed_domains=["example.org"],
        max_depth=2, max_pages=2, delay_seconds=0,
        source_rules={"example.org": {"source_type": "blog", "follow_pattern": "/story/"}})
    report = asyncio.run(crawl(config, fetch=fetch))
    assert called == ["https://example.org/", "https://example.org/story/1"]
    assert {page.source_type for page in report.pages} == {"blog"}


@pytest.mark.parametrize("override", [
    {"max_depth": -1}, {"max_pages": 0}, {"allowed_domains": ["https://example.org"]},
    {"source_rules": {"example.org": {"follow_pattern": "["}}},
])
def test_invalid_configuration_fails_early(override):
    values = {"seeds": ["https://example.org"], "allowed_domains": ["example.org"]}
    values.update(override)
    with pytest.raises(ValidationError):
        CrawlConfig(**values)
