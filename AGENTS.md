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

These rules apply to every agent and override `leveltravel-pr-workflow` and `leveltravel-hotfix-workflow` where they differ.

- Branches: `feature/LT-<number>-<slug>`. Hotfixes, without a task number: `hotfix/<slug>` into `master` and `hotfix/<slug>-dev` into `develop`. Older `_dev` and `-master` suffixes are legacy; keep them only when continuing an existing paired PR.
- Commits: title only, no body, no `Co-Authored-By` trailer, always in English. Regular tasks: `LT-<number> <imperative title>`. Hotfixes: `HOTFIX: <summary>`.
- PR title and description: always in Russian. Title format: `LT-<number> <title>`, hotfixes `HOTFIX: <summary>`.
- PR body: start from `.github/PULL_REQUEST_TEMPLATE/group_backend_template.md`, then add the Tests, Review, and Tracker sections from `leveltravel-pr-workflow` (headings and text in Russian). Regular tasks are squash-merged into `develop`.

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

- Task artifacts live under `.agents/tasks/<number>/`: `SPEC.md` (from `to-spec`, when used) and `PROGRESS.md` (from `implement`: progress and decisions that deviate from the spec).
- Look there when the user mentions a task or spec. Specs can be large (the LT-54329 one is about 110 KB): read `Scenarios` and `Implementation decisions` first and open other sections only when needed.
- Create a spec only through `to-spec`, and only when the task warrants them.

## 8) Definition of Done

All applicable MUST rows must be satisfied:

| Change | MUST |
|---|---|
| Behavior or application code | Related tests pass locally |
| Database schema | Migration workflow completed; migrations applied; schema changes clean and relevant |
| PAPI v3 route or contract | Documentation updated in the same PR |
| Personal skills or agent materials | Changes committed and pushed to `agents_md` |

`db/schema.rb` is committed in the old Rails 6.1 format, while Rails 8.1 dumps a different one (`charset:` instead of `options: "ENGINE=…"`, other column order, new header). After `db:migrate` the dump rewrites the whole file (thousands of diff lines): restore it with `git checkout db/schema.rb` and add by hand only the new table, columns, and indexes plus the `version:` line, in the existing style.

For changed code, also check it against [Architecture](.agents/docs/architecture.md) and [Rails and Ruby conventions](.agents/docs/rails-conventions.md): ActiveAdmin block order, thin controllers, composable queries, eager loading, indexes for new query patterns, I18n keys.

When every applicable MUST row is satisfied, the change is ready for review.
