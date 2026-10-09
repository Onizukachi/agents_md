# Coding Agent Instructions

## 1) Project

LevelTravel is a travel aggregator: it searches, books, and sells travel Packages sourced from external Operators — it does not operate tours itself. Stack: Ruby 3.4.10, Rails 8.1, MySQL (main database), ClickHouse (analytics models under `app/models/clickhouse/`), Redis, Sidekiq, and RSpec. See [CONTEXT.md](CONTEXT.md) for domain vocabulary.

## 2) Quick Start

- Run every Rails command inside the Rails container, non-interactively from the host: `docker exec lt.rails bash -lc '<command>'` (the working directory is `/app`). Do not use `lt sh`: it opens an interactive shell. If `lt.rails` is not running, ask the user to start it with `lt start`.
- Run tests with `docker exec lt.rails bash -lc 'bundle exec rspec <paths>'`. Ignore the `leveltravel-tests` skill entirely.
- Apply the Definition of Done (end of this document) before considering a change finished.

## 3) Task Routing

If no skill matches, follow this document and the linked files below, and proceed directly; do not invent a skill.

Project skills in `.agents/skills/` are written for Codex. Under Claude Code, apply them with these overrides:

- Tests: the `leveltravel-pr-workflow` test gate is replaced by `bundle exec rspec` in the Rails container (see Quick Start). In the PR body's Tests section, list the exact rspec commands actually run with their real results, plus `PENDING remote authoritative amd64 gate: TeamCity rails-rspec`; no local full-gate lines.
- Review: the native pass of `leveltravel-pr-review` is the built-in `code-review` skill; the focused companion is a fresh subagent with the companion prompt. Run the gate once, on the committed head, as a step of `leveltravel-pr-workflow`.
- Spec conformance: when the task has `SPEC.md` or tickets, run `code-vs-spec` alongside `leveltravel-pr-review` before push and add its Spec conformance section to the PR body. It reports and does not gate.
- Skill syntax: `$skill-name` in a skill text means "invoke that skill through the Skill tool". Skip Codex-only steps such as `$CODEX_BIN exec review`.
- Host commands: where a skill runs `ruby`, `bundle`, or `rails` on the host (migration generator and uniqueness check, `script/api_docs.rb`, the host-first fallback of `focused_rspec.sh`), run it in the Rails container instead (see Quick Start).
- `lt` CLI: it is a shell function from the profile, so `source ./lt.sh` is not needed. Never run `lt logs`: it streams and blocks. Read logs with `docker logs --tail 200 lt.rails` (or `lt.nginx`).

### Git conventions

- Branches: `feature/LT-<number>-<slug>`. Hotfixes: `hotfix/LT-<number>-<slug>` into `master` and `hotfix/LT-<number>-<slug>-dev` into `develop`. Older `_dev`, `-master`, or number-less names are legacy; keep them only when continuing an existing paired PR.
- Commits: title only, no body, no `Co-Authored-By` trailer. Regular tasks: `LT-<number> <English imperative title>`. Hotfixes: `HOTFIX: <summary in Russian>`.
- PR body: start from `.github/PULL_REQUEST_TEMPLATE/group_backend_template.md`, then add the Tests, Review, and Tracker sections from `leveltravel-pr-workflow`. Regular tasks are squash-merged into `develop`.

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

For changed code, also verify where applicable — see [Further Reading](#4-further-reading) for the underlying rules:

- ActiveAdmin files follow the agreed block order.
- Controllers remain thin with clear guard clauses.
- Queries remain composable and views contain no complex filtering.
- N+1 risks are handled with eager loading.
- Query patterns have the required indexes.
- ActiveRecord and reusable UI text use appropriate I18n keys.

When every applicable MUST row is satisfied, the change is ready for review.
