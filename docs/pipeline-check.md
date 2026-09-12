# Connected pipeline check

Ran the actual command with live public URLs:

```sh
python scripts/run_pipeline.py --db data/graph.db --strict --crawl-output data/pipeline-live-crawl.json --report data/pipeline-live-report.json
```

All six scheduled pages were fetched and processed, with zero crawl or
processing failures. Each source type contributed two pages. The resulting
database has six sources, 705 nodes, 554 edges and 581 source-evidence links.
The complete test suite passes 69 tests at this stage.

The report distinguishes successful crawling from successful processing,
lists failed URLs/stages, reports source coverage, and records final database
counts. A missing source type fails the run; `--strict` also fails for any
individual page failure. Configuration, missing model and database failures
exit clearly. The pipeline does not replace failed extraction with fake data.

Saved Crawl4AI output can be replayed with `--from-crawl PATH`. Replay preserves
original observation timestamps and is labeled `replay` in the report. It is
useful for extraction debugging; a saved crawl is not a new live crawl.
Databases, full page bodies and run artifacts remain under ignored `data/`.

The API phases follow this check. This establishes crawl -> normalization ->
extraction -> SQLite; the final validation phase verifies all three endpoints
against a live-run database and a changed seed list.
