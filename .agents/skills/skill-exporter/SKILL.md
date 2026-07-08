---
name: skill-exporter
description: Prepare local Codex skills for export into a shared skills repository. Use when Codex needs to copy or synchronize an installed skill into a repo, sanitize user-specific paths and local secrets, make commands portable across install locations, validate the skill, split unrelated exports into separate branches or pull requests, or review a skill for repository readiness.
---

# Skill Exporter

## Purpose

Use this skill to turn a locally installed Codex skill into a repository-ready artifact. The output should preserve useful workflow knowledge while removing assumptions tied to one developer's filesystem, credentials, shell setup, or installation path.

Before publishing changes, read `references/access.md` to check repository write and PR access requirements.

## Export Workflow

1. **Locate both copies.** Identify the source installed skill and the target repository skill directory. Do not assume `~/.codex/skills` or a specific repository path; use the user's provided paths, `CODEX_HOME`, git remotes, and local discovery.
2. **Inventory files.** List `SKILL.md`, `agents/openai.yaml`, and any `scripts/`, `references/`, or `assets/` files. Copy only files that directly support the skill.
3. **Compare before editing.** If the target skill already exists, inspect its diff and current branch before overwriting anything. Preserve unrelated user edits.
4. **Sanitize local coupling.** Replace user-specific paths, machine-specific install paths, personal usernames, local token file names, hardcoded app bundle paths, and stale endpoint assumptions with portable instructions, environment variables, or documented config files.
5. **Keep domain defaults explicit.** It is acceptable to keep company/service defaults such as internal hostnames, localhost ports, target names, data source ids, or default config locations when they are part of the workflow and can be overridden.
6. **Make commands location-independent.** Prefer commands relative to the skill directory such as `python3 scripts/tool.py`. If a command may run from another directory, say how to resolve the path instead of hardcoding the current installation.
7. **Document access requirements.** If the skill needs credentials, local auth, tunnels, API scopes, local tools, or service permissions, add `references/access.md` with required access, local config, setup, validation, and where to request access. If the request path is unknown, ask the user or skill owner instead of inventing it.
8. **Update repository metadata.** Add or refresh `agents/openai.yaml` and repository README entries so the exported skill is discoverable.
9. **Validate.** Run the skill validator, syntax checks for bundled scripts, `git diff --check`, and targeted searches for leaked local paths or stale auth flows.
10. **Review independently for risky exports.** Use a subagent or separate review pass to check portability and secret hygiene when the skill contains scripts, credentials, tunnels, API clients, or production-system instructions.
11. **Publish deliberately.** Group related changes into one branch or PR. Split unrelated skill exports into separate branches or PRs.

## Sanitization Checklist

Search the exported files for:

```bash
rg -n '(/Users/|/home/|C:\\\\Users\\\\|USER_NAME|~/.codex/skills|\\.codex/skills|token|secret|password|Authorization|Bearer|/Applications/|Library/Application Support)' <skill-dir> README.md
```

Treat matches as findings unless they are intentionally documented, configurable defaults. Redact or rewrite:

- absolute paths to the current developer's home or workspace;
- commands that only work from one local install path;
- local credential filenames when the exact filename is not essential;
- committed tokens, API keys, session ids, or copied command output containing secrets;
- local app bundle paths when `PATH` or an environment variable is sufficient;
- stale instructions that contradict the exported helper scripts.

Prefer these patterns:

- `CODEX_HOME` or "the installed skill directory" instead of a fixed Codex path;
- `python3 scripts/<name>.py` from the skill directory instead of `python3 ~/.codex/skills/...`;
- `*_CONFIG`, `*_TOKEN_FILE`, or `*_BIN` environment variables for machine-specific overrides;
- clear failure messages when local auth, tunnels, or credentials are missing.

## Repository Shape

An exported skill should normally contain:

```text
skills/<skill-name>/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── scripts/       # only when deterministic helpers are useful
└── references/    # only when detailed docs should load on demand
```

Keep `SKILL.md` concise and move long query templates, API references, or examples into `references/`. Do not add extra README, changelog, installation notes, or process notes inside the skill unless the repository already uses that convention.

## Access Requirements

If a skill touches non-public systems, create `references/access.md`:

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

Keep secrets out of the repository. Store only credential names, config file paths, environment variables, scopes, and request instructions. The `skill-importer` uses this file to tell the user what must be configured after installation.

## Validation Commands

Run the validator from the skill-creator skill when available:

```bash
python3 <skill-creator>/scripts/quick_validate.py <repo>/skills/<skill-name>
```

Run script checks for bundled code:

```bash
python3 -m py_compile <repo>/skills/<skill-name>/scripts/*.py
git -C <repo> diff --check
```

Run targeted leak searches over the changed skill and shared README. Tune the pattern to the skill's domain, then explain any intentional matches.

## Pull Request Scope

Before committing, inspect:

```bash
git -C <repo> status --short --branch
git -C <repo> diff --stat
```

Create separate PRs when exports are independent. For example, one PR may contain an existing skill's portability fixes plus this `skill-exporter` workflow skill, while another PR exports a separate API skill. Stage explicit files for each PR and avoid `git add -A` in mixed worktrees.
