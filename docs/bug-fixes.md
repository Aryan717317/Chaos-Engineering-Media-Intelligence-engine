# Bugs reproduced during final validation

These are defects found in the implementation, not deliberately introduced
failures. Regression tests run without live websites.

## Invalid source configuration

Before the fix, a null or numeric `seeds` value raised an uncaught `TypeError`.
An uppercase domain in `source_rules` silently selected the generic `web` rule,
even though the whitelist already normalized uppercase domains. Invalid CSS
selectors passed configuration validation and failed later during extraction.

The new tests reproduced eight failures before the fix. Configuration now
validates list shape and selectors before opening a browser, normalizes both
domain maps consistently, and rejects duplicate normalized rules and blank
source types. Selector validation uses the existing Beautiful Soup/Soup Sieve
parser. No dependency or architecture change was needed.

Reproduce the regression checks with:

```shell
python -m pytest tests/test_crawler.py -q
```

## Malformed YAML escaped command error handling

A missing closing bracket in any of the three configuration files raised
`yaml.ParserError`, which was outside the command's existing exception list.
All three regression cases failed before the fix. Both commands now handle
`yaml.YAMLError` and return exit code 2 with the parser's error location.
Page failures still return 1 under strict mode; SQLite failures still invalidate
the run. Tests also verify that an extraction failure on one page does not
discard subsequent valid pages.

```shell
python -m pytest tests/test_pipeline.py -q
```
