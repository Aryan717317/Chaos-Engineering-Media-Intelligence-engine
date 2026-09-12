"""Convert articles, blogs and discussion blocks into one content contract."""

import json
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup

from app.config import SourceRule
from app.crawler import RawPage
from app.models import ContentItem

logger = logging.getLogger(__name__)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    if re.match(r"^\d{4}-\d\d-\d\dT\S+ \d+$", value):
        value = value.split()[0]
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
        except (ValueError, TypeError):
            logger.warning("Unrecognized publication date: %r", value)
            return None
    if date.tzinfo is None:
        logger.warning("Publication date has no timezone; assuming UTC: %s", value)
        date = date.replace(tzinfo=timezone.utc)
    return date.astimezone(timezone.utc)


def article_metadata(soup: BeautifulSoup) -> dict:
    def walk(value):
        if isinstance(value, list):
            for item in value:
                yield from walk(item)
        elif isinstance(value, dict):
            yield value
            yield from walk(value.get("@graph", []))

    for script in soup.select('script[type="application/ld+json"]'):
        try:
            for item in walk(json.loads(script.string or script.get_text())):
                types = item.get("@type", [])
                types = [types] if isinstance(types, str) else types
                if set(types) & {"Article", "NewsArticle", "BlogPosting", "DiscussionForumPosting"}:
                    return item
        except (ValueError, TypeError):
            logger.warning("Ignoring malformed JSON-LD metadata")
    return {}


def author_name(value) -> str | None:
    if isinstance(value, list):
        return ", ".join(filter(None, (author_name(v) for v in value))) or None
    if isinstance(value, dict):
        return author_name(value.get("name"))
    return (clean_text(value) or None) if isinstance(value, str) else None


def normalize(page: RawPage, rule: SourceRule | None = None) -> ContentItem:
    rule = rule or SourceRule()
    soup = BeautifulSoup(page.html, "html.parser")
    metadata = article_metadata(soup)

    def meta(*names):
        for name in names:
            tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
            if tag and tag.get("content"):
                return tag["content"]
        return None

    def selected(selector, *attributes):
        tag = soup.select_one(selector) if selector else None
        if tag is None:
            return None
        for attribute in attributes:
            if tag.get(attribute):
                return tag[attribute]
        return tag.get_text(" ", strip=True) or None

    title = (selected(rule.title_selector) or meta("og:title", "twitter:title")
             or metadata.get("headline") or selected("h1") or selected("title") or page.source_url)
    author = (author_name(metadata.get("author")) or meta("author", "article:author")
              or selected(rule.author_selector) or selected('[rel="author"]'))
    published = (metadata.get("datePublished") or meta("article:published_time", "datePublished", "date")
                 or selected(rule.published_selector, "datetime", "title") or selected("time[datetime]", "datetime"))
    for tag in soup.select("script, style, noscript, nav, header, footer, aside, form, button, svg"):
        tag.decompose()
    visible = clean_text(soup.get_text(" ", strip=True))
    if len(visible) < 2000 and re.search(
        r"verify (?:that )?you(?:'re| are) (?:not a robot|human)|checking your browser|access denied|just a moment",
        visible, re.I,
    ):
        raise ValueError("Page contains a verification/access challenge instead of usable content")

    parts = []
    comments = soup.select(rule.comment_selector or ".commtext, .comment-body, .comment-content")
    if page.source_type in {"discussion", "social"} or rule.comment_selector:
        if comments:
            if rule.body_selector:
                root = soup.select_one(rule.body_selector)
                if root:
                    parts.append(root.get_text(" ", strip=True))
            parts.extend(comment.get_text(" ", strip=True) for comment in comments)
        else:
            logger.warning("No comment blocks matched at %s; using generic content fallback", page.source_url)
    if not parts:
        root = soup.select_one(rule.body_selector) if rule.body_selector else None
        if rule.body_selector and root is None:
            logger.warning("Body selector did not match %s; using generic content fallback", page.source_url)
        if root is None:
            candidates = soup.select("article") or soup.select("main")
            root = max(candidates, key=lambda tag: len(tag.get_text()), default=None)
        if root is None:
            root = soup.body or soup
        blocks = root.select("p, h2, h3, li, blockquote")
        block_ids = {id(block) for block in blocks}
        blocks = [block for block in blocks if not any(id(parent) in block_ids for parent in block.parents)]
        parts = [block.get_text(" ", strip=True) for block in blocks] if blocks else [root.get_text(" ", strip=True)]
    body = "\n\n".join(clean_text(part) for part in parts if clean_text(part))
    return ContentItem(source_url=page.source_url, source_type=page.source_type,
        scraped_at=page.scraped_at, title=clean_text(str(title)), body=body,
        author=author_name(author), published_at=parse_date(str(published)) if published else None)
