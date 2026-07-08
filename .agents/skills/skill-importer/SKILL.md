---
name: skill-importer
description: Install or update Codex skills from a shared skills repository into a local Codex skills directory. Use when Codex needs to find a repository skill, inspect its access requirements, install it by symlink or copy, update an existing local skill, avoid overwriting local edits, or tell the user which credentials and permissions are needed after installation.
---

# Skill Importer

## Purpose

Use this skill to install repository-managed skills into the local Codex skills directory. The importer must also surface the skill's access requirements so the user knows which credentials, accounts, tunnels, or permissions must be prepared before the skill can actually be used.

Before importing from a private repository, read `references/access.md` to check repository read access requirements.

## Import Workflow

1. **Locate the repository.** Use the user's provided path first. If absent, search common local checkouts and confirm the git remote points to the expected shared skills repository.
2. **Select the skill.** Verify `skills/<skill-name>/SKILL.md` exists and the frontmatter `name` matches the folder.
3. **Read access requirements.** If `references/access.md` exists, read it before installing and summarize required credentials, local tools, config files, and request path. If it is missing, warn that access metadata is absent.
4. **Choose install mode.** Prefer symlink for active development, copy for stable local use or when the repository path may move. Use the mode requested by the user if they specify one.
5. **Resolve destination.** Install into `${CODEX_HOME:-$HOME/.codex}/skills/<skill-name>` unless the user gives another Codex skills directory.
6. **Protect local edits.** If the destination exists, inspect whether it is a symlink, copied directory, or modified local skill. Do not overwrite it blindly. Compare `SKILL.md` and resource files, then ask before replacing non-symlink local edits.
7. **Install atomically.** For symlink mode, create or update the symlink to the repository skill directory. For copy mode, copy only the skill directory contents and exclude generated files such as `__pycache__`, `.pyc`, `.DS_Store`, local logs, and temp files.
8. **Validate after install.** Confirm `SKILL.md` exists at the destination and run the skill validator when available.
9. **Report next steps.** Tell the user what was installed, where it points, which access requirements remain, and whether the skill may require Codex UI/thread reload before it appears in automatic skill discovery.

## Access Metadata

Repository skills should document setup in `references/access.md`. Use this shape:

```markdown
# Access Requirements

## Summary

- Required access: ...
- Local credentials/config: ...
- Local tools: ...
- Request from: ...

## Setup

1. ...

## Validation

...
```

When importing, read this file and report:

- whether the user already appears to have the required local files/tools;
- which credentials must be created manually;
- where the user should request access;
- any safe validation command that does not reveal secrets.

Do not create, print, or request secrets in chat. Ask the user to create local config files or run setup commands on their machine when needed.

## Commands

Use shell commands like these, adjusted to the actual repository and destination paths:

```bash
repo=/path/to/skills
skill=skill-name
dest="${CODEX_HOME:-$HOME/.codex}/skills/$skill"
test -f "$repo/skills/$skill/SKILL.md"
```

Symlink install:

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
if [ -e "$dest" ] && [ ! -L "$dest" ]; then
  echo "Refusing to replace non-symlink destination: $dest" >&2
  exit 1
fi
ln -sfn "$repo/skills/$skill" "$dest"
```

Copy install:

```bash
if [ -e "$dest" ]; then
  echo "Destination already exists; inspect diff before copy: $dest" >&2
  exit 1
fi
mkdir -p "$dest"
rsync -a --delete \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  "$repo/skills/$skill/" "$dest/"
```

Use `cp -R` only when `rsync` is unavailable and the skill has no generated files to exclude. If the destination already exists, compare first and ask for explicit approval before using `rsync --delete`.
