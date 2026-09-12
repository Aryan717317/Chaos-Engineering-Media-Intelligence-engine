"""One orchestration path from raw pages to a traceable SQLite graph."""

import logging
from collections import Counter

from pydantic import BaseModel, Field

from app.config import CrawlConfig
from app.crawler import RawPage
from app.entities import AliasDefinition, resolve_entities
from app.extract import analyze
from app.normalize import normalize
from app.relationships import extract_relationships
from app.storage import initialize, upsert_item

logger = logging.getLogger(__name__)


class PipelineSummary(BaseModel):
    processed: int = 0
    entities: int = 0
    relationships: int = 0
    evidence_added: int = 0
    source_types: dict[str, int] = Field(default_factory=dict)
    failures: list[dict[str, str]] = Field(default_factory=list)


def process_pages(pages: list[RawPage], config: CrawlConfig, database: str, nlp,
                  topics: dict[str, list[str]], aliases: list[AliasDefinition]) -> PipelineSummary:
    initialize(database)
    summary = PipelineSummary()
    types = Counter()
    for page in pages:
        try:
            item = normalize(page, config.rule_for(page.source_url))
        except ValueError as exc:
            summary.failures.append({"url": page.source_url, "stage": "normalization", "error": str(exc)})
            logger.warning("Normalization failed %s: %s", page.source_url, exc)
            continue
        try:
            analysis = analyze(item.body, nlp, topics)
            entities, mentions = resolve_entities(item.body, analysis.mentions, aliases, source_type=item.source_type)
            relationships = extract_relationships(item.body, analysis.sentences, mentions)
        except ValueError as exc:
            summary.failures.append({"url": page.source_url, "stage": "extraction", "error": str(exc)})
            logger.warning("Extraction failed %s: %s", page.source_url, exc)
            continue
        # A storage failure invalidates the run; do not report a healthy partial graph.
        counts = upsert_item(database, item, entities, relationships)
        summary.processed += 1
        summary.entities += len(entities)
        summary.relationships += len(relationships)
        summary.evidence_added += counts["evidence_added"]
        types[item.source_type] += 1
        logger.info("Processed %s type=%s entities=%d relationships=%d new_evidence=%d",
                    item.source_url, item.source_type, len(entities), len(relationships), counts["evidence_added"])
    summary.source_types = dict(sorted(types.items()))
    return summary
