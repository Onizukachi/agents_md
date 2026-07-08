# Access Requirements

## Summary

- Required access: read access to the shared skills repository for status/pull; write and PR permissions only for export workflows.
- Local credentials/config: git credentials for private repository access; authenticated `gh` only when creating PRs.
- Local tools: `git`, `python3`, `diff`, and optionally `rsync`.
- Request from: Level Travel DevOps.

## Setup

1. Clone or locate the shared skills repository.
2. Ensure local Codex skills are discoverable through `${CODEX_HOME:-$HOME/.codex}/skills` or a user-provided path.
3. Install `skill-importer` and `skill-exporter` when the syncer needs to execute import or export actions.

## Validation

Run read-only status checks first:

```bash
git -C <repo> status --short --branch
find "${CODEX_HOME:-$HOME/.codex}/skills" -mindepth 1 -maxdepth 1 -print
```

Do not install, delete, commit, push, or create PRs from a periodic sync without a user-approved plan.
