---
name: yandex-wiki
description: Read and inspect corporate Yandex Wiki pages through the Yandex Wiki API. Use when Codex needs to find, list, retrieve, export, or summarize internal Wiki articles, Яндекс.Вики pages, page slugs, descendants, breadcrumbs, metadata, or content using OAuth or IAM-token authentication.
---

# Yandex Wiki

## Quick Start

Before first use, read `references/access.md` to check Yandex Wiki access, IAM token, OAuth, organization ID, and local CLI requirements.

Use the installed helper for API calls instead of hand-writing `curl` so credentials are not echoed accidentally. Resolve it from the global Codex skills directory:

```bash
WIKI_HELPER="${CODEX_HOME:-$HOME/.codex}/skills/yandex-wiki/scripts/wiki.py"
```

For a federated account with Yandex Cloud CLI access, configure read-only Wiki access like this:

```bash
python3 "$WIKI_HELPER" setup \
  --org-id '<organization-id>' \
  --auth-type Bearer \
  --org-header X-Org-Id \
  --refresh-iam
```

This stores non-secret config in `~/.yandex-wiki.env` with mode `0600`. IAM tokens are short-lived and are created with `yc iam create-token`; the helper refreshes the local token file when `YANDEX_WIKI_REFRESH_IAM=1`.

Check non-secret effective config:

```bash
python3 "$WIKI_HELPER" config
```

Validate API access:

```bash
python3 "$WIKI_HELPER" descendants --slug '' --include-self --limit 20
```

Read `references/api.md` when the task needs exact endpoint behavior, field names, pagination, content retrieval, or troubleshooting.

## Common Tasks

### List Pages

List descendants under a slug:

```bash
python3 "$WIKI_HELPER" descendants --slug content --limit 100
```

Use `--slug '' --include-self` to start from the Wiki root. Results are paginated; the helper follows `next_cursor` until `--limit`.

### Read A Page

Fetch page metadata and common readable fields:

```bash
python3 "$WIKI_HELPER" page content/content-tools
```

Fetch only content:

```bash
python3 "$WIKI_HELPER" page content/content-tools --content-only
```

Use `--raw` when a task needs the full API response:

```bash
python3 "$WIKI_HELPER" page content/content-tools --raw
```

### Export A Page Set

Export page details for a subtree to JSONL:

```bash
python3 "$WIKI_HELPER" export --slug content --limit 200 --output work/wiki-content.jsonl
```

Use `--no-content` if only IDs, slugs, titles, page types, breadcrumbs, and attributes are needed.

### Call A Read-Only Endpoint

Use `raw` only for GET requests:

```bash
python3 "$WIKI_HELPER" raw /pages --query slug=content/content-tools --query fields=content,attributes
```

Do not use this skill for writes. It is intentionally read-only even if the token has broader permissions.

## Reporting Guidance

When answering from Wiki:

1. Cite page `slug`, title, and page type for each important source page.
2. Distinguish exact page content from inference or synthesis across pages.
3. Mention if content is missing because the API response lacks `content`, the page is a grid/template, or permissions block the page.
4. Avoid exposing access lists, owner details, or raw internal identifiers unless the user asks for access diagnostics.

Use absolute dates in summaries when comparing `created_at` or `modified_at`.
