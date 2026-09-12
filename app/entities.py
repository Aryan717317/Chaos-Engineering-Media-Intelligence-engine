"""Conservative canonical identities; no fuzzy or global surname merging."""

import re
import unicodedata
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from app.models import Entity, EntityType, Mention, stable_id


def canonical_key(name: str) -> str:
    name = unicodedata.normalize("NFKC", name).casefold().strip().lstrip("@")
    name = re.sub(r"['’]s$", "", name)
    name = re.sub(r"[^\w\s]", "", name)
    return " ".join(name.split())


class AliasDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1)
    type: EntityType
    aliases: list[str] = Field(default_factory=list)


def load_aliases(path: str | Path) -> list[AliasDefinition]:
    definitions = TypeAdapter(list[AliasDefinition]).validate_python(
        yaml.safe_load(Path(path).read_text(encoding="utf-8")))
    alias_lookup(definitions)
    return definitions


def alias_lookup(definitions: list[AliasDefinition]) -> dict[str, AliasDefinition]:
    lookup = {}
    for definition in definitions:
        for surface in [definition.name, *definition.aliases]:
            key = canonical_key(surface)
            if not key:
                raise ValueError("Aliases must contain letters or digits")
            existing = lookup.get(key)
            if existing and (existing.type, canonical_key(existing.name)) != (definition.type, canonical_key(definition.name)):
                raise ValueError(f"Conflicting canonical entities for alias {surface!r}")
            lookup[key] = definition
    return lookup


def entity_for(name: str, entity_type: EntityType) -> Entity:
    name = " ".join(unicodedata.normalize("NFKC", name).strip(" @.,;:\"'").split())
    key = canonical_key(name)
    if not key:
        raise ValueError("An entity must contain letters or digits")
    return Entity(id=stable_id(entity_type, key), canonical_name=name, type=entity_type)


class ResolvedMention(Mention):
    entity_id: str


def resolve_entities(body: str, mentions: list[Mention], aliases: list[AliasDefinition]):
    known = []
    lookup = alias_lookup(aliases)
    for definition in aliases:
        for surface in [definition.name, *definition.aliases]:
            for match in re.finditer(r"(?<![\w@])" + re.escape(surface) + r"(?!\w)", body, re.I):
                known.append(Mention(text=match.group(), type=definition.type, canonical_name=definition.name,
                                     start=match.start(), end=match.end()))
    preferred = []
    for mention in sorted(known, key=lambda m: (m.start, -(m.end - m.start))):
        if not preferred or mention.start >= preferred[-1].end:
            preferred.append(mention)
    candidates = preferred + [m for m in mentions if not any(k.start < m.end and m.start < k.end for k in preferred)]
    surnames = {}
    for mention in candidates:
        name = mention.canonical_name or mention.text
        words = canonical_key(name).split()
        if mention.type == "person" and len(words) > 1:
            surnames.setdefault(words[-1], {})[canonical_key(name)] = name
    entities = {}
    resolved = []
    for mention in sorted(candidates, key=lambda m: (m.start, m.end)):
        if re.search(r"https?://|www\.", mention.text, re.I):
            continue
        definition = lookup.get(canonical_key(mention.text))
        name = definition.name if definition else (mention.canonical_name or mention.text)
        kind = definition.type if definition else mention.type
        choices = surnames.get(canonical_key(name), {})
        if not definition and kind == "person" and len(choices) == 1:
            name = next(iter(choices.values()))
        if not canonical_key(name):
            continue
        entity = entity_for(name, kind)
        if entity.id not in entities:
            entities[entity.id] = entity
        entities[entity.id].aliases.append(mention.text)
        resolved.append(ResolvedMention(text=mention.text, type=kind, start=mention.start,
            end=mention.end, canonical_name=name, entity_id=entity.id))
    for entity in entities.values():
        entity.aliases = sorted(set(entity.aliases))
    return sorted(entities.values(), key=lambda e: e.id), resolved
