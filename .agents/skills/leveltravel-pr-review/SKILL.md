---
name: leveltravel-pr-review
description: Run a read-only LevelTravel pull-request review after tests and before push or PR update. Use when auditing a Rails branch against develop for behavior regressions, migration risk, job/idempotency issues, external integration safety, and missing tests.
---

# LevelTravel PR Review

Use this skill as the final read-only review gate before pushing or updating a pull request.

This skill does not replace deterministic tests. It is meant to catch design, behavior, and operational risks that tests often miss.

## Preconditions

- Confirm the workspace is the LevelTravel Rails repository by checking for `Gemfile`, `config/application.rb`, `app/`, and `engines/` or `lib/engines/`.
- Confirm the branch state with `git status --short --branch`.
- Use `origin/develop` as the comparison base after fetching `origin develop`, unless the active PR explicitly targets another branch.
- If intended PR changes are uncommitted, either commit them first or state that the review is only a working-tree review and cannot approve push or PR creation.
- Do not edit files during the review.
- Do not push or update a PR while any `BLOCKER` finding remains unresolved.

## Gather Context

Run and keep the useful output:

```bash
git fetch origin develop
git diff --stat origin/develop...HEAD
git diff --name-only origin/develop...HEAD
git status --short
```

Read only relevant changed files and nearby context. Prefer:

```bash
git diff origin/develop...HEAD -- <path>
sed -n '<start>,<end>p' <path>
rg "<class-or-method-name>" app lib engines spec
```

For Rails/Ruby changes, also run targeted searches that force a performance and contract pass:

```bash
rg -n "\.(each|map|select|group_by|find_each|find_in_batches)" app lib engines
rg -n "\.(includes|preload|eager_load|joins|references|count|size|length|exists\?|any\?|first|last|pluck)" app lib engines
rg -n "serializer|serialize_as_hash|as_json|jbuilder|broadcast|ActionCable" app lib engines
rg -n "perform_async|sidekiq_options|retry|find_each|find_in_batches|rake|backfill|Redis|REDIS" app lib engines
```

Avoid reviewing unrelated dirty files.

## Run The Reviewer Pass

When subagents are available, spawn exactly one read-only reviewer subagent. The main agent may gather context and summarize, but the independent PASS/BLOCKED decision should come from the subagent.

Give the reviewer:

- repository path;
- comparison base `origin/develop`;
- changed file list;
- exact test commands and results;
- instruction to inspect diffs and nearby context directly;
- instruction not to edit files.

Use this prompt shape:

```text
Use the LevelTravel repository at <repo>. Fetch origin develop, then review the current branch against origin/develop. Do not edit files.

Focus on concrete bugs, behavior regressions, operational risk, and missing tests. Do not report style-only issues unless they hide a real defect.

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

If subagents are unavailable, perform the same review locally and clearly label it as local-only.

## Severity

- `BLOCKER`: likely production regression, data corruption or loss, unsafe migration, non-idempotent job behavior, broken external contract, security or credential leak, or broad behavior change without meaningful tests.
- `CONCERN`: maintainability or rollout risk that should be fixed or explicitly accepted, weak coverage around important edge cases, unclear ownership boundaries, or surprising behavior that is not an immediate blocker.
- `NIT`: optional polish that should not block push or PR.

Prefer no finding over speculative findings. A finding must point to changed code or directly affected unchanged context.

## Output

Return:

```markdown
## Agent Review
- Status: PASS | BLOCKED
- Base: origin/develop
- Scope: Rails | Data | Jobs | API | Docs/Process | Mixed

### Findings
- BLOCKER: ...
- CONCERN: ...
- NIT: ...

### Checked
- Migrations: ...
- Jobs/backfills: ...
- Query/N+1: ...
- Nil/input tolerance: ...
- External integrations: ...
- Frontend/date behavior: ...
- Security/permissions: ...
- Tests reviewed: ...
```

If there are no findings, say `Status: PASS` and list the main surfaces checked.

For PR bodies, include a compact version:

```markdown
## Review
- PASS: `leveltravel-pr-review` completed against `origin/develop`
- Checked: Rails behavior, query/N+1, migrations, jobs/backfills, integrations, nil/input tolerance, tests
- Findings: none / addressed / accepted concerns listed above
```
