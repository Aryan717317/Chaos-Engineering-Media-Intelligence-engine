from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api import create_app
from app.entities import entity_for
from app.models import ContentItem, Relationship
from app.storage import initialize, upsert_item


def test_network_http_contract_and_encoded_names(tmp_path):
    path = tmp_path / "api.db"
    initialize(path)
    alice, bob = entity_for("Alice Smith", "person"), entity_for("Bob Jones", "person")
    body = "Alice Smith replied to Bob Jones."
    item = ContentItem(source_url="https://example.org/story", source_type="news", title="Report", body=body,
                       scraped_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    relation = Relationship(source=alice.id, target=bob.id, relation="responded_to", sentence=body,
                            sentence_start=0, rule="explicit_reply")
    upsert_item(path, item, [alice, bob], [relation])
    with TestClient(create_app(str(path))) as client:
        response = client.get("/entity/Alice%20Smith/network?depth=1")
        assert response.status_code == 200
        data = response.json()
        assert len(data["nodes"]) == 2 and len(data["edges"]) == 1
        assert data["edges"][0]["evidence"][0]["source_url"] == item.source_url
        assert client.get("/entity/Unknown/network").status_code == 404
        assert client.get("/entity/Alice%20Smith/network?depth=3").status_code == 422
        assert client.get("/entity/Alice%20Smith/network?depth=nope").status_code == 422
        assert "/entity/{name}/network" in client.get("/openapi.json").json()["paths"]
        new = client.get("/connections/new", params={"since": "2026-01-01T05:30:00+05:30"})
        assert new.status_code == 200
        assert new.json()["edges"][0]["reason"] == "new"
        assert new.json()["edges"][0]["increase"] == 1
        assert client.get("/connections/new?since=2027-01-01T00:00:00Z").json()["edges"] == []
        assert client.get("/connections/new").status_code == 422
        for invalid in ("bad", "2026-01-01", "2026-01-01T00:00:00"):
            assert client.get("/connections/new", params={"since": invalid}).status_code == 422
        central = client.get("/entities/central?limit=1")
        assert central.status_code == 200
        assert len(central.json()["entities"]) == 1
        assert central.json()["entities"][0]["degree_centrality"] == 1
        for invalid in ("0", "101", "bad"):
            assert client.get("/entities/central", params={"limit": invalid}).status_code == 422


def test_ambiguous_names_offer_ids_and_weak_edges_can_be_filtered(tmp_path):
    path = tmp_path / "api.db"
    initialize(path)
    person, place = entity_for("Jordan", "person"), entity_for("Jordan", "location")
    body = "Jordan visited Jordan."
    item = ContentItem(source_url="https://example.org/story", source_type="news", title="Report", body=body,
                       scraped_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    relation = Relationship(source=person.id, target=place.id, relation="mentioned_with", sentence=body,
                            sentence_start=0, rule="adjacent_sentence_mentions")
    upsert_item(path, item, [person, place], [relation])
    with TestClient(create_app(str(path))) as client:
        response = client.get("/entity/Jordan/network")
        assert response.status_code == 409
        assert len(response.json()["detail"]["candidates"]) == 2
        assert len(client.get(f"/entity/{person.id}/network").json()["nodes"]) == 2
        strong = client.get(f"/entity/{person.id}/network?include_weak=false").json()
        assert len(strong["nodes"]) == 1 and strong["edges"] == []
        assert client.get("/connections/new?since=2026-01-01T00:00:00Z&include_weak=false").json()["edges"] == []
        assert all(node["degree"] == 0 for node in client.get("/entities/central?include_weak=false").json()["entities"])
