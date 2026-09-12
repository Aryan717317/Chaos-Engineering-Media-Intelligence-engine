# Normalization check

The six real pages in `data/crawl-verified.json` were normalized successfully.
The output `data/normalized.json` stays local; the complete article/comment text
is not distributed in this repository.

| Source | Body characters | Text blocks | Author available | Publication date available |
| --- | ---: | ---: | --- | --- |
| Guardian seed | 6,044 | 22 | yes | yes |
| Hacker News seed | 580,342 | 2,530 | yes | yes |
| Microsoft partnership blog | 3,371 | 11 | yes | yes |
| Guardian linked article | 5,503 | 25 | yes | yes |
| Hacker News linked discussion | 1,989 | 6 | yes | yes |
| Microsoft M12 blog | 7,220 | 21 | yes | yes |

Counts refer to the initial normalization check; whitespace handling can change
slightly as parsing improves. Discussion blocks preserve comment separation.
Thread-level author/date describe the thread, not every individual commenter.
Reply structure is flattened; the extractor must not infer reply relationships
from adjacency between comments. Nested reply text is emitted once.

Nine normalization tests cover news JSON-LD, company blog selectors, discussion
metadata and boundaries, nested replies, missing fields, unexpected structures,
malformed dates/JSON-LD, empty pages and recognizable verification pages.
The full suite has 30 tests at the end of this phase.

Phase 3 was split into configuration, normalization, tests, nested-reply handling,
and this real-data check. No architecture or dependency changes were needed.
