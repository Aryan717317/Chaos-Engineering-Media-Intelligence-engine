"""Local entity recognition and an explicit topic vocabulary."""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.models import Mention

NER_TYPES = {"PERSON": "person", "ORG": "organization", "GPE": "location", "LOC": "location", "FAC": "location"}


@dataclass
class Sentence:
    text: str
    start: int
    end: int


@dataclass
class Analysis:
    mentions: list[Mention]
    sentences: list[Sentence]


def load_nlp(model: str = "en_core_web_sm"):
    import spacy

    try:
        return spacy.load(model)
    except OSError as exc:
        raise RuntimeError(f"Missing spaCy model {model}. Run: python -m spacy download {model}") from exc


def analyze(body: str, nlp, topics: dict[str, list[str]]) -> Analysis:
    mentions = []
    sentences = []
    offset = 0
    for block in body.split("\n\n"):
        if block.strip():
            doc = nlp(block)
            for span in doc.ents:
                if span.label_ in NER_TYPES:
                    mentions.append(Mention(text=span.text, type=NER_TYPES[span.label_],
                                            start=offset + span.start_char, end=offset + span.end_char))
            sentences.extend(Sentence(sent.text, offset + sent.start_char, offset + sent.end_char) for sent in doc.sents)
        offset += len(block) + 2
    candidates = mentions + topic_mentions(body, topics)
    selected = []
    for mention in sorted(candidates, key=lambda m: (m.start, -(m.end - m.start), m.type != "topic")):
        if not selected or mention.start >= selected[-1].end:
            selected.append(mention)
    return Analysis(selected, sentences)


def load_topics(path: str | Path) -> dict[str, list[str]]:
    topics = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(topics, dict) or any(
        not isinstance(name, str) or not isinstance(terms, list) or not terms
        or any(not isinstance(term, str) or not term.strip() for term in terms)
        for name, terms in topics.items()
    ):
        raise ValueError("Topics must map canonical names to nonempty lists of phrases")
    return topics


def topic_mentions(body: str, topics: dict[str, list[str]]) -> list[Mention]:
    candidates = []
    for name, terms in sorted(topics.items()):
        for term in terms:
            for match in re.finditer(r"(?<!\w)" + re.escape(term) + r"(?!\w)", body, re.I):
                candidates.append(Mention(text=match.group(), type="topic", canonical_name=name,
                                          start=match.start(), end=match.end()))
    selected = []
    for mention in sorted(candidates, key=lambda m: (m.start, -(m.end - m.start), m.canonical_name)):
        if not selected or mention.start >= selected[-1].end:
            selected.append(mention)
    return selected
