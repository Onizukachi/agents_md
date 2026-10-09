# Coding Agent Instructions

## 1) Project

LevelTravel is a travel aggregator: it searches, books, and sells travel Packages sourced from external Operators — it does not operate tours itself. Stack: Ruby 3.4.10, Rails 8.1, MySQL (main database), ClickHouse (analytics models under `app/models/clickhouse/`), Redis, Sidekiq, and RSpec. Domain vocabulary: [CONTEXT.md](CONTEXT.md).

## 2) Quick Start

- Run every Rails command in the Rails container: `docker exec lt.rails bash -lc '<command>'` (working directory `/app`), even if a skill says to run `ruby`, `bundle`, or `rails` on the host. Never use `lt sh`: it is interactive. If `lt.rails` is not running, start it with `lt start`; if that fails on login or VPN, ask the user.
- Run tests with `docker exec lt.rails bash -lc 'bundle exec rspec <paths>'`. `spec_helper` forces `RAILS_ENV=test`, so no env prefix is needed, and one spec file takes about 10 seconds including boot. After a schema change recreate the test database the way `lt` does: `bundle exec rails db:drop db:create db:schema:load RAILS_ENV=test` in the container. Ignore the `leveltravel-tests` skill entirely.
- Apply the Definition of Done (end of this document) before considering a change finished.

## 3) Task Routing

If no skill matches, follow this document and the linked files below, and proceed directly; do not invent a skill.

These rules apply to every agent and override the project skills in `.agents/skills/` where they differ:

- Tests: the local full gate of `leveltravel-pr-workflow` is replaced by `bundle exec rspec` in the Rails container (see Quick Start). The PR body's Tests section lists the commands actually run and, instead of local full-gate lines, `PENDING remote authoritative amd64 gate: TeamCity rails-rspec`.
- Review: the native pass of `leveltravel-pr-review` is the host's own code review (Codex: `codex exec review`; Claude Code: the built-in `code-review` skill); the focused companion is a fresh subagent with the companion prompt. Skip steps meant for another host.

Questions about production behavior are answered with the installed `lt-*` skills, not guessed from code. They need the corporate VPN or an office network: `lt-sentry` (errors), `lt-elastic` (logs), `lt-metrics` (metrics), `lt-redash` (read-only data: Replica, ClickHouse), `lt-teamcity` (builds and deploys), `lt-k8s-dev` (developer stands).

## 4) Git and PRs

- Branches: `feature/LT-<number>-<slug>`. Hotfixes: `hotfix/LT-<number>-<slug>` into `master` and `hotfix/LT-<number>-<slug>-dev` into `develop`. Older `_dev`, `-master`, or number-less names are legacy; keep them only when continuing an existing paired PR.
- Commits: title only, no body, no `Co-Authored-By` trailer, always in English. Regular tasks: `LT-<number> <imperative title>`. Hotfixes: `HOTFIX: <summary>`.
- PR body: start from `.github/PULL_REQUEST_TEMPLATE/group_backend_template.md`, then add the Tests, Review, and Tracker sections from `leveltravel-pr-workflow`. Regular tasks are squash-merged into `develop`.

## 5) Further Reading

Load these only when the task touches their topic:

- [Architecture and file placement](.agents/docs/architecture.md) — layered responsibilities, where code goes, Sidekiq vs ActiveJob.
- [Project invariants](.agents/docs/invariants.md) — dependencies, external HTTP, legacy feature flags.
- [Rails and Ruby conventions](.agents/docs/rails-conventions.md) — model file order, controllers/services/workers style, queries, localization, formatting, ActiveAdmin, tests.
- [Payments flow](.agents/docs/payments.md) — order, payment, callback, and receipt flows.
- [PAPI v3 docs](.agents/docs/papi_v3_docs.md) — route/contract documentation rules; keep in sync with code changes in the same PR.

## 6) Agent Materials

`AGENTS.md`, `CONTEXT.md`, `.agents/docs/`, and `.agents/tasks/` are symbolic links to the personal `agents_md` checkout. Edit them through the links; never replace them with local copies.

## 7) Task Artifacts

- Task artifacts live under `.agents/tasks/<number>/`: `SPEC.md` (from `to-spec`, when used) and `ticket-<NN>-<slug>.md` files (from `to-tickets`).
- Look there when the user mentions a task, spec, or ticket. Specs can be large (the LT-54329 one is about 110 KB): read `Scenarios` and `Implementation decisions` first and open other sections only when needed.
- Create artifacts only through `to-spec`/`to-tickets`, and only when the task warrants them.

## 8) Definition of Done

All applicable MUST rows must be satisfied:

| Change | MUST |
|---|---|
| Behavior or application code | Related tests pass locally |
| Database schema | Migration workflow completed; migrations applied; schema changes clean and relevant |
| PAPI v3 route or contract | Documentation updated in the same PR |
| Personal skills or agent materials | Changes committed and pushed to `agents_md` |

For changed code, also check it against [Architecture](.agents/docs/architecture.md) and [Rails and Ruby conventions](.agents/docs/rails-conventions.md): ActiveAdmin block order, thin controllers, composable queries, eager loading, indexes for new query patterns, I18n keys.

When every applicable MUST row is satisfied, the change is ready for review.
