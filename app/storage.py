"""SQLite operations shared by the pipeline and analysis API."""

import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from app.config import canonical_url
from app.entities import canonical_key
from app.models import ContentItem, Entity, Relationship, stable_id, utc_time


def timestamp(value: datetime) -> str:
    return utc_time(value).isoformat(timespec="microseconds")


@contextmanager
def connect(path: str | Path):
    connection = sqlite3.connect(str(path), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize(path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(Path(__file__).with_name("schema.sql").read_text(encoding="utf-8"))


def store_content(connection: sqlite3.Connection, item: ContentItem, entities: list[Entity]) -> tuple[str, str]:
    """The caller owns the transaction so content and edges commit together."""
    url = canonical_url(item.source_url)
    source_id = stable_id("source", url)
    observed = timestamp(item.scraped_at)
    digest = hashlib.sha256(item.body.encode("utf-8")).hexdigest()
    published = timestamp(item.published_at) if item.published_at else None
    values = (source_id, url, item.source_type, observed, observed, item.title, item.body, item.author, published, digest)
    connection.execute("INSERT INTO sources VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING", values)
    connection.execute("UPDATE sources SET first_seen=MIN(first_seen,?) WHERE id=?", (observed, source_id))
    connection.execute("""UPDATE sources SET source_type=?,scraped_at=?,title=?,body=?,author=?,published_at=?,content_hash=?
                          WHERE id=? AND scraped_at<=?""",
                       (item.source_type, observed, item.title, item.body, item.author, published, digest, source_id, observed))
    for entity in entities:
        connection.execute("""INSERT INTO nodes (id,name,canonical_key,entity_type,first_seen) VALUES (?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET first_seen=MIN(nodes.first_seen,excluded.first_seen)""",
            (entity.id, entity.canonical_name, canonical_key(entity.canonical_name), entity.type, observed))
        connection.execute("""INSERT INTO node_mentions VALUES (?,?,?) ON CONFLICT(node_id,source_id)
            DO UPDATE SET observed_at=MIN(node_mentions.observed_at,excluded.observed_at)""",
            (entity.id, source_id, observed))
        connection.execute("UPDATE nodes SET mention_count=(SELECT COUNT(*) FROM node_mentions WHERE node_id=?) WHERE id=?",
                           (entity.id, entity.id))
        for surface in {entity.canonical_name, *entity.aliases}:
            key = canonical_key(surface)
            if key:
                connection.execute("INSERT INTO aliases VALUES (?,?) ON CONFLICT DO NOTHING", (key, entity.id))
    return source_id, digest


def upsert_item(path: str | Path, item: ContentItem, entities: list[Entity], relationships: list[Relationship]) -> dict:
    ids = {entity.id for entity in entities}
    for relationship in relationships:
        if relationship.source not in ids or relationship.target not in ids:
            raise ValueError("Relationship endpoint is absent from this content's entities")
        start = relationship.sentence_start
        if item.body[start:start + len(relationship.sentence)] != relationship.sentence:
            raise ValueError("Relationship sentence does not match the normalized content")
    observed = timestamp(item.scraped_at)
    published = timestamp(item.published_at) if item.published_at else None
    with connect(path) as connection:
        before = connection.execute("SELECT COUNT(*) FROM edge_evidence").fetchone()[0]
        source_id, digest = store_content(connection, item, entities)
        touched = set()
        for relationship in relationships:
            source, target = relationship.source, relationship.target
            if source == target:
                continue
            if relationship.relation == "mentioned_with":
                source, target = sorted((source, target))
            edge_id = stable_id("edge", source, target, relationship.relation)
            connection.execute("INSERT INTO edges VALUES (?,?,?,?,0,?,?) ON CONFLICT DO NOTHING",
                               (edge_id, source, target, relationship.relation, observed, observed))
            connection.execute("""INSERT INTO edge_evidence VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(edge_id,source_id) DO NOTHING""", (edge_id, source_id, observed, observed,
                relationship.sentence, relationship.sentence_start, relationship.rule, item.title,
                item.source_type, published, digest))
            # If an older snapshot is imported later, its earlier evidence owns the citation.
            connection.execute("""UPDATE edge_evidence SET observed_at=?,sentence=?,sentence_start=?,rule=?,
                source_title=?,source_type=?,published_at=?,content_hash=?
                WHERE edge_id=? AND source_id=? AND observed_at>?""", (observed, relationship.sentence,
                relationship.sentence_start, relationship.rule, item.title, item.source_type, published,
                digest, edge_id, source_id, observed))
            connection.execute("UPDATE edge_evidence SET last_observed_at=MAX(last_observed_at,?) WHERE edge_id=? AND source_id=?",
                               (observed, edge_id, source_id))
            touched.add(edge_id)
        for edge_id in touched:
            connection.execute("""UPDATE edges SET
                weight=(SELECT COUNT(*) FROM edge_evidence WHERE edge_id=?),
                first_seen=(SELECT MIN(observed_at) FROM edge_evidence WHERE edge_id=?),
                last_seen=(SELECT MAX(last_observed_at) FROM edge_evidence WHERE edge_id=?) WHERE id=?""",
                (edge_id, edge_id, edge_id, edge_id))
        added = connection.execute("SELECT COUNT(*) FROM edge_evidence").fetchone()[0] - before
    return {"entities_processed": len(ids), "edges_processed": len(touched), "evidence_added": added}
