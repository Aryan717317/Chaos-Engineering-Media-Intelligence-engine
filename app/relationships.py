"""Small sentence rules with explicit direction and retained evidence."""

import re
from bisect import bisect_left

from app.entities import ResolvedMention
from app.extract import Sentence
from app.models import Relationship

ROLE = r"(?:co[- ]?founder|chief executive(?: officer)?|chief technology officer|ceo|cto|president|chairman|chairwoman|chairperson|employee|researcher)"
ROLES = rf"{ROLE}(?:\s+(?:and|&)\s+{ROLE})*"


def typed_relation(left: ResolvedMention, right: ResolvedMention, gap: str, after: str = ""):
    gap = gap.replace("’", "'").strip(" ,:;-").lower()
    actors = {"person", "organization"}
    if left.type in actors and right.type in actors:
        if re.fullmatch(r"(?:has )?(?:responded|replied) to", gap):
            return left.entity_id, right.entity_id, "responded_to", "explicit_reply"
        if re.fullmatch(r"(?:has )?quoted", gap):
            return right.entity_id, left.entity_id, "quoted_by", "active_quote"
        if re.fullmatch(r"(?:was|is) quoted by", gap):
            return left.entity_id, right.entity_id, "quoted_by", "passive_quote"
    if left.type == "person" and right.type == "organization":
        if re.fullmatch(r"(?:joined|works for|worked for|is employed by|was employed by)", gap):
            return left.entity_id, right.entity_id, "affiliated_with", "employment_verb"
        if re.fullmatch(rf"(?:(?:is|was|became) )?(?:the )?{ROLES} (?:of|at)", gap):
            return left.entity_id, right.entity_id, "affiliated_with", "person_role_organization"
        if re.fullmatch(ROLES, gap):
            return left.entity_id, right.entity_id, "affiliated_with", "role_comma_organization"
        if not gap and re.match(rf"['’]s\s+{ROLES}\b", after, re.I):
            return left.entity_id, right.entity_id, "affiliated_with", "person_organization_possessive_role"
    if left.type == "organization" and right.type == "person":
        if re.fullmatch(rf"(?:'s )?(?:(?:former|interim|new|then) )?{ROLES}", gap):
            return right.entity_id, left.entity_id, "affiliated_with", "organization_role_person"
    return None


def extract_relationships(body: str, sentences: list[Sentence], mentions: list[ResolvedMention]) -> list[Relationship]:
    mentions = sorted(mentions, key=lambda m: m.start)
    starts = [m.start for m in mentions]
    relationships = []
    seen = set()
    for sentence in sentences:
        uncertain = bool(re.search(r"\b(?:not|never|no longer|if|would|could|might|may|will)\b|n['’]t\b",
                                   sentence.text, re.I)) or sentence.text.rstrip().endswith("?")
        first, last = bisect_left(starts, sentence.start), bisect_left(starts, sentence.end)
        members = [m for m in mentions[first:last] if m.end <= sentence.end]
        for left, right in zip(members, members[1:]):
            if left.entity_id == right.entity_id:
                continue
            gap = body[left.end:right.start]
            if len(gap.split()) > 12:
                continue
            match = None if uncertain else typed_relation(left, right, gap, body[right.end:sentence.end])
            if not match:
                source, target = sorted((left.entity_id, right.entity_id))
                match = source, target, "mentioned_with", "adjacent_sentence_mentions"
            source, target, relation, rule = match
            key = (source, target, relation, sentence.start)
            if key not in seen:
                relationships.append(Relationship(source=source, target=target, relation=relation,
                    sentence=sentence.text, sentence_start=sentence.start, rule=rule))
                seen.add(key)
    return relationships
