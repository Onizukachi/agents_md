# Coding Agent Instructions

## 1) Business Context

- Product domain: travel.
- The app lets participants search, book, and purchase tours and hotels.
- Business model: travel aggregator, not a tour operator.

## 2) Architectural Principles

- Prefer Rails conventions over custom architecture.
- Keep code simple, clear, and maintainable.
- Use business/domain naming, not generic technical naming.
- Keep responsibilities by layer:
  - Models: persistence, associations, validations, callbacks, and small domain behavior.
  - Controllers: HTTP only.
  - Jobs: background execution, orchestration, and small job-specific logic.
  - Services: complex business operations, reusable workflows, and external integrations.

## 3) Skill Routing

- Use `.agents/skills/leveltravel-migrations` for Rails migration work.
- Use `.agents/skills/leveltravel-tests` for CI-equivalent and focused test verification flows.
- Use `.agents/skills/leveltravel-pr-workflow` for preparing, pushing, or opening regular pull requests.
- Use `.agents/skills/leveltravel-pr-review` for the final read-only review gate before push or PR update.
- Use `.agents/skills/leveltravel-hotfix-workflow` for production hotfixes that require paired `master` and `develop` PRs.
- Use `.agents/skills/lvtv-elastic-logs` for production/staging/integration Elasticsearch log investigations.
- Use `.agents/skills/yandex-tracker` for reading, creating, updating, or analyzing Tracker tasks.
- Use `.agents/skills/redash-api` for Redash API access, saved query execution, and read-only ad-hoc SQL through Redash.
- Use `.agents/skills/sentry-local` for investigating issues and events in the local LevelTravel Sentry.
- Use `.agents/skills/leveltravel-frontend-asset-recovery` when frontend changes are not visible after reload and restart.
- Use `.agents/skills/leveltravel-activeadmin-ui-check` for ActiveAdmin page checks and recovery flow.
- Use `.agents/skills/leveltravel-agents-sync` for syncing `AGENTS.md` and `.agents/` into `../agents_md`.
- Use `.agents/skills/skill-importer` for installing or updating shared Codex skills into the local skills directory.
- Use `.agents/skills/skill-exporter` for exporting local Codex skills into a shared skills repository.
- Use `.agents/skills/skills-syncer` for comparing and synchronizing local Codex skills with a shared skills repository.

## 4) Operating Workflow

### LT CLI in shell session

- Before any LT command, run: `source ./lt.sh`.
- Run LT commands through the loaded function (`lt logs rails`, `lt status`, `lt sh`, etc.).
- For any interaction with Rails inside the container, first enter the Rails container with `lt sh`, then run the needed command there.

### Task Artifacts

- Task artifacts live in `.agents/tasks/` as `task-<number>.md`.
- If the user mentions working with artifacts, look in `.agents/tasks/`.
- Create task artifacts only when the user explicitly asks for them.

## 5) Dependency And HTTP Policy

Dependency policy:
- Do not add new gems without explicit approval.
- If a gem is needed, propose short rationale + tradeoffs first.

HTTP policy:
- Use `ExternalRequest` as wrapper around `Typhoeus`.
- Do not introduce `Faraday` or `RestClient`.

## 6) File Placement

- `app/admin/`: ActiveAdmin resources/controllers
- `app/apis/`: external integrations (payments/fiscal/etc.)
- `app/query/`: read-only query objects
- `app/decorators/`: presentation formatting

## 7) Modeling And Conventions

### Naming

- Use domain names (`Participant`, `Cloud`, etc.), not technical placeholders (`User`, `GeneratedImage`, etc.).
- Models must inherit from `ApplicationRecord`.

### Model structure order

Keep this order in model files:
1. DSL/gem extensions
2. associations
3. enums
4. validations
5. scopes
6. callbacks
7. delegations
8. public methods
9. private methods

### State fields

- Use enums for states/statuses.
- Keep DB columns as strings.
- Prefer string-backed enum mapping:

```ruby
enum :state, %w(uploaded analyzing analyzed generating generated failed).index_with(&:to_s)
```

### Controller constraints

- Keep controllers thin and focused on HTTP concerns.
- Use guard clauses and early returns.
- Keep business logic out of controllers.

### Service extraction rules

Extract to namespaced services (e.g. `Clouds::CardGenerator`) when logic is:
- complex,
- calling external APIs,
- reused,
- or too large for a model/controller method.

### Data modeling

- Normalize tables: one concern per table.
- Index reference-like columns and frequently filtered columns.
- Add composite indexes for common query patterns.

For any work with Rails migrations, use the `.agents/skills/leveltravel-migrations` skill.

## 8) Job Rules

- Jobs handle background execution, orchestration, retries, and small job-specific logic; heavy reusable logic belongs in services.
- Handle errors explicitly:
  - rescue,
  - report (Sentry where used),
  - persist failed state/reason.

## 9) Query and View Rules

- Use query objects for complex/reused data fetching.
- Keep views simple: associations/scopes only.
- Avoid complex filtering logic in templates.
- Prevent N+1 with eager loading (`includes`, etc.).

## 10) Localization (I18n)

- Prefer translations in `config/locales/ru.yml`.
- For ActiveRecord validations, model names, and attribute names, prefer keys under:
  - `activerecord.errors.models`
  - `activerecord.attributes`
  - `activerecord.models`
- When adding a new model or new persisted fields, add at least draft Russian translations for the model name and its attributes in `config/locales/ru.yml`.
- Custom I18n keys are allowed (and preferred) for business/UI texts that are not model metadata.
- Avoid hardcoded Russian strings in reusable user-facing messages.

## 11) Formatting Rules

- Prefer single-quoted strings unless interpolation/escaping requires double quotes.
- Use percent literal parentheses delimiters:
  - `%w(...)`, `%i(...)`, `%W(...)`, `%I(...)`, `%q(...)`, `%Q(...)`, `%r(...)`, `%x(...)`.

## 12) ActiveAdmin Rules

### Resource section order (`app/admin/*.rb`)

1. Base config: `menu`, `actions`, `permit_params`, `includes`, `config.*`
2. `scope`
3. `filter`
4. presentation: `index`, `show`, `form`
5. UI actions: `action_item`, `batch_action`, `sidebar`
6. custom actions: `member_action`, `collection_action`
7. `controller do ... end`

## 13) Testing Guidance

- Use `.agents/skills/leveltravel-tests` for test-running workflows.
- Before local test commands through the project environment, run `source ./lt.sh`.
- Prefer `let_it_be` or `let_it_be_with_reload` when they improve suite speed and clarity.

## 14) Feature Flags

- Current baseline flags: `use_advanced_receipts`, `new_payments_architecture`.
- These two flags are currently legacy and must be treated as always `true`.
- Until removed, do not implement or rely on `false` behavior for these two flags.

## 15) Payments

- For order/payment/callback/receipt flows, follow: `.agents/docs/payments.md`.

## 16) PAPI v3 Documentation

- For any added/changed PAPI v3 route or contract, update docs using: `.agents/docs/papi_v3_docs.md`.
- Keep PAPI v3 docs in sync in the same PR as code changes.

## 17) Definition of Done

### MUST

- Required migrations are applied and schema changes are clean/relevant.
- Tests related to changed files or changed behavior pass locally.
- PAPI v3 docs are updated when routes or contracts change.
- `AGENTS.md` and `.agents/` changes are synced via `.agents/skills/leveltravel-agents-sync`.

### SHOULD

- `app/admin/*.rb` follows the agreed block order.
- Controllers stay thin with clear guard clauses.
- Queries remain composable/readable; no view-level complex filtering.
- N+1 risks are handled with eager loading.
- New indexes are added where query patterns require them.
- I18n keys are used for AR errors/attributes/model names.

If all MUST items are satisfied, the change is ready for review.
