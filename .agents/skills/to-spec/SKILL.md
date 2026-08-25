---
name: to-spec
description: "Turn the current conversation into a SPEC.md for the task under `.agents/tasks/<number>/`: no interview, just synthesis of what's already been discussed."
---

# To Spec

Take the current conversation context and codebase understanding and produce a spec. Do NOT interview the user; just synthesize what you already know. If something remains unclear and blocks the spec, use skill `grill` first.

## Resolving the task

Determine the task number and the `.agents/tasks/<number>/` path: an explicit number/path passed in → otherwise parse `LT-<number>` from the current git branch name → otherwise ask the user; never invent one.

## Process

1. Explore the repo to understand the current state of the codebase, if you haven't already. Use the project's domain glossary (`CONTEXT.md`) throughout, and respect existing decisions in the area you're touching.
2. Sketch out the seams at which you're going to test the feature. Prefer existing seams to new ones, at the highest level possible. Fewer seams is better — the ideal is one. Check with the user that these seams match their expectations.
3. Write the spec using the template below to `.agents/tasks/<number>/SPEC.md`.

<spec-template>

# <Task title>

## Problem

The problem, from the perspective of the user or process depending on it.

## Solution

The solution, from the same perspective.

## Current system state

Facts established from the code: entry points, file:line references, the models/services/workers/integrations involved. This is discovery, not a future contract — specific paths and lines belong here and don't go stale as long as the code doesn't change.

## Usage scenarios

A numbered list: "As a `<actor>`, I want `<feature>`, so that `<benefit>`." The actor doesn't have to be an end user — it can be an internal role, process, or worker (e.g. "As the accountant...", "As the registry-processing worker..."). As many scenarios as needed to cover the distinct kinds of behavior — no padding for length.

## Implementation decisions

Modules to be built or changed; their interfaces; technical clarifications; architectural decisions; schema changes; contracts. Do NOT encode specific file paths or code as part of a forward-looking decision — they go stale. If a path/snippet is really an existing fact rather than a decision, it belongs in "Current system state" instead.

## Testing decisions

What makes a good test here (external behavior only, not implementation details); which modules will be tested; prior art — similar tests already in the codebase.

## Out of scope

What's explicitly excluded.

## Further notes

Anything else worth recording.

</spec-template>
