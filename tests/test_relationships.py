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
