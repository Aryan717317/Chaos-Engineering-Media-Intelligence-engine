# Media intelligence engine

A one-day backend assessment: crawl real web content, extract entities and typed
relationships, keep a traceable graph in SQLite, and expose three analysis APIs.

Author: Aryan Bharat Kumar.

GitHub: [Aryan717317](https://github.com/Aryan717317) · Student ID: 22BAI71264

The verified six-page crawl produced **705 entities, 554 edges and 581 evidence
links**, with two news articles, two discussion threads and two company blog
posts. All three API endpoints were checked over HTTP against that database.
There are **96 passing deterministic tests**. See [validation](docs/validation.md)
for commands, changed-seed results and limitations, and the
[assessment audit](docs/assessment.md) for requirement coverage.

## Setup

Python 3.11+ is required. Development and verification used Python 3.12.14 on
Windows. Run commands from the repository root. No API keys are required.

```shell
git clone https://github.com/Aryan717317/Chaos-Engineering-Media-Intelligence-engine-.git
cd Chaos-Engineering-Media-Intelligence-engine-
python -m venv .venv
```

Activate the environment in PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

On Linux/macOS, use `source .venv/bin/activate`. If activation is unavailable,
invoke `.venv\Scripts\python.exe` on Windows or `.venv/bin/python` on Unix in
place of `python` in the commands below.

```shell
python -m pip install -r requirements.txt
python -m pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
python -m playwright install chromium
python -m pip check
```

The browser and model require an initial download. Linux hosts may also need
Playwright's browser system dependencies (`python -m playwright install --with-deps chromium`).
Direct Python dependencies and the model version are pinned; transitive packages
are resolved by pip. The application uses Crawl4AI, spaCy, Beautiful Soup,
PyYAML, Pydantic, FastAPI and Uvicorn. Tests use pytest and HTTPX. SQLite access
uses Python's `sqlite3`; the application does not use an ORM, a graph library or
a paid NLP service. Crawl4AI has additional transitive dependencies.

## Run

```shell
python scripts/run_pipeline.py --strict --crawl-output data/crawl.json
python -m uvicorn app.api:app --host 127.0.0.1 --port 8000
```

The first command creates `data/graph.db` and `data/run-summary.json`. The second
serves the existing graph, with interactive API documentation at
[localhost:8000/docs](http://127.0.0.1:8000/docs). Starting the API alone creates
an empty database; it does not crawl or load the NLP model.

Use `--db PATH` for a different pipeline database and `MEDIA_DB_PATH` for the
API. The pipeline also honors `MEDIA_DB_PATH` when `--db` is omitted. Set both
entry points to the same database. In PowerShell:

```powershell
$env:MEDIA_DB_PATH = 'data/experiment.db'
python scripts/run_pipeline.py --strict
python -m uvicorn app.api:app --host 127.0.0.1 --port 8000
```

For crawling alone or debugging extraction from saved real content:

```shell
python scripts/crawl_sources.py --config config/sources.yaml --output data/crawl.json
python scripts/run_pipeline.py --from-crawl data/crawl.json --strict
python -m pytest -q --basetemp=tmp/tests
```

Replay preserves the saved observation times and is labeled `replay` in the
report. It does not count as a new live crawl. No populated database or full
scraped archive is committed; `data/` and temporary test output are ignored.

Pipeline exit codes: `0` means content was processed for every configured source
type; `1` means no usable content, a missing type, or any page failure under
`--strict`; `2` means a configuration, model, file or database failure. Without
strict mode, partial page failures are still listed in the report. The crawl-only
command returns `0` if at least one page was fetched and `1` if none were fetched.

## Configure new sources

[config/sources.yaml](config/sources.yaml) owns all source URLs, crawl limits and
HTML selectors. No source URL is embedded in application logic. The sample
uses historical coverage from The Guardian, Hacker News and Microsoft's blog
because their shared entities make cross-source relationships inspectable.

```yaml
seeds:
  - url: https://example.org/story
    source_type: news
max_depth: 1
max_pages: 6
max_links_per_page: 1
delay_seconds: 1
page_timeout_ms: 45000
allowed_domains: [example.org]
source_rules:
  example.org:
    source_type: news
    body_selector: article
    follow_pattern: '/story'
```

This is a configuration example, not a source of sample graph data. Replace
seeds and whitelist entries together. Plain URL strings are also accepted as
seeds; their type comes from the matching domain rule. Set `source_type` on the
domain rule for discovered pages too. Domains match their subdomains, with the
most specific rule taking precedence. A missing rule defaults to `web`.

Seeds have depth 0 and take priority over discovered links. Canonical URLs remove
tracking parameters and fragments, preserve content queries, and deduplicate
cycles. Page budgets include failed scheduled URLs. Robots checks are delegated
to Crawl4AI. The whitelist controls scheduled links and acceptance of final
redirect URLs; it is not a browser network firewall for redirect hops or assets.

Optional selectors are `body_selector`, `comment_selector`, `title_selector`,
`author_selector` and `published_selector`. Invalid selectors fail before
crawling. Missing matches fall back to article/main/body extraction and log
warnings where applicable. Normalized content always has URL, type, scrape
time, title and body; author/publication date can be null. A missing title falls
back to the URL, and empty/challenge content is rejected. Discussion comments
stay separate, with nested reply text removed from parent blocks. Thread-level
author/date metadata is retained; individual comment authors are not modeled.

[config/topics.yaml](config/topics.yaml) defines phrase-based topics and
[config/aliases.yaml](config/aliases.yaml) defines known canonical names and
handles. Both can change without editing Python. Use a fresh `--db` when comparing
extraction configurations: the existing graph accumulates historical evidence.

## How the graph is built

```text
config -> Crawl4AI -> normalized content -> spaCy + topic phrases
       -> cautious aliases -> sentence rules -> SQLite -> FastAPI
```

```text
app/       contracts, crawl, normalization, extraction, storage, queries, API
config/    source settings, topics and aliases
scripts/   live pipeline and crawl-only commands
tests/     deterministic fixtures and regression tests
docs/      design decisions, real-data checks and assessment audit
```

spaCy supplies people, organizations and locations. Topics use whole-phrase
matches with longer overlapping phrases preferred. NLP processes paragraphs and
comments in bounded batches; long blocks split at whitespace while retaining
body offsets. Topic vocabulary cannot discover arbitrary new themes.

Entity keys use Unicode normalization, case folding, whitespace and punctuation
cleanup. IDs hash the entity type and canonical key. Explicit aliases correct
known NER type mistakes. A person surname expands only if exactly one full
person name in the document supports it. There is no fuzzy or global surname
merge. URLs mistaken for names are discarded. This favors cautious merging but
still cannot distinguish two people sharing a full name and type.

Relationships use adjacent entities in the same sentence, at most 12 intervening
whitespace-separated tokens. They retain the exact supporting sentence, body
offset and rule name. No confidence score is invented.

| Relation | Direction and rule | Main limitation |
| --- | --- | --- |
| `affiliated_with` | Person → organization; employment/joining verbs or explicit role phrases | Historical roles have no end date; complex clauses and NER errors can mislead |
| `responded_to` | Responder → addressed entity; explicit replied/responded-to phrase | Pronouns and structural thread replies are missed |
| `quoted_by` | Quoted entity → quoting entity; active quoted or passive quoted-by phrase | Ordinary quotation attribution using “said” is not inferred |
| `mentioned_with` | Symmetric nearby co-mention when no typed rule matches | Lists, opinions and unrelated actors can produce noise |

Obvious negation, questions and conditional/future words suppress typed claims,
but can still emit weak co-mentions. The guard applies to the whole sentence,
so unrelated uncertainty can suppress a valid relationship. Rules do not cross
comment boundaries, resolve pronouns or establish factual truth.

### Storage and counting

[app/schema.sql](app/schema.sql) defines the graph and provenance explicitly:

| Table | Purpose |
| --- | --- |
| `nodes` | Stable ID, canonical name/type, first observation and mention count |
| `edges` | Typed endpoints, weight, first/last observation |
| `sources` | Canonical URL, source type, latest normalized body and metadata |
| `edge_evidence` | Edge/source linkage, first supporting sentence, timestamps, rule and body hash |
| `node_mentions` | Distinct node/source observations |
| `aliases` | Observed lookup keys and their canonical node IDs |

Edge weight counts **distinct source URLs ever supporting that typed edge**.
Node mention count also counts distinct URLs, not repeated words. Each page is
stored transactionally, with foreign keys and uniqueness constraints. Repeated
crawls update last observation times without adding another source vote. An
older imported snapshot can move the first observation earlier. Source bodies
keep their latest version; evidence retains the earliest citation and its hash.

Observation times are UTC and differ from publication/event times. Historical
evidence is not retracted when a page changes or removes a claim. Distinct URLs
can also be syndicated copies, so weight is not a count of independent witnesses.
See [design details](docs/design.md) for these trade-offs.

## API

All endpoints accept `include_weak=false` to exclude `mentioned_with` edges.

| Request | Behavior |
| --- | --- |
| `GET /entity/{name}/network?depth=2` | Traverse incoming/outgoing links for depth 1 or 2; preserve edge direction and include evidence |
| `GET /connections/new?since=2026-01-01T00:00:00Z` | Return new or significantly growing edges and their endpoint nodes |
| `GET /entities/central?limit=20` | Rank entities by normalized undirected degree; limit 1–100 |

Names can be URL-encoded or replaced with a stable node ID. Unknown names return
404. Ambiguous aliases return 409 with candidate IDs. Invalid depth, limit or
timestamp returns 422. `since` must include a timezone; URL-encode `+` in an
offset, or use `Z`. Empty/future connection windows return an empty graph.

Network JSON contains stable `nodes` and `edges`; edges include `source`,
`target`, `relation`, `weight` and evidence. Depth 2 returns traversed edges,
not additional edges solely between nodes first reached at the outer boundary.
The following is a **field excerpt** from the verified Mira Murati network;
the live response also includes the root entity, timestamps and citations:

```json
{
  "nodes": [
    {"id": "6881f4c331e5ae5890bc6eff", "name": "Mira Murati", "type": "person"},
    {"id": "95a3f7190d6397c1069d3c44", "name": "OpenAI", "type": "organization"}
  ],
  "edges": [
    {
      "id": "68474addbd31049bd4b3017d",
      "source": "6881f4c331e5ae5890bc6eff",
      "target": "95a3f7190d6397c1069d3c44",
      "relation": "affiliated_with",
      "weight": 1
    }
  ]
}
```

### Emerging connections

For each edge, `weight_before` counts source evidence first observed strictly
before `since`; `increase` counts first observations at or after it.

- **New:** baseline is zero and increase is positive.
- **Growing:** baseline is positive, increase is at least 3 URLs, and increase
  is at least 50% of baseline.

Responses include `reason`, `weight_before`, `increase`, `relative_increase`
and the applied thresholds. New edges have a null relative increase because
their baseline is zero. Three additional URLs resist single-page noise; the
50% condition also requires proportional change. This is an explainable
heuristic, not a calibrated significance test. It misses small important
stories and slow growth on established edges. A first crawl of old articles
makes their relationships newly *observed*, not newly occurring events.

### Centrality

`degree_centrality = unique undirected neighbors / (total nodes - 1)`, or zero
when the graph has fewer than two nodes. Multiple relation types/directions
between a pair count as one neighbor. All stored nodes, including isolates,
remain in the denominator when weak edges are filtered. Ties use mention count,
then name and ID. Responses include degree, mention count and relation types.

In the verified graph, OpenAI has 91 neighbors and a score of approximately
0.1293 across 705 nodes. With weak edges excluded, it has 3 neighbors. This
measures connection breadth in the collected graph, not real-world influence;
it misses intermediaries and depends strongly on seeds and extraction quality.

## Assessment reflections

### A. One actual relationship and whether it was correct

The [Microsoft partnership post](https://blogs.microsoft.com/blog/2023/01/23/microsoftandopenaiextendpartnership/)
identifies Sam Altman's executive role at OpenAI. The
`person_role_organization` rule in [relationships.py](app/relationships.py)
recognizes the CEO/of phrase between the person and organization and emits
Sam Altman → `affiliated_with` → OpenAI. That matches what the historical source
reports. It does not establish current employment. SQLite retains the sentence,
rule, source URL, publication date and scrape time so the claim can be checked.

The sample contains 7 distinct affiliation edges and 547 weak co-mention edges.
There were no matched explicit reply or quotation phrases in this crawl; those
rules are tested with deterministic fixtures. The strong/weak imbalance is a
real quality limit, not evidence that all 554 edges are meaningful claims.

### B. A real entity normalization failure

In the [Guardian seed](https://www.theguardian.com/technology/2023/nov/20/sam-altman-openai-exit-ai-microsoft),
spaCy assigned the surname Altman different entity types. Person mentions can
resolve to Sam Altman, while organization/location mentions remain separate.
The [Hacker News thread](https://news.ycombinator.com/item?id=38309611) also
mentions both Sam and Annie Altman, making document-wide surname resolution
ambiguous. `/entity/Altman/network` therefore returns 409 in the verified graph.
OpenAI's configured alias corrects its observed type errors, but adding a global
Altman alias would incorrectly merge unrelated contexts. A useful improvement
is comment-local disambiguation with explicit supporting context.

### C. Suppressing noisy edges at scale

The existing sentence boundary, adjacency limit and distinct-URL counting reduce
document-wide pair explosions and repeated-comment inflation. The API's
`include_weak=false` immediately separates typed claims from the 547 weak edges.
For a larger corpus, group evidence by publisher and content hash before counting
support, and flag edges whose evidence comes from one syndicated story or mostly
generic topic mentions. Review samples by `rule` and source type to measure
precision before changing thresholds. Preserve rejected evidence with a reason
if auditability is needed. Requiring several independent sources improves
precision but hides genuinely new single-source reports; expose that trade-off
instead of treating a higher weight as automatic truth.

### D. Replacing SQLite with Neo4j

The current [queries.py](app/queries.py) handles shallow traversal and simple
counts directly. Neo4j would make variable-length paths, constrained multi-hop
patterns and graph exploration easier as those queries grow. It would require
a separate database service, deployment, driver and an ingestion rewrite,
giving up the current single-file setup and straightforward SQL inspection.
The current provenance, alias ambiguity and temporal counting rules would still
need explicit modeling; switching databases would not fix extraction quality.
The assignment's depth-1/2 queries do not justify that change.

### E. Moving to continuous updates

Start by scheduling the existing command with non-overlapping runs and per-domain
budgets. Add durable crawl checkpoints, bounded retries/backoff and a way to
resume failed URLs. The existing content hash could skip unchanged NLP work,
while observation metadata still advances. Evidence would need versions or
retraction status before presenting the graph as current: today, deleted claims
remain historical edges. Track per-source failures and changes in extraction
volume to detect broken selectors. SQLite WAL supports readers during ingestion,
but writes should remain serialized until measured contention warrants another
store. A queue or distributed workers would need a demonstrated workload first.

## Known limits

This is a bounded English-language take-home implementation. Websites can change,
block automation or time out; selectors and source coverage need inspection.
Sarcasm, pronouns, same-name entities, long clauses and aliases outside the
configured vocabulary remain difficult. Discussion pages retain thread-level
provenance rather than a comment/reply graph. Evidence is historical, centrality
is sample-dependent, and large network/evidence responses have no pagination.
The API is intended for local evaluation; it has no authentication or public
hosting configuration. No extra infrastructure was added for this assignment.
