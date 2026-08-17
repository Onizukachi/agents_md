---
name: leveltravel-hotfix-workflow
description: Create paired LevelTravel hotfix pull requests. Use when a production fix must go first from fresh master to a hotfix branch and PR into master, then be cherry-picked into a fresh develop-based hotfix branch with a second PR into develop. Handles one shared Tracker task and status updates when the yandex-tracker skill is available.
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

## Tracker Task Automation

When `$yandex-tracker` is available, create or reuse one shared `LT-<number>` task for the paired hotfix. Use the same Tracker task for the `master` PR and the `develop` PR.

Treat this workflow as the user's standing instruction to create a missing `LT` task for hotfix work in this repository. Do not require the user to separately ask "create a Tracker task" when the hotfix has no task yet.

If the skill is unavailable in the current Codex installation, continue the hotfix workflow without Tracker automation and state that the Tracker step could not run because `$yandex-tracker` is not installed. If the skill is available but credentials, permissions, or network fail, stop before push/PR unless the user explicitly asks to continue without Tracker writes.

Before creating a new Tracker task, inspect `python3 "$TRACKER_HELPER" config`. If both `defaultUser.name` and `defaultUser.email` are empty, stop and ask the user to configure `YANDEX_TRACKER_DEFAULT_USER_NAME` or `YANDEX_TRACKER_DEFAULT_USER_EMAIL`; do not guess from git author, shell username, or a remembered short login. An explicitly configured Tracker user id/login is acceptable only when the helper accepts it as `--assignee`.

Resolve the task before creating the master hotfix branch:

- Use an explicit `LT-<number>` from the user request, current Sentry/support context, current branch, existing PR, or incident notes.
- Otherwise load `$yandex-tracker`, inspect config with `python3 "$TRACKER_HELPER" config`, and search current/recent `LT` tasks by incident keywords, Sentry issue, failing worker/controller, affected behavior, and hotfix slug.
- If exactly one current task clearly matches, use it.
- If several plausible tasks match, ask the user to choose.
- If no task matches, create a new `LT` task.

Create missing hotfix tasks through `$yandex-tracker` with LevelTravel defaults:

- Queue: `LT`.
- Type: `task`.
- Priority: `critical` or `blocker` only when the incident severity justifies it; otherwise use `normal`.
- Assignee: current Codex/Tracker user from `YANDEX_TRACKER_DEFAULT_USER_EMAIL` or `YANDEX_TRACKER_DEFAULT_USER_NAME`. If no current user is configured, ask once for the Tracker login/email instead of assigning to a guessed git author.
- Sprint: current Scrum sprint from `python3 "$TRACKER_HELPER" current-sprint`.
- Team: infer from the work. For Rails hotfixes, use `WebBack` when no safer team is evident.
- Story points: estimate conservatively and fill `storyPoints`; most real production one-commit Rails hotfixes with a regression spec are `2`, while purely mechanical or config/test-only slices are `1`.
- Project: attach only when the user request, existing EpicFlow context, branch, or code owner makes the project clear; do not invent a project for an incident-only hotfix.
- Description: include the production symptom, evidence source, customer/operational impact, proposed narrow fix, paired PR plan, test plan, rollback/deploy notes, and source links such as Sentry/support issue.

Use the installed helper shape. The global LevelTravel helper may require queue-specific fields through `--field-json`, for example:

```bash
python3 "$TRACKER_HELPER" create \
  --queue LT \
  --summary 'HOTFIX: <short Russian incident title>' \
  --type task \
  --priority normal \
  --assignee '<tracker-login-or-id>' \
  --sprint-ids '<current-sprint-id>' \
  --description-file /path/to/description.md \
  --markup-type md \
  --field-json '{"storyPoints": 2, "65ba668d034eb51c5204c8d4--team": "WebBack"}'
```

Status flow:

- After creating or switching to the master hotfix branch, move the task to the actual work-start status, usually `В работе` / `In Progress`.
- After both ready PRs are opened or updated, move the task to the actual review status, usually `Ревью` / `Review`, and comment with both PR links. For LevelTravel `LT`, the transition to `Ревью` usually uses screen `431`; pass `--field-json` with `chtosdelanovzadache` and `kakdeploitzadachunastejdzhkakt`.
- If the develop PR is merged while the paired master PR is still open, missing, failed, or review-blocked, keep the task in `Ревью` or report it as blocked; for paired hotfixes the master PR is the production ship vehicle. Do not use a develop-only merge as the normal signal for `Готово к релизу` in this hotfix workflow.
- After the master PR is merged, the target business status is `Завершено` / `Done`; in this workflow, `master` means shipped. If the paired develop PR is still open or missing, report it as a follow-up branch-sync note rather than blocking the business status.
- Without a merged `master` PR, move the task to `Завершено` / `Done` only after the required deployment/release/production-verification condition for the incident is satisfied.

The screen id and field keys below are current LT examples, not a permanent schema contract. Treat `transitions` as the source of truth; if Tracker exposes another screen or required fields change, inspect transitions and existing task examples before guessing field keys.

Before status moves, inspect available transitions when needed:

```bash
python3 "$TRACKER_HELPER" transitions LT-123
python3 "$TRACKER_HELPER" move LT-123 'Ревью' \
  --field-json '{"chtosdelanovzadache":"Implemented hotfix <summary>. PRs: master <url>, develop <url>.","kakdeploitzadachunastejdzhkakt":"Deploy/test: <stage/prod checks>. Checks: <real checks>."}' \
  --comment 'Hotfix PRs ready: master <url>, develop <url>'
```

Follow required intermediate transitions instead of forcing a final status. If a status move is impossible, keep the PR work going only after reporting the exact Tracker blocker. At final response time, if the task is in `Ревью`, explicitly state the next Tracker action after merge: for paired hotfixes, a develop-only merge leaves the task in `Ревью`/blocked until the master PR is handled; `master` means move to `Завершено`, with any unmerged develop pair reported as follow-up.

Reference shape: the FastConfirm hotfix for Sentry `47593` would use one task for `hotfix/fastconfirm-order-reload` and `hotfix/fastconfirm-order-reload-dev`, estimate `2` story points, describe the stale `OrderLog` association and `order.reload` fix, then move to Review after the `master` and `develop` PRs are both open.

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
- shared Tracker task key and status automation result when Tracker automation ran, or the exact unavailable/bypassed reason;
- any skipped local CI with reason;
- operational notes such as migrations, jobs, schedules, external services, and rollout risks.

## Final Response

Return both PR links and clearly label which one targets `master` and which one targets `develop`. Include the shared Tracker task key plus its latest status move when Tracker automation ran; if it did not, state the exact unavailable/bypassed reason.
