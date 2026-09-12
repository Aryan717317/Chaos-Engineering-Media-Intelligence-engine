import pytest
import spacy

from app.extract import analyze, load_nlp, text_blocks


@pytest.fixture
def nlp():
    pipeline = spacy.blank("en")
    pipeline.add_pipe("sentencizer")
    ruler = pipeline.add_pipe("entity_ruler")
    ruler.add_patterns([
        {"label": "PERSON", "pattern": "Ada Lovelace"},
        {"label": "ORG", "pattern": "Acme"},
        {"label": "GPE", "pattern": "London"},
        {"label": "DATE", "pattern": "Monday"},
        {"label": "ORG", "pattern": "AI"},
    ])
    return pipeline


def test_extracts_supported_types_and_exact_offsets(nlp):
    body = "Ada Lovelace joined Acme in London on Monday. AI matters."
    analysis = analyze(body, nlp, {"Artificial intelligence": ["AI"]})
    assert [m.type for m in analysis.mentions] == ["person", "organization", "location", "topic"]
    assert all(body[m.start:m.end] == m.text for m in analysis.mentions)
    assert all(body[s.start:s.end] == s.text for s in analysis.sentences)


def test_separate_comments_never_become_one_sentence(nlp):
    analysis = analyze("Ada Lovelace\n\nAcme", nlp, {})
    assert [s.text for s in analysis.sentences] == ["Ada Lovelace", "Acme"]


def test_missing_model_has_actionable_error():
    with pytest.raises(RuntimeError, match="python -m spacy download"):
        load_nlp("nonexistent_model_for_test")


def test_long_comment_is_processed_without_losing_text(nlp):
    body = "Ada Lovelace joined Acme. " * 20
    blocks = list(text_blocks(body, max_chars=80))
    assert "".join(text for text, _ in blocks) == body
    assert all(body[offset:offset + len(text)] == text for text, offset in blocks)
    nlp.max_length = 81
    assert len(analyze(body, nlp, {}).mentions) == 40
