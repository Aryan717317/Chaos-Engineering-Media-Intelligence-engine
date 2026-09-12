import pytest

from app.entities import ResolvedMention
from app.extract import Sentence
from app.relationships import extract_relationships


def extract(body, names):
    mentions = [ResolvedMention(text=name, type=kind, start=body.index(name),
        end=body.index(name) + len(name), entity_id=name.lower(), canonical_name=name)
        for name, kind in names]
    return extract_relationships(body, [Sentence(body, 0, len(body))], mentions)


@pytest.mark.parametrize("body,names,relation,source,target", [
    ("Alice works for Acme.", [("Alice", "person"), ("Acme", "organization")], "affiliated_with", "alice", "acme"),
    ("Acme CEO Alice spoke.", [("Acme", "organization"), ("Alice", "person")], "affiliated_with", "alice", "acme"),
    ("Alice replied to Bob.", [("Alice", "person"), ("Bob", "person")], "responded_to", "alice", "bob"),
    ("Alice quoted Bob.", [("Alice", "person"), ("Bob", "person")], "quoted_by", "bob", "alice"),
])
def test_typed_relationships_have_defined_direction(body, names, relation, source, target):
    edge = extract(body, names)[0]
    assert (edge.relation, edge.source, edge.target) == (relation, source, target)
    assert edge.sentence == body


def test_fallback_is_symmetric_and_only_for_adjacent_sentence_mentions():
    first = extract("Bob met Alice.", [("Bob", "person"), ("Alice", "person")])[0]
    second = extract("Alice met Bob.", [("Alice", "person"), ("Bob", "person")])[0]
    assert (first.source, first.target, first.relation) == (second.source, second.target, "mentioned_with")
    body = "Alice waited. Bob left."
    mentions = [ResolvedMention(text=name, type="person", start=body.index(name),
        end=body.index(name) + len(name), entity_id=name) for name in ["Alice", "Bob"]]
    assert extract_relationships(body, [Sentence("Alice waited.", 0, 13), Sentence("Bob left.", 14, 23)], mentions) == []


def test_distant_entities_are_not_paired():
    body = "Alice " + "word " * 13 + "Bob."
    assert not extract(body, [("Alice", "person"), ("Bob", "person")])


@pytest.mark.parametrize("body", ["Alice did not join Acme.", "If Alice joined Acme, things would change.",
    "Alice works for Acme?", "Alice never works for Acme."])
def test_negation_conditionals_and_questions_do_not_assert_affiliation(body):
    assert extract(body, [("Alice", "person"), ("Acme", "organization")])[0].relation == "mentioned_with"


def test_active_and_passive_quotation_agree_on_direction():
    active = extract("Alice quoted Bob.", [("Alice", "person"), ("Bob", "person")])[0]
    passive = extract("Bob was quoted by Alice.", [("Bob", "person"), ("Alice", "person")])[0]
    assert (active.source, active.target, active.relation) == (passive.source, passive.target, passive.relation)


@pytest.mark.parametrize("body", ["Alice, Chairman and CEO, Acme.",
    "Alice, the chief executive of Acme, spoke.", "Alice, Acme's chief technology officer, spoke."])
def test_role_phrasings_seen_in_news_and_company_blogs(body):
    edge = extract(body, [("Alice", "person"), ("Acme", "organization")])[0]
    assert (edge.source, edge.target, edge.relation) == ("alice", "acme", "affiliated_with")
