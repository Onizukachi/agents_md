---
name: redash-api
description: Access Level Travel Redash through its HTTP API. Use when Codex needs to list Redash data sources, find or inspect saved Redash queries, run saved Redash queries with parameters, execute read-only ad-hoc SQL through Redash, poll query jobs, fetch query results, or summarize Redash API output. The default Redash host is redash.level.travel and credentials come from REDASH_API_KEY, REDASH_API_KEY_FILE, or ~/.config/redash-api/api-key.
---

# Redash API

## Defaults

Before first use, read `references/access.md` to check Redash API key and data source access requirements.

- Use `https://redash.level.travel` unless the user explicitly gives another Redash host.
- Read the API key from `REDASH_API_KEY` or `REDASH_API_KEY_FILE`. If neither is set, the helper reads `~/.config/redash-api/api-key`.
- Never print, quote, log, or place the API key in a command line. Prefer the bundled script, which sends it via `Authorization: Key ...`.
- Treat Redash as a live company data system. Run only the requested query and avoid broad exploratory queries unless the user asks for them.

## Quick Start

Prefer `scripts/redash_api.py` for API calls:

```bash
python3 scripts/redash_api.py data-sources
python3 scripts/redash_api.py queries --search "bookings"
python3 scripts/redash_api.py get-query 123
python3 scripts/redash_api.py run-query 123 --param country=TR --format table
python3 scripts/redash_api.py replica --query-file query.sql --format table
python3 scripts/redash_api.py adhoc --data-source-id 7 --query-file query.sql --format json
```

Run commands from the `redash-api` skill directory, or resolve `scripts/redash_api.py` relative to the installed skill location. Use `--help` on the script or any subcommand for the exact options. Use environment variables only when needed:

- `REDASH_BASE_URL` overrides the Redash host.
- `REDASH_API_KEY_FILE` overrides the key file path.
- `REDASH_API_KEY` overrides file-based credentials. Do not echo this value.

## Workflow

1. If the user names a saved query or dashboard but not an ID, search saved queries with `queries --search`.
2. If the query requires parameters, inspect it with `get-query` and ask only for missing required values.
3. Run saved queries with `run-query <id>` and `--param key=value` pairs.
4. For ad-hoc SQL, use `adhoc --data-source-id <id> --query-file <file>`. Keep SQL read-only unless the user explicitly authorizes mutation.
5. Summarize results in chat. Do not paste huge result sets; save large outputs under the current workspace `outputs/` directory when a file deliverable is useful.

## Level Travel Replica

- Use `replica` for ad-hoc read-only SQL against the Level Travel project database replica.
- The Redash data source is `Replica`, id `4`, type `mysql`.
- Redash connects to database `leveltravel_views`; project tables are exposed mostly as MySQL `VIEW` objects with the same names.
- Treat it as a production replica: prefer `SELECT`, add `LIMIT` while exploring, and avoid heavy full-table scans unless the user explicitly asks for a broad aggregate.
- Before writing SQL, inspect the local Rails project if available. Prefer the path in `LEVELTRAVEL_REPO`; otherwise ask for the checkout path. Start with `db/schema.rb` for table/column/index names and use `app/models/` when associations or business names are unclear.
- To discover available objects, query `information_schema.tables` with `table_schema = DATABASE()`.
- To discover columns for one object, query `information_schema.columns` with `table_schema = DATABASE()` and `table_name = '<name>'`.

## Parameter Handling

- Pass each Redash parameter as `--param name=value`.
- For numeric and boolean parameters, the script keeps simple JSON types where possible.
- For dates and strings, pass the literal value expected by the Redash query.
- For many parameters or complex values, create a JSON file and pass `--params-file params.json`.

## References

Read `references/redash-api.md` if endpoint behavior, job states, or result shapes need clarification.
