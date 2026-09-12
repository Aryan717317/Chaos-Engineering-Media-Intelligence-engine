from datetime import datetime, timezone

import pytest

from app.config import SourceRule
from app.crawler import RawPage
from app.normalize import normalize


def page(html, source_type="news"):
    return RawPage(source_url="https://example.org/story", requested_url="https://example.org/story",
                   source_type=source_type, scraped_at=datetime.now(timezone.utc), depth=0, html=html)


def test_news_json_ld_and_article_body():
    html = '''<title>Fallback</title><script type="application/ld+json">
    {"@graph":[{"@type":"NewsArticle","headline":"A report","author":[{"name":"Alex"}],
    "datePublished":"2026-01-01T05:30:00+05:30"}]}</script>
    <nav>unrelated navigation</nav><article><p>Ada joined Acme.</p><p>More reporting.</p></article>'''
    item = normalize(page(html))
    assert item.title == "A report" and item.author == "Alex"
    assert item.published_at.hour == 0
    assert item.body == "Ada joined Acme.\n\nMore reporting."


def test_discussion_preserves_comment_boundaries_and_metadata():
    html = '''<b class="headline">Thread</b><span class="poster">alex</span>
    <span class="age" title="2026-01-01T00:00:00 1767225600">a while ago</span>
    <div class="intro">Opening post.</div><div class="comment">Ada joined Acme.</div>
    <div class="comment">Bob replied to Ada.</div>'''
    rule = SourceRule(title_selector=".headline", body_selector=".intro", comment_selector=".comment",
                      author_selector=".poster", published_selector=".age")
    item = normalize(page(html, "discussion"), rule)
    assert item.body.split("\n\n") == ["Opening post.", "Ada joined Acme.", "Bob replied to Ada."]
    assert item.title == "Thread" and item.author == "alex"
    assert item.published_at.year == 2026


def test_blog_selector_and_optional_fields():
    item = normalize(page('<h1>Update</h1><section class="entry"><p>Company update.</p></section>', "blog"),
                     SourceRule(body_selector=".entry"))
    assert item.title == "Update" and item.body == "Company update."
    assert item.author is None and item.published_at is None


def test_missing_title_and_unexpected_structure_have_visible_fallback(caplog):
    item = normalize(page("<body><section>Readable content.</section></body>"), SourceRule(body_selector=".gone"))
    assert item.title == item.source_url and item.body == "Readable content."
    assert "did not match" in caplog.text


@pytest.mark.parametrize("html", ["<html></html>", "<script>onlyJavascript()</script>",
    "<p>We need to verify that you're not a robot.</p>"])
def test_empty_and_challenge_pages_fail_explicitly(html):
    with pytest.raises(ValueError):
        normalize(page(html))


def test_malformed_metadata_and_dates_do_not_discard_body(caplog):
    item = normalize(page('<script type="application/ld+json">bad json</script>'
                          '<meta name="date" content="unknown"><p>Content survives.</p>'))
    assert item.body == "Content survives." and item.published_at is None
    assert "malformed" in caplog.text and "Unrecognized" in caplog.text


def test_nested_replies_are_not_repeated_in_parent_comment():
    html = '<div class="comment">Parent says <b>hello</b>.<div class="comment">Child replies.</div></div>'
    item = normalize(page(html, "discussion"), SourceRule(comment_selector=".comment"))
    assert item.body.split("\n\n") == ["Parent says hello .", "Child replies."]
