# Access Requirements

## Summary

- Required access: Boundary access to the read-only Elasticsearch MCP targets for `k8s-core`, `k8s-integrations`, and `k8s-dynamic`, depending on which profile is used.
- Local credentials/config: existing local Boundary authentication/cache; optional `LVTV_LOGS_BOUNDARY_CONFIG` or `~/.config/lvtv-elastic-logs/boundary.json` for target overrides.
- Local tools: `python3`; Boundary CLI available in `PATH` or configured through `LVTV_LOGS_BOUNDARY_BIN`.
- Request from: Level Travel DevOps.

## Setup

1. Ensure Boundary CLI is installed and authenticated locally.
2. Ensure the needed read-only Elasticsearch MCP targets are visible in the local Boundary cache.
3. Optionally create `~/.config/lvtv-elastic-logs/boundary.json` when target ids, ports, or Boundary address must differ from defaults.
4. Do not create or store Elasticsearch MCP tokens for this skill.

## Validation

From the `lvtv-elastic-logs` skill directory, run a safe index discovery:

```bash
python3 scripts/mcp_call.py --profile main list_indices '{"index_pattern":"*gateway*"}'
```

If access is missing or stale, the helper should fail with a Boundary or tunnel error without printing secrets.
