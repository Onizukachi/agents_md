---
name: skills-syncer
description: Compare and synchronize local Codex skills with a shared skills repository. Use when Codex needs to audit installed skills against repository skills, install missing repository skills, update local skills from the repository, identify local-only skills to export, coordinate skill-importer and skill-exporter workflows, or produce a periodic sync report without silently overwriting local changes.
---

# Skills Syncer

## Purpose

Use this skill as the orchestration layer for local Codex skill hygiene. It compares installed skills and repository skills, then routes each action to `skill-importer` for repository-to-local installation or `skill-exporter` for local-to-repository export.

Before sync actions that read or write a private repository, read `references/access.md` to check repository access requirements.

## Modes

- **status**: compare local and repository skills, then report missing, changed, and local-only skills.
- **pull**: install or update selected local skills from the repository using `skill-importer`.
- **export**: prepare repository changes for selected local-only or locally modified skills using `skill-exporter`.
- **audit-access**: inspect `references/access.md` files and report missing credential/request documentation.
- **sync-all**: run status first, then propose a plan. Do not modify files until the user approves the plan.

## Sync Workflow

1. **Locate roots.** Identify the shared skills repository and the local Codex skills directory `${CODEX_HOME:-$HOME/.codex}/skills` unless the user gives explicit paths.
2. **Inventory repository skills.** List `skills/*/SKILL.md` and read frontmatter names.
3. **Inventory installed skills.** List local installed skills, resolving symlinks and noting whether each skill points into the repository.
4. **Classify state.**
   - `repo-only`: exists in repository but is not installed locally.
   - `local-only`: exists locally but not in repository.
   - `linked`: local symlink points at repository skill.
   - `copied-clean`: copied local skill matches repository.
   - `copied-different`: copied local skill differs from repository.
   - `repo-dirty`: repository skill has uncommitted changes.
5. **Check access docs.** For every repository skill, check whether `references/access.md` exists and whether it names required access, local config, local tools, request path, setup, and validation.
6. **Propose actions.** Use `skill-importer` for `repo-only`, stale copied skills, or broken links. Use `skill-exporter` for local-only skills or local edits that should become repository changes.
7. **Protect work.** Never overwrite copied local skills with differences unless the user explicitly approves. Never create commits or PRs in automatic sync status mode.
8. **Validate after changes.** Run skill validation and targeted generated-file checks for any changed repository skills.

## Status Commands

Use commands like these as building blocks:

```bash
repo=/path/to/skills
local="${CODEX_HOME:-$HOME/.codex}/skills"
find "$repo/skills" -mindepth 2 -maxdepth 2 -name SKILL.md -print | sort
find "$local" -mindepth 1 -maxdepth 1 -print | sort
```

For symlink state:

```bash
for path in "$local"/*; do
  [ -e "$path" ] || continue
  if [ -L "$path" ]; then
    printf '%s -> %s\n' "$path" "$(readlink "$path")"
  fi
done
```

For copied skill comparison, prefer `diff -qr` with generated files excluded:

```bash
diff -qr \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.DS_Store' \
  "$repo/skills/<skill-name>" "$local/<skill-name>"
```

On macOS `diff` may not support all GNU options. If an exclude option fails, fall back to `rsync --dry-run --checksum --delete` or targeted `rg --files` comparisons.

## Periodic Use

For recurring audits, run `status` or `audit-access` only. A periodic automation should produce a report or open a thread; it should not install, delete, commit, push, or create PRs without a user-approved plan.
