---
name: leveltravel-agents-sync
description: Use when AGENTS.md or anything under .agents/ changes in the LevelTravel repository and those updates must be mirrored into ../agents_md. Covers the safe mirror workflow, git-repository health checks, and the required pull, commit, and push sequence without damaging ../agents_md git metadata.
---

# LevelTravel Agents Sync

Use this skill whenever `AGENTS.md` or `.agents/**/*` changes and the documentation mirror at `../agents_md` must be updated.

This skill governs sync only. Do not change application code merely because this skill loaded.

## Guardrails

Protect the target repository:

- never delete or overwrite `../agents_md/.git`;
- never copy nested git metadata from the source `.agents/.git` into the mirror;
- never use destructive root-level sync that can remove destination-only git metadata;
- mirror only `AGENTS.md` and `.agents/`;
- if `../agents_md` is not a git repository, stop and report that state before attempting `git pull`, commit, or push.

## Verify The Target

Before any sync, confirm the target exists and still has git metadata:

```bash
test -d ../agents_md
test -e ../agents_md/.git
git -C ../agents_md status --short --branch
```

If any of these checks fails, stop and report the exact problem.

## Mirror Files Safely

Mirror only the intended content:

```bash
rsync -a AGENTS.md ../agents_md/
mkdir -p ../agents_md/.agents
rsync -a --exclude='.git' .agents/ ../agents_md/.agents/
```

Do not use `--delete` against the root of `../agents_md`.

The destination may contain git metadata or other repository-only files that must survive the mirror.

The source `.agents/` may itself be a git repository. Always exclude its nested `.git` directory from the mirror copy.

## Git Sync Sequence

Only after the target passes the git checks:

```bash
git -C ../agents_md pull --ff-only
git -C ../agents_md status --short
git -C ../agents_md add AGENTS.md .agents
git -C ../agents_md commit -m "<concise message>"
git -C ../agents_md push
```

If `git pull --ff-only` fails because of divergence or unrelated local changes, stop and report it instead of forcing through.

## Reporting

When summarizing the sync:

- say what was mirrored;
- say whether the target repository passed the git health checks;
- say whether `pull`, commit, and push completed or were blocked;
- if blocked, include the exact blocking condition.
