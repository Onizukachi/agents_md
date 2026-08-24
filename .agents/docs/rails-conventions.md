# Rails and Ruby Conventions

## Models and data

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

## Controllers, services, and workers

- Keep controllers thin, use guard clauses, and keep business logic out of them.
- Extract namespaced services, such as `Clouds::CardGenerator`, for complex, reused, external-API, or oversized model/controller logic.
- Keep reusable business logic out of workers.
- Handle worker errors explicitly: rescue, report to Sentry where used, and persist the failed state or reason.

## Queries and views

- Keep query objects composable and read-only.
- Keep views limited to simple associations and scopes; do not put complex filtering in templates.
- Prevent N+1 queries with eager loading such as `includes`.

## Localization

- Prefer translations in `config/locales/ru.yml`.
- Put ActiveRecord validation, attribute, and model translations under:
  - `activerecord.errors.models`
  - `activerecord.attributes`
  - `activerecord.models`
- Add at least draft Russian model and attribute translations for new models or persisted fields.
- Prefer custom I18n keys for reusable business and UI text; avoid hardcoded Russian messages.

## Formatting

- Follow `.rubocop.yml`: single-quoted strings and parentheses delimiters for percent literals.

## ActiveAdmin

Keep `app/admin/*.rb` blocks in this order:

1. Base config: `menu`, `actions`, `permit_params`, `includes`, `config.*`
2. `scope`
3. `filter`
4. Presentation: `index`, `show`, `form`
5. UI actions: `action_item`, `batch_action`, `sidebar`
6. Custom actions: `member_action`, `collection_action`
7. `controller do ... end`

## Tests

- Prefer `let_it_be` or `let_it_be_with_reload` when they improve suite speed and clarity.
