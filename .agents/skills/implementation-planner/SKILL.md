---
name: implementation-planner
description: Turn a development request into an explicitly approved implementation plan and task artifact. Use before implementation when the scope, behavior, or technical decisions need agreement.
---

# Implementation Planner

Create an approved, executable plan; do not implement it.

## Discovery

1. Invoke `grill` and follow its interview process through to a shared understanding. It is responsible for resolving domain vocabulary and updating `CONTEXT.md` where appropriate.
2. Find facts from the repository, documentation, and available tools rather than asking the user for discoverable information.
3. When the design frontier is empty, create the task artifact as a draft, summarize it, and ask the user to approve that artifact. Do not start implementation before explicit approval.

## Task Artifact

Create the requested draft artifact under `.agents/tasks/task-<number>.md`. If no task number or destination was supplied, ask for it before creating a durable artifact; do not invent one. After explicit approval, update its approval status and record the approval evidence.

The artifact must be concise but implementation-ready:

```markdown
# <task title>

## Approval
- Status: Draft | Approved
- Evidence: <user message/date once approved>

## Goal
<observable client or system outcome>

## Non-goals
- <out of scope>

## Decisions
- <confirmed product or technical decision>

## Implementation plan
1. <ordered step, owned files/components, expected behavior>

## Parallelization boundaries
- <work item>: <owner>, files it owns, dependencies, public contract

## Acceptance criteria
- [ ] <observable behavior>

## Verification
- <focused tests/checks>

## Execution context
- Review base: <target branch/ref>
- Branch/commit at approval: <ref>
- Requested/actual profiles: <filled by delivery orchestrator>

## Risks and rollout
- <migration, compatibility, job, or integration consideration>
```

Only include parallel work items when their ownership boundaries are real. List shared files and integration order explicitly; an empty parallelization section is valid.

Finish by reporting the artifact path, approval status/evidence, verification plan, and any unresolved decision. The caller decides whether to begin implementation.
