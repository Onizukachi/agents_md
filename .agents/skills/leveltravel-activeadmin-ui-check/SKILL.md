---
name: leveltravel-activeadmin-ui-check
description: Use when checking or recovering LevelTravel ActiveAdmin pages in the browser. Covers the project workflow for opening the page, handling login, retrying after 502 errors, restarting Rails and nginx, and falling back to Rails logs for diagnosis.
---

# LevelTravel ActiveAdmin UI Check

Use this skill when the user asks to verify an ActiveAdmin page, reproduce an admin UI issue, or recover an admin page that may return `502 Bad Gateway`.

This skill governs the UI-check workflow only. Diagnose and fix application issues only after the page recovery steps have been exhausted.

## Bootstrap LT CLI

Before any LT command on the host, load the helper:

```bash
source ./lt.sh
```

## UI Check Workflow

Follow this order:

1. Start Rails logs:
```bash
lt logs rails
```

2. Open the target ActiveAdmin page directly.
Example:
```text
https://leveltravel.dev/admin/payment_logs
```

3. If authentication is required, click `Войти`. Credentials are expected to be prefilled.

4. If the page returns `502 Bad Gateway`, reload it and wait up to 20 seconds.

5. If the page is still unavailable after that wait, restart services:
```bash
lt restart rails && lt restart nginx
```

6. Reload the page again and wait up to 20 seconds.

7. If the page still fails after the restart, treat it as an application error and use Rails logs to diagnose the failure.

## Diagnosis Boundary

Do not jump to code changes before this recovery loop finishes. A transient `502` is not enough evidence of an application bug.

Only after the page remains broken after reload and restart should the task become a real Rails investigation.
