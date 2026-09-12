"""Hand-annotated dependency fixtures; no model download or live website needed."""

import pytest

from app.entities import ResolvedMention
from app.extract import ParsedToken, Sentence
from app.relationships import extract_relationships


def parsed_edges(words, heads, deps, names, lemmas=None):
    body = " ".join(words)
    starts, offset = [], 0
    for word in words:
        starts.append(offset)
        offset += len(word) + 1
    lemmas = lemmas or [word.lower() for word in words]
    tokens = tuple(ParsedToken(starts[i], starts[i] + len(word), starts[heads[i]], deps[i], lemmas[i])
                   for i, word in enumerate(words))
    mentions = [ResolvedMention(text=name, type=kind, start=body.index(name), end=body.index(name) + len(name),
                                entity_id=name, canonical_name=name) for name, kind in names]
    result = extract_relationships(body, [Sentence(body, 0, len(body), tokens)], mentions)
    assert all(edge.sentence == body and edge.sentence_start == 0 for edge in result)
    return {(edge.source, edge.target, edge.relation) for edge in result if edge.relation != "mentioned_with"}


def test_company_hiring_two_people_preserves_both_objects():
    edges = parsed_edges("Acme hired Alice and Bob .".split(), [1, 1, 1, 2, 2, 1],
        ["nsubj", "ROOT", "dobj", "cc", "conj", "punct"],
        [("Acme", "organization"), ("Alice", "person"), ("Bob", "person")],
        ["acme", "hire", "alice", "and", "bob", "."])
    assert edges == {("Alice", "Acme", "affiliated_with"), ("Bob", "Acme", "affiliated_with")}


@pytest.mark.parametrize("words,names,lemma", [
    ("Alice was hired by Acme .", [("Alice", "person"), ("Acme", "organization")], "hire"),
    ("Acme was founded by Alice .", [("Alice", "person"), ("Acme", "organization")], "found"),
])
def test_passive_employment_and_founding_have_person_to_organization_direction(words, names, lemma):
    assert parsed_edges(words.split(), [2, 2, 2, 2, 3, 2],
        ["nsubjpass", "auxpass", "ROOT", "agent", "pobj", "punct"], names,
        [words.split()[0].lower(), "be", lemma, "by", words.split()[4].lower(), "."]) == {
            ("Alice", "Acme", "affiliated_with")}


def test_reply_can_have_an_adverb_without_losing_its_target():
    assert parsed_edges("Alice replied directly to Bob .".split(), [1, 1, 1, 1, 3, 1],
        ["nsubj", "ROOT", "advmod", "prep", "pobj", "punct"], [("Alice", "person"), ("Bob", "person")],
        ["alice", "reply", "directly", "to", "bob", "."]) == {("Alice", "Bob", "responded_to")}


def test_quotation_of_two_people_keeps_the_quoter_direction():
    assert parsed_edges("Alice quoted Bob and Carol .".split(), [1, 1, 1, 2, 2, 1],
        ["nsubj", "ROOT", "dobj", "cc", "conj", "punct"],
        [("Alice", "person"), ("Bob", "person"), ("Carol", "person")],
        ["alice", "quote", "bob", "and", "carol", "."]) == {
            ("Bob", "Alice", "quoted_by"), ("Carol", "Alice", "quoted_by")}


def test_fire_requires_an_employment_object_not_a_weapon_target():
    assert not parsed_edges("Acme fired rockets at Bob .".split(), [1, 1, 1, 1, 3, 1],
        ["nsubj", "ROOT", "dobj", "prep", "pobj", "punct"], [("Acme", "organization"), ("Bob", "person")],
        ["acme", "fire", "rocket", "at", "bob", "."])


@pytest.mark.parametrize("words,heads,deps,lemmas", [
    ("Acme did not hire Alice .", [3, 3, 3, 3, 3, 3],
     ["nsubj", "aux", "neg", "ROOT", "dobj", "punct"], ["acme", "do", "not", "hire", "alice", "."]),
    ("Acme may hire Alice .", [2, 2, 2, 2, 2],
     ["nsubj", "aux", "ROOT", "dobj", "punct"], ["acme", "may", "hire", "alice", "."]),
    ("Bob denied Acme hired Alice .", [1, 1, 3, 1, 3, 1],
     ["nsubj", "ROOT", "nsubj", "ccomp", "dobj", "punct"], ["bob", "deny", "acme", "hire", "alice", "."]),
    ("If Acme hired Alice , Bob left Beta .", [2, 2, 6, 2, 6, 6, 6, 6, 6],
     ["mark", "nsubj", "advcl", "dobj", "punct", "nsubj", "ROOT", "dobj", "punct"],
     ["if", "acme", "hire", "alice", ",", "bob", "leave", "beta", "."]),
])
def test_negated_modal_denied_and_conditional_claims_are_not_typed(words, heads, deps, lemmas):
    names = [(name, kind) for name, kind in [("Acme", "organization"), ("Alice", "person"), ("Bob", "person"), ("Beta", "organization")] if name in words]
    assert not parsed_edges(words.split(), heads, deps, names, lemmas)


def test_separate_clauses_do_not_mix_people_and_employers():
    assert parsed_edges("Acme hired Alice after Bob left Beta .".split(), [1, 1, 1, 5, 5, 1, 5, 1],
        ["nsubj", "ROOT", "dobj", "mark", "nsubj", "advcl", "dobj", "punct"],
        [("Acme", "organization"), ("Alice", "person"), ("Bob", "person"), ("Beta", "organization")],
        ["acme", "hire", "alice", "after", "bob", "leave", "beta", "."]) == {
            ("Alice", "Acme", "affiliated_with"), ("Bob", "Beta", "affiliated_with")}


def test_clear_role_survives_uncertainty_in_a_later_clause():
    assert parsed_edges("Alice , CEO of Acme , warned that Bob might leave Beta .".split(),
        [6, 0, 0, 2, 3, 0, 6, 10, 10, 10, 6, 10, 6],
        ["nsubj", "punct", "appos", "prep", "pobj", "punct", "ROOT", "mark", "nsubj", "aux", "ccomp", "dobj", "punct"],
        [("Alice", "person"), ("Acme", "organization"), ("Bob", "person"), ("Beta", "organization")],
        ["alice", ",", "ceo", "of", "acme", ",", "warn", "that", "bob", "might", "leave", "beta", "."]) == {
            ("Alice", "Acme", "affiliated_with")}


def test_negated_copular_role_is_not_an_affiliation():
    assert not parsed_edges("Alice is not CEO of Acme .".split(), [1, 1, 1, 1, 3, 4, 1],
        ["nsubj", "ROOT", "neg", "attr", "prep", "pobj", "punct"],
        [("Alice", "person"), ("Acme", "organization")], ["alice", "be", "not", "ceo", "of", "acme", "."])


@pytest.mark.parametrize("label", ["Prediction", "Speculation", "Hypothetical"])
def test_labeled_predictions_are_not_current_employment(label):
    assert not parsed_edges(f"{label} : Acme hired Alice .".split(), [3, 0, 3, 3, 3, 3],
        ["dep", "punct", "nsubj", "ROOT", "dobj", "punct"],
        [("Acme", "organization"), ("Alice", "person")], [label.lower(), ":", "acme", "hire", "alice", "."])


def test_request_to_make_someone_ceo_does_not_assert_the_role():
    assert not parsed_edges("Please get Alice to be the next CEO of Acme .".split(),
        [1, 1, 1, 4, 1, 7, 7, 4, 7, 8, 1],
        ["intj", "ROOT", "dobj", "aux", "xcomp", "det", "amod", "attr", "prep", "pobj", "punct"],
        [("Alice", "person"), ("Acme", "organization")],
        ["please", "get", "alice", "to", "be", "the", "next", "ceo", "of", "acme", "."])
