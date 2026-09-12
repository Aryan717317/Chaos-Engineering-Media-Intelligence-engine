"""Graph queries over SQLite; no separate in-memory graph service."""

from app.entities import canonical_key
from app.models import (CentralEntity, CentralityResponse, ConnectionsResponse, EmergingEdge,
                        Evidence, GraphEdge, GraphNode, NetworkResponse)
from app.storage import connect, timestamp


class AmbiguousEntity(ValueError):
    def __init__(self, candidates):
        super().__init__("Ambiguous entity name; use a canonical name or node ID")
        self.candidates = candidates


def batches(values, size=400):
    values = list(values)
    for start in range(0, len(values), size):
        yield values[start:start + size]


def node_from_row(row) -> GraphNode:
    return GraphNode(id=row["id"], name=row["name"], type=row["entity_type"],
                     first_seen=row["first_seen"], mention_count=row["mention_count"])


def find_node(connection, name: str) -> GraphNode:
    row = connection.execute("SELECT * FROM nodes WHERE id=?", (name,)).fetchone()
    if row:
        return node_from_row(row)
    rows = connection.execute("SELECT n.* FROM nodes n JOIN aliases a ON n.id=a.node_id WHERE a.alias_key=? ORDER BY n.id",
                              (canonical_key(name),)).fetchall()
    if not rows:
        raise KeyError(name)
    if len(rows) > 1:
        raise AmbiguousEntity([node_from_row(row) for row in rows])
    return node_from_row(rows[0])


def read_nodes(connection, ids) -> list[GraphNode]:
    nodes = []
    for batch in batches(sorted(set(ids))):
        placeholders = ",".join("?" for _ in batch)
        nodes.extend(node_from_row(row) for row in connection.execute(f"SELECT * FROM nodes WHERE id IN ({placeholders})", batch))
    return sorted(nodes, key=lambda n: n.id)


def read_edges(connection, rows) -> list[GraphEdge]:
    rows = list(rows)
    evidence = {row["id"]: [] for row in rows}
    for batch in batches(sorted(evidence)):
        placeholders = ",".join("?" for _ in batch)
        for row in connection.execute(f"""SELECT v.edge_id,s.source_url,v.source_type,v.source_title AS title,
            v.observed_at,v.last_observed_at,v.published_at,v.sentence,v.rule,v.sentence_start,v.content_hash
            FROM edge_evidence v JOIN sources s ON s.id=v.source_id
            WHERE v.edge_id IN ({placeholders}) ORDER BY v.observed_at,s.source_url""", batch):
            evidence[row["edge_id"]].append(Evidence(**dict(row)))
    return [GraphEdge(**dict(row), evidence=evidence[row["id"]]) for row in sorted(rows, key=lambda r: r["id"])]


def network(path, name: str, depth: int = 2, include_weak: bool = True) -> NetworkResponse:
    if depth not in (1, 2):
        raise ValueError("Depth must be 1 or 2")
    with connect(path) as connection:
        connection.execute("BEGIN")
        entity = find_node(connection, name)
        found = {entity.id}
        frontier = {entity.id}
        edges = {}
        for _ in range(depth):
            neighbors = set()
            for batch in batches(sorted(frontier)):
                placeholders = ",".join("?" for _ in batch)
                strength_filter = "" if include_weak else " AND relation!='mentioned_with'"
                for row in connection.execute(f"SELECT * FROM edges WHERE (source IN ({placeholders}) OR target IN ({placeholders})){strength_filter}",
                                              [*batch, *batch]):
                    edges[row["id"]] = row
                    neighbors.update((row["source"], row["target"]))
            frontier = neighbors - found
            found.update(neighbors)
            if not frontier:
                break
        return NetworkResponse(entity=entity, depth=depth, nodes=read_nodes(connection, found),
                               edges=read_edges(connection, edges.values()))


def growth_reason(before: int, increase: int) -> str | None:
    if before == 0 and increase > 0:
        return "new"
    if before > 0 and increase >= 3 and increase >= before * 0.5:
        return "growing"
    return None


def emerging_connections(path, since, include_weak: bool = True) -> ConnectionsResponse:
    boundary = timestamp(since)
    strength_filter = "" if include_weak else "WHERE e.relation!='mentioned_with'"
    with connect(path) as connection:
        connection.execute("BEGIN")
        rows = connection.execute(f"""SELECT e.*,
            SUM(CASE WHEN v.observed_at < ? THEN 1 ELSE 0 END) AS weight_before,
            SUM(CASE WHEN v.observed_at >= ? THEN 1 ELSE 0 END) AS increase
            FROM edges e JOIN edge_evidence v ON e.id=v.edge_id {strength_filter} GROUP BY e.id""",
            (boundary, boundary)).fetchall()
        selected = {row["id"]: row for row in rows if growth_reason(row["weight_before"], row["increase"])}
        edges = []
        for edge in read_edges(connection, selected.values()):
            row = selected[edge.id]
            before, increase = row["weight_before"], row["increase"]
            edges.append(EmergingEdge(**edge.model_dump(), reason=growth_reason(before, increase),
                weight_before=before, increase=increase, relative_increase=increase / before if before else None))
        ids = {node_id for edge in edges for node_id in (edge.source, edge.target)}
        return ConnectionsResponse(since=boundary, nodes=read_nodes(connection, ids), edges=edges)


def central_entities(path, limit: int = 20, include_weak: bool = True) -> CentralityResponse:
    if not 1 <= limit <= 100:
        raise ValueError("Limit must be between 1 and 100")
    strength_filter = "" if include_weak else "WHERE relation!='mentioned_with'"
    with connect(path) as connection:
        connection.execute("BEGIN")
        total = connection.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        rows = connection.execute(f"""WITH neighbors AS (
            SELECT source AS node_id, target AS neighbor FROM edges {strength_filter}
            UNION SELECT target AS node_id, source AS neighbor FROM edges {strength_filter}
        ) SELECT n.*, COUNT(v.neighbor) AS degree FROM nodes n
          LEFT JOIN neighbors v ON n.id=v.node_id GROUP BY n.id
          ORDER BY degree DESC, n.mention_count DESC, LOWER(n.name), n.id LIMIT ?""", (limit,)).fetchall()
        types = {row["id"]: set() for row in rows}
        for batch in batches(types):
            placeholders = ",".join("?" for _ in batch)
            for edge in connection.execute(f"""SELECT source,target,relation FROM edges
                WHERE (source IN ({placeholders}) OR target IN ({placeholders}))
                {"" if include_weak else "AND relation!='mentioned_with'"}""", [*batch, *batch]):
                for node_id in (edge["source"], edge["target"]):
                    if node_id in types:
                        types[node_id].add(edge["relation"])
        entities = [CentralEntity(**node_from_row(row).model_dump(), degree=row["degree"],
                    degree_centrality=row["degree"] / (total - 1) if total > 1 else 0,
                    relation_types=sorted(types[row["id"]])) for row in rows]
        return CentralityResponse(total_nodes=total, include_weak=include_weak, entities=entities)
