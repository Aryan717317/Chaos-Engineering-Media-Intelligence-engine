# Relationship and identity quality review

The same six real pages from `data/pipeline-live-crawl.json` were reprocessed
with the same spaCy model and new rules. This comparison uses saved content with
original timestamps, not a new live crawl. Separate databases avoid mixing old,
unretracted extraction results with the revised graph. No library, architecture
or schema change was needed; spaCy's existing dependency parse is now retained
and used in relationship extraction.

## Before and after

| Measure | Original | Improved |
| --- | ---: | ---: |
| Source pages | 6 | 6 |
| Canonical entities | 705 | 716 |
| Distinct edges | 554 | 557 |
| Typed affiliation edges | 7 | 22 |
| Weak co-mention edges | 547 | 535 |
| Edge/source evidence records | 581 | 586 |
| Deterministic tests | 96 | 125 |

The entity count rises because the revised resolver declines unsupported
cross-comment merges. More or fewer nodes alone does not establish quality.
Likewise, 22 typed edges is not a precision score. Most graph edges remain weak.
No reply or quotation phrases matched this sample; their parser behavior is
tested using hand-annotated dependency fixtures without a model download.

## Relationships recovered and checked

The resulting typed edges were inspected against their stored supporting text.
These are interpretations of source claims, not independent fact checks.

| Source | Recovered relationship | Why the previous rule missed it |
| --- | --- | --- |
| [Guardian leadership report](https://www.theguardian.com/technology/2023/nov/20/sam-altman-openai-exit-ai-microsoft) | Sam Altman and Greg Brockman each affiliated with Microsoft | An employer is the subject of hiring; two people are coordinated objects, and both surnames had incorrect NER types |
| Same Guardian report | Emmett Shear affiliated with OpenAI | Appointment by a named organization's board needs argument binding |
| Same Guardian report | Jason Kwon and Ilya Sutskever affiliated with OpenAI | Additional executive/scientist role forms; unrelated later uncertainty previously suppressed a role |
| [Guardian earlier article](https://www.theguardian.com/technology/2023/nov/17/openai-ceo-sam-altman-fired) | Sam Altman and Mira Murati affiliated with OpenAI | Established role appositives were suppressed by negation/future wording elsewhere in the sentence |
| [Hacker News discussion](https://news.ycombinator.com/item?id=38309611) | Named founders affiliated with OpenAI | Passive founding plus a coordinated list of names |

Several founding edges originate in one quoted list in one comment. That adds
relationship coverage, not independent corroboration. An unresolved Sam/Stanford
edge also remains: its workplace wording is explicit but the person's full
identity is not established in that comment. Historical employment, departure
and firing all express association; the API does not claim current employment.

The first candidate replay exposed defects which were corrected before adopting
the new graph:

- A request to make Elon Musk a future CEO was incorrectly treated as an existing
  role. Request and future-role guards now suppress it.
- A comment explicitly labeled as a prediction produced an appointment edge.
  Prediction/speculation labels now suppress typed claims for that comment.
- A bare LLC fragment was treated as a named organization. Generic corporate
  suffixes are now discarded unless explicitly configured as an entity.

The stored sentence, offsets and extraction rule remain available for every edge.
Dependency rules bind named subjects/objects and passive agents, handle coordinated
people, and reject negation, modals and denial/planning context. Narrow phrase
rules remain as a supplement. The weak fallback does not duplicate a typed pair
within the same sentence.

## Name resolution, including Elon Musk

Six reviewed news mentions previously labeled organizations now resolve to the
appropriate person: five Altman occurrences and one Brockman occurrence across
the two Guardian articles. Guards require a unique full-name candidate and
human context before overriding a type. Explicit places and configured
organizations are protected. Other ambiguous labels remain unresolved.

Within discussions, only the same comment supplies short-name context. Reviewed
examples now connect short Sam references to Sam Altman and an Elon reference
to Elon Musk where the comment supplies the full name. A standalone Musk comment
without a full-name anchor is left unresolved. Malformed model spans, including
Will Sam and a span combining a name with a handle and another name, cannot
guide contextual merges. Such bad NER output is still an underlying model limit.

| Input / context | Expected behavior |
| --- | --- |
| Elon Musk and @elonmusk | Same configured canonical person |
| Musk in a comment identifying only Elon Musk | Same canonical person |
| Musk with both Elon and Kimbal as candidates | Remains unresolved |
| Musk in a different comment with no full-name anchor | Remains unresolved |
| Full name appears but configured handle does not | Handle still works for API lookup; no extra mention is counted |

Configured multiword aliases also cannot span two separate comments; a regression
test verifies that boundary. The first three forms are verified in both resolver
and API tests. In the actual
graph, `Elon Musk` and `@elonmusk` return node `4722d966e1a7f0e0af87fc39`.
`Musk` returns 409 because both the resolved person and an unresolved surname are
present. The correct response to that ambiguity is a candidate ID, not a global
Musk alias. Y Combinator's observed hyphenated/unspaced forms also share its
configured identity.

Elon Musk has 14 weak direct connections in this sample and no retained typed
affiliation. The misleading future-CEO request was rejected rather than used to
make that example look more connected.

## Reproduce and inspect

```shell
python -m pytest -q --basetemp=tmp/quality-tests
python scripts/run_pipeline.py --db data/graph-quality-final.db --from-crawl data/pipeline-live-crawl.json --strict --report data/quality-final-report.json
```

The saved crawl is a local artifact from the original live validation. On a
fresh clone, first run the live command with `--crawl-output`; current website
content may produce different counts. Use a new database when comparing rules,
because normal ingestion preserves previously observed evidence.

The final replay processed all six pages with no failures. SQLite integrity,
foreign keys and evidence weights were checked. A second replay added no new
evidence and retained identical table rows. The local API's default database was
refreshed from this reviewed graph after preserving the previous database.

Useful requests against the improved graph:

| Request | Observed result |
| --- | --- |
| `/entity/OpenAI/network?depth=1&include_weak=false` | 15 nodes, 14 typed edges |
| `/entity/OpenAI/network?depth=2&include_weak=false` | 17 nodes, 17 typed edges |
| `/entity/Sam%20Altman/network?depth=1&include_weak=false` | 4 nodes, 3 typed edges |
| `/entity/Elon%20Musk/network?depth=1` | 15 nodes, 14 weak edges |
| `/entity/%40elonmusk/network?depth=1` | Same root ID and graph as Elon Musk |
| `/connections/new?since=2026-01-01T00:00:00Z&include_weak=false` | 22 newly observed typed edges |

This is a focused, manually inspected improvement on six pages, not a held-out
accuracy benchmark. Parser mistakes, long-clause ambiguity, unresolved people,
implicit relationships and unseen expressions still limit quality.
