---
name: leveltravel-code-review
description: Run a read-only, three-axis code review for a LevelTravel branch before push or PR update — Spec conformance (when a task SPEC.md/tickets exist), repo Standards + a code-smell baseline, and LevelTravel domain risk (Rails/migrations/jobs/security). Spawns one parallel read-only subagent per axis and aggregates a PASS/BLOCKED gate.
---

# LevelTravel Code Review

Use this skill as the final read-only review gate before pushing or updating a pull request.

This skill does not replace deterministic tests. It is meant to catch spec-conformance gaps, convention drift, and behavior/operational risks that tests often miss.

## Preconditions

- Confirm the workspace is the LevelTravel Rails repository by checking for `Gemfile`, `config/application.rb`, `app/`, and `engines/` or `lib/engines/`.
- Confirm the branch state with `git status --short --branch`.
- Use `origin/develop` as the comparison base after fetching `origin develop`, unless the active PR explicitly targets another branch.
- If intended PR changes are uncommitted, either commit them first or state that the review is only a working-tree review and cannot approve push or PR creation.
- Do not edit files during the review.
- Do not push or update a PR while `Status: BLOCKED` (see [Aggregation](#aggregation--status)).

## Gather Shared Context

Run once, and hand the results to every axis below instead of letting each subagent re-derive them:

```bash
git fetch origin develop
git diff --stat origin/develop...HEAD
git diff --name-only origin/develop...HEAD
git status --short
git log origin/develop..HEAD --oneline
```

Resolve the task number the same way `to-spec`/`to-tickets` do: an explicit number passed to this skill → otherwise parse `LT-<number>` from the current branch name → otherwise treat it as unresolved (do not ask; this feeds the Spec axis below, and an unresolved number just means that axis is skipped).

Avoid reviewing unrelated dirty files.

## Axis 1: Spec

Only runs when a spec source exists.

Look, in order:

1. `.agents/tasks/<number>/SPEC.md` for the resolved task number.
2. `.agents/tasks/<number>/ticket-*.md` for the resolved task number, if no `SPEC.md`.

If neither exists (including when the task number is unresolved), skip this axis and note `Spec: skipped (no SPEC.md/tickets found)` in the output. Do not ask the user to point at a spec — absence is a valid, common state.

Spec sub-agent prompt shape:

```text
Use the LevelTravel repository at <repo>. Compare origin/develop...HEAD (commits: <commit list>) against the spec below. Do not edit files.

<contents of SPEC.md and/or ticket-*.md files>

Report:
- Requirements the spec asked for that are missing or only partially done.
- Behavior in the diff that the spec didn't ask for (scope creep).
- Requirements that look implemented but where the implementation looks wrong.
Quote the spec line for each finding. Under 400 words.
```

## Axis 2: Standards

Always runs.

Standards sources in this repo:

- [.agents/docs/rails-conventions.md](../../docs/rails-conventions.md)
- [.agents/docs/architecture.md](../../docs/architecture.md)
- [.agents/docs/invariants.md](../../docs/invariants.md)
- [.agents/docs/papi_v3_docs.md](../../docs/papi_v3_docs.md) when a PAPI v3 route or contract changed

On top of whatever the repo documents, this axis always carries the **smell baseline** below — a fixed set of Fowler code smells (_Refactoring_, ch. 3) that applies even where the repo is silent. Two rules bind it:

- **The repo overrides.** A documented repo standard always wins; where it endorses something the baseline would flag, suppress the smell.
- **Always a judgement call.** Each smell is a labelled heuristic ("possible Feature Envy"), never a hard violation. Skip anything tooling already enforces (Rubocop, etc.).

Smell baseline — each reads *what it is* → *how to fix*, matched against the diff:

- **Mysterious Name**: a function, variable, or type whose name doesn't reveal what it does or holds. → rename it; if no honest name comes, the design's murky.
- **Duplicated Code**: the same logic shape appears in more than one hunk or file in the change. → extract the shared shape, call it from both.
- **Feature Envy**: a method that reaches into another object's data more than its own. → move the method onto the data it envies.
- **Data Clumps**: the same few fields or params keep travelling together. → bundle them into one type, pass that.
- **Primitive Obsession**: a primitive or string standing in for a domain concept that deserves its own type. → give the concept its own small type.
- **Repeated Switches**: the same `case`/`if`-cascade on the same type recurs across the change. → replace with polymorphism, or one map both sites share.
- **Shotgun Surgery**: one logical change forces scattered edits across many files in the diff. → gather what changes together into one module.
- **Divergent Change**: one file or module is edited for several unrelated reasons. → split so each module changes for one reason.
- **Speculative Generality**: abstraction, parameters, or hooks added for needs the spec doesn't have. → delete it; inline back until a real need shows.
- **Message Chains**: long `a.b.c.d` navigation the caller shouldn't depend on. → hide the walk behind one method on the first object.
- **Middle Man**: a class or method that mostly just delegates onward. → cut it, call the real target direct.
- **Refused Bequest**: a subclass or implementer that ignores or overrides most of what it inherits. → drop the inheritance, use composition.

Standards sub-agent prompt shape:

```text
Use the LevelTravel repository at <repo>. Review origin/develop...HEAD (commits: <commit list>, changed files: <file list>). Do not edit files.

Standards sources: <paths above that exist>
Smell baseline: <paste the full list above>

Report, per file/hunk where relevant:
(a) every place the diff violates a documented standard — cite the standard (file + rule);
(b) any baseline smell you spot — name it, quote the hunk.
Distinguish hard violations (documented-standard breaches) from judgement calls (baseline smells are always judgement calls). A documented repo standard overrides the baseline. Skip anything tooling enforces. Under 400 words.
```

## Axis 3: Domain Risk

Always runs. This is LevelTravel-specific production/operational risk — migrations, jobs, integrations, security — the kind of thing generic standards/spec review won't catch.

Domain-risk sub-agent prompt shape:

```text
Use the LevelTravel repository at <repo>. Fetch origin develop, then review origin/develop...HEAD (commits: <commit list>, changed files: <file list>). Test commands run and their results: <test commands/results>. Do not edit files.

Focus on concrete bugs, behavior regressions, operational risk, and missing tests. Do not report style-only issues unless they hide a real defect (style/convention issues belong to the Standards axis, not this one).

Return findings only when there is a concrete risk. Classify each as BLOCKER, CONCERN, or NIT.
For BLOCKER and CONCERN findings include file:line, risk, evidence from the diff, and a recommended direction.

Required review lenses:
- Rails model, association, validation, callback, and transaction behavior.
- Rails query performance and N+1 behavior:
  - Trace every changed index/list endpoint, serializer, presenter, view, decorator, worker loop, rake/backfill loop, and ActionCable payload builder from query to output.
  - Look for association access or query methods inside `.each`, `.map`, `.select`, `.group_by`, serializers, JSON builders, broadcasts, and batch loops.
  - Check `.count`, `.size`, `.length`, `.exists?`, `.any?`, `.first`, `.last`, `pluck`, scoped associations, and memoized queries inside loops.
  - Verify required associations are preloaded with `includes`, `preload`, or `eager_load`, and that `joins`/`includes` with filtering or sorting cannot duplicate or drop records.
  - Prefer database-side filtering, aggregation, and `pluck` over loading records and filtering/counting in Ruby.
  - For high-volume list or batch paths, require a Bullet/query-count-covered spec or explicitly report that coverage is missing.
- Database migration safety, reversibility, null/default/index choices, lock risk, and partitioned or high-volume tables.
- Database rollout safety: check foreign key defaults, `bigint`/id types, deploy windows between migration and app restart, data backfills after deploy, and whether code can run before/after the migration.
- Background job and backfill safety:
  - Check idempotency, retry amplification, duplicate enqueue prevention, queue choice, batch size, memory pressure, external API quotas, Redis counters/TTL, and resumability.
  - Ensure recurring failures are observable through logs, Sentry, metrics, or explicit progress/error state.
- External service calls, credentials, timeouts, prompt/schema contracts, payload key names, API versioning, and failure handling.
- Serializer/API compatibility and frontend-facing payload changes.
- Nil/input tolerance: changed parsers, serializers, services, workers, and API handlers must tolerate `nil`, blank, invalid, missing, or out-of-contract external input when that can occur in production.
- Rails callback and dirty tracking behavior: field-specific recalculation must be guarded by `*_changed?`, `saved_change_to_*?`, or equivalent so unrelated updates do not rewrite data or enqueue work.
- Security and permissions: check raw SQL/interpolation, untrusted params, authorization boundaries, secret/token exposure, and admin/internal endpoint access.
- Frontend/date behavior when `client/` files change: check local-vs-UTC calendar dates, null API fields, mobile/desktop conditionals, TypeScript `any`/`unknown`, and package/localization version bumps.
- Test coverage for success, duplicate, empty, invalid, and failure paths.
- Whether tests prove the generalized contract rather than only the motivating fixture.
```

## Spawning

Spawn one subagent per axis that applies (always Standards and Domain Risk; Spec only when a source was found), in parallel, so they don't pollute each other's context. Each gets: repository path, comparison base `origin/develop`, commit list, changed file list, and (Domain Risk only) test commands/results. None of them may edit files.

If subagents are unavailable, perform the same three reviews locally and clearly label the result as local-only.

## Aggregation & Status

Present the three reports under their own headings, verbatim or lightly cleaned:

```markdown
## Spec
...findings, or "skipped (no SPEC.md/tickets found)"...

## Standards
...findings, split into hard violations and smells...

## Domain Risk
...findings, classified BLOCKER/CONCERN/NIT...
```

Do **not** merge or rerank findings across axes — a Standards judgement call and a Domain Risk BLOCKER are not comparable, and collapsing them would let one axis mask another.

Then compute one gate line from a fixed, narrow rule — only things that unambiguously mean "this doesn't do what it's supposed to, or will break in production" set the gate; everything else stays visible to the reader as CONCERN/NIT but doesn't block:

```
Status: PASS | BLOCKED
```

- `BLOCKED` if the **Spec** axis reports a missing requirement or a "looks implemented but wrong" finding, OR the **Domain Risk** axis has any `BLOCKER`.
- Everything else — Spec's partial/scope-creep findings, every **Standards** finding (hard violations and smells alike), and Domain Risk `CONCERN`/`NIT` — is reported but never sets `Status: BLOCKED` on its own. Standards is about maintainability and convention, not regression risk, so it stays advisory even for a "hard violation."

If there are no findings on an axis, say so explicitly rather than omitting the section.

For PR bodies, include a compact version:

```markdown
## Review
- <PASS|BLOCKED>: `leveltravel-code-review` completed against `origin/develop`
- Checked: Spec conformance (or "no spec"), repo standards + smells, LevelTravel domain risk
- Findings: none / addressed / accepted concerns listed above
```
