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

Each phase was checked as it was built. Unit tests accompanied the relevant
code; phase 12 filled gaps instead of postponing verification. At the author's
request, the granular development history was consolidated into fewer coherent
steps, retaining identical file snapshots and the original README author edit.

## Minimum design

One Python package, one pipeline command, one FastAPI application, one SQLite
file. Modules separate stages without repositories, factories or service layers.
Use Crawl4AI, spaCy, Pydantic, PyYAML, Beautiful Soup, pytest, HTTPX and Uvicorn.
Use Python's sqlite3 rather than adding an ORM. Simple queries and bounded BFS
are sufficient; no NetworkX or additional infrastructure is needed.

The local database and full crawled pages are generated outputs and ignored by
Git. Small real-data excerpts and a validation report will make findings
reviewable without publishing a large crawl archive.

## Final rubric audit

All required behaviors have been implemented and checked. Weaknesses below are
explicit limits of this scoped solution; they are not hidden behind test counts.

| Criterion | Implementation | Demonstration | Remaining weakness / further work |
| --- | --- | --- | --- |
| Complete pipeline | `scripts/run_pipeline.py`, `app/pipeline.py`, `app/api.py` | Six real pages through storage and all three HTTP endpoints | Websites remain an external dependency; no further work needed for the bounded run |
| Multiple source types | `config/sources.yaml`, `app/normalize.py` | News/discussion/blog contributed two pages each; changed-seed run contributed one each | New layouts can need new selectors; arbitrary-site quality is not guaranteed |
| Configurable crawling | `app/config.py`, `app/crawler.py` | Three replaced URLs, depth-0 live run; deterministic depth/budget/domain tests | Whitelist is not an asset/redirect firewall; static rule configuration is deliberate |
| Entity extraction | `app/extract.py`, topic vocabulary | Real people, organizations, locations and topics, with retained offsets | English NER and vocabulary coverage are imperfect |
| Entity normalization | `app/entities.py`, alias vocabulary | Known OpenAI/handle variants converge; ambiguous surname returns 409 | Same-name people and document-wide surname scope need richer context |
| Relationship quality | `app/relationships.py` | Seven affiliation edges inspected with evidence; four supported types tested | 547 weak edges; no live matched reply/quote phrases; larger precision study is future work |
| Graph and provenance | `app/schema.sql`, `app/storage.py` | 554 edges, all traced; exact replay equality; weights checked against evidence | No retractions, content version archive or syndication deduplication |
| Depth-1/2 network | `app/queries.py`, `app/api.py` | Cycles/directions tested; eight live network requests checked | No pagination for large neighborhoods |
| Emerging connections | `growth_reason`, `emerging_connections` | Live new-edge query; absolute/relative threshold and boundary tests | Heuristic significance; first observation is not event time |
| Centrality | `central_entities` | Star/isolate/parallel-edge tests and actual top-five ranking | Measures degree, misses brokerage and real-world influence |
| Specific reflections | `README.md` sections A–E | Real relationship, real alias failure, noise, Neo4j and continuous-update trade-offs | Improvements are described as future work, not claimed as implemented |
| Simplicity and reproducibility | One package, CLI, API and SQLite file | Pinned direct dependencies, offline tests, setup/run instructions | Transitive dependencies and live pages may change; no extra infrastructure required |

See [final validation](validation.md) for observed counts, HTTP outcomes,
repeatability and environment checks. The database and full scraped bodies are
generated locally; no fake populated graph is supplied.
