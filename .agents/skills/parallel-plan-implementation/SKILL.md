---
name: parallel-plan-implementation
description: Deliver a LevelTravel development task through approved planning, dependency-aware parallel implementation, tests, and repeated independent reviews. Use for a full multi-agent delivery cycle, not for a quick isolated edit.
---

# Parallel Plan Implementation

Run a controlled delivery cycle. Preserve user authorization boundaries: planning requires approval before implementation; reviewers are read-only; do not push, open a PR, or change external state unless separately requested.

## Requested Profiles

- Main agent: `gpt-5.6-sol`, reasoning effort `xhigh`
- Implementor agents: `gpt-5.6-terra`, reasoning effort `xhigh`
- Reviewer agents: `gpt-5.6-sol`, reasoning effort `xhigh`
- Cross-reviewer: Claude CLI, `claude-sonnet-5`, reasoning effort `xhigh`

At the start, confirm the requested Codex profiles are available. Record requested and actual profiles in the task artifact. A fallback or profile substitution requires explicit user approval.

## 1. Plan and Approval

Use `implementation-planner`. It invokes `grill`, produces a task artifact, and stops for the user's explicit approval. Do not treat agreement with a summary as approval; ask directly whether to start implementation from the artifact.

If the user requests only planning, stop after the approved artifact.

## 2. Prepare Execution

Read the approved artifact and inspect the current worktree. Preserve unrelated changes. Before code changes, record one review base in the artifact's Execution context. Use `origin/develop` unless the approved task explicitly targets another base; both reviewers must use exactly this ref.

Use one implementor by default. Create multiple implementor agents only when the approved artifact proves that each work item is independently executable. Split work only where all of these are true:

- each item has a clear owner and file boundary;
- its dependency inputs and outputs are stated in the artifact;
- concurrent edits cannot conflict, including tests, schemas, routes, and shared configuration.

Always sequence migrations, shared models and contracts, routes and serializers, shared configuration/locales, and final integration tests. Keep shared files with one owner. Create one implementor agent per eligible independent item using the Implementor profile; give each the artifact path, owned paths, acceptance criteria, test expectations, and a direction not to alter unowned paths. Implement sequentially when boundaries are not safe.

Each implementor runs focused tests for its changed behavior. After integrating the work, the main agent runs the focused tests needed to prove the combined changed behavior and records their results. Relevant focused tests must pass before review, unless a failure is demonstrably pre-existing and documented. Migration workflow and PAPI v3 documentation are handled during implementation when the changed work requires them. Do not use destructive Git operations or force-push.

## 3. Independent Reviews

After implementation and integration are complete, run these reviewers independently:

1. Invoke `leveltravel-pr-review` using a Reviewer-profile Codex agent. It is read-only and reviews against the recorded review base.
2. Invoke `claude-review` through the local Claude CLI, supplying the same recorded base, approved artifact path, changed-file list, and test evidence. It is read-only and must receive none of the Codex review findings.

Use the repository's routed review skill where a more specific reviewer applies. Do not let either reviewer edit, commit, push, or create a PR.

## 4. Findings Loop

The main agent adjudicates each finding against code, plan, and tests:

- Normalize findings before adjudication: Codex `BLOCKER` is `critical`, Codex `CONCERN` is `medium`, and Codex `NIT` is `low`; Claude findings retain their reported severity.
- Fix confirmed `critical`, `high`, and `medium` findings.
- Document a finding as rejected only with concrete evidence that it is inapplicable or false.
- `LOW`/`NIT` findings do not block delivery unless the user asks otherwise.
- Add a focused regression test for each confirmed defect when practical.

After any code change, rerun relevant tests and both independent reviews. Repeat until neither review reports unresolved blocking findings. Limit the automated loop to three review rounds; if it reaches the limit, stop and ask the user to decide among the remaining disputed issues rather than claiming success.

## Completion Record

Report the approved artifact, actual agent profiles, implementation ownership, tests run and outcomes, both review outputs, fixed/rejected findings with evidence, and any remaining non-blocking concerns. The task is ready for review only after applicable repository Definition of Done conditions hold.
