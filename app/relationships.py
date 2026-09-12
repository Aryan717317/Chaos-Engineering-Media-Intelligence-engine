"""Small sentence rules with explicit direction and retained evidence."""

import re
from bisect import bisect_left
from collections import defaultdict

from app.entities import ResolvedMention
from app.extract import Sentence
from app.models import Relationship

ROLE = r"(?:co[- ]?founder|founder|chief executive(?: officer)?|chief (?:technology|strategy|operating|financial) officer|chief scientist|ceo|cto|cfo|president|chairman|chairwoman|chairperson|employee|researcher|director|board member)"
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


def dependency_relationships(sentence: Sentence, mentions: list[ResolvedMention]):
    """Use the already-computed parse to bind named arguments, never pronoun guesses."""
    tokens = {token.start: token for token in sentence.tokens}
    children = defaultdict(list)
    for token in tokens.values():
        if token.head != token.start:
            children[token.head].append(token)

    def named(token, *, conjunctions=True):
        found = []
        queue, visited = [token], set()
        while queue:
            current = queue.pop()
            if current.start in visited:
                continue
            visited.add(current.start)
            found.extend(m for m in mentions if m.start <= current.start and current.end <= m.end)
            if conjunctions:
                queue.extend(c for c in children[current.start] if c.dep == "conj")
        return {m.entity_id: m for m in found}.values()

    def arguments(predicate, deps):
        result = []
        for child in children[predicate.start]:
            if child.dep in deps:
                result.extend(named(child))
                # A named company's board can hire/appoint on that company's behalf.
                if child.lemma == "board":
                    for owner in children[child.start]:
                        if owner.dep in {"poss", "compound", "nmod"}:
                            result.extend(m for m in named(owner) if m.type == "organization")
        return result

    def prepositions(predicate, allowed):
        result = []
        for prep in children[predicate.start]:
            if prep.lemma in allowed and prep.dep in {"prep", "agent"}:
                for obj in children[prep.start]:
                    if obj.dep == "pobj":
                        result.extend(named(obj))
                        for appos in children[obj.start]:
                            if appos.dep == "appos":
                                result.extend(named(appos))
        return result

    def uncertain(predicate):
        if sentence.text.rstrip().endswith("?"):
            return True
        visited = set()
        while predicate and predicate.start not in visited:
            visited.add(predicate.start)
            if predicate.lemma in {"deny", "plan", "hope", "wish", "want", "intend", "expect", "consider", "rumor", "imagine", "believe", "predict", "speculate"}:
                return True
            for child in children[predicate.start]:
                if child.dep == "neg" or child.lemma in {"if", "unless", "whether", "maybe", "perhaps", "allegedly", "supposedly"}:
                    return True
                if child.dep == "aux" and child.lemma in {"will", "would", "could", "may", "might", "should", "must", "can"}:
                    return True
                if child.dep == "advcl" and any(c.lemma in {"if", "unless"} for c in children[child.start]):
                    return True
            predicate = tokens.get(predicate.head) if predicate.head != predicate.start else None
        return False

    result = []
    def emit(left, right, relation, rule):
        if left.entity_id != right.entity_id:
            result.append((left.entity_id, right.entity_id, relation, rule))

    employer_verbs = {"hire", "employ", "recruit", "appoint", "fire", "dismiss", "sack", "oust"}
    member_verbs = {"join", "found", "cofound", "lead", "head", "run", "leave", "quit"}
    for predicate in tokens.values():
        if predicate.lemma not in employer_verbs | member_verbs | {"work", "reply", "respond", "quote"} or uncertain(predicate):
            continue
        subjects = arguments(predicate, {"nsubj"})
        objects = arguments(predicate, {"dobj", "obj"})
        patients = arguments(predicate, {"nsubjpass"})
        agents = prepositions(predicate, {"by"})
        if predicate.lemma in employer_verbs | member_verbs:
            pairs = [(a, b) for a in subjects for b in objects] + [(a, b) for a in agents for b in patients]
            for left, right in pairs:
                person, org = (right, left) if predicate.lemma in employer_verbs else (left, right)
                if person.type == "person" and org.type == "organization":
                    emit(person, org, "affiliated_with", "dependency_employment")
        elif predicate.lemma == "work":
            for person in subjects:
                for org in prepositions(predicate, {"for", "at"}):
                    if person.type == "person" and org.type == "organization":
                        emit(person, org, "affiliated_with", "dependency_workplace")
        elif predicate.lemma in {"reply", "respond"}:
            for actor in subjects:
                for target in prepositions(predicate, {"to"}):
                    if actor.type in {"person", "organization"} and target.type in {"person", "organization"}:
                        emit(actor, target, "responded_to", "dependency_reply")
        else:
            for quoter, quoted in [(a, b) for a in subjects for b in objects] + [(a, b) for a in agents for b in patients]:
                if quoter.type in {"person", "organization"} and quoted.type in {"person", "organization"}:
                    emit(quoted, quoter, "quoted_by", "dependency_quote")

    roles = {"ceo", "cto", "cfo", "founder", "cofounder", "executive", "officer", "scientist",
             "president", "chairman", "chairwoman", "chairperson", "chair", "director", "researcher", "employee", "advisor"}
    for role in tokens.values():
        if role.lemma not in roles:
            continue
        modifiers = children[role.start]
        if any(c.lemma in {"no", "not", "alleged", "supposed", "aspiring", "prospective", "future", "potential", "next"} for c in modifiers):
            continue
        if sentence.text.rstrip().endswith("?") or re.search(r"\b(?:if|unless|hypothetically|allegedly)\b", sentence.text[:role.start - sentence.start], re.I):
            continue
        people = []
        current, visited = role, set()
        while current.start not in visited:
            visited.add(current.start)
            parent = tokens.get(current.head)
            if parent and current.dep in {"appos", "compound"}:
                people.extend(m for m in named(parent, conjunctions=False) if m.type == "person")
            if not parent or current.dep != "conj" or parent.lemma not in roles:
                break
            current = parent
        for child in modifiers:
            if child.dep == "appos":
                people.extend(m for m in named(child, conjunctions=False) if m.type == "person")
        parent = tokens.get(role.head)
        if role.dep in {"attr", "acomp"} and parent and parent.lemma == "be" and not uncertain(parent):
            people.extend(m for m in arguments(parent, {"nsubj"}) if m.type == "person")
        organizations = [m for m in prepositions(role, {"of", "at", "for"}) if m.type == "organization"]
        for child in modifiers:
            if child.dep in {"poss", "compound", "nmod"}:
                organizations.extend(m for m in named(child, conjunctions=False) if m.type == "organization")
        for person in people:
            for org in organizations:
                emit(person, org, "affiliated_with", "dependency_role")
    return result


def extract_relationships(body: str, sentences: list[Sentence], mentions: list[ResolvedMention]) -> list[Relationship]:
    mentions = sorted(mentions, key=lambda m: m.start)
    starts = [m.start for m in mentions]
    relationships = []
    seen = set()
    for sentence in sentences:
        first, last = bisect_left(starts, sentence.start), bisect_left(starts, sentence.end)
        members = [m for m in mentions[first:last] if m.end <= sentence.end]
        block_start = body.rfind("\n\n", 0, sentence.start) + 2
        block_prefix = body[max(0, block_start if block_start > 1 else 0):sentence.start + len(sentence.text)]
        speculative = bool(re.match(r"\s*(?:(?:prediction|speculation|hypothetical|scenario|wish(?:ful thinking)?)\s*:"
                                    r"|(?:I\s+(?:predict|speculate|wish)|imagine|what if|please)\b)", block_prefix, re.I))
        matches = dependency_relationships(sentence, members) if sentence.tokens and not speculative else []
        for left, right in zip(members, members[1:]):
            if left.entity_id == right.entity_id:
                continue
            gap = body[left.end:right.start]
            if len(gap.split()) > 12:
                continue
            # Inspect the assertion's prefix, not unrelated uncertainty later in the sentence.
            assertion = body[sentence.start:right.end]
            uncertain = speculative or bool(re.search(r"\b(?:not|never|no longer|if|unless|would|could|might|may|will|alleged|allegedly|supposed|aspiring|deny|denied|next)\b|n['’]t\b",
                                       assertion, re.I)) or sentence.text.rstrip().endswith("?")
            match = None if uncertain else typed_relation(left, right, gap, body[right.end:sentence.end])
            if match:
                matches.append(match)
        typed_pairs = {frozenset((source, target)) for source, target, _, _ in matches}
        for left, right in zip(members, members[1:]):
            if left.entity_id == right.entity_id or len(body[left.end:right.start].split()) > 12:
                continue
            if frozenset((left.entity_id, right.entity_id)) not in typed_pairs:
                source, target = sorted((left.entity_id, right.entity_id))
                matches.append((source, target, "mentioned_with", "adjacent_sentence_mentions"))
        for source, target, relation, rule in matches:
            key = (source, target, relation, sentence.start)
            if key not in seen:
                relationships.append(Relationship(source=source, target=target, relation=relation,
                    sentence=sentence.text, sentence_start=sentence.start, rule=rule))
                seen.add(key)
    return relationships
