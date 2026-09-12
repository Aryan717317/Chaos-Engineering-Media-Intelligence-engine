from datetime import datetime, timezone

import pytest

from app.entities import entity_for
from app.models import ContentItem, Relationship
from app.queries import emerging_connections
from app.storage import initialize, upsert_item


@pytest.mark.parametrize("before,increase,reason", [
    (0, 1, "new"), (1, 0, None), (1, 2, None), (6, 3, "growing"), (7, 3, None), (4, 3, "growing"),
])
def test_growth_uses_absolute_and_relative_thresholds(tmp_path, before, increase, reason):
    path = tmp_path / "graph.db"
    initialize(path)
    entities = [entity_for("Alice", "person"), entity_for("Acme", "organization")]
    body = "Alice works for Acme."
    relation = Relationship(source=entities[0].id, target=entities[1].id, relation="affiliated_with",
                            sentence=body, sentence_start=0, rule="employment_verb")
    for index in range(before + increase):
        day = 1 if index < before else 2
        item = ContentItem(source_url=f"https://example.org/{index}", source_type="news", title="Report", body=body,
                           scraped_at=datetime(2026, 1, day, tzinfo=timezone.utc))
        upsert_item(path, item, entities, [relation])
        if index < before:
            # A later crawl changes last_seen, but is not another source vote.
            upsert_item(path, item.model_copy(update={"scraped_at": datetime(2026, 1, 3, tzinfo=timezone.utc)}), entities, [relation])
    result = emerging_connections(path, datetime(2026, 1, 2, tzinfo=timezone.utc))
    if reason is None:
        assert result.edges == []
    else:
        edge = result.edges[0]
        assert (edge.reason, edge.weight_before, edge.increase, edge.weight) == (reason, before, increase, before + increase)
        assert len(edge.evidence) == edge.weight
    assert not emerging_connections(path, datetime(2026, 2, 1, tzinfo=timezone.utc)).edges
