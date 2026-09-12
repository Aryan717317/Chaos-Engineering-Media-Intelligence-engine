import pytest

from app.entities import AliasDefinition, canonical_key, entity_for, load_aliases, resolve_entities
from app.models import Mention


def test_canonical_keys_clean_case_unicode_spacing_and_punctuation():
    assert canonical_key("  ＯpenAI’s ") == "openai"
    assert canonical_key("@ELONMUSK") == "elonmusk"
    assert canonical_key("Elon   Musk.") == "elon musk"


def test_entity_ids_are_stable_and_keep_types_distinct():
    assert entity_for("Sam Altman", "person").id == entity_for("sam altman", "person").id
    assert entity_for("Jordan", "person").id != entity_for("Jordan", "location").id
    with pytest.raises(ValueError):
        entity_for("@@!", "person")


def test_known_handles_and_type_corrections_share_identity():
    body = "Elon Musk met @elonmusk at OpenAI."
    aliases = [AliasDefinition(name="Elon Musk", type="person", aliases=["@elonmusk"]),
               AliasDefinition(name="OpenAI", type="organization")]
    start = body.index("OpenAI")
    wrong_type = Mention(text="OpenAI", type="location", start=start, end=start + 6)
    entities, mentions = resolve_entities(body, [wrong_type], aliases)
    assert len(entities) == 2
    assert mentions[0].entity_id == mentions[1].entity_id
    assert mentions[-1].type == "organization"
    assert all(body[m.start:m.end] == m.text for m in mentions)


def mentions_for(body, names):
    return [Mention(text=name, type="person", start=body.index(name), end=body.index(name) + len(name))
            for name in names]


def test_surname_resolves_only_with_one_full_person_in_content():
    body = "Musk met Elon Musk."
    entities, resolved = resolve_entities(body, mentions_for(body, ["Musk", "Elon Musk"]), [])
    assert len(entities) == 1
    assert resolved[0].entity_id == resolved[1].entity_id
    alone, _ = resolve_entities("Musk", mentions_for("Musk", ["Musk"]), [])
    assert alone[0].canonical_name == "Musk"


def test_ambiguous_surname_is_not_merged():
    body = "Musk met Elon Musk and Kimbal Musk."
    entities, _ = resolve_entities(body, mentions_for(body, ["Musk", "Elon Musk", "Kimbal Musk"]), [])
    assert len(entities) == 3


def test_conflicting_alias_configuration_is_rejected(tmp_path):
    path = tmp_path / "aliases.yaml"
    path.write_text('- {name: Alice Smith, type: person, aliases: [AS]}\n'
                    '- {name: Acme Services, type: organization, aliases: [as]}', encoding="utf-8")
    with pytest.raises(ValueError, match="Conflicting"):
        load_aliases(path)


def test_alias_matching_uses_whole_words_and_does_not_depend_on_input_order():
    aliases = [AliasDefinition(name="Acme", type="organization")]
    assert resolve_entities("Acmeish", [], aliases) == ([], [])
    body = "Musk met Elon Musk."
    mentions = mentions_for(body, ["Musk", "Elon Musk"])
    assert resolve_entities(body, mentions, [])[0] == resolve_entities(body, list(reversed(mentions)), [])[0]


def test_urls_mistaken_for_entities_are_discarded():
    body = "https://example.org/sam-altman"
    entities, resolved = resolve_entities(body, [Mention(text=body, type="person", start=0, end=len(body))], [])
    assert not entities and not resolved


def test_elon_musk_full_name_surname_and_handle_share_one_node():
    body = "Elon Musk spoke. Musk replied as @elonmusk."
    aliases = [AliasDefinition(name="Elon Musk", type="person", aliases=["@elonmusk"])]
    start = body.index("Musk replied")
    mentions = [Mention(text="Musk", type="person", start=start, end=start + 4)]
    entities, resolved = resolve_entities(body, mentions, aliases, source_type="discussion")
    assert len(entities) == 1
    assert entities[0].canonical_name == "Elon Musk"
    assert set(entities[0].aliases) == {"Elon Musk", "Musk", "@elonmusk"}
    assert len({m.entity_id for m in resolved}) == 1
    assert all(body[m.start:m.end] == m.text for m in resolved)


def test_surnames_resolve_within_comments_despite_other_comment_ambiguity():
    body = "Elon Musk spoke. Musk replied.\n\nKimbal Musk spoke. Musk left.\n\nMusk waited."
    import re
    names = [Mention(text=m.group(), type="person", start=m.start(), end=m.end())
             for m in re.finditer(r"Elon Musk|Kimbal Musk|Musk", body)]
    _, resolved = resolve_entities(body, names, [], source_type="discussion")
    assert [m.canonical_name for m in resolved] == ["Elon Musk", "Elon Musk", "Kimbal Musk", "Kimbal Musk", "Musk"]


def test_given_names_need_a_unique_full_name_in_the_same_comment():
    body = "Sam Altman spoke to Sam.\n\nSam waited."
    import re
    mentions = [Mention(text=m.group(), type="person", start=m.start(), end=m.end())
                for m in re.finditer(r"Sam Altman|Sam", body)]
    _, resolved = resolve_entities(body, mentions, [], source_type="discussion")
    assert [m.canonical_name for m in resolved] == ["Sam Altman", "Sam Altman", "Sam"]


def test_person_context_corrects_surname_types_but_keeps_real_places():
    body = "Alice Jordan spoke. Jordan resigned. We visited Jordan."
    import re
    mentions = [Mention(text=m.group(), type="person" if m.group() == "Alice Jordan" else "location",
                        start=m.start(), end=m.end()) for m in re.finditer(r"Alice Jordan|Jordan", body)]
    _, resolved = resolve_entities(body, mentions, [])
    assert [(m.canonical_name, m.type) for m in resolved] == [
        ("Alice Jordan", "person"), ("Alice Jordan", "person"), ("Jordan", "location")]


def test_explicit_organization_alias_overrides_surname_guess():
    body = "Alice Jordan spoke. Jordan said sales grew."
    mentions = mentions_for(body, ["Alice Jordan"])
    entities, resolved = resolve_entities(body, mentions, [AliasDefinition(name="Jordan", type="organization")])
    assert resolved[0].canonical_name == "Alice Jordan"
    assert resolved[-1].type == "organization"


def test_known_aliases_inside_urls_are_not_entities():
    assert resolve_entities("https://example.org/Elon-Musk/OpenAI", [],
                            [AliasDefinition(name="OpenAI", type="organization")]) == ([], [])
