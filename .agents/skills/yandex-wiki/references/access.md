# Access Requirements

## Summary

- Required access: read permission to the target Yandex Wiki pages and enabled Yandex Wiki API access for the organization.
- Local credentials/config: `~/.yandex-wiki.env`, a short-lived IAM token file, or an OAuth token with `wiki:read`.
- Local tools: `python3`; `yc` Yandex Cloud CLI for federated-account IAM token refresh.
- Request from: the organization's Wiki/Yandex Cloud administrator.

## Federated Account Setup

For federated users, prefer IAM tokens. They are short-lived, but avoid the OAuth frontend-sync failure that can happen with Wiki API.

1. Ensure Yandex Cloud CLI is installed:

```bash
yc version
```

2. Configure a federated CLI profile if one is not already configured:

```bash
yc init --federation-id=<federation-id>
```

3. Confirm the profile has a federation:

```bash
yc config list
```

4. Configure the Wiki helper:

```bash
WIKI_HELPER="${CODEX_HOME:-$HOME/.codex}/skills/yandex-wiki/scripts/wiki.py"
python3 "$WIKI_HELPER" setup \
  --org-id '<organization-id>' \
  --auth-type Bearer \
  --org-header X-Org-Id \
  --refresh-iam
```

5. Validate:

```bash
python3 "$WIKI_HELPER" descendants --slug '' --include-self --limit 20
```

The helper creates IAM tokens with `yc iam create-token` and stores them in `~/.config/yandex-wiki/iam-token` by default. IAM tokens live no more than 12 hours and may be limited by federation cookie lifetime.

## OAuth Setup

OAuth can work for non-federated users if the token is issued for the same user that has Wiki page access.

1. Create an OAuth application for API/debug access.
2. Grant only `wiki:read` unless write access is explicitly required outside this skill.
3. Request the token using the OAuth authorize URL from the app's ClientID.
4. Configure:

```bash
python3 "$WIKI_HELPER" setup \
  --org-id '<organization-id>' \
  --auth-type OAuth \
  --org-header X-Org-Id \
  --token-file ~/.config/yandex-wiki/oauth-token
```

5. Store the token file with mode `0600`.

If OAuth returns `FORCED_SYNC_REQUIRED` with "Please authenticate user via frontend first", open the Wiki frontend with the same account and retry. If it still fails and the account is federated, use IAM instead.

## Organization Header

Yandex Wiki documents two organization headers:

- `X-Org-Id` for Yandex 360 for Business organizations.
- `X-Cloud-Org-Id` for Yandex Cloud Organization / Identity Hub organizations.

Use the header that actually validates against Wiki API. In the verified Level Travel setup, federated CLI IAM auth worked with `Authorization: Bearer <iam-token>` and `X-Org-Id`.

## Local Config

`~/.yandex-wiki.env` supports:

```dotenv
YANDEX_WIKI_ORG_ID=<organization-id>
YANDEX_WIKI_AUTH_TYPE=Bearer
YANDEX_WIKI_ORG_HEADER=X-Org-Id
YANDEX_WIKI_API_BASE=https://api.wiki.yandex.net/v1
YANDEX_WIKI_TOKEN_FILE=~/.config/yandex-wiki/iam-token
YANDEX_WIKI_REFRESH_IAM=1
YANDEX_WIKI_YC_BIN=yc
```

Do not commit token files or local config files. The shared skill repository must contain only variable names, setup commands, and non-secret defaults.

## Validation

Run:

```bash
python3 "$WIKI_HELPER" config
python3 "$WIKI_HELPER" refresh-token
python3 "$WIKI_HELPER" descendants --slug '' --include-self --limit 5
```

Expected successful auth uses HTTP 200 and returns JSON with `results`. A `401` usually means an invalid/expired token. A `403` can mean the wrong org header, missing page permissions, disabled API access, or OAuth/federation mismatch.
