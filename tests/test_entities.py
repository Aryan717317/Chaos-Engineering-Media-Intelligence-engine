import pytest

from app.entities import AliasDefinition, canonical_key, entity_for, resolve_entities
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
