# Access Requirements

## Summary

- Required access: permission to read and create issues in the LevelTravel Yandex Tracker organization.
- Local credentials/config: the configuration required by the installed `yandex-tracker` skill.
- Local tools: Python 3 and the installed `yandex-tracker` skill.
- Request from: Level Travel DevOps.

## Setup

1. Install both `integration-task` and `yandex-tracker` in the same Codex skills directory.
2. Follow the setup instructions in the `yandex-tracker` skill.
3. Keep Tracker credentials outside this repository.

## Validation

Resolve the shared Tracker helper and inspect its configuration:

```bash
TRACKER_HELPER="${CODEX_HOME:-$HOME/.codex}/skills/yandex-tracker/scripts/tracker.py"
python3 "$TRACKER_HELPER" config
```
