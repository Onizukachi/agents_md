# Local Sentry Configuration

Verified on 2026-07-07.

## Connection

- Base URL: `https://sentry.lvtv.me`
- Organization slug: `sentry`
- Token env override: `SENTRY_AUTH_TOKEN`
- Token file override: `SENTRY_TOKEN_FILE`
- Default token file: `~/.config/sentry-local/token`

The token was verified against:

- `GET /api/0/organizations/` -> HTTP 200, empty array for the integration token.
- `GET /api/0/projects/` -> HTTP 200, 18 visible projects.
- `GET /api/0/organizations/sentry/` -> HTTP 200.
- `GET /api/0/organizations/sentry/projects/` -> HTTP 200.
- `GET /api/0/organizations/sentry/issues/?project=-1&query=&limit=5` -> HTTP 200.
- `GET /api/0/organizations/sentry/issues/{issue_id}/` -> HTTP 200.
- `GET /api/0/organizations/sentry/issues/{issue_id}/events/latest/` -> HTTP 200.

The `GET /api/0/organizations/` endpoint can return an empty array for this token; do not treat that as failed auth if direct org/project endpoints work.

## Visible Projects

- `web`
- `frontend-wl-staging`
- `frontend-wl`
- `web-staging`
- `mail-receiver`
- `imap-poller`
- `ghc`
- `tourparser`
- `crm-front`
- `frontend-staging`
- `frontend`
- `front-rails-staging`
- `front-manager`
- `front-rails-prod`
- `rails-prod`
- `sidekiq-prod`
- `rails-staging`
- `internal`

## Useful API Paths

- List all projects: `GET /api/0/projects/`
- List org projects: `GET /api/0/organizations/sentry/projects/`
- List org issues: `GET /api/0/organizations/sentry/issues/?project=-1&query=&limit=20`
- Retrieve issue: `GET /api/0/organizations/sentry/issues/{issue_id}/`
- Retrieve issue latest event: `GET /api/0/organizations/sentry/issues/{issue_id}/events/latest/`
- Retrieve issue events: `GET /api/0/organizations/sentry/issues/{issue_id}/events/`
- Update issue: `PUT /api/0/organizations/sentry/issues/{issue_id}/`

For issue reads, useful `expand` values include `owners`, `inbox`, and `latestEventHasAttachments`.
