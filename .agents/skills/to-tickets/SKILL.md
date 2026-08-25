---
name: to-tickets
description: Break a plan, SPEC.md, or the current conversation into a set of tracer-bullet tickets with explicit blocking edges, saved as files under `.agents/tasks/<number>/`.
---

# To Tickets

Break a plan, spec, or conversation into **tickets**: tracer-bullet vertical slices, each declaring the tickets that **block** it.

## Resolving the task and source

Determine the task number the same way as in `to-spec`. Pull context from wherever it exists: `.agents/tasks/<number>/SPEC.md` if present; an explicitly passed reference/path; otherwise the current conversation.

## Process

### 1. Gather context

Work from whatever is already in the conversation or in SPEC.md. If a reference is passed (a path, a task number), read it in full.

### 2. Explore the codebase (if needed)

Explore if you haven't already. Ticket titles and descriptions use the project's domain glossary and respect existing decisions in the area you're touching. Look for opportunities to prefactor the code to make the implementation easier: "make the change easy, then make the easy change."

### 3. Draft vertical slices

<vertical-slice-rules>

- Each slice cuts a narrow but COMPLETE path through every layer (schema, services, admin/UI, tests): vertical, not a horizontal slice of one layer.
- A completed slice is demoable or verifiable on its own.
- Each slice is sized to fit in a single fresh agent context window.
- Any prefactoring comes first, as its own slice.

</vertical-slice-rules>

Give each ticket its **blocking edges**: the other tickets that must complete before it can start. A ticket with no blockers can start immediately.

**Wide refactors are the exception to vertical slicing.** A wide refactor is one mechanical change (rename a column, retype a shared symbol) whose blast radius fans across the whole codebase, so a single edit breaks thousands of call sites at once and no vertical slice can land green. Don't force it into a tracer bullet — sequence it as expand–contract instead. First expand: add the new form beside the old so nothing breaks. Then migrate the call sites over in batches sized by blast radius (per package, per directory), each batch its own ticket blocked by the expand ticket, keeping things green batch to batch because the old form still exists. Finally contract: delete the old form once no caller remains, in a ticket blocked by every migration batch. When even the batches can't stay green alone, keep the sequence but let them share an integration branch that all block a final integrate-and-verify ticket — green is promised only there.

### 4. Check with the user

Present the proposed breakdown as a numbered list. For each ticket, show: **Title**, **Blocked by** (which other tickets, if any, must complete first), **What it delivers** (the end-to-end behavior this ticket makes work). Ask whether the granularity feels right (too coarse/too fine), whether the blocking edges are correct, and whether anything should be merged or split further. Iterate until the user approves the breakdown.

### 5. Write the tickets

Write one file per ticket under `.agents/tasks/<number>/`: `ticket-01-<slug>.md`, `ticket-02-<slug>.md`, ... numbered from 01 in dependency order (blockers first). Work the frontier: any ticket whose blockers are all done.

<ticket-template>

# <NN>: <Ticket title>

Task: LT-<number>[, spec: SPEC.md]

**What to build:** the end-to-end behavior this ticket makes work, from the user's or process's perspective — not a layer-by-layer implementation list.

**Blocked by:** the numbers/titles of the tickets that gate this one, or "None (can start immediately)".

**Context:** only when the task has no SPEC.md — brief facts about the code (entry points, file:line references, relevant models/services) needed to work this ticket.

**Status:** ready-for-agent

- [ ] Acceptance criterion 1
- [ ] Acceptance criterion 2

## Progress log

_(not started yet)_

</ticket-template>

Avoid specific file paths or code as part of the decision — they go stale fast. Exception: facts about existing code needed for orientation (see "Context" above).
