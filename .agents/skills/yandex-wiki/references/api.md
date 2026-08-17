# Yandex Wiki API Notes

## Base

Default base URL:

```text
https://api.wiki.yandex.net/v1
```

Always send:

```text
Authorization: OAuth <oauth-token>
Authorization: Bearer <iam-token>
X-Org-Id: <organization-id>
X-Cloud-Org-Id: <organization-id>
```

Use only one authorization style and one organization header per request.

## Pages

Get page details by slug:

```http
GET /pages?slug=<slug>&fields=content,attributes,breadcrumbs
```

Important fields:

- `id`
- `slug`
- `title`
- `page_type`: `page`, `grid`, `cloud_page`, `wysiwyg`, or `template`
- `content`: returned only when `fields` includes `content`
- `attributes`: returned only when `fields` includes `attributes`
- `breadcrumbs`: returned only when `fields` includes `breadcrumbs`

Get descendants by slug:

```http
GET /pages/descendants?slug=<slug>&include_self=true&page_size=100
```

The response contains:

- `results`: array of `{id, slug}`
- `next_cursor`
- `prev_cursor`

Use `cursor=<next_cursor>` to continue pagination. `page_size` is capped at 100.

## Helper Commands

Use:

```bash
python3 scripts/wiki.py descendants --slug '' --include-self --limit 20
python3 scripts/wiki.py page <slug>
python3 scripts/wiki.py page <slug> --content-only
python3 scripts/wiki.py export --slug <slug> --limit 100 --output work/wiki.jsonl
python3 scripts/wiki.py raw /pages --query slug=<slug> --query fields=content
```

The helper only performs GET requests.

## Troubleshooting

`FORCED_SYNC_REQUIRED` with OAuth usually means Wiki did not accept OAuth for the user/session or the account is federated. Try opening the Wiki frontend with the same account; if it persists, use an IAM token from `yc iam create-token`.

`IAM token is invalid` means the token was sent as `Bearer` but is not an IAM token, is expired, or was copied incorrectly.

`Organization collab_id=None does not exist` can indicate the wrong organization header for the organization. Try `X-Org-Id` versus `X-Cloud-Org-Id`.

`401 Unauthorized` usually means an invalid or expired token.

`403 Forbidden` with page-specific requests can also mean the user lacks access to the page.
