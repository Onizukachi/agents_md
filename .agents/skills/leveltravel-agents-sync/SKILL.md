---
name: leveltravel-agents-sync
description: Synchronize the LevelTravel project's Git-tracked agent skills with origin/develop and its local AGENTS.md, CLAUDE.md, docs, tasks, and private skills with the adjacent agents_md repository. Use when importing the agent mirror on a workstation, publishing local agent material to the mirror, checking synchronization, or changing AGENTS.md, CLAUDE.md, or anything under .agents/.
---

# LevelTravel Agents Sync

Use `scripts/agents_sync.sh`; do not reproduce the sync with broad manual `rsync` commands.

## Ownership

Treat `origin/develop` as authoritative for exactly these skills:

- `leveltravel-hotfix-workflow`
- `leveltravel-pr-review`
- `leveltravel-pr-workflow`
- `leveltravel-tests`

Treat `agents_md` as authoritative for:

- `AGENTS.md`
- `CLAUDE.md`
- `.agents/docs/`
- `.agents/tasks/`
- every other directory under `.agents/skills/`

Never import mirror copies of develop-owned skills into the project.

## Shared Instructions Invariant

`AGENTS.md` is the canonical source of project guidance. Apply instruction
changes only to `AGENTS.md`.

`CLAUDE.md` must be a symbolic link to `AGENTS.md`. Do not duplicate project
guidance in it. The sync script refuses to pull, check, or publish an overlay
when the link target differs.

## Local Excludes

Configure `.git/info/exclude` on every workstation:

```gitignore
/AGENTS.md
/CLAUDE.md
/.agents/docs/
/.agents/tasks/
/.agents/skills/*
!/.agents/skills/leveltravel-hotfix-workflow/
!/.agents/skills/leveltravel-pr-review/
!/.agents/skills/leveltravel-pr-workflow/
!/.agents/skills/leveltravel-tests/
```

The script refuses to run if private paths are visible to Git or develop-owned skill paths are ignored.

## Commands

Run from the LevelTravel repository:

```bash
sync_script='.agents/skills/leveltravel-agents-sync/scripts/agents_sync.sh'
"$sync_script" pull "$PWD" ../agents_md
"$sync_script" check "$PWD" ../agents_md
"$sync_script" publish "$PWD" ../agents_md "Sync LevelTravel agent files"
```

Use `pull` when installing or refreshing mirror-owned files. It:

- requires a clean mirror and performs `git pull --ff-only`;
- replaces only mirror-owned paths;
- deletes stale mirror-owned files locally;
- verifies that tracked project state did not change.

Use `publish` only when the user asks to update or push the mirror. It:

- updates the mirror with `git pull --ff-only`;
- fetches `origin/develop`;
- exports the four develop-owned skills from `origin/develop`, never from the current branch;
- copies mirror-owned material from the project;
- validates, commits, and pushes only when the mirror changed.

Use `check` for a read-only comparison. It does not fetch or pull; report that its develop comparison uses the existing local `origin/develop`.

For first-time installation, invoke the script from the mirror:

```bash
../agents_md/.agents/skills/leveltravel-agents-sync/scripts/agents_sync.sh \
  pull "$PWD" ../agents_md
```

## Guardrails

- Never delete or overwrite `../agents_md/.git`.
- Never use `--delete` at the mirror repository root.
- Stop if the mirror is dirty or `git pull --ff-only` fails.
- Do not change application code.
- Do not commit or push the LevelTravel repository as part of this workflow.

Report the command used, the source revision for develop-owned skills, whether tracked project state stayed unchanged, and whether the mirror commit and push completed.
