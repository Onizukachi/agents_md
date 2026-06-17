---
name: leveltravel-pr-workflow
description: Use when creating, updating, pushing, or opening a pull request in the LevelTravel Rails repository. Handles fresh develop workflow, GitFlow branch naming, TeamCity-compatible test gate, read-only PR review, GitHub push, and ready PR creation.
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

- The authoritative PR gate is the TeamCity-compatible Docker RSpec flow.
- Focused host-side commands are useful during development, but they do not replace the PR gate.
- If Docker, registry credentials, `PROTO_REPO_TOKEN`, or other CI-equivalent inputs are unavailable, state that explicitly in the PR body and include every partial command that did run.
- If the full gate fails for a product or test regression, fix it before push or PR.
- If the full gate cannot run because local infrastructure is unavailable, do not claim the branch is fully verified.

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

After the workspace guard, test gate, and review gate are complete:

```bash
git push -u origin <branch>
```

Create or update a ready PR against `develop`:

```bash
gh pr create --base develop --head <branch> --title "<title>" --body-file <body-file>
```

Prefer `--body-file` over inline bodies to avoid shell quoting problems. Do not create a draft PR unless the user asked for a draft or a required external dependency prevents ready review.

## PR Body

Every PR body should include:

```markdown
## What changed
- ...

## Why
- ...

## Tests
- PASS: `<exact command>`
- BLOCKED: `<exact command>` - <reason>

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
- Call out migrations, background jobs, data backfills, scheduled tasks, external service calls, and rollout risks.
- If the PR updates an existing open PR, update the body so the latest tests and review status remain accurate.
