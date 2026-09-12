# Media intelligence engine

A one-day backend assessment: crawl real web content, extract entities and typed
relationships, keep a traceable graph in SQLite, and expose three analysis APIs.

Author: Aryan Bharat Kumar.

GitHub: [Aryan717317](https://github.com/Aryan717317) · Student ID: 22BAI71264

Reprocessing the verified six-page crawl with the improved extraction produced
**716 entities, 557 edges and 586 evidence links**, including **22 typed
affiliations** (up from 7). The pages include two news articles, two discussion
threads and two company blog posts. There are **125 passing deterministic tests**.
See the [quality comparison](docs/quality-review.md), [initial validation](docs/validation.md)
for changed-seed and setup results, and the
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
known NER type mistakes. First names and surnames use a unique full name in the
same paragraph/comment. Narrative sources can also use a unique document-wide
surname; discussions cannot borrow evidence from unrelated comments. Overriding
a surname's incorrect organization/location label requires human context, with
guards for explicit places and configured organizations. Malformed full-name
spans cannot guide other names. URLs and standalone company suffixes are filtered.
There is no fuzzy matching, and same-full-name people remain a limitation.

### Entity example: Elon Musk

In a comment containing `Elon Musk spoke. Musk replied as @elonmusk.`, all three
forms resolve to one person node. This is an illustrative regression fixture,
not a quotation from the crawl. The full name supplies context for the surname;
the handle is explicitly configured. Tests cover the ambiguous case with both
Elon and Kimbal Musk and a separate comment containing only Musk.

The actual reprocessed graph resolves `Elon Musk` and `@elonmusk` to
`4722d966e1a7f0e0af87fc39`. Configured lookup aliases work even when a page uses
only the full name; they do not add mention counts. The graph also retains an
unresolved Musk mention, so `/entity/Musk/network` returns 409 with candidates.
This avoids claiming a confident identity without sufficient context. Use the
full name or stable ID for the [Elon Musk network](http://127.0.0.1:8000/entity/Elon%20Musk/network?depth=1).

Typed relationships use spaCy's existing dependency parse to bind named subjects,
objects, coordinated people, passive agents and explicit roles within one
sentence. Narrow phrase rules supplement the parse. The weak fallback uses only
adjacent mentions with at most 12 intervening whitespace-separated tokens, and
does not duplicate a typed pair in that sentence. Evidence retains the exact
sentence, body offset and rule name. No confidence score is invented.

| Relation | Direction and rule | Main limitation |
| --- | --- | --- |
| `affiliated_with` | Person → organization; hiring, employment, founding, joining, leaving/dismissal or explicit roles | Reports historical association, not current employment; parsing/NER errors remain |
| `responded_to` | Named responder → addressed entity; reply/respond predicate with a named target | Pronouns and structural thread replies are missed |
| `quoted_by` | Quoted entity → quoting entity; active/passive quote predicate, including coordinated names | Ordinary quotation attribution using “said” is not inferred |
| `mentioned_with` | Symmetric nearby co-mention when no typed rule matches | Lists, opinions and unrelated actors can produce noise |

Negation, modal/conditional wording and denial/planning ancestors suppress
predicate claims. Explicit role appositives can survive uncertainty in a later
clause. Comments labeled as predictions/speculation and requests beginning with
“please” do not produce typed claims. Rejected assertions can still be weak
co-mentions. These guards are conservative heuristics, not complete linguistic
scope resolution. Rules do not cross comments, resolve pronouns or establish truth.

### Storage and counting

[app/schema.sql](app/schema.sql) defines the graph and provenance explicitly:

| Table | Purpose |
| --- | --- |
| `nodes` | Stable ID, canonical name/type, first observation and mention count |
| `edges` | Typed endpoints, weight, first/last observation |
| `sources` | Canonical URL, source type, latest normalized body and metadata |
| `edge_evidence` | Edge/source linkage, first supporting sentence, timestamps, rule and body hash |
| `node_mentions` | Distinct node/source observations |
| `aliases` | Configured and observed lookup keys and their canonical node IDs |

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
      "weight": 2
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

In the improved graph, OpenAI has 97 neighbors and a score of approximately
0.1357 across 716 nodes. With weak edges excluded, it has 14 neighbors. This
measures connection breadth in the collected graph, not real-world influence;
it misses intermediaries and depends strongly on seeds and extraction quality.

## Assessment reflections

### A. One actual relationship and whether it was correct

The [Microsoft partnership post](https://blogs.microsoft.com/blog/2023/01/23/microsoftandopenaiextendpartnership/)
identifies Sam Altman's executive role at OpenAI. The
`dependency_role` rule in [relationships.py](app/relationships.py)
binds the executive-role phrase to the person and organization and emits
Sam Altman → `affiliated_with` → OpenAI. That matches what the historical source
reports. It does not establish current employment. SQLite retains the sentence,
rule, source URL, publication date and scrape time so the claim can be checked.

The improved sample contains 22 distinct affiliation edges and 535 weak
co-mention edges. The Guardian hiring statement now yields both Sam Altman →
Microsoft and Greg Brockman → Microsoft. Newly recovered founding relationships
also include several people listed together in one discussion comment, so these
are not independent confirmations. No explicit reply or quotation phrases
matched this crawl; those rules have deterministic tests. Most edges are still
weak, and the increased typed count is not an accuracy score.

### B. A real entity normalization failure

In the [Guardian seed](https://www.theguardian.com/technology/2023/nov/20/sam-altman-openai-exit-ai-microsoft),
spaCy assigned the surname Altman different entity types. The original resolver
left organization/location mentions separate. Context guards now correct six
reviewed surname-type errors across the two news articles, including both people
in the Microsoft hiring statement. Other unsupported type errors remain separate.
The [Hacker News thread](https://news.ycombinator.com/item?id=38309611) also
mentions both Sam and Annie Altman. Comment-local matching can resolve a short
name when that comment identifies it, without using a different reply as evidence.
`/entity/Altman/network` still returns 409 in the improved graph.
OpenAI's configured alias corrects its observed type errors, but adding a global
Altman alias would incorrectly merge unrelated contexts. During review, malformed
NER spans such as Will Sam incorrectly attracted short names; these spans are now
excluded from contextual matching. Better coreference and NER remain future work.

### C. Suppressing noisy edges at scale

The existing sentence boundary, weak-pair adjacency limit, named dependency
arguments and distinct-URL counting reduce document-wide pair explosions and
repeated-comment inflation. The API's `include_weak=false` separates typed claims
from the 535 weak edges. Actual review caught a request to make Elon Musk CEO
being treated as an affiliation; request/prediction guards now reject that claim.
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
