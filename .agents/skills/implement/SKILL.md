---
name: implement
description: Implement the work described by a SPEC.md or an agreed-upon conversation for a task under `.agents/tasks/<number>/`.
---

# Implement

Implement the work described by the spec, or by the agreed-upon conversation when there is no spec.

## Resolving the task

Determine the task number the same way as in `to-spec`.

## Working order

Implement the work as a single unit. Do not spin up parallel implementor agents on the same task.

Run focused tests for the changed behavior as you go, not just at the end. Use skill `leveltravel-migrations` for migrations and the conventions in `.agents/docs/rails-conventions.md`.

## Progress log

As you implement, append to `.agents/tasks/<number>/PROGRESS.md` (create it if missing): what's done, what was tried and rejected and why, current state. Append — don't rewrite history as if the spec had contained all these decisions from the start.

Record every decision that deviates from the spec under a `Rejected / changed` heading. `code-vs-spec` reads that file and treats those items as overriding the spec, so an unrecorded deviation looks like a missing requirement.

## Finishing

Stop once the spec is implemented and its focused tests are green. Do not commit or push, and do not run `leveltravel-pr-review` here: the review gate runs once, on the committed head, as part of `leveltravel-pr-workflow`.
