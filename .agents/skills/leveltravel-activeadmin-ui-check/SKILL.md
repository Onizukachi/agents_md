---
name: leveltravel-activeadmin-ui-check
description: Use when checking or recovering LevelTravel ActiveAdmin pages in the local environment. Covers the page URL, login, telling "app is down" from "app error", recovering a 502, and reading Rails logs for a 500.
---

# LevelTravel ActiveAdmin UI Check

Use this skill to verify an ActiveAdmin page, reproduce an admin UI issue, or recover a page that returns `502`. Change application code only after the recovery steps below are exhausted.

## Facts

- Admin pages are at `https://leveltravel.dev/admin/<resource>` (for example `/admin/payment_logs`). `leveltravel.dev`, `manager.leveltravel.dev`, and `crm.leveltravel.dev` resolve to `127.0.0.1` through `/etc/hosts` and are served by the `lt.nginx` container, which proxies to Puma in `lt.rails`.
- An unauthenticated request is redirected (`302`) to `/users/login`. The login form has no prefilled credentials; the browser may autofill them and the button is `Войти`. Never guess credentials: if the form is empty, ask the user to log in.
- Rails logs go to stdout, not to `log/development.log`. Read them with `docker logs --tail 200 lt.rails`. Never use `lt logs`: it streams and blocks.

## Check

1. Status without a browser:

   ```bash
   curl -sk -o /dev/null -m 10 -w '%{http_code} %{redirect_url}\n' https://leveltravel.dev/admin/<resource>
   ```

   - `302` to `/users/login`: the app is up, only a login is needed.
   - `200`: the page loads (when a session cookie is sent).
   - `502`/`504`: nginx is up but Puma is down or still booting; go to Recover.
   - `500`: an application error; go to Diagnose.
   - `000`: nginx itself is down; run `lt start`.

2. Visual check: open the URL with the claude-in-chrome tools (`tabs_context_mcp` first, then a new tab, `navigate`, `get_page_text` or a screenshot). On the login page, let the user log in, then reload the target page.

## Recover a 502

1. `docker inspect lt.rails --format '{{.State.Health.Status}}'`. If it is `starting`, wait up to 60 seconds and re-check the page.
2. If `lt.rails` is `unhealthy` or the page is still `502`: `docker restart lt.rails`, wait for `healthy`, reload the page.
3. If the page is still `502` while `lt.rails` is `healthy`: `docker restart lt.nginx` (nginx resolves its upstreams at start and can keep a stale address after Rails was recreated), reload the page.
4. If it still fails, treat it as an application problem and diagnose.

## Diagnose a 500 or a failed boot

```bash
docker logs --tail 300 lt.rails | grep -n -E 'Completed 500|Error|Exception' | tail -20
```

Read the stack trace around the last match with `docker logs --tail 300 lt.rails | sed -n '<from>,<to>p'`. A transient `502` right after a restart is not evidence of a bug.
