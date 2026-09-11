# Assessment checklist and implementation order

Source: the supplied four-page `evaluation.pdf`, Backend Engineering Intern
take-home, Python, one full day. This checklist paraphrases requirements; it does
not include or redistribute the assessment itself.

## Required outcome

- Configured seed URLs -> Crawl4AI -> normalization -> entity and typed relation
  extraction -> SQLite graph -> responding analysis endpoints.
- Three distinct source types, including news and discussion/social. Use a
  primary-source blog as the third angle on a shared topic.
- Configurable seed URLs, maximum link depth and domain whitelist. Changed seeds
  must work without editing Python. Handle failed pages and duplicate URLs.
- Common content fields: source_url, source_type, scraped_at, title, body,
  optional author and published_at. Preserve structurally different content.
- People, organizations, locations and topics/themes. No paid extraction API.
- Deterministic entity identity, aliases and a documented actual failure.
- Explicit relation types with explainable rules; document-level co-occurrence
  alone is insufficient. Inspect an actual extracted relationship.
- SQLite nodes (name/type/first_seen/mention_count), edges
  (endpoints/type/weight/first_seen/last_seen), sources and explicit evidence links.
- GET /entity/{name}/network: depth 1 and 2, nodes and edges, types and weights.
- GET /connections/new?since=<ISO timestamp>: newly observed or significantly
  growing relationships. Define, justify and test the growth threshold.
- GET /entities/central: explainable ranking and its limitations.
- README reflections grounded in actual code/data: relationship correctness,
  normalization failure, noise suppression, Neo4j trade-offs, continuous updates.
- Working setup, meaningful deterministic tests and a real crawl/API check.
- Keep the design small enough to explain and reproduce in a day.

## Phases and commits

0. Read requirements and record this checklist.
1. Define data contracts, identity, evidence counting and analysis semantics.
2. Implement and manually inspect the configurable Crawl4AI crawl.
3. Normalize three source structures and test missing fields.
4. Extract entities and deterministic topics using spaCy.
5. Resolve cautious aliases; inspect real normalization failures.
6. Extract sentence-level typed relationships and retain evidence.
7. Store an idempotent graph with timestamped provenance in SQLite.
8. Connect the pipeline and inspect real graph records.
9. Expose depth-limited graph traversal.
10. Expose and test emerging connections.
11. Expose and test centrality.
12. Complete deterministic boundary and integration coverage.
13. Run real end-to-end validation, including changed seeds and repeated input.
14. Finish setup, API examples and the five specific README reflections.
15. Audit every rubric item with implementation, evidence and weaknesses.

Each phase is checked before its commit is pushed. Unit tests accompany the
relevant code; phase 12 fills gaps instead of postponing verification.

## Minimum design

One Python package, one pipeline command, one FastAPI application, one SQLite
file. Modules separate stages without repositories, factories or service layers.
Use Crawl4AI, spaCy, Pydantic, PyYAML, Beautiful Soup, pytest, HTTPX and Uvicorn.
Use Python's sqlite3 rather than adding an ORM. Simple queries and bounded BFS
are sufficient; no NetworkX or additional infrastructure is needed.

The local database and full crawled pages are generated outputs and ignored by
Git. Small real-data excerpts and a validation report will make findings
reviewable without publishing a large crawl archive.
