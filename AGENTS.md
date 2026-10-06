# Coding Agent Instructions

## 1) Project

LevelTravel is a travel aggregator: it searches, books, and sells travel Packages sourced from external Operators — it does not operate tours itself. Stack: Ruby 3.4.10, Rails 7.2, PostgreSQL, Redis, Sidekiq, and RSpec. See [CONTEXT.md](CONTEXT.md) for domain vocabulary.

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
