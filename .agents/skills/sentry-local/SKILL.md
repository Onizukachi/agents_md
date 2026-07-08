---
name: sentry-local
description: Work with the local LevelTravel Sentry instance at sentry.lvtv.me. Use when Codex needs to investigate Sentry issues, event IDs, error spikes, affected projects, tags, releases, stack traces, issue metadata, latest events, or prepare issue handoffs across local Sentry projects; also use for carefully confirmed issue mutations such as status, priority, assignment, or subscription changes.
---

# Sentry Local

## Defaults

Use the local Sentry API through `scripts/sentry_api.py`.

Default connection:

- URL: `https://sentry.lvtv.me`
- organization slug: `sentry`
- token override: `SENTRY_AUTH_TOKEN`
- token file override: `SENTRY_TOKEN_FILE`
- default token file: `~/.config/sentry-local/token`

Never print the token. Prefer the helper script over raw shell snippets because it reads credentials without echoing them.

Before first use, read `references/access.md` to check required Sentry access, token scopes, and local setup.
Read `references/local-config.md` when you need the verified local project inventory, auth notes, or example API paths.

Resolve the helper from the installed skill directory so commands work from any current working directory:

```bash
SENTRY_HELPER="${CODEX_HOME:-$HOME/.codex}/skills/sentry-local/scripts/sentry_api.py"
```

## Quick Start

Check access:

```bash
python3 "$SENTRY_HELPER" projects
```

List recent issues across all accessible projects:

```bash
python3 "$SENTRY_HELPER" issues --limit 20 --query ""
```

Retrieve an issue:

```bash
python3 "$SENTRY_HELPER" issue 62761
```

Retrieve the latest event for an issue:

```bash
python3 "$SENTRY_HELPER" event 62761 latest
```

Call a specific API path:

```bash
python3 "$SENTRY_HELPER" raw GET /api/0/projects/
```

## Investigation Workflow

1. Start from the user's identifier:
   - numeric issue ID: call `issue`, then `event ISSUE_ID latest`;
   - short ID such as `SIDEKIQ-PROD-6P2`: search issues with `--short-id-lookup`;
   - event ID: search likely projects or use the project/event endpoint if project is known;
   - vague spike: list org issues with `project=-1`, absolute time windows, and the user's environment/query.
2. Pull issue-level context: project, status, substatus, priority, count, user count, first/last seen, assignee, tags, releases, activity, owners.
3. Pull event-level context: `metadata`, `tags`, `entries`, exception frames, request data, breadcrumbs, contexts, release, environment, server name, transaction.
4. Summarize with evidence: issue ID, project, timestamps, top tags, failing frame/function/file, release/environment, and a direct Sentry permalink when available.
5. If code ownership is needed, map the project or stack frame to the relevant local repo before proposing a fix.

Use absolute dates and times in user-facing summaries. The local timezone is usually Europe/Moscow, while Sentry event timestamps are UTC unless the API says otherwise.

## Query Guidance

Use Sentry structured search in `--query`, for example:

```bash
python3 "$SENTRY_HELPER" issues --query 'is:unresolved level:error' --limit 50
python3 "$SENTRY_HELPER" issues --project rails-prod --query 'transaction:*Booking*' --limit 20
python3 "$SENTRY_HELPER" issues --query 'release:abc123 environment:production' --sort freq
```

For all projects, omit `--project` or pass `--project -1`. For all statuses, pass an empty query with `--query ""`; otherwise Sentry may apply a default unresolved filter.

## Write Safety

Treat Sentry writes as production-affecting operations.

Before any mutation:

1. Read the issue immediately before writing.
2. Tell the user exactly which issue IDs and fields will change.
3. Get explicit confirmation unless the user already gave a precise mutation command in the same turn.
4. Use the helper with both `--write` and `SENTRY_ALLOW_WRITE=1`.
5. Re-read the changed issue and report the resulting state.

Do not perform destructive actions such as remove, discard, bulk mutate, or bulk remove unless the user explicitly names the operation and target issue set.

Example guarded write:

```bash
SENTRY_ALLOW_WRITE=1 python3 "$SENTRY_HELPER" raw PUT /api/0/organizations/sentry/issues/62761/ --write --data '{"status":"resolved"}'
```
