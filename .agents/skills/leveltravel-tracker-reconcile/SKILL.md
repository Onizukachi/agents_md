---
name: leveltravel-tracker-reconcile
description: Reconcile LevelTravel Yandex Tracker tasks created by Codex PR/hotfix workflows with actual GitHub PR, CI, merge, release, deploy, and production verification state. Use when the user asks to актуализировать, разгрести, close, move, or audit Codex-created LT tasks stuck in Review, Ready for release, or related PR workflow statuses.
---

# LevelTravel Tracker Reconcile

Use this skill to update stale Tracker state after PR work continued outside the original Codex thread.

## Scope

This skill reconciles existing `LT-*` tasks. It does not implement application fixes.

Use `$yandex-tracker` for Tracker reads/writes. Use GitHub/`gh` for PR state. Use `$teamcity`, deploy evidence, Sentry/log skills, or explicit user evidence only when release or production verification matters.

## Default Mode

Start read-only unless the user explicitly asks to move/update Tracker tasks. For broad requests like "актуализируй мои Codex-задачи", produce a proposed action table first, then apply only unambiguous moves that match the user's request and have sufficient evidence.

Never move a task from memory alone. Re-query current Tracker and PR state.

## Candidate Selection

Default to the configured Tracker user:

```bash
python3 "$TRACKER_HELPER" config
```

If both `defaultUser.name` and `defaultUser.email` are empty, stop and ask the user to configure them or provide an exact Tracker assignee id/login. Do not guess short logins.

Find candidates by exact user and active PR workflow statuses:

```bash
python3 "$TRACKER_HELPER" search \
  --filter-json '{"queue":"LT","assignee":"<configured-user>","status":"inReview"}' \
  --order=-updated \
  --fields key,summary,status,assignee,updatedAt,storyPoints
```

Use Tracker status keys in `--filter-json`; for this helper `inReview` is the accepted key for `Ревью`.

Also inspect `Готово к релизу` tasks when the user asks about release/deploy cleanup.

## PR Resolution

For each candidate, find linked PRs from:

- issue description and comments;
- branch names containing the issue key;
- `gh pr list --state all --search "LT-123" --json number,url,title,body,headRefName,baseRefName,state,mergedAt,closedAt,reviewDecision,mergeStateStatus,statusCheckRollup` as candidate discovery only;
- existing PR body `## Tracker` section.

Validate every discovered PR before using its state. Accept a PR as linked to `LT-123` only when at least one strict signal is present:

- `headRefName` contains the exact issue key as a branch token, such as `feature/LT-123-...`;
- PR title contains the exact issue key as the task prefix or token and the summary is about the candidate task;
- the PR body `## Tracker` section names `LT-123` as the primary `Task:` value, or a clearly labelled primary task list includes `LT-123` and there is no conflicting single-task `Task:` value;
- the Tracker issue description or comments explicitly contain that PR URL/number or branch name.

Reject plain full-text hits where `LT-123` appears only in unrelated notes, test output, lock messages, another task's PR body, comments, or historical context. Do not use rejected PRs for `merged-to-develop`, `merged-to-master`, or release classification. If no strict PR remains, classify as `blocked` with `missing linked PR` or `ambiguous PR match`; if both strict and rejected hits exist, report the rejected false positives briefly and classify from strict PRs only.

Classify each task:

- `open-pr`: at least one required PR is open and there is no merged `develop` or `master` PR.
- `merged-to-master`: at least one required PR is merged into `master`; for this workflow, `master` means shipped and the Tracker target is `Завершено`.
- `merged-to-develop`: at least one required PR is merged into `develop`, but no required PR is merged into `master`.
- `closed-unmerged`: all linked PRs are closed without merge; this is not a release signal, so leave the task unchanged and report it as blocked/stale.
- `released-verified`: deploy/release/prod evidence exists for the merged code.
- `blocked`: conflicting PRs, failed CI, unresolved required review, missing linked PR, ambiguous branch, or missing transition fields.

Resolve overlapping classes in this order:

1. `merged-to-master`: any strict linked PR is merged into `master`; this is enough for business status `Завершено` even if a paired develop follow-up PR is still open or missing.
2. `blocked`: missing or ambiguous strict PR linkage for the ship-bearing PR, failed CI, unresolved required review, merge conflicts, missing transition fields, or a required ship-bearing PR that is still open/missing.
3. `open-pr`: at least one required linked PR is still open, even if another linked PR for the same task is already merged.
4. `released-verified`: non-master release/deploy/prod proof exists and no required PR is open or blocked.
5. `merged-to-develop`: at least one required linked PR is merged into `develop`, no required PR is open/blocked, and no linked `master` PR is merged.
6. `closed-unmerged`: every strict linked PR is closed without merge.

For paired hotfix tasks, the `master` PR is the ship-bearing PR and the `develop` PR keeps branches synchronized. Do not move a task to `Готово к релизу` from a merged develop PR while the paired master PR is open, missing, failed, or otherwise blocked. If the master PR is merged, move to `Завершено` and report any unmerged develop pair as a follow-up note instead of blocking the business status.

## Status Targets

Use business targets, not merely the first visible transition:

- Ready PR waiting for review/CI: `Ревью`.
- Merged into `develop` only, with no required linked PR still open/blocked and no merged `master` PR: `Готово к релизу`.
- Merged into `master`: `Завершено`.
- Released/deployed and verified by other current evidence: `Завершено`.
- Not actually started/currently wrong: ask before moving back to `Открыт` or `В работе`.

If Tracker does not offer the business target directly, inspect `transitions` and follow required intermediate transitions. Do not leave the task in `Можно тестировать`, `Assembly`, `Тестируется`, or `Готово к релизу` as the final meaning when the evidence says `Завершено`.

## Required Fields

Before any move, inspect available transitions:

```bash
python3 "$TRACKER_HELPER" transitions LT-123
```

When moving into `Ревью`, pass LevelTravel screen `431` fields:

```bash
--field-json '{"chtosdelanovzadache":"<what changed + PR links>","kakdeploitzadachunastejdzhkakt":"<stage/deploy/test/CI/prod notes>"}'
```

The screen id and field keys above are current LT examples, not a permanent schema contract. Treat `transitions` as the source of truth; when a transition exposes another screen or required fields change, inspect the screen or existing task examples before guessing field keys. If required fields are unknown, report the blocker instead of forcing a move.

## Evidence Rules

Do not treat these as release/prod proof:

- PR opened;
- CI green;
- PR mergeable;
- human review approved;
- Tracker already says `Готово к релизу`.

For this LevelTravel Tracker reconciliation workflow, a merged `master` PR is enough evidence to move to `Завершено`. A merged `develop` PR without a merged `master` PR is only enough for `Готово к релизу` when no required linked PR is still open or blocked. When no `master` PR exists, move to `Завершено` only when current release/deploy/prod evidence shows the merged commit in the relevant release/deployment and the requested business/incident outcome is checked.

## Output

Report compactly:

```markdown
## Reconcile
- moved to `Готово к релизу`: LT-...
- moved to `Завершено`: LT-... - merged into `master`
- left in `Ревью`: LT-... - PR still open / CI failed / review required
- left unchanged: LT-... - linked PRs are closed without merge
- blocked: LT-... - exact missing evidence or transition error
```

Include PR links and evidence dates for every moved task.
