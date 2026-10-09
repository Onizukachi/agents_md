---
name: code-vs-spec
description: "Read-only review of a branch diff against the spec it was written from — what the spec asked for and is missing, what the diff adds that the spec never asked for, and what looks implemented but is implemented wrong. Use only when the user asks for a spec check of a branch that has a SPEC.md or tickets."
---

# Code vs Spec

Answer one question: **does this diff do what the spec asked for, and only that?**

This is not a correctness or production-risk review, and not a style review. Bugs, migrations, N+1, security, and conventions belong to other skills (`leveltravel-pr-review` in the LevelTravel repository, the built-in `code-review` and `simplify` elsewhere). Findings here are always anchored to a line of the spec.

Nothing is edited during this review, and this skill sets no gate — it reports, and the push/PR decision stays with the user and the repository's own review gate. Run it only when the user asks.

## Resolve The Spec

Determine the task number and `.agents/tasks/<number>/` path the same way `to-spec`/`to-tickets` do: an explicit number or path passed to this skill → otherwise parse `<TRACKER>-<number>` (for LevelTravel, `LT-<number>`) from the current git branch name → otherwise ask; never invent one.

Then look, in order:

1. `.agents/tasks/<number>/SPEC.md`
2. `.agents/tasks/<number>/ticket-*.md`, if there is no `SPEC.md`

Also note `.agents/tasks/<number>/PROGRESS.md` (or a ticket's "Progress log") if it exists: decisions rejected or changed during implementation supersede the spec text.

If neither a spec nor tickets exist, stop and say so. Without a spec this review has no subject — do not fall back to reviewing the diff "in general", and do not treat the branch name or commit messages as a spec.

## Resolve The Base

The base is the branch the PR targets, not the branch's own upstream (that would show only unpushed commits). Use, in order:

1. A base passed to this skill.
2. The base of the open PR for this branch: `gh pr view --json baseRefName -q .baseRefName`.
3. In LevelTravel, by branch name: `hotfix/<slug>` without a `-dev` suffix targets `master`; every other branch targets `develop`.
4. The remote's default branch: `git symbolic-ref --short refs/remotes/origin/HEAD`.

Then pin both ends so the review is reproducible. With `<branch>` being the base without the `origin/` prefix:

```bash
git fetch origin <branch>
git status --short --branch
BASE_SHA=$(git rev-parse origin/<branch>)
HEAD_SHA=$(git rev-parse HEAD)
git merge-base $BASE_SHA $HEAD_SHA
git diff --stat $BASE_SHA...$HEAD_SHA
git diff --name-only $BASE_SHA...$HEAD_SHA
git log $BASE_SHA..$HEAD_SHA --oneline
```

Always use the three-dot form: two-dot or plain `BASE HEAD` compares trees and drags in unrelated changes from the target branch. If the intended changes are still uncommitted, commit them first or state that this is a working-tree review; ignore unrelated dirty files.

## Run The Reviewer Pass

Spawn exactly **one** read-only subagent (an `Explore` agent, or any agent told not to edit files). The point is independence: the reviewer must not have watched the implementation being written, so it judges the diff on its own reading. Do not summarize or characterize the diff for it.

Hand it paths, not the spec text: specs can be 100 KB. Tell it which parts to read — `Scenarios`, `Implementation decisions`, `Testing decisions`, and `Out of scope` of `SPEC.md` (the rest only when a finding needs it), every `ticket-*.md` when there is no spec, and `PROGRESS.md` if present.

```text
Use the repository at <repo>. Review `git diff <BASE_SHA>...<HEAD_SHA>` (merge-base <merge-base>, commits: <commit list>, changed files: <file list>) against the spec at <path(s)>. Read the spec files, the diff, and the surrounding code yourself. Do not edit files.

Read in the spec: Scenarios, Implementation decisions, Testing decisions, Out of scope. Also read <PROGRESS.md path if any>: a decision recorded there as rejected or changed overrides the spec, so a rejected item is not MISSING.

Report only these:
- MISSING: a requirement the spec asked for that the diff does not implement, or implements only partially.
- UNASKED: behavior, abstraction, or scope in the diff that the spec never asked for. Anything listed under "Out of scope" that the diff does is UNASKED.
- WRONG: a requirement that looks implemented, but where the implementation does not do what the spec describes.
- SCENARIOS: one line per numbered scenario: implemented in code / covered by a test (as the spec's Testing decisions ask) / neither.

Quote the exact spec line for every MISSING, UNASKED, and WRONG finding, and give file:line from the diff. Say explicitly when a category has nothing. Do not report bugs, style, conventions, or performance unless the spec speaks to them. Prefer no finding over a speculative one. Under 500 words, not counting the SCENARIOS list.
```

If subagents are unavailable, do the same review in the main context, label it `local-only`, and note that the independent reading was lost.

## Output

Write the report in the user's language:

```markdown
## Code vs Spec
- Spec: `.agents/tasks/<number>/SPEC.md` (or the ticket files read); progress notes: <PROGRESS.md or none>
- Base: <base branch> @ <BASE_SHA>, head <HEAD_SHA>

### Missing
- <spec line> -> file:line, what is absent

### Unasked
- file:line, what the spec never asked for

### Wrong
- <spec line> -> file:line, how the implementation differs

### Scenarios
| # | Implemented | Tested |
|---|---|---|
| 1 | yes | yes |
```

State every empty category as empty rather than dropping its heading — "Unasked: none" is a result, and a silently missing section reads as an oversight.

Do not add a `PASS`/`BLOCKED` line. A gap against the spec is usually a decision to discuss (the spec may be the thing that is wrong), not a binary verdict.

For PR bodies in LevelTravel (written in Russian):

```markdown
## Соответствие спеке
- `code-vs-spec` против `.agents/tasks/<number>/SPEC.md`, база `<BASE_SHA>`, голова `<HEAD_SHA>`
- Не хватает / лишнее / неверно: нет, либо список выше с принятым решением
```
