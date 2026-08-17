---
name: leveltravel-pr-workflow
description: Use when creating, updating, pushing, or opening a pull request in the LevelTravel Rails repository. Handles Tracker task discovery/creation/status updates when the yandex-tracker skill is available, fresh develop workflow, GitFlow branch naming, architecture-aware local testing, read-only PR review, GitHub push, ready PR creation, and the authoritative remote TeamCity gate before merge.
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
- If `$yandex-tracker` is available and there is no LT tracker ticket, create one before creating the branch.
- Use `feature/<short-english-slug>` only when Tracker automation is unavailable or blocked; mention that explicitly in the branch/PR context.
- Use `hotfix/<short-english-slug>` only for hotfix PRs and `release/<YYYYMMDD>` only for release PRs.
- Use English, lowercase, kebab-case slugs after the ticket number.
- Use two to five semantic words after the ticket number.
- Avoid vague slugs such as `fix`, `updates`, `changes`, `misc`, or `wip`.
- Do not use `codex/*` as the default branch prefix in this repository; Codex authorship belongs in the PR context, not the branch name.

## Tracker Task Automation

When `$yandex-tracker` is available, every PR branch must be tied to one `LT-<number>` task before commit, push, or PR creation.

Treat this workflow as the user's standing instruction to create a missing `LT` task for PR work in this repository. Do not require the user to separately ask "create a Tracker task" when the PR work has no task yet.

If the skill is unavailable in the current Codex installation, continue the Git workflow without Tracker automation and state that the Tracker step could not run because `$yandex-tracker` is not installed. If the skill is available but credentials, permissions, or network fail, stop before push/PR unless the user explicitly asks to continue without Tracker writes.

Before creating a new Tracker task, inspect `python3 "$TRACKER_HELPER" config`. If both `defaultUser.name` and `defaultUser.email` are empty, stop and ask the user to configure `YANDEX_TRACKER_DEFAULT_USER_NAME` or `YANDEX_TRACKER_DEFAULT_USER_EMAIL`; do not guess from git author, shell username, or a remembered short login. An explicitly configured Tracker user id/login is acceptable only when the helper accepts it as `--assignee`.

Resolve the Tracker task before creating a new branch:

- Use an explicit `LT-<number>` from the user request, current branch, commit subject, or existing PR.
- Otherwise load `$yandex-tracker`, inspect config with `python3 "$TRACKER_HELPER" config`, and search current/recent `LT` tasks by user request keywords, touched area, Sentry issue, support ticket, project, and branch slug.
- If exactly one current task clearly matches, use it.
- If several plausible tasks match, ask the user to choose.
- If no task matches, create a new `LT` task.

For broad mechanical waves, prefer reusing one umbrella `LT` task instead of creating many small tasks. Use one task with multiple PR branches when the work is one technical initiative, one owner, and no separate QA/release ownership is needed. Create separate tasks only for independent QA units, incidents, product-visible behavior, ownership boundaries, or release/accounting slices.

Create missing tasks through `$yandex-tracker` with LevelTravel defaults:

- Queue: `LT`.
- Type: `task`.
- Priority: `normal` unless the user provided another priority.
- Assignee: current Codex/Tracker user from `YANDEX_TRACKER_DEFAULT_USER_EMAIL` or `YANDEX_TRACKER_DEFAULT_USER_NAME`. If no current user is configured, ask once for the Tracker login/email instead of assigning to a guessed git author.
- Sprint: current Scrum sprint from `python3 "$TRACKER_HELPER" current-sprint`.
- Team: infer from the work. For this Rails repo, use `WebBack` when no safer team is evident.
- Story points: estimate conservatively and fill `storyPoints`.
- Project: attach only when the user request, existing EpicFlow context, branch, or code owner makes the project clear; do not invent a project.
- Description: include the user request, why the change is needed, affected behavior, planned implementation, test plan, risks, and source links such as Sentry/PR/support issue.

Use the installed helper shape. The global LevelTravel helper may require queue-specific fields through `--field-json`, for example:

```bash
python3 "$TRACKER_HELPER" create \
  --queue LT \
  --summary '<short Russian task title>' \
  --type task \
  --priority normal \
  --assignee '<tracker-login-or-id>' \
  --sprint-ids '<current-sprint-id>' \
  --description-file /path/to/description.md \
  --markup-type md \
  --field-json '{"storyPoints": 2, "65ba668d034eb51c5204c8d4--team": "WebBack"}'
```

Story point heuristic:

- `1`: mechanical cleanup, test-only/config-only/docs-only change, one narrow contract-preserving PR, or a small technical slice inside a larger umbrella task.
- `2`: real production or user-visible bugfix with focused regression coverage and some rollout/QA context.
- `3`: behavior change across several Rails layers, serializers, jobs, controllers, or specs.
- `5`: migration, backfill, external integration behavior, operational rollout, or cross-module risk.
- `8+`: broad or unclear scope; ask the user before creating the task.

Move the task through statuses with `$yandex-tracker`:

- After creating or switching to the implementation branch, move the task to the actual work-start status, usually `В работе` / `In Progress`.
- After tests/review gate are complete and the ready PR is opened or updated, move the task to the actual review status, usually `Ревью` / `Review`. For LevelTravel `LT`, the transition to `Ревью` usually uses screen `431`; pass `--field-json` with `chtosdelanovzadache` and `kakdeploitzadachunastejdzhkakt`.
- After the PR is merged into `develop`, and no required linked PR for the same task is still open or blocked, the target business status is `Готово к релизу`. If a linked `master` PR is merged, use `Завершено` instead. If Tracker requires intermediate statuses, inspect transitions and follow them, but do not leave the task in `Можно тестировать` or `Assembly` as the final post-merge meaning.
- After a linked PR for the same task is merged into `master`, the target business status is `Завершено` / `Done`; in this workflow, `master` means shipped.
- Without a merged `master` PR, move the task to `Завершено` / `Done` only after the required release/deploy condition and any necessary production or business verification are satisfied.

The screen id and field keys below are current LT examples, not a permanent schema contract. Treat `transitions` as the source of truth; if Tracker exposes another screen or required fields change, inspect transitions and existing task examples before guessing field keys.

Before status moves, inspect available transitions when needed:

```bash
python3 "$TRACKER_HELPER" transitions LT-123
python3 "$TRACKER_HELPER" move LT-123 'Ревью' \
  --field-json '{"chtosdelanovzadache":"Implemented <summary>. PR: <url>.","kakdeploitzadachunastejdzhkakt":"Deploy/test: <stage steps>. Checks: <real checks>."}' \
  --comment 'PR ready for review: <url>'
```

Follow required intermediate transitions instead of forcing a final status. If a status move is impossible, keep the PR work going only after reporting the exact Tracker blocker. At final response time, if the task is in `Ревью`, explicitly state the next Tracker action after merge: `develop` only and no required linked PR open/blocked means move to `Готово к релизу`; `master` means move to `Завершено`.

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

## Tracker
- Task: `LT-...`
- Status: moved to Review / blocked: <reason>
- Next after merge: `develop` only with no required linked PR open/blocked -> `Готово к релизу`; `master` -> `Завершено`

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
- Include the Tracker task key and real status automation result. If `$yandex-tracker` is unavailable, say so instead of implying the task was created or moved.
