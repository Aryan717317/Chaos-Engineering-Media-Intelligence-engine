CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    canonical_key TEXT NOT NULL,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('person','organization','location','topic')),
    first_seen TEXT NOT NULL,
    mention_count INTEGER NOT NULL DEFAULT 0 CHECK (mention_count >= 0),
    UNIQUE (canonical_key, entity_type)
);
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    source_url TEXT NOT NULL UNIQUE,
    source_type TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    scraped_at TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    author TEXT,
    published_at TEXT,
    content_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS node_mentions (
    node_id TEXT NOT NULL REFERENCES nodes(id),
    source_id TEXT NOT NULL REFERENCES sources(id),
    observed_at TEXT NOT NULL,
    PRIMARY KEY (node_id, source_id)
);
CREATE TABLE IF NOT EXISTS aliases (
    alias_key TEXT NOT NULL,
    node_id TEXT NOT NULL REFERENCES nodes(id),
    PRIMARY KEY (alias_key, node_id)
);
CREATE TABLE IF NOT EXISTS edges (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL REFERENCES nodes(id),
    target TEXT NOT NULL REFERENCES nodes(id),
    relation TEXT NOT NULL CHECK (relation IN ('mentioned_with','responded_to','quoted_by','affiliated_with')),
    weight INTEGER NOT NULL DEFAULT 0 CHECK (weight >= 0),
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    CHECK (source != target),
    UNIQUE (source, target, relation)
);
CREATE TABLE IF NOT EXISTS edge_evidence (
    edge_id TEXT NOT NULL REFERENCES edges(id),
    source_id TEXT NOT NULL REFERENCES sources(id),
    observed_at TEXT NOT NULL,
    last_observed_at TEXT NOT NULL,
    sentence TEXT NOT NULL,
    sentence_start INTEGER NOT NULL CHECK (sentence_start >= 0),
    rule TEXT NOT NULL,
    source_title TEXT NOT NULL,
    source_type TEXT NOT NULL,
    published_at TEXT,
    content_hash TEXT NOT NULL,
    PRIMARY KEY (edge_id, source_id)
);
CREATE INDEX IF NOT EXISTS edges_target ON edges(target);
CREATE INDEX IF NOT EXISTS edges_first_seen ON edges(first_seen);
CREATE INDEX IF NOT EXISTS evidence_observation ON edge_evidence(observed_at, edge_id);
CREATE INDEX IF NOT EXISTS mentions_source ON node_mentions(source_id);
