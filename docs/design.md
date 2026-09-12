# Data contracts and counting rules

## Boundaries

The pipeline and API are entry points into the same Python package. Crawl4AI
fetches pages; normalization produces `ContentItem`; spaCy and deterministic
rules produce mentions and relationships; sqlite3 stores them. The API reads
SQLite. No queue, scheduler, graph server or frontend is required by the PDF.

`ContentItem` contains the PDF's seven fields. A missing title falls back to its
URL. Author and publication time can be null. Empty content is a visible failed
normalization, not a successful empty article. All stored times are UTC. Scrape
timestamps must be timezone-aware. A page's timezone-free publication metadata
will be treated as UTC and this assumption logged by normalization.

## Identity before storage

- Canonical lookup keys use Unicode NFKC, case folding, collapsed whitespace,
  leading @ removal and punctuation cleanup.
- Entity IDs hash `(type, canonical lookup key)`; spelling case and insertion
  order do not change IDs. Different types cannot accidentally share an ID.
- A small external alias file can map handles and known variants to a canonical
  name. URLs never occur in extraction logic.
- Short names first use a unique full-name candidate in the same paragraph/comment.
  Narrative sources can fall back to a unique document-wide surname; discussions
  cannot borrow that context from another reply. Type corrections need human
  context and protect explicit places/known organizations. No fuzzy matching.
- Mention offsets refer to the exact normalized body; the relationship stage
  uses those offsets to resolve sentence entities.
- API lookup can use stored aliases, but ambiguity returns an explicit error.
  Same-name people and mistakes made by NER remain known limitations.

## Graph and evidence

`nodes`: stable id, canonical name/key/type, first_seen and mention_count.
`edges`: stable id, source/target node IDs, relation, weight, first_seen, last_seen.
`sources`: unique normalized URL, source_type, first_seen, latest scraped_at,
title, body, author, published_at and content hash.
`edge_evidence`: unique `(edge_id, source_id)`, first observed_at,
last_observed_at, supporting sentence, sentence offset and extraction rule.
`node_mentions`: unique `(node_id, source_id)` with first observation time.
`aliases`: lookup keys associated with entity IDs, including observed surfaces
and explicit configured aliases for encountered entities.

The extra linkage tables support the PDF's required provenance, temporal
analysis and idempotent reruns. They add a few joins, avoiding a history service.

**Edge weight is the number of distinct source URLs ever observed supporting
that typed edge.** Repeating a sentence or crawling an unchanged page again
does not increase weight. A revised page can introduce a new relationship,
but cannot add another vote for an existing one. Retain the first supporting
sentence and its publication metadata even if the page later changes.

Node mention_count likewise means distinct source URLs mentioning the entity,
not raw word occurrences. This reduces long-thread repetition bias. Sources
retain their latest content; evidence is historical and is not retracted if a
page later deletes or corrects a claim. Syndicated copies on different URLs can
still inflate counts. A source's claim is evidence of reporting, not proof.

Directed edges retain linguistic direction. `mentioned_with` is symmetric and
sorts endpoint IDs before hashing. Self-edges are omitted. Reprocessing is one
transaction per content item, with foreign keys and uniqueness constraints.

## Relationship vocabulary

- `responded_to`: responder -> addressed entity, explicit response/reply pattern.
- `quoted_by`: quoted entity -> quoting entity, explicit active quote pattern.
- `affiliated_with`: person -> organization, explicit employment/joining or
  organization-role-person pattern.
- `mentioned_with`: nearby entities in one sentence where no typed rule matches;
  this is weak co-mention evidence, not a claim of affiliation.

Retain the exact sentence and rule name, not an invented confidence number.
Use named dependency arguments and role bindings for typed rules. Limit pair
distance for weak co-mentions. Reject negation, conditional/modal and
denial/planning context, with explicit prediction/request guards. Syntax,
pronouns, irony and complex clauses will still cause errors. See the
[quality review](quality-review.md) for actual improvements and failures.

## Analysis contracts

- Network: depth defaults to 2; allowed values 1 and 2. Traverse incoming and
  outgoing links to find connected entities, retain original edge directions,
  deduplicate nodes/edges, include evidence. Unknown names return 404.
- Emerging: `since` is a timezone-aware ISO timestamp. A baseline counts evidence
  first observed strictly before since; an increase counts observations at or
  after it. New means baseline=0 and increase>0. Growing means baseline>0,
  increase>=3 and increase/baseline>=0.5. Three additional URLs reduce single-page
  noise; 50% requires a meaningful proportional change. This is a documented
  heuristic, not statistically calibrated. It misses small but important stories
  and gradual growth on established edges. Observation time measures discovery
  by this crawl, not when the reported event happened.
- Centrality: normalized undirected degree = unique neighbors / (node count-1),
  or zero with fewer than two nodes. Return degree, mention_count and distinct
  relation types alongside score. Degree measures breadth of connection; it
  misses intermediaries and real-world influence. Deterministic ties use mention
  count, then canonical name and ID. No NetworkX dependency is necessary.
