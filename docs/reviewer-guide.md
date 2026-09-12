# Reviewer walkthrough

This short route checks the behavior described in the [README](../README.md).
The [validation report](validation.md) records the observed six-page run;
counts from a fresh live crawl can differ as websites change.

## Build a fresh graph

Install the pinned packages, spaCy model and Chromium using the README setup.
From the repository root, run:

```shell
python scripts/run_pipeline.py --db data/review.db --strict --crawl-output data/review-crawl.json --report data/review-summary.json
```

Read the report's `success`, `source_types`, `crawl_failures`, `failures` and
`database_counts`. A successful browser fetch alone is insufficient: every
configured source type must contribute processed content. Inspect failures
before comparing graph sizes.

To exercise the evaluator's changed-seed requirement, copy `config/sources.yaml`,
replace its URLs and whitelist entries, and pass `--config` with another `--db`.
Depth 0 isolates the new seeds; depth 1 also checks link following. Source rules
control selectors and the type assigned to discovered pages.

## Check API behavior

Point the API at the same database. In PowerShell:

```powershell
$env:MEDIA_DB_PATH = 'data/review.db'
python -m uvicorn app.api:app --host 127.0.0.1 --port 8000
```

Use the interactive [API documentation](http://127.0.0.1:8000/docs) to try:

| Request | What to inspect |
| --- | --- |
| `/entity/OpenAI/network?depth=1` | Stable node IDs, relation direction and citations |
| `/entity/OpenAI/network?depth=2` | Additional neighbors without duplicate nodes/edges |
| `/entity/OpenAI/network?depth=2&include_weak=false` | Typed claims after co-mentions are excluded |
| `/connections/new?since=2026-01-01T00:00:00Z` | Newly observed evidence, its source URLs and observation dates |
| `/entities/central?limit=5` | Degree, normalized score, mention count and relation types |

The historical article date is separate from the time this crawl first observed
it. A first ingestion can therefore return old reported relationships as new
observations. Replaying the same URLs should not add source votes:

```shell
python scripts/run_pipeline.py --db data/review.db --from-crawl data/review-crawl.json --strict --report data/review-replay.json
```

Compare the database counts and verify `evidence_added` is zero. The live sample
used during development also retained identical rows across all six tables.

## Inspect one claim

In the network response, select an `affiliated_with` edge and inspect an evidence
record. It gives a source URL, source type, publication date when available,
first and last observation times, exact normalized sentence, rule and body hash.
Check whether the sentence actually supports the person/organization relationship.

The development sample's Sam Altman/OpenAI affiliation came from an explicit
executive-role phrase in Microsoft's partnership post. A co-mention is weaker:
sharing a sentence does not prove affiliation. The API exposes that distinction
instead of assigning an unexplained confidence score.

## Failure cases worth checking

| Symptom | Interpretation and next step |
| --- | --- |
| API returns no central entities | Check that ingestion completed and API/CLI use the same database path |
| Unknown name returns 404 | Inspect central entities or use an existing canonical name/ID |
| A surname returns 409 | Choose a candidate ID; do not force an ambiguous surname merge |
| `since` returns 422 | Supply an ISO timestamp with `Z` or a URL-encoded offset |
| Crawl succeeds but processing fails | Inspect challenge detection, selector matches and normalized body availability |
| A source has DNS/timeout errors | Retry after connectivity recovers; retain the failed-run report |
| Broken YAML or selector configuration | Correct the reported configuration error before crawling |
| A replay has unexpected extra edges after changing aliases/rules | Use a fresh database for the experiment; existing evidence is historical and is not retracted |

The two configuration fixes and their failing-before/passing-after checks are
documented in [bug-fixes.md](bug-fixes.md). Core tests are independent of live
sites:

```shell
python -m pytest -q --basetemp=tmp/reviewer-tests
```

The current implementation does not claim universal extraction accuracy,
independent-source verification, current employment status or true influence.
Review those limits alongside the working pipeline and evidence trail.
