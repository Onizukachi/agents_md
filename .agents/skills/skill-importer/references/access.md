# Access Requirements

## Summary

- Required access: read access to the shared skills repository.
- Local credentials/config: git credentials if the repository is private.
- Local tools: `git`, `python3`, and either `ln` for symlink installs or `rsync`/`cp` for copy installs.
- Request from: Level Travel DevOps.

## Setup

1. Clone or locate the shared skills repository.
2. Ensure the repository can be read locally and is on the expected branch or commit.
3. Ensure the local Codex skills directory exists or can be created.

## Validation

Run:

```bash
git -C <repo> status --short --branch
test -f <repo>/skills/<skill-name>/SKILL.md
```

After install, verify the destination `SKILL.md` exists.
