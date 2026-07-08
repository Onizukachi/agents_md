# Access Requirements

## Summary

- Required access: Yandex Tracker API access for the Level Travel organization and enough issue/board permissions for the requested operation.
- Local credentials/config: `YANDEX_TRACKER_TOKEN`, `YANDEX_TRACKER_ORG_ID`, auth type, and org header stored in `~/.yandex-tracker.env` or passed through environment variables.
- Local tools: `python3`.
- Request from: create a personal OAuth token through the official Yandex documentation; use Tracker permissions for the Level Travel organization.

## Setup

1. Create a personal OAuth token using the official Yandex documentation, or obtain an IAM token when the organization requires IAM.
2. Obtain the organization id and the correct organization header type: `X-Org-ID` for OAuth or `X-Cloud-Org-ID` for IAM.
3. From the installed `yandex-tracker` skill, run `tracker.py setup` with the token and org id.
4. Configure defaults such as user name, user email, and default boards when the user wants "my tasks" or board summaries to work without repeated parameters.

## Validation

Run the non-secret config check:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/yandex-tracker/scripts/tracker.py" config
```

Then run a small read-only request such as an issue lookup or board status command. Do not print or paste stored tokens.
