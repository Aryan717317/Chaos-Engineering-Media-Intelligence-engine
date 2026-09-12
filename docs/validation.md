# Final validation

This records the initial implementation. The subsequent
[quality review](quality-review.md) reports the current extraction results,
125 tests and updated API examples. The setup and changed-seed checks below
remain evidence of the original end-to-end run.

Verified on 2026-09-12 with Python 3.12.14, the pinned requirements and
`en_core_web_sm` 3.8.0. Raw page bodies, databases and machine-readable reports
remain in ignored `data/`; the following records observed results, not fixtures.

## Live crawl through graph storage

```shell
python scripts/run_pipeline.py --db data/graph.db --strict --crawl-output data/pipeline-live-crawl.json --report data/pipeline-live-report.json
```

Completed at 03:50:32 UTC: 6 scheduled, 6 crawled, 6 processed, zero failures.
News, discussion and blog each contributed two pages. The graph had 705 nodes,
554 edges and 581 distinct edge/source evidence records across six sources.
Seven edges were affiliations; 547 were weak co-mentions. Reply/quotation rules
had no matched observations in this sample and are covered by deterministic
tests. [Extraction checks](extraction-check.md) explain actual successes/errors.

## Changed seed URLs

Copied the source configuration to `data/changed-sources.yaml`, replaced all
three seeds below, and set depth 0 / page budget 3. No Python code was edited:

- [Guardian: OpenAI leadership change](https://www.theguardian.com/technology/2023/nov/17/openai-ceo-sam-altman-fired)
- [Hacker News discussion](https://news.ycombinator.com/item?id=12592010)
- [Microsoft M12 post](https://blogs.microsoft.com/blog/2023/01/05/m12-ventures-down-a-new-path/)

```shell
python scripts/run_pipeline.py --config data/changed-sources.yaml --db data/changed-seeds-retry.db --strict --crawl-output data/changed-seeds-retry-crawl.json --report data/changed-seeds-retry-report.json
```

The first attempt failed with a navigation timeout, DNS resolution failure and
browser network suspension; it returned failure and reported all missing types.
The retry completed at 10:21:03 UTC with all three pages processed, no failures,
46 nodes, 36 edges and 36 evidence records. Each source type contributed one
page. This checks different URLs on the supported sites, not universal extraction
quality on arbitrary domains.

## Repeatability and integrity

```shell
python scripts/run_pipeline.py --db data/graph.db --from-crawl data/pipeline-live-crawl.json --strict --report data/replay-report.json
```

Replay completed at 10:21:45 UTC with zero new evidence. Rows in all six tables
were compared before and after; they were identical, including observation
times and evidence. `PRAGMA integrity_check` returned `ok`. Every edge had
evidence, and every stored weight equaled its distinct evidence count.

## Actual HTTP requests

Started Uvicorn on `127.0.0.1:8765` against the live-run database and used HTTPX
to make requests. The checks were over HTTP, in addition to FastAPI TestClient
coverage. The machine-readable result is local `data/http-check.json`.

| Entity | Depth | Include weak | Nodes | Edges |
| --- | ---: | --- | ---: | ---: |
| Sam Altman | 1 | yes | 34 | 34 |
| Sam Altman | 2 | yes | 211 | 334 |
| Sam Altman | 1 | no | 3 | 2 |
| Sam Altman | 2 | no | 5 | 4 |
| OpenAI | 1 | yes | 92 | 94 |
| OpenAI | 2 | yes | 244 | 390 |
| OpenAI | 1 | no | 4 | 3 |
| OpenAI | 2 | no | 5 | 4 |

All returned edges had citations. Unknown names returned 404, the ambiguous
Altman alias returned 409, and invalid depth returned 422.

`/connections/new?since=2026-01-01T00:00:00Z` returned 554 newly observed edges;
filtering weak edges returned 7. A future boundary returned an empty graph.
Missing or timezone-free boundaries returned 422. This single live observation
window demonstrates new edges; controlled multi-date tests verify the growing
threshold, equality boundary and rerun behavior.

`/entities/central?limit=5` ranked OpenAI (91 neighbors), Artificial intelligence
(50), Sam (40), Sam Altman (33) and Microsoft (30). The unresolved Sam node shows
how extraction errors affect ranking. With weak edges excluded, OpenAI had three
neighbors and Sam Altman had two. Invalid limits returned 422. OpenAPI exposed
all three required paths.

## Tests and real fixes

```shell
python -m pytest -q --basetemp=tmp/tests
python -m pip check
```

96 tests passed. A dependency deprecation warning is present; it does not affect
the assertions. `pip check` found no broken requirements. Coverage includes
crawl budgets/whitelists, three content structures, aliases, relation direction
and uncertainty, storage rollback/provenance, cycles, growth thresholds,
centrality, HTTP validation and failure handling.

[Bug-fix notes](bug-fixes.md) record defects reproduced before correction:
invalid seed shapes, silently ignored domain rules, malformed selectors and
uncaught YAML parser errors.

## Fresh environment setup

Created a separate virtual environment without system site packages, installed
`requirements.txt` and the pinned 3.8.0 model using the README commands, and ran
`pip check`. An initial package-registry DNS failure interrupted installation;
the retry succeeded without modifying dependencies.

All 96 tests passed in that environment. Replaying the three changed-seed pages
into a fresh database produced the same 46 nodes, 36 edges and 36 evidence links.
The model loaded successfully, and Playwright's Chromium installation check and
headless browser launch passed. This reused the host's installed browser binary;
it did not simulate a new operating system. Linux/macOS setup was not executed.
