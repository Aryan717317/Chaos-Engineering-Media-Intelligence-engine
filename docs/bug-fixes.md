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
