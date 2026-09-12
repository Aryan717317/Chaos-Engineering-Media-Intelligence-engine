import pytest

from app.extract import load_topics, topic_mentions


def test_topics_use_word_boundaries_and_prefer_specific_phrases():
    body = "AI safety matters. AI is not a substring match in fair."
    mentions = topic_mentions(body, {"Artificial intelligence": ["AI"], "AI safety": ["AI safety"]})
    assert [m.canonical_name for m in mentions] == ["AI safety", "Artificial intelligence"]
    assert all(body[m.start:m.end] == m.text for m in mentions)


def test_topic_configuration_is_validated(tmp_path):
    path = tmp_path / "topics.yaml"
    path.write_text("AI: not-a-list", encoding="utf-8")
    with pytest.raises(ValueError, match="Topics"):
        load_topics(path)
