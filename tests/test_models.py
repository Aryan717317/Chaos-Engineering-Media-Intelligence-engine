from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models import ContentItem, stable_id, utc_time


def test_content_accepts_missing_optional_metadata():
    item = ContentItem(source_url="https://example.org/story", source_type="news",
                       scraped_at=datetime.now(timezone.utc), title="Story", body=" Text ")
    assert item.author is None
    assert item.published_at is None
    assert item.body == "Text"


def test_blank_body_is_an_explicit_failure():
    with pytest.raises(ValidationError, match="no usable body"):
        ContentItem(source_url="https://example.org", source_type="news",
                    scraped_at=datetime.now(timezone.utc), title="", body="  ")


def test_naive_time_is_rejected_and_offsets_are_normalized():
    with pytest.raises(ValueError, match="timezone"):
        utc_time(datetime(2026, 1, 1))
    assert utc_time(datetime.fromisoformat("2026-01-01T05:30:00+05:30")).hour == 0


def test_identity_is_stable_and_type_specific():
    assert stable_id("person", "alex") == stable_id("person", "alex")
    assert stable_id("person", "alex") != stable_id("organization", "alex")
