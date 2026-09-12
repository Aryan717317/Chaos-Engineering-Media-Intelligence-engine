# Extraction checks on real crawled content

## Phase 4: raw entity recognition

The installed `en_core_web_sm` 3.8.0 model processed all six normalized pages.
No remote NLP API was used. The raw annotations stay in `data/analysis.json`.

| Source | Sentences | People | Organizations | Locations | Topics |
| --- | ---: | ---: | ---: | ---: | ---: |
| Guardian seed | 43 | 33 | 36 | 11 | 10 |
| Hacker News seed | 6,689 | 1,181 | 1,208 | 450 | 404 |
| Microsoft partnership | 19 | 4 | 22 | 2 | 21 |
| Guardian linked page | 44 | 22 | 23 | 14 | 9 |
| Hacker News linked page | 26 | 3 | 0 | 3 | 0 |
| Microsoft M12 | 46 | 2 | 31 | 0 | 6 |

These are raw mention counts, not a quality score or the graph's document-level
mention_count. Every mention and sentence was checked against its character
offset in the normalized body. Blocks are processed in batches of eight, with
a 50,000-character ceiling per block. Splitting a very long comment can lose a
relationship across that artificial boundary; text itself is retained.

The Microsoft partnership page shows `OpenAI` classified as location, person
and organization in different sentences. The Guardian and Hacker News pages
also show inconsistent types for `Altman`. These observed failures motivate
explicit canonical types for known aliases. They do not justify globally
guessing a type for every ambiguous name.

Topic detection is a phrase vocabulary in `config/topics.yaml`, with word
boundaries and preference for longer overlapping phrases. It cannot discover
arbitrary themes, and terms such as alignment can be used outside AI contexts.

## Phase 5: canonical entities

Known OpenAI mentions now become one organization ID even when the model gives
them different types. Microsoft and configured handles use the same mechanism.
The real Hacker News thread also contains multiple surface forms that resolve
to Elon Musk. Canonical identities include the entity type and are independent
of insertion order, case and repeated whitespace. Raw URLs misclassified as
names are filtered after a real-data inspection revealed this failure.

A concrete remaining failure is `Altman` in the Guardian seed. Its person
mentions can map to Sam Altman, but the same surface labeled organization or
location still becomes separate nodes. We deliberately do not assume an
organization sharing a surname is a person. The long Hacker News thread also
mentions both Sam and Annie Altman, so its standalone person surname is
ambiguous and remains unresolved. Document-wide surname matching loses recall
on large threads; comment-local evidence would be a useful next improvement.

The initial check found 30/698/8/29/4/15 canonical entities across the six pages,
before the raw-URL filter. These counts are diagnostic, not ground-truth counts.
Aliases are explicit and versioned in `config/aliases.yaml`; conflicting aliases
fail validation rather than letting file order choose an identity.
