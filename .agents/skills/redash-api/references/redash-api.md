# Redash API Reference

## Authentication

Use an API key in the request header:

```text
Authorization: Key <api-key>
```

Do not put the key in URLs because URLs are more likely to appear in logs, shell history, and error output.

## Common Endpoints

- `GET /api/data_sources`: list data sources the key can access.
- `GET /api/queries?q=<text>`: search saved queries.
- `GET /api/queries/<query_id>`: inspect a saved query, including SQL text and options.
- `POST /api/queries/<query_id>/results`: run or fetch a saved query result. Body commonly includes `parameters` and `max_age`.
- `POST /api/query_results`: execute an ad-hoc query. Body includes `data_source_id`, `query`, `parameters`, and `max_age`.
- `GET /api/jobs/<job_id>`: poll asynchronous query execution.
- `GET /api/query_results/<query_result_id>.json`: fetch a completed result as JSON.
- `GET /api/query_results/<query_result_id>.csv`: fetch a completed result as CSV.

## Level Travel Replica

The Level Travel project replica is available as Redash data source `Replica`:

- id: `4`
- type: `mysql`
- database: `leveltravel_views`
- helper command from the `redash-api` skill directory: `python3 scripts/redash_api.py replica --query-file query.sql`

Use the local Level Travel Rails project as the schema reference when available. Prefer the path in `LEVELTRAVEL_REPO`; otherwise ask for the checkout path. Start with `db/schema.rb`, then inspect `app/models/` for associations and domain names.

The replica exposes project tables mostly as MySQL views. Useful discovery queries:

```sql
SELECT table_name, table_type
FROM information_schema.tables
WHERE table_schema = DATABASE()
ORDER BY table_name
LIMIT 50;
```

```sql
SELECT column_name, column_type, is_nullable, column_key
FROM information_schema.columns
WHERE table_schema = DATABASE()
  AND table_name = 'orders'
ORDER BY ordinal_position;
```

## Job States

Redash jobs are asynchronous. Common numeric states:

- `1`: pending
- `2`: started
- `3`: success
- `4`: failure
- `5`: cancelled

On success, the job payload normally contains a `query_result_id`. Fetch the result from `/api/query_results/<id>.json` or `.csv`.

## Result Shape

JSON query results usually contain:

```json
{
  "query_result": {
    "id": 123,
    "data": {
      "columns": [{"name": "column_name", "type": "string"}],
      "rows": [{"column_name": "value"}]
    }
  }
}
```

Saved query list responses may be either a JSON array or an object with a `results` array, depending on the Redash version and pagination.
