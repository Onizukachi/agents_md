# Coding Agent Instructions

## 1) Project

LevelTravel is a travel aggregator: it searches, books, and sells travel Packages sourced from external Operators — it does not operate tours itself. Stack: Ruby 3.4.10, Rails 7.2, PostgreSQL, Redis, Sidekiq, and RSpec. See [CONTEXT.md](CONTEXT.md) for domain vocabulary.

## 2) Quick Start

- Before any LT command, run `source ./lt.sh`, then use the loaded `lt` function.
- Run every Rails command inside the Rails container: enter it with `lt sh` first.
- Use the task-routing table below before starting specialized work.
- Apply the Definition of Done (end of this document) before considering a change finished.

## 3) Task Routing

| Task | Skill | Type |
|---|---|---|
| Large or ambiguous task, before implementation starts | `grill` | Personal |
| Turn an agreed spec-worthy conversation into a spec artifact | `to-spec` | Personal |
| Break a spec, plan, or conversation into ordered, dependency-aware tickets | `to-tickets` | Personal |
| Implement a task's tickets/spec from `.agents/tasks/` | `implement` | Personal |
| Codebase terminology, or writing/editing `CONTEXT.md` | `domain-modeling` | Personal |
| Rails migrations | `leveltravel-migrations` | Personal |
| Final read-only review before push or PR update | `leveltravel-pr-review` | LevelTravel |
| Production hotfix with `master` and `develop` PRs (skip all Yandex Tracker steps) | `leveltravel-hotfix-workflow` | LevelTravel |
| Elasticsearch log investigation | `lvtv-elastic-logs` | Shared |
| Yandex Tracker work | `yandex-tracker` | Shared |
| Redash queries or read-only SQL | `redash-api` | Shared |
| Local LevelTravel Sentry investigation | `sentry-local` | Shared |
| Corporate Yandex Wiki page lookup, export, or summary | `yandex-wiki` | Shared |
| Read own Mattermost: unread, threads, search, channel history, reactions, attachments | `mm-gateway` | Shared |
| Frontend changes missing after reload/restart | `leveltravel-frontend-asset-recovery` | Personal |
| ActiveAdmin browser check or recovery | `leveltravel-activeadmin-ui-check` | Personal |
| Install, update, export, or compare shared skills | `skill-importer`, `skill-exporter`, or `skills-syncer`, respectively | Shared |

If no route matches, follow this document and the linked files below, and proceed directly; do not invent a skill.

## 4) Further Reading

Load these only when the task touches their topic:

- [Architecture and file placement](.agents/docs/architecture.md) — layered responsibilities, where code goes, Sidekiq vs ActiveJob.
- [Project invariants](.agents/docs/invariants.md) — dependencies, external HTTP, legacy feature flags.
- [Rails and Ruby conventions](.agents/docs/rails-conventions.md) — model file order, controllers/services/workers style, queries, localization, formatting, ActiveAdmin, tests.
- [Payments flow](.agents/docs/payments.md) — order, payment, callback, and receipt flows.
- [PAPI v3 docs](.agents/docs/papi_v3_docs.md) — route/contract documentation rules; keep in sync with code changes in the same PR.

## 5) Agent Materials

`AGENTS.md`, `CLAUDE.md`, `CONTEXT.md`, `.agents/docs/`, and `.agents/tasks/`
are symbolic links to the personal `agents_md` checkout. Edit them through
those links; do not replace them with local copies or synchronize them with a
copy workflow.

## 6) Task Artifacts

- Task artifacts live under `.agents/tasks/<number>/`: `SPEC.md` (from `to-spec`, when used) and `ticket-<NN>-<slug>.md` files (from `to-tickets`).
- Look there when the user mentions a task, spec, or ticket.
- Create artifacts only through `to-spec`/`to-tickets`, and only when the task warrants them.

## 7) Definition of Done

All applicable MUST rows must be satisfied:

| Change | MUST |
|---|---|
| Behavior or application code | Related tests pass locally |
| Database schema | Migration workflow completed; migrations applied; schema changes clean and relevant |
| PAPI v3 route or contract | Documentation updated in the same PR |
| Personal skills or agent materials | Changes committed and pushed to `agents_md` |
| Push or PR update | Required test, review, and PR workflows completed |

For changed code, also verify where applicable — see [Further Reading](#4-further-reading) for the underlying rules:

- ActiveAdmin files follow the agreed block order.
- Controllers remain thin with clear guard clauses.
- Queries remain composable and views contain no complex filtering.
- N+1 risks are handled with eager loading.
- Query patterns have the required indexes.
- ActiveRecord and reusable UI text use appropriate I18n keys.

When every applicable MUST row is satisfied, the change is ready for review.
