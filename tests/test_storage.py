import sqlite3
from datetime import datetime, timezone

import pytest

from app.entities import entity_for
from app.models import ContentItem, Relationship
from app.storage import connect, initialize, store_content, upsert_item


def test_schema_is_repeatable_and_enforces_foreign_keys(tmp_path):
    path = tmp_path / "graph.db"
    initialize(path)
    initialize(path)
    with connect(path) as connection:
        names = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert names == {"nodes", "sources", "node_mentions", "aliases", "edges", "edge_evidence"}
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO node_mentions VALUES ('missing','missing','2026-01-01')")


def content(url="https://example.org/story", day=1, body="Alice works for Acme."):
    return ContentItem(source_url=url, source_type="news", scraped_at=datetime(2026, 1, day, tzinfo=timezone.utc),
                       title="Report", body=body)


def test_content_reruns_do_not_inflate_mentions_and_older_input_does_not_replace_latest(tmp_path):
    path = tmp_path / "graph.db"
    initialize(path)
    entity = entity_for("Alice", "person")
    with connect(path) as connection:
        store_content(connection, content(day=2, body="Latest content."), [entity])
        store_content(connection, content(day=1), [entity])
        store_content(connection, content(url="https://example.org/story?utm_source=test", day=3), [entity])
        assert connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 1
        assert connection.execute("SELECT mention_count FROM nodes").fetchone()[0] == 1
        assert connection.execute("SELECT body FROM sources").fetchone()[0] == "Alice works for Acme."
        assert connection.execute("SELECT first_seen FROM sources").fetchone()[0].startswith("2026-01-01")


def graph_input():
    entities = [entity_for("Alice", "person"), entity_for("Acme", "organization")]
    relation = Relationship(source=entities[0].id, target=entities[1].id, relation="affiliated_with",
                            sentence="Alice works for Acme.", sentence_start=0, rule="employment_verb")
    return entities, [relation]


def test_edges_count_sources_and_preserve_citations(tmp_path):
    path = tmp_path / "graph.db"
    initialize(path)
    entities, relations = graph_input()
    assert upsert_item(path, content(), entities, relations)["evidence_added"] == 1
    assert upsert_item(path, content(day=2), entities, relations)["evidence_added"] == 0
    upsert_item(path, content(url="https://example.org/another", day=3), entities, relations)
    with connect(path) as connection:
        edge = connection.execute("SELECT * FROM edges").fetchone()
        assert edge["weight"] == 2
        assert edge["first_seen"].startswith("2026-01-01") and edge["last_seen"].startswith("2026-01-03")
        rows = connection.execute("SELECT sentence,source_url FROM edge_evidence e JOIN sources s ON s.id=e.source_id").fetchall()
        assert len(rows) == 2 and all(r["sentence"] == "Alice works for Acme." for r in rows)
