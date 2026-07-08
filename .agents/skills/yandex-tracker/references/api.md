# Yandex Tracker API Notes

Official docs: https://yandex.ru/support/tracker/ru/api-ref/about-api

## Auth

Base URL: `https://api.tracker.yandex.net/v3`.

Required headers:

- `Authorization: OAuth <token>` for OAuth tokens.
- `Authorization: Bearer <token>` for IAM tokens.
- `Content-Type: application/json` for requests with JSON bodies.
- `X-Org-ID: <organization_id>` for Yandex 360 organizations.
- `X-Cloud-Org-ID: <organization_id>` for Yandex Cloud organizations.

Organization ID is available in Tracker: Administration -> Organizations.

## Local Config

Default config file: `~/.yandex-tracker.env`.

Supported keys:

- `YANDEX_TRACKER_ORG_ID`
- `YANDEX_TRACKER_TOKEN`
- `YANDEX_TRACKER_AUTH_TYPE`
- `YANDEX_TRACKER_ORG_HEADER`
- `YANDEX_TRACKER_API_BASE`
- `YANDEX_TRACKER_DEFAULT_USER_NAME`
- `YANDEX_TRACKER_DEFAULT_USER_EMAIL`
- `YANDEX_TRACKER_DEFAULT_BOARDS`
- `YANDEX_TRACKER_SCRUM_BOARD_ID`
- `YANDEX_TRACKER_EPICFLOW_BOARD_ID`
- `YANDEX_TRACKER_DEV_EPICS_BOARD_ID`
- `YANDEX_TRACKER_DEV_QUEUE`
- `YANDEX_TRACKER_EPIC_QUEUE`
- `YANDEX_TRACKER_TASK_TEAM_FIELD`
- `YANDEX_TRACKER_EPIC_TEAM_FIELD`
- `YANDEX_TRACKER_STORY_POINTS_FIELD`

Use `YANDEX_TRACKER_DEFAULT_BOARDS` as comma-separated `id:name` entries, for example `2:Scrum,214:EpicFlow`.
Use the default user and boards when the prompt does not explicitly name a different person or board.

## Core Endpoints

- Create issue: `POST /issues/?notify=true|false`
- Read issue: `GET /issues/<issue_ID>?fields=...&expand=...`
- Update issue fields: `PATCH /issues/<issue_ID>?version=...`
- Search issues: `POST /issues/_search?fields=...&expand=...&perPage=50&page=1`
- Count issues: `POST /issues/_count`
- List boards: `GET /boards`
- Read board: `GET /boards/<board_ID>`
- Read board columns: `GET /boards/<board_ID>/columns`
- List board sprints: `GET /boards/<board_ID>/sprints`
- Read statuses: `GET /statuses`
- List issue transitions: `GET /issues/<issue_ID>/transitions`
- Execute issue transition: `POST /issues/<issue_ID>/transitions/<transition_ID>/_execute`
- Add issue comment: `POST /issues/<issue_ID>/comments`
- Read issue changelog: `GET /issues/<issue_ID>/changelog`

## Issue Creation

Create tasks with:

```bash
python3 "$TRACKER_HELPER" create \
  --queue LT \
  --summary 'Issue title' \
  --description-file /path/to/description.md \
  --markup-type md
```

API shape:

- Method: `POST /issues/`
- Query: optional `notify=false` or `notify=true`
- Required body fields: `queue` and `summary`
- Common body fields: `description`, `markupType`, `parent`, `type`, `priority`, `followers`, `assignee`, `author`, `project`, `links`, `unique`, `attachmentIds`, `tags`
- Custom/global/local queue fields are also accepted in the body when the current queue supports them.

The helper exposes common fields as flags and accepts additional fields through `--field-json`.
Use `--unique` for idempotency when task creation may be retried.

## Issue Updates

Patch tasks with:

```bash
python3 "$TRACKER_HELPER" update LT-123 \
  --summary 'New title' \
  --description-file /path/to/description.md \
  --markup-type md
```

API shape:

- Method: `PATCH /issues/<issue_ID>`
- Query: optional `version=<current_version>` for optimistic concurrency.
- Body: JSON object with updated field IDs and values.
- Supported update operators include direct set values and operator objects such as `{"add": [...]}` and `{"remove": [...]}` for fields that support them.
- Status is not patchable through this endpoint; use status transitions.

The helper exposes common direct fields as flags, plus additive/removal flags for tags and followers.
Use `--field-json` for local queue fields, custom fields, projects, attachment operators, or other documented patch bodies.
Read the current issue first when replacing text fields or when the update depends on the existing value.

## Issue Search

Use exactly one primary selector in the request body:

- `queue`: queue key.
- `keys`: issue key or list of keys.
- `filter`: object keyed by issue field.
- `filterId`: saved filter ID.
- `query`: Tracker query-language string.

Search supports query parameters:

- `fields`: comma-separated returned fields.
- `expand`: `attachments` or `comments`.
- `perPage`: page size, default 50.
- `page`: page number for `filter`, `query`, `keys`.
- `id`: relative pagination page ID for `queue`; get it from the `Link` response header.

Do not send `page` with `queue` searches. Tracker uses relative pagination for `queue`, while `filter`, `query`, and `keys` use page-based pagination.

For board summaries, get the board, then search issues using board `query` if present; otherwise use board `filter`, `orderBy`, and `orderAsc`.
If a board has no stored `query`, `filter`, or `defaultQueue`, search by Tracker query language with `"Sprints By Board": <board_id>`.

## Board Grouping

`GET /boards/<board_ID>` returns board metadata, filter/query, default queue, and columns.
`GET /boards/<board_ID>/columns` returns columns with the status keys that belong to each column.

To summarize a board:

1. Load board and columns.
2. Search tasks by board `query` or `filter`.
3. Map each issue `status.key` to the column that contains that status.
4. Group counts and sample tasks by column/status.

## LevelTravel EpicFlow Coverage

The helper has LevelTravel defaults for Scrum/EpicFlow analysis:

- Scrum board: `2`
- EpicFlow queue: `EPICFLOW`
- Development queue: `LT`
- Scrum task team field: `65ba668d034eb51c5204c8d4--team`
- EpicFlow team field: `69c2cd23dcc4e4691efad1ad--dev_team`

Find the current Scrum sprint:

```bash
python3 "$TRACKER_HELPER" current-sprint
```

Analyze project/EpicFlow coverage:

```bash
python3 "$TRACKER_HELPER" epicflow-coverage --sprint current
python3 "$TRACKER_HELPER" epicflow-coverage --sprint current --team WebFront
python3 "$TRACKER_HELPER" epicflow-coverage --sprint current --details
```

Cluster tasks that cannot satisfy the EpicFlow manifest because they have no development project:

```bash
python3 "$TRACKER_HELPER" no-project-clusters --sprint current
```

This is read-only. It joins `LT` tasks to `EPICFLOW` issues through `project.primary` and `project.secondary`.

Compare current Scrum sprint against active EpicFlow issues on the Epic Flow board:

```bash
python3 "$TRACKER_HELPER" scrum-epicflow-alignment --sprint current
```

This is read-only. It loads current Scrum `LT` tasks, active `EPICFLOW` issues from `Boards: <EpicFlow board ID>`, and reports:

- Scrum tasks without project;
- Scrum projects without active EpicFlow;
- projects with multiple active EpicFlow issues;
- tasks whose project has EpicFlow but not for the task team;
- active EpicFlow development-stage projects with no current Scrum task.

Summarize recent activity:

```bash
python3 "$TRACKER_HELPER" activity-summary --days 14
python3 "$TRACKER_HELPER" activity-summary --since 2026-06-08 --until 2026-06-22 --with-changelog
```

`--with-changelog` calls `GET /issues/<issue_ID>/changelog` for every task in the window and counts actual transitions into done statuses. Use it for productivity/throughput reports; omit it for faster activity summaries.

## Status Transitions

`GET /issues/<issue_ID>/transitions` returns available transitions for the current issue state.
Each transition has:

- `id`: transition ID used by `_execute`.
- `display`: transition button name in the UI.
- `to.key` and `to.display`: target status key and display name.
- `screen`: optional transition screen metadata; if the transition requires fields, pass them through `--field-json`.

To move an issue:

```bash
python3 "$TRACKER_HELPER" move LT-123 'Review'
```

The helper matches the target against transition `id`, transition `display`, target status `key`, or target status `display`.
If there is no exact match or more than one exact match, it refuses to execute.

Use explicit transition IDs when the user or UI gives one:

```bash
python3 "$TRACKER_HELPER" transition LT-123 review \
  --field-json '{"fieldKey":"value"}' \
  --comment 'Комментарий при переходе'
```

Transition body fields are queue/workflow-specific. Do not guess them; read the transition screen or ask for values if the API returns a validation error.

## Comments

Add comments with:

```bash
python3 "$TRACKER_HELPER" comment LT-123 --text 'Комментарий'
```

API body:

- `text`: required comment text.
- `markupType`: use `md` for YFM/Markdown-like formatting.
- `attachmentIds`: temporary attachment IDs to attach to the comment.
- `summonees`: user IDs or logins to mention.
- `maillistSummonees`: mailing lists to mention.

Query parameter:

- `isAddToFollowers=false`: do not add the comment author to followers.

## Write Boundary

Only use write endpoints when the user explicitly asks to create or change Tracker data.
Creation requires queue and summary.
Updates, comments, and transitions require a specific issue key or ID.
Do not guess local queue field names or workflow-specific values.
Do not patch issue status; execute a status transition instead.

Common error meanings:

- `401`: bad/expired token or API access disabled.
- `403`: token user lacks rights or required API scope.
- `404`: invalid issue or board ID.
- `409`: update conflict/version problem.
- `422`: JSON validation error.
