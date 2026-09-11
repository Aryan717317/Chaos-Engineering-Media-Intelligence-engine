# Live crawl check

Ran `python scripts/crawl_sources.py --output data/crawl-verified.json` during
the crawling phase on 2026-09-11. All six scheduled URLs returned real content:
two news pages, two discussion pages and two company blog posts, at depths 0/1.
The three seed pages contained a roughly 6,300-character news body, 2,530
discussion comments (roughly 575,600 characters), and a 3,300-character blog body.
The raw output is local and ignored by Git.

The initial Ars Technica seed returned a short JavaScript verification page,
despite a successful crawler response. It was replaced in configuration with
a Guardian article. This is why the normalization stage also needs an explicit
empty/challenge-page check; HTTP/crawler success alone does not prove content.

The initial broad discussion crawl also reached account actions blocked by
robots.txt. Optional per-domain follow patterns and a per-page link budget now
keep this sample focused. No domain or source URL is embedded in Python code.
The crawler delegates robots checks to Crawl4AI and logs denied pages.

At this phase, 21 deterministic tests pass for contracts, configuration,
whitelist boundaries, cycles, limits, redirects and failure isolation. Full
normalization/extraction and graph validation follow in later phases.
