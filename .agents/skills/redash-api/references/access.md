# Access Requirements

## Summary

- Required access: Redash account access to `https://redash.level.travel` and permission to read the required data sources, including `Replica` for Level Travel replica SQL.
- Local credentials/config: Redash API key stored in `REDASH_API_KEY`, `REDASH_API_KEY_FILE`, or `~/.config/redash-api/api-key`.
- Local tools: `python3`.
- Request from: use the API key from the user's Redash account settings.

## Setup

1. Sign in to Redash.
2. Open account settings and copy the personal API key.
3. Store the key in `~/.config/redash-api/api-key` with restrictive file permissions, or set `REDASH_API_KEY_FILE` to another local key file.
4. Confirm the Redash account has access to the data source required by the task.

## Validation

From the `redash-api` skill directory, run:

```bash
python3 scripts/redash_api.py data-sources --format table
```

Do not print or paste the API key.
