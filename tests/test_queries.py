from datetime import datetime, timezone

import pytest

from app.entities import entity_for
from app.models import ContentItem, Relationship
from app.queries import find_node, network, read_edges
from app.storage import connect, initialize, upsert_item


@pytest.fixture
def graph(tmp_path):
    path = tmp_path / "graph.db"
    initialize(path)
    entities = [entity_for(name, "person") for name in ("Alice", "Bob", "Carol", "Dana")]
    for index, (left, right) in enumerate([(0, 1), (1, 2), (2, 0), (2, 3)]):
        body = f"{entities[left].canonical_name} replied to {entities[right].canonical_name}."
        item = ContentItem(source_url=f"https://example.org/{index}", source_type="news",
            scraped_at=datetime(2026, 1, 1, tzinfo=timezone.utc), title="Report", body=body)
        relation = Relationship(source=entities[left].id, target=entities[right].id,
            relation="responded_to", sentence=body, sentence_start=0, rule="explicit_reply")
        upsert_item(path, item, [entities[left], entities[right]], [relation])
    return path


def test_lookup_and_edge_json_keep_stable_ids_and_citations(graph):
    with connect(graph) as connection:
        node = find_node(connection, "ALICE")
        assert find_node(connection, node.id) == node
        with pytest.raises(KeyError):
            find_node(connection, "Unknown")
        rows = connection.execute("SELECT * FROM edges").fetchall()
        edges = read_edges(connection, rows)
        assert all(edge.evidence and edge.evidence[0].content_hash for edge in edges)
        assert all(edge.model_dump(mode="json")["evidence"][0]["source_url"].startswith("https://") for edge in edges)


def test_depth_limits_cycles_and_duplicate_paths(graph):
    first = network(graph, "Alice", 1)
    second = network(graph, "Alice", 2)
    assert {node.name for node in first.nodes} == {"Alice", "Bob", "Carol"}
    assert {node.name for node in second.nodes} == {"Alice", "Bob", "Carol", "Dana"}
    assert len(first.edges) == 2 and len(second.edges) == 4
    assert len({edge.id for edge in second.edges}) == len(second.edges)
    with pytest.raises(ValueError, match="Depth"):
        network(graph, "Alice", 3)
