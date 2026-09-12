from datetime import datetime, timezone

import pytest

from app.entities import entity_for
from app.models import ContentItem, Relationship
from app.queries import central_entities
from app.storage import initialize, upsert_item


def test_degree_counts_neighbors_once_and_keeps_isolates(tmp_path):
    path = tmp_path / "graph.db"
    initialize(path)
    assert central_entities(path).entities == []
    entities = [entity_for(name, "person") for name in ("Alice", "Bob", "Carol", "Isolated")]
    body = "Alice replied to Bob and Carol."
    item = ContentItem(source_url="https://example.org/1", source_type="news", title="Report", body=body,
                       scraped_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    relations = [Relationship(source=entities[left].id, target=entities[right].id, relation=kind,
                 sentence=body, sentence_start=0, rule="test_fixture")
                 for left, right, kind in [(0, 1, "responded_to"), (1, 0, "quoted_by"),
                                            (0, 1, "mentioned_with"), (0, 2, "mentioned_with")]]
    upsert_item(path, item, entities, relations)
    result = central_entities(path)
    assert result.total_nodes == 4
    assert [(node.name, node.degree) for node in result.entities] == [
        ("Alice", 2), ("Bob", 1), ("Carol", 1), ("Isolated", 0)]
    assert result.entities[0].degree_centrality == pytest.approx(2 / 3)
    assert set(result.entities[0].relation_types) == {"responded_to", "quoted_by", "mentioned_with"}
    strong = central_entities(path, include_weak=False)
    assert [node.degree for node in strong.entities] == [1, 1, 0, 0]
    assert strong.entities[0].degree_centrality == pytest.approx(1 / 3)
    assert len(central_entities(path, limit=1).entities) == 1


def test_single_node_has_zero_centrality(tmp_path):
    path = tmp_path / "graph.db"
    initialize(path)
    item = ContentItem(source_url="https://example.org/1", source_type="news", title="Report", body="Alice.",
                       scraped_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    upsert_item(path, item, [entity_for("Alice", "person")], [])
    assert central_entities(path).entities[0].degree_centrality == 0
