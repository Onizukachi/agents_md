---
name: implement
description: Implement the work described by SPEC.md, tickets, or an agreed-upon conversation for a task under `.agents/tasks/<number>/`.
---

# Implement

Implement the work described by the spec or tickets.

## Resolving the task

Determine the task number the same way as in `to-spec`/`to-tickets`.

## Working order

If `.agents/tasks/<number>/` has tickets, work the frontier: take a ticket whose "Blocked by" list is fully satisfied. If there are no tickets (just a SPEC.md or an agreed-upon conversation), implement it as a single unit.

One ticket, one agent, sequentially. Do not spin up parallel implementor agents on different tickets of the same task.

Run focused tests for the changed behavior as you go, not just at the end. Use skill `leveltravel-migrations` for migrations and the conventions in `.agents/docs/rails-conventions.md`.

As you implement, append to the ticket file's "Progress log": what's done, what was tried and rejected and why, current state. Append — don't rewrite history as if the ticket had contained all these decisions from the start.

## Finishing

Once every ticket for the task is implemented and its focused tests are green, run the read-only `leveltravel-pr-review` once for the whole task (not per ticket). Handle its findings as usual.

Do not commit or push. That's a separate step the user requests explicitly (see `leveltravel-pr-workflow`).
