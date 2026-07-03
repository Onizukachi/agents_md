---
name: leveltravel-hotfix-workflow
description: Create paired LevelTravel hotfix pull requests. Use when a production fix must go first from fresh master to a hotfix branch and PR into master, then be cherry-picked into a fresh develop-based hotfix branch with a second PR into develop.
---

# LevelTravel Hotfix Workflow

Use this skill for LevelTravel production hotfixes that must produce two pull requests: one into `master`, and one into `develop`.

## Required Shape

- Start from freshly fetched `origin/master`.
- Create a `hotfix/<short-english-slug>` branch.
- Make the fix and commit it once on the master hotfix branch.
- Push and open a ready PR into `master` with title `HOTFIX: <human-readable summary>`.
- Start a separate branch from freshly fetched `origin/develop`.
- Name the develop branch with the same hotfix slug plus `-dev`, for example `hotfix/example-prod-fix-dev`. Use the existing branch suffix if updating an already opened paired PR.
- Cherry-pick the exact commit from the master hotfix branch into the develop hotfix branch.
- Push and open a ready PR into `develop` with the same `HOTFIX: <human-readable summary>` title.

## Naming

- Use `hotfix/<short-english-slug>` for the master branch.
- Prefer `hotfix/<short-english-slug>-dev` for the develop branch. `_dev` exists in older PRs, but `-dev` is the preferred current style unless continuing an existing branch.
- Use `HOTFIX: <human-readable summary>` for both PR titles.
- Do not use raw branch names as PR titles, such as `hotfix/example-prod-fix`.
- Do not use mixed legacy title styles such as `Hotfix / ...` or `Hotfix/...` for new PRs.

## Guardrails

- Inspect `git status --short --branch` before creating worktrees, editing files, committing, pushing, or opening PRs.
- Protect unrelated local changes. Use separate worktrees when the main workspace is dirty.
- Do not use `codex/*` branch names for LevelTravel hotfixes.
- Do not manually reimplement the fix on develop if cherry-pick is possible; the develop PR should contain the cherry-picked commit.
- Do not force-push unless updating an existing branch intentionally and the expected remote SHA is known.
- Do not run destructive cleanup commands unless the user explicitly asks for them.

## Verification

- Run narrow syntax/static checks for changed Ruby/YAML files.
- Run focused specs for the changed behavior when practical.
- If the user asks not to run local CI, skip the full TeamCity-compatible gate and state that remote CI will be authoritative.
- Run a read-only review before push when time and tools allow; do not push while a blocker finding is unresolved.

## PR Body

Include:

- what changed;
- why it is a production hotfix;
- tests/checks actually run;
- any skipped local CI with reason;
- operational notes such as migrations, jobs, schedules, external services, and rollout risks.

## Final Response

Return both PR links and clearly label which one targets `master` and which one targets `develop`.
