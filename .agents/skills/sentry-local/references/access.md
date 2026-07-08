# Access Requirements

## Summary

- Required access: LevelTravel local Sentry account with organization/project/event permissions for the requested operation.
- Local credentials/config: Sentry API token in `SENTRY_AUTH_TOKEN` or in a file referenced by `SENTRY_TOKEN_FILE`.
- Local tools: `python3`.
- Request from: Level Travel DevOps.

## Token Scopes

For read-only investigation, request an internal integration token or equivalent token with:

- Organization: Read
- Project: Read
- Event: Read
- Team: Read, if owner/team context is needed
- Member: Read, if assignee/member context is needed

For issue mutations such as status, priority, assignment, or subscription changes, also request:

- Event: Write

Do not request admin scopes unless the task explicitly needs destructive or administrative Sentry operations.

## Obtaining a Token

Ask Level Travel DevOps for a Sentry API token for `https://sentry.lvtv.me`.
Include whether the token should be read-only or should also allow issue mutations.

## Setup

1. Create a local token file:

```bash
mkdir -p ~/.config/sentry-local
chmod 700 ~/.config/sentry-local
printf '%s\n' '<sentry-token>' > ~/.config/sentry-local/token
chmod 600 ~/.config/sentry-local/token
```

2. Or point the helper at an existing token file:

```bash
export SENTRY_TOKEN_FILE=/path/to/token-file
```

3. Override defaults only when needed:

```bash
export SENTRY_URL=https://sentry.lvtv.me
export SENTRY_ORG=sentry
```

## Validation

From the installed skill directory, run:

```bash
python3 scripts/sentry_api.py projects
python3 scripts/sentry_api.py issues --limit 5 --query ""
```

The token is valid when project and issue reads return JSON. Do not print or paste stored tokens.
