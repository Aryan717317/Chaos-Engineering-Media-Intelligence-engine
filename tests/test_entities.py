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
