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
    return TypeAdapter(list[AliasDefinition]).validate_python(
        yaml.safe_load(Path(path).read_text(encoding="utf-8")))


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
    lookup = {}
    for definition in aliases:
        for surface in [definition.name, *definition.aliases]:
            lookup[canonical_key(surface)] = definition
            for match in re.finditer(r"(?<![\w@])" + re.escape(surface) + r"(?!\w)", body, re.I):
                known.append(Mention(text=match.group(), type=definition.type, canonical_name=definition.name,
                                     start=match.start(), end=match.end()))
    preferred = []
    for mention in sorted(known, key=lambda m: (m.start, -(m.end - m.start))):
        if not preferred or mention.start >= preferred[-1].end:
            preferred.append(mention)
    candidates = preferred + [m for m in mentions if not any(k.start < m.end and m.start < k.end for k in preferred)]
    entities = {}
    resolved = []
    for mention in sorted(candidates, key=lambda m: (m.start, m.end)):
        definition = lookup.get(canonical_key(mention.text))
        name = definition.name if definition else (mention.canonical_name or mention.text)
        kind = definition.type if definition else mention.type
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
