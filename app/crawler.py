"""A bounded breadth-first crawl using Crawl4AI for each page."""

import asyncio
import logging
import os
import re
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from pydantic import BaseModel, Field

from app.config import CrawlConfig, canonical_url, domain_allowed

logger = logging.getLogger(__name__)


class RawPage(BaseModel):
    source_url: str
    requested_url: str
    source_type: str
    scraped_at: datetime
    depth: int
    html: str
    links: list[str] = Field(default_factory=list)


class CrawlFailure(BaseModel):
    url: str
    error: str


class CrawlReport(BaseModel):
    pages: list[RawPage] = Field(default_factory=list)
    failures: list[CrawlFailure] = Field(default_factory=list)
    discovered: int = 0


async def crawl(config: CrawlConfig, *, fetch=None) -> CrawlReport:
    """fetch is optional so queue/whitelist tests need no browser or network."""
    if fetch is None:
        os.environ.setdefault("CRAWL4_AI_BASE_DIRECTORY", str(Path("data").resolve()))
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig

        run_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, verbose=False,
                                      page_timeout=config.page_timeout_ms,
                                      word_count_threshold=1, check_robots_txt=True)
        async with AsyncWebCrawler(config=BrowserConfig(headless=True, verbose=False)) as browser:
            async def fetch_page(url):
                return await browser.arun(url=url, config=run_config)
            return await crawl(config, fetch=fetch_page)

    queue = deque()
    scheduled = set()
    visited = set()
    for seed in config.seeds:
        if seed.url not in scheduled:
            queue.append((seed.url, 0, seed.source_type or config.rule_for(seed.url).source_type))
            scheduled.add(seed.url)
    report = CrawlReport()
    while queue:
        url, depth, source_type = queue.popleft()
        if url in visited:
            continue
        visited.add(url)
        try:
            result = await fetch(url)
            if not result.success:
                raise ValueError(result.error_message or "Crawler reported an unsuccessful page")
            if getattr(result, "status_code", 200) and result.status_code >= 400:
                raise ValueError(f"HTTP {result.status_code}")
            final_url = canonical_url(getattr(result, "redirected_url", None) or result.url or url)
            if not domain_allowed(final_url, config.allowed_domains):
                raise ValueError("Redirect ended outside allowed_domains")
            if final_url in visited and final_url != url:
                continue
            visited.add(final_url)
            if not result.html or not result.html.strip():
                raise ValueError("Page returned empty HTML")
            links = set()
            for group in (result.links or {}).values():
                for link in group:
                    try:
                        target = canonical_url(urljoin(final_url, link["href"]))
                    except (ValueError, KeyError):
                        continue
                    if domain_allowed(target, config.allowed_domains):
                        links.add(target)
            report.pages.append(RawPage(source_url=final_url, requested_url=url,
                source_type=source_type, scraped_at=datetime.now(timezone.utc), depth=depth,
                html=result.html, links=sorted(links)))
            if depth < config.max_depth:
                added = 0
                for target in sorted(links):
                    pattern = config.rule_for(target).follow_pattern
                    if pattern and not re.search(pattern, target):
                        continue
                    if added >= config.max_links_per_page:
                        break
                    if target not in scheduled and target not in visited and len(scheduled) < config.max_pages:
                        queue.append((target, depth + 1, config.rule_for(target).source_type))
                        scheduled.add(target)
                        added += 1
            logger.info("Crawled %s depth=%d type=%s", final_url, depth, source_type)
        except Exception as exc:
            # Browser/network failures are isolated here; extraction failures are handled separately.
            report.failures.append(CrawlFailure(url=url, error=str(exc)))
            logger.warning("Crawl failed %s: %s", url, exc)
        if queue and config.delay_seconds:
            await asyncio.sleep(config.delay_seconds)
    report.discovered = len(scheduled)
    return report


def save_crawl(report: CrawlReport, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
