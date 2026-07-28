---
name: leveltravel-pr-workflow
description: Use when creating, updating, pushing, or opening a pull request in the LevelTravel Rails repository. Handles fresh develop workflow, GitFlow branch naming, architecture-aware local testing, read-only PR review, GitHub push, ready PR creation, and the authoritative remote TeamCity gate before merge.
---

# LevelTravel PR Workflow

Use this skill whenever work in this repository should be prepared for a GitHub pull request.

This skill governs the PR workflow only. Do not change application code merely because this skill loaded.

## Workspace Guard

Before changing tracked files, creating a branch, committing, pushing, or updating a PR, inspect:

```bash
git status --short --branch
```

Protect existing work:

- Do not stage, commit, revert, or push unrelated user changes.
- If intended PR changes cannot be isolated from unrelated workspace changes, stop and explain what needs to be separated.
- Never use destructive cleanup commands such as `git reset --hard` or `git checkout --` unless the user explicitly asked for that exact operation.

## Base Branch

Use `develop` as the PR base branch.

For new work, refresh the base before branching:

```bash
git fetch origin develop
git switch develop
git pull --ff-only origin develop
git switch -c feature/LT-<ticket-number>-<short-english-slug>
```

If the current branch already contains the requested work, keep using it unless the user asks for a new branch.

Branch naming:

- Prefer the repository GitFlow pattern from existing PRs: `feature/LT-<ticket-number>-<short-english-slug>`.
- If there is no LT tracker ticket, use `feature/<short-english-slug>` and mention the missing ticket in the PR body.
- Use `hotfix/<short-english-slug>` only for hotfix PRs and `release/<YYYYMMDD>` only for release PRs.
- Use English, lowercase, kebab-case slugs after the ticket number.
- Use two to five semantic words after the ticket number.
- Avoid vague slugs such as `fix`, `updates`, `changes`, `misc`, or `wip`.
- Do not use `codex/*` as the default branch prefix in this repository; Codex authorship belongs in the PR context, not the branch name.

## Development Loop

Make changes in the smallest coherent scope that satisfies the request.

Before committing:

- inspect the diff with `git diff --stat` and targeted `git diff`;
- ensure new files are intentionally placed and named;
- keep migrations, schema changes, factories, workers, serializers, and specs consistent with existing Rails patterns;
- do not commit local Bundler, editor, log, tmp, or Docker runtime artifacts.

## Required Test Gate

Before push or PR creation, use `$leveltravel-tests`.

Strict policy:

- Run the repository local full-test entry point: `bash .agents/skills/leveltravel-tests/scripts/local_rspec.sh`.
- On Apple Silicon, native ARM64 Docker RSpec is the required broad local gate. Report it explicitly as not TeamCity-equivalent.
- On x86_64, the entry point runs the canonical local TeamCity-compatible amd64 helper.
- Focused host-side commands are useful during development, but they do not replace the architecture-appropriate local full gate.
- If Docker, registry access, credentials, or another local input is unavailable, state that explicitly in the PR body and include every partial command that did run.
- If the local full gate finds a product or test regression, fix it before push or PR creation.
- If the local full gate is blocked by infrastructure, do not claim the branch is fully locally verified.
- Do not require the canonical amd64 helper through QEMU on Apple Silicon. It is available as an explicit diagnostic command only: `bash .agents/skills/leveltravel-tests/scripts/teamcity_rspec.sh`.

The remote TeamCity `rails-rspec` build is the authoritative amd64 parity gate. It runs after the PR is opened and must pass before merge. A native ARM64 pass is strong local evidence, but it never substitutes for this remote result.

## Required Review Gate

After intended changes are committed and tests have passed or are explicitly blocked by local infrastructure, use `$leveltravel-pr-review`.

Strict policy:

- The review is read-only and must not edit files.
- The review must compare the current branch against freshly fetched `origin/develop`.
- The review must cover Rails behavior, data migrations, background jobs, external integrations, tests, and operational risk.
- Push and PR creation are blocked while any `BLOCKER` finding remains unresolved.
- `CONCERN` findings must either be fixed or explicitly accepted in the PR body with a short reason.
- `NIT` findings do not block push or PR creation.

If subagent review is unavailable, state that in the PR body. Do not describe a local-only read as an independent agent review.

## Push And PR

After the workspace guard, local test gate, and review gate are complete:

```bash
git push -u origin <branch>
```

Create or update a ready PR against `develop`:

```bash
gh pr create --base develop --head <branch> --title "<title>" --body-file <body-file>
```

Prefer `--body-file` over inline bodies to avoid shell quoting problems. Do not create a draft PR unless the user asked for a draft or a required external dependency prevents ready review.

After PR creation, inspect the remote TeamCity `rails-rspec` result. Keep the PR open and report it as pending or blocked until that authoritative amd64 parity gate passes. Do not merge, or report the PR as merge-ready, while it is pending or failing.

## PR Body

Every PR body should include:

```markdown
## What changed
- ...

## Why
- ...

## Tests
- PASS local full ARM64 gate (not TeamCity-equivalent): `<exact command>`
- PASS local TeamCity-compatible amd64 gate: `<exact command>`
- BLOCKED local infrastructure: `<exact command>` - <reason>
- PENDING remote authoritative amd64 gate: TeamCity `rails-rspec`

## Review
- PASS: `leveltravel-pr-review` completed against `origin/develop`
- Findings: none / addressed / accepted concerns listed above

## Operational notes
- Migrations: yes/no
- Background jobs: yes/no
- External services or credentials: yes/no
```

Rules:

- Mention behavior changed, not only filenames.
- List exact test commands and real results.
- Include local infrastructure blockers honestly.
- On Apple Silicon, never label the native ARM64 result as TeamCity-equivalent or amd64 parity.
- After TeamCity finishes, update the PR test status to `PASS remote authoritative amd64 gate` with its build URL, or report the exact failure.
- Call out migrations, background jobs, data backfills, scheduled tasks, external service calls, and rollout risks.
- If the PR updates an existing open PR, update the body so the latest tests and review status remain accurate.
