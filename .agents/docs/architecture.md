# Architecture and File Placement

Use business names such as `Package`, `Hotel`, or `Order`, not generic technical placeholders such as `Data` or `Result`.

## Responsibilities

- Models: persistence, associations, validations, callbacks, and small domain behavior.
- Controllers: HTTP concerns only.
- Workers: background execution, orchestration, retries, and small worker-specific logic.
- Services: complex business operations, reusable workflows, and external integrations.
- Query objects: complex or reusable read-only data fetching.
- Decorators and serializers: presentation and API response formatting.

## File locations

| Code | Location |
|---|---|
| Main customer frontend | `../lt-frontend/apps/leveltravel/` |
| White-label customer frontend | `../lt-frontend/apps/wl/` |
| ActiveAdmin resources/controllers | `app/admin/` |
| External integrations | `app/apis/` |
| Query objects | `app/queries/` |
| Presentation formatting | `app/decorators/` |
| Business services | `app/services/` |
| Sidekiq workers | `app/workers/` |
| API serializers | `app/serializers/` |

Background jobs are Sidekiq workers in `app/workers/`, not ActiveJob classes; there is no `app/jobs/`.

Look for customer-facing frontend code in the adjacent `../lt-frontend/` repository first. Frontend code in this repository is current for the manager interface and ActiveAdmin, and also for the white-label checkout and payment step: it is still served from `client/lt-modules` (the `package_checkout` bundle), because `../lt-frontend/apps/wl` has no payment yet. Check which side serves a page before editing.
