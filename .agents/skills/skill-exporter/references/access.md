# Access Requirements

## Summary

- Required access: read access to the local installed skill, write access to the target skills repository, and GitHub push/PR permissions when publishing.
- Local credentials/config: authenticated `git`/`gh` session for the target repository when creating branches or pull requests.
- Local tools: `git`, optional `gh`, `python3` for skill validation.
- Request from: Level Travel DevOps.

## Setup

1. Ensure the target skills repository is cloned locally.
2. Ensure the current git identity and remote allow branch pushes.
3. Authenticate `gh` if the workflow should open pull requests.

## Validation

Run:

```bash
git -C <repo> status --short --branch
```

Run `gh auth status` only when the workflow needs to create or inspect GitHub pull requests. Do not publish changes until the intended PR scope is clear.
