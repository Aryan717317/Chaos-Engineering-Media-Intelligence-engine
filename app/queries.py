"""Graph queries over SQLite; no separate in-memory graph service."""

from app.entities import canonical_key
from app.models import Evidence, GraphEdge, GraphNode, NetworkResponse
from app.storage import connect


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
