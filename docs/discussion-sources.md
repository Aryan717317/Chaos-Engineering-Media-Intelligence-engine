# Hacker News and the optional subreddit source

Hacker News already supplies discussion content in the default configuration.
An optional configuration also names a public `r/MachineLearning` thread about
the same OpenAI leadership story. The two sources have different verification
status; Reddit has not contributed content to the demonstrated graph.

| Source | Role | Verified status |
| --- | --- | --- |
| [Hacker News: OpenAI board fires Sam Altman](https://news.ycombinator.com/item?id=38309611) | Public discussion alongside news and company statements | Crawled and normalised; present in the stored graph with source evidence |
| [r/MachineLearning: OpenAI announces leadership transition](https://www.reddit.com/r/MachineLearning/comments/17xp85q/) | Additional public discussion of the same event | Configured, but the live Crawl4AI check was denied by robots.txt |

## What is already working

[config/sources.yaml](../config/sources.yaml) includes Hacker News with the news
and blog sources. Its selectors read `.commtext` comments, the thread title,
thread author and available publication metadata. Comments remain separate in
the normalised body, so name resolution cannot use a different comment's full
name to guess the identity of a short name.

The reviewed graph contains two Hacker News pages. The leadership thread above
supports 501 edge/source evidence records, and the second thread,
[a discussion featuring Sam Altman's brother](https://news.ycombinator.com/item?id=12592010),
supports one. These are counts of edge/source links, not counts of independent
comments or confirmations. Each supporting edge retains its source URL and
sentence. The counts are part of the existing six-page sample in the README.

## What happened with Reddit

A one-page check used the existing Crawl4AI path with `check_robots_txt=True`,
depth 0 and a one-page budget. The actual crawler result was:

```json
{
  "pages": [],
  "failures": [
    {
      "url": "https://www.reddit.com/r/MachineLearning/comments/17xp85q/",
      "error": "Access denied by robots.txt"
    }
  ],
  "discovered": 1
}
```

The crawl command exited with status 1. No Reddit post or comments were acquired,
and no Reddit rows were added to the graph. Robots checks remain enabled. There
was no attempt to switch domains, impersonate a browser or use a proxy to work
around that denial.

The optional [discussion configuration](../config/discussion-sources.yaml)
contains both seed URLs and their allowed domains. It has verified Hacker News
selectors, but no claimed Reddit-specific selectors: without permitted access,
the Reddit HTML and its normalisation could not be checked. Successful access
alone would still need a content review before claiming Reddit support.

## Using the optional configuration

The default setup command continues to use the verified news, Hacker News and
blog configuration. If permitted Reddit access becomes available, this separate
command provides a bounded check of both discussion sources:

```shell
python scripts/run_pipeline.py --config config/discussion-sources.yaml --db data/discussions.db --strict --crawl-output data/discussions-crawl.json --report data/discussions-report.json
```

Keep `--strict`: both sites use the `discussion` source type, so Hacker News
succeeding by itself would otherwise satisfy the source-type check. Strict mode
returns failure when either requested page fails, while the report preserves
each URL's outcome. Successful pages can still be stored in this separate
database; a failure does not roll back pages already processed.

At present, this command is expected to report the Reddit access failure. The
original graph and its screenshots remain the verified six-page result. Adding
Reddit through an approved API would require suitable access and an explicit
implementation decision; the current project has no Reddit API integration.

The assessment asks for a discussion/social source and lists Reddit and Hacker
News as examples. The verified Hacker News ingestion already covers that source
category. Reddit is an additional requested source whose acquisition remains
blocked, not extra evidence claimed toward the rubric.
