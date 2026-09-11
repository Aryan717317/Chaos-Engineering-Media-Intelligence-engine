"""Shared contracts for the pipeline and graph API."""

import hashlib
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

EntityType = Literal["person", "organization", "location", "topic"]
RelationType = Literal["mentioned_with", "responded_to", "quoted_by", "affiliated_with"]


def utc_time(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone, for example +00:00 or Z")
    return value.astimezone(timezone.utc)


def stable_id(*parts: str) -> str:
    return hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()[:24]


class ContentItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_url: str
    source_type: str = Field(min_length=1)
    scraped_at: datetime
    title: str
    body: str = Field(min_length=1)
    author: str | None = None
    published_at: datetime | None = None

    @field_validator("scraped_at", "published_at")
    @classmethod
    def timestamps_are_aware(cls, value: datetime | None) -> datetime | None:
        return utc_time(value) if value is not None else None

    @field_validator("body")
    @classmethod
    def body_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Content has no usable body")
        return value.strip()


class Mention(BaseModel):
    text: str
    type: EntityType
    start: int = Field(ge=0)
    end: int = Field(gt=0)


class Entity(BaseModel):
    id: str
    canonical_name: str
    type: EntityType
    aliases: list[str] = Field(default_factory=list)


class Relationship(BaseModel):
    source: str
    target: str
    relation: RelationType
    sentence: str
    sentence_start: int = Field(ge=0)
    rule: str


class Evidence(BaseModel):
    source_url: str
    source_type: str
    title: str
    observed_at: datetime
    last_observed_at: datetime
    published_at: datetime | None
    sentence: str
    rule: str


class GraphNode(BaseModel):
    id: str
    name: str
    type: EntityType
    first_seen: datetime
    mention_count: int


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relation: RelationType
    weight: int
    first_seen: datetime
    last_seen: datetime
    evidence: list[Evidence] = Field(default_factory=list)


class NetworkResponse(BaseModel):
    entity: GraphNode
    depth: int
    nodes: list[GraphNode]
    edges: list[GraphEdge]
