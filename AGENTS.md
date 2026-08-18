# Coding Agent Instructions

## 1) Quick Start

- Use the task-routing table below before starting specialized work.
- Before any LT command, run `source ./lt.sh`, then use the loaded `lt` function.
- Run every Rails command inside the Rails container: enter it with `lt sh` first.
- Background jobs are Sidekiq workers in `app/workers/`, not ActiveJob classes; there is no `app/jobs/`.
- Apply the conditional Definition of Done at the end of this document.

## 2) Project Context

- Domain: travel.
- The product is a travel aggregator, not a tour operator.
- Participants can search, book, and purchase tours and hotels.
- Stack: Ruby 3.4.10, Rails 7.2, PostgreSQL, Redis, Sidekiq, and RSpec.

## 3) Task Routing

| Task | Required guidance |
|---|---|
| Rails migrations | `leveltravel-migrations` |
| Focused or CI-equivalent tests | `leveltravel-tests` |
| Prepare, push, or open a regular PR | `leveltravel-pr-workflow` |
| Final read-only review before push or PR update | `leveltravel-pr-review` |
| Production hotfix with `master` and `develop` PRs | `leveltravel-hotfix-workflow` |
| Reconcile LevelTravel Tracker tasks after PR work | `leveltravel-tracker-reconcile` |
| Elasticsearch log investigation | `lvtv-elastic-logs` |
| Yandex Tracker work | `yandex-tracker` |
| Redash queries or read-only SQL | `redash-api` |
| Local LevelTravel Sentry investigation | `sentry-local` |
| Frontend changes missing after reload/restart | `leveltravel-frontend-asset-recovery` |
| ActiveAdmin browser check or recovery | `leveltravel-activeadmin-ui-check` |
| Install, update, export, or compare shared skills | `skill-importer`, `skill-exporter`, or `skills-syncer`, respectively |
| Payment, callback, or receipt flow | `.agents/docs/payments.md` |
| PAPI v3 route or contract | `.agents/docs/papi_v3_docs.md` |

If no route matches, follow this document and proceed directly; do not invent a skill.

## 4) Agent Materials

`AGENTS.md`, `CLAUDE.md`, `.agents/docs/`, and `.agents/tasks/` are symbolic
links to the personal `agents_md` checkout. Edit them through those links; do
not replace them with local copies or synchronize them with a copy workflow.

## 5) Project Invariants

### Dependencies

- Do not add gems without explicit user approval.
- When proposing a gem, first give a short rationale and tradeoffs.

### External HTTP

- Use `ExternalRequest` as the wrapper around `Typhoeus`.
- Do not introduce `Faraday` or `RestClient`.

### Feature flags

- Treat `use_advanced_receipts` and `new_payments_architecture` as always `true`.
- These flags are legacy; do not implement or rely on their `false` behavior.

## 6) Architecture and File Placement

Prefer Rails conventions and simple, maintainable code. Use business names such as `Tour`, `Hotel`, or `Order`, not generic technical placeholders such as `Data` or `Result`.

Keep responsibilities separated:

- Models: persistence, associations, validations, callbacks, and small domain behavior.
- Controllers: HTTP concerns only.
- Workers: background execution, orchestration, retries, and small worker-specific logic.
- Services: complex business operations, reusable workflows, and external integrations.
- Query objects: complex or reusable read-only data fetching.
- Decorators and serializers: presentation and API response formatting.

Use these locations:

| Code | Location |
|---|---|
| ActiveAdmin resources/controllers | `app/admin/` |
| External integrations | `app/apis/` |
| Query objects | `app/queries/` |
| Presentation formatting | `app/decorators/` |
| Business services | `app/services/` |
| Sidekiq workers | `app/workers/` |
| API serializers | `app/serializers/` |

## 7) Rails Conventions

### Models and data

- Models inherit from `ApplicationRecord`.
- Normalize tables: one concern per table.
- Index reference-like and frequently filtered columns.
- Add composite indexes for common query patterns.
- Use string columns and string-backed enums for states and statuses:

```ruby
enum :state, %w(uploaded analyzing analyzed generating generated failed).index_with(&:to_s)
```

Keep model files in this order:

1. DSL/gem extensions
2. associations
3. enums
4. validations
5. scopes
6. callbacks
7. delegations
8. public methods
9. private methods

### Controllers, services, and workers

- Keep controllers thin, use guard clauses, and keep business logic out of them.
- Extract namespaced services, such as `Clouds::CardGenerator`, for complex, reused, external-API, or oversized model/controller logic.
- Keep reusable business logic out of workers.
- Handle worker errors explicitly: rescue, report to Sentry where used, and persist the failed state or reason.

### Queries and views

- Keep query objects composable and read-only.
- Keep views limited to simple associations and scopes; do not put complex filtering in templates.
- Prevent N+1 queries with eager loading such as `includes`.

### Localization

- Prefer translations in `config/locales/ru.yml`.
- Put ActiveRecord validation, attribute, and model translations under:
  - `activerecord.errors.models`
  - `activerecord.attributes`
  - `activerecord.models`
- Add at least draft Russian model and attribute translations for new models or persisted fields.
- Prefer custom I18n keys for reusable business and UI text; avoid hardcoded Russian messages.

### Formatting

- Follow `.rubocop.yml`: single-quoted strings and parentheses delimiters for percent literals.

### ActiveAdmin

Keep `app/admin/*.rb` blocks in this order:

1. Base config: `menu`, `actions`, `permit_params`, `includes`, `config.*`
2. `scope`
3. `filter`
4. Presentation: `index`, `show`, `form`
5. UI actions: `action_item`, `batch_action`, `sidebar`
6. Custom actions: `member_action`, `collection_action`
7. `controller do ... end`

### Tests

- Use RSpec.
- Prefer `let_it_be` or `let_it_be_with_reload` when they improve suite speed and clarity.

## 8) Domain-Specific Guidance

### Payments

Follow `.agents/docs/payments.md` for order, payment, callback, and receipt flows.

### PAPI v3

- Follow `.agents/docs/papi_v3_docs.md` for route and contract changes.
- Keep PAPI v3 documentation synchronized in the same PR as the code.

## 9) Task Artifacts

- Task artifacts live in `.agents/tasks/` as `task-<number>.md`.
- Look there when the user mentions an artifact.
- Create an artifact only when the user explicitly requests one.

## 10) Conditional Definition of Done

All applicable MUST rows must be satisfied:

| Change | MUST |
|---|---|
| Behavior or application code | Related tests pass locally |
| Database schema | Migration workflow completed; migrations applied; schema changes clean and relevant |
| PAPI v3 route or contract | Documentation updated in the same PR |
| Personal agent materials | Changes committed and pushed to `agents_md` |
| Push or PR update | Required test, review, and PR workflows completed |

For changed code, also verify where applicable:

- ActiveAdmin files follow the agreed block order.
- Controllers remain thin with clear guard clauses.
- Queries remain composable and views contain no complex filtering.
- N+1 risks are handled with eager loading.
- Query patterns have the required indexes.
- ActiveRecord and reusable UI text use appropriate I18n keys.

When every applicable MUST row is satisfied, the change is ready for review.
