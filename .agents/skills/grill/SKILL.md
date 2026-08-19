---
name: grill
description: Propose and run a short alignment interview before starting a large or ambiguous task - a new feature spanning multiple models/services, a payments/schema/PAPI v3 change, or requirements with more than one reasonable reading. Ask in rounds, dig up facts yourself, stop once every open branch is resolved.
---

# Grill

A short, rounds-based interview to align on scope before code gets written. Use it as a **gate**, not a mandate - most tasks don't need it.

## When to reach for it

Offer a grill round when the task has any of:

- A new feature or flow spanning more than one model/service/worker/controller.
- A change to payments, the order/receipt flow, database schema, or a PAPI v3 route/contract.
- Requirements with more than one reasonable interpretation.
- Scope large enough that an assumption made now is expensive to unwind later.

Skip it for focused bug fixes, small tweaks, or a task the user already specified precisely (exact files, exact behavior).

## Propose first, don't just start

If the user didn't explicitly ask for a grill session, don't launch straight into rounds of questions. In one or two sentences, say why the task looks big or ambiguous and ask whether they want a short alignment pass first, e.g.:

> "This touches both the payment callback flow and the receipt worker - a couple of decisions here are expensive to reverse. Want a quick round of questions before I start, or should I go with my best judgment?"

If they decline or are AFK, proceed with your best judgment per the project's default working mode. If they agree, or if they invoked this skill directly, run the interview below.

## The interview

Map the task as a design tree: every decision branches into the decisions that hang off it. The **frontier** is every decision whose prerequisites are already settled - the questions answerable right now without guessing at ones you haven't heard back on yet.

Work it in rounds:

1. Ask the whole current frontier in one round, numbered, each with your recommended answer:

   ```
   ❓ Q1 - <question title>: <question body>
   ➡️ <your recommended answer>
   ```

2. Wait for the user's answers before asking anything else.
3. Recompute the frontier - settled answers unblock the next layer of questions.
4. Repeat until the frontier is empty.

A question whose answer depends on another still-open question belongs to a later round, not this one.

Finding facts is your job, never the user's. If a frontier question needs something you could look up yourself - existing code, `.agents/docs/payments.md`, `.agents/docs/papi_v3_docs.md`, a Yandex Wiki page, a past PR - go get it, dispatching a sub-agent for a real search. Only put genuine decisions to the user, never facts you could have found on your own.

## Closing out

The session is done when the frontier is empty - every branch resolved, nothing silently assumed. Summarize the resolved decisions in a few lines, then move into implementation.

This skill's job is alignment, not documentation - write a `.agents/tasks/task-<number>.md` artifact only if the user explicitly asks for one.
