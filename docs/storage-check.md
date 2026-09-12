# SQLite storage check

The six actual normalized pages and their extracted entities/relations were
ingested into an ignored local `data/storage-check.db` file.

| Record | Count |
| --- | ---: |
| Source URLs | 6 |
| Nodes | 705 |
| Edges | 554 |
| Edge/source evidence links | 581 |
| Edges without evidence | 0 |

There are seven distinct affiliation edges supported by nine source-level
observations, plus 547 weak co-mention edges supported by 572 observations.
SQLite `integrity_check` returned `ok`. Seven storage tests pass.

The schema is in `app/schema.sql`. Uniqueness constraints deduplicate canonical
entities, source URLs, typed endpoint pairs and edge/source evidence. Each item
uses one transaction. Tests force a failure after writes begin and verify that
both source and node changes are rolled back. Foreign keys are enabled on every
connection; WAL allows readers while a writer is active.

Historical evidence retains its first supporting sentence, normalized-body
offset, source title, type, publication time, body hash and observation time.
If an older saved crawl arrives later, it becomes the first evidence; the
source table still keeps the newest content. Updated/deleted claims do not
remove historical edges. Reruns of one source never increase edge weight.

The graph is generated locally rather than committed. This avoids publishing
large scraped bodies and an opaque pre-populated answer. Final reproduction
instructions and API validation are added in the pipeline and API phases.
