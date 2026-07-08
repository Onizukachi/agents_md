---
name: leveltravel-frontend-asset-recovery
description: Use when LevelTravel frontend JS, templates, or frontend I18n changes do not appear after a browser hard reload and service restart. Covers the project asset recovery flow for clearing Rails cache, precompiling assets inside the Rails container, and restarting Rails and nginx.
---

# LevelTravel Frontend Asset Recovery

Use this skill when code changes are present in the repository but the browser still serves stale frontend assets.

This skill governs frontend asset recovery only. Do not make unrelated application changes merely because this skill loaded.

## Bootstrap LT CLI

Before any LT command on the host, load the helper:

```bash
source ./lt.sh
```

## Use This Recovery Flow

Use this only after both of these have already happened:

- a browser hard reload;
- a normal service restart.

Typical triggers:

- updated JS still does not execute;
- updated templates do not render;
- frontend I18n changes do not appear;
- compiled assets such as `manager/index.prod.js` still contain old code or translations.

## Recovery Commands

Run these commands in order:

```bash
docker exec lt.rails sh -lc 'bundle exec rake tmp:cache:clear'
docker exec lt.rails sh -lc 'RAILS_ENV=development bundle exec rails assets:precompile'
source ./lt.sh
lt restart rails && lt restart nginx
```

Keep the cache cleanup and asset precompile inside `lt.rails`. Host-side cleanup may miss the cache actually served by the container.

## Verification

After recovery:

- reload the target page again;
- confirm the new asset behavior is visible;
- if needed, inspect the compiled asset content inside the container to verify the new code was built.

If the page still serves stale behavior after this flow, treat it as a deeper application or asset pipeline issue rather than a simple cache problem.
