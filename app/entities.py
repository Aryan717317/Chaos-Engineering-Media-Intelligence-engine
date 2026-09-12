"""Conservative canonical identities; no fuzzy or global surname merging."""

import re
import unicodedata
from bisect import bisect_right
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


def person_context(body: str, mention: Mention) -> bool:
    """Require human context before overriding a location/organization NER label."""
    before = body[max(0, mention.start - 90):mention.start]
    after = body[mention.end:mention.end + 90].replace("’", "'")
    if re.search(r"\b(?:in|across|through|visiting|visited|country of|capital of)\s+$", before, re.I):
        return False
    if re.match(r"\s+(?:borders|province|city|county|Inc|Ltd|Corporation|Company)\b", after, re.I):
        return False
    return bool(re.match(r"(?:'s\s+(?:departure|dismissal|return|wife|husband|brother|sister|colleague|comments?)\b"
                         r"|\s+(?:(?:has|had)\s+)?(?:said|wrote|tweeted|quit|resigned|posted|told|spoke|joined)\b)", after, re.I)
                or re.search(r"\b(?:hired|fired|dismissed|ousted|appointed)\s+(?:[\w'-]+\s+and\s+)?$"
                             r"|\b(?:Mr|Ms|Mrs|Dr)\.?\s+$", before, re.I))


def usable_full_name(name: str) -> bool:
    words = name.split()
    # Bad NER spans such as "Will Sam" or "Greg ... @handle Sam" must not become anchors.
    return (2 <= len(words) <= 4 and words[0].casefold() not in
            {"will", "may", "can", "would", "could", "should", "does", "did", "is", "the"}
            and all(re.fullmatch(r"[^\W\d_]+(?:['’-][^\W\d_]+)*", word) for word in words))


def resolve_entities(body: str, mentions: list[Mention], aliases: list[AliasDefinition], *, source_type: str = "news"):
    known = []
    lookup = alias_lookup(aliases)
    for definition in aliases:
        for surface in [definition.name, *definition.aliases]:
            pattern = re.escape(surface).replace(r"\ ", r"\s+")
            for match in re.finditer(r"(?<![\w@])" + pattern + r"(?!\w)", body, re.I):
                known.append(Mention(text=match.group(), type=definition.type, canonical_name=definition.name,
                                     start=match.start(), end=match.end()))
    # A known short organization name must not erase a longer recognized person name.
    known = [k for k in known if not any(m.type == "person" and len(m.text.split()) > 1
             and m.start <= k.start and k.end <= m.end and m.end - m.start > k.end - k.start
             and k.type != "person" for m in mentions)]
    preferred = []
    for mention in sorted(known, key=lambda m: (m.start, -(m.end - m.start))):
        if not preferred or mention.start >= preferred[-1].end:
            preferred.append(mention)
    candidates = preferred + [m for m in mentions if not any(k.start < m.end and m.start < k.end for k in preferred)]
    url_spans = [match.span() for match in re.finditer(r"(?:https?://|www\.)\S+", body, re.I)]
    candidates = [m for m in candidates if not any(start < m.end and m.start < end for start, end in url_spans)]
    blocks = [0] + [match.end() for match in re.finditer(r"\n\s*\n", body)]
    local_names, document_surnames = {}, {}
    for mention in candidates:
        name = mention.canonical_name or mention.text
        words = canonical_key(name).split()
        definition = lookup.get(canonical_key(name))
        if mention.type == "person" and (usable_full_name(name) or (len(words) > 1 and definition and definition.type == "person")):
            key = canonical_key(name)
            block = bisect_right(blocks, mention.start) - 1
            for short in {words[0], words[-1]}:
                local_names.setdefault((block, short), {})[key] = name
            document_surnames.setdefault(words[-1], {})[key] = name
    entities = {}
    resolved = []
    for mention in sorted(candidates, key=lambda m: (m.start, m.end)):
        if re.search(r"https?://|www\.", mention.text, re.I):
            continue
        definition = lookup.get(canonical_key(mention.text))
        if not definition and mention.type == "organization" and canonical_key(mention.text) in {"llc", "inc", "ltd", "corp"}:
            continue
        name = definition.name if definition else (mention.canonical_name or mention.text)
        kind = definition.type if definition else mention.type
        short = canonical_key(name)
        if not definition and len(short.split()) == 1 and kind != "topic":
            block = bisect_right(blocks, mention.start) - 1
            choices = local_names.get((block, short), {})
            # A comment is its own context. Full names in unrelated replies are not evidence.
            if not choices and source_type not in {"discussion", "social"}:
                choices = document_surnames.get(short, {})
            if len(choices) == 1:
                full_name = next(iter(choices.values()))
                is_surname = canonical_key(full_name).split()[-1] == short
                if kind == "person" or (is_surname and person_context(body, mention)):
                    name, kind = full_name, "person"
        if not canonical_key(name):
            continue
        entity = entity_for(name, kind)
        if entity.id not in entities:
            entities[entity.id] = entity
        entities[entity.id].aliases.append(mention.text)
        resolved.append(ResolvedMention(text=mention.text, type=kind, start=mention.start,
            end=mention.end, canonical_name=name, entity_id=entity.id))
    for entity in entities.values():
        definition = lookup.get(canonical_key(entity.canonical_name))
        if definition and definition.type == entity.type:
            # Known lookup aliases do not count as extra mentions or source votes.
            entity.aliases.extend(definition.aliases)
        entity.aliases = sorted(set(entity.aliases))
    return sorted(entities.values(), key=lambda e: e.id), resolved
