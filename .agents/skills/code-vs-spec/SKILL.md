---
name: code-vs-spec
description: "Read-only review of a branch diff against the spec it was written from — what the spec asked for and is missing, what the diff adds that the spec never asked for, and what looks implemented but is implemented wrong. Use before pushing or updating a PR for a task that has a SPEC.md or tickets."
---

# Code vs Spec

Answer one question: **does this diff do what the spec asked for, and only that?**

This is not a correctness or production-risk review, and not a style review. Bugs, migrations, N+1, security, and conventions belong to other skills (`leveltravel-pr-review` in the LevelTravel repository, the built-in `code-review` and `simplify` elsewhere). Findings here are always anchored to a line of the spec.

Nothing is edited during this review, and this skill sets no gate — it reports, and the push/PR decision stays with whatever review gate the repository already has.

## Resolve The Spec

Determine the task number and `.agents/tasks/<number>/` path the same way `to-spec`/`to-tickets` do: an explicit number or path passed to this skill → otherwise parse `<TRACKER>-<number>` (for LevelTravel, `LT-<number>`) from the current git branch name → otherwise ask; never invent one.

Then look, in order:

1. `.agents/tasks/<number>/SPEC.md`
2. `.agents/tasks/<number>/ticket-*.md`, if there is no `SPEC.md`

Read every file found; tickets are reviewed as a set, not one at a time.

If neither exists, stop and say so. Without a spec this review has no subject — do not fall back to reviewing the diff "in general", and do not treat the branch name or commit messages as a spec.

## Resolve The Base

Use, in order: a base passed to this skill → the current branch's upstream (`git rev-parse --abbrev-ref '@{upstream}'`) → `origin/develop` → `origin/main`.

Nothing here is language- or framework-specific; this skill works in any repository that keeps specs under `.agents/tasks/`.

## Gather Context

```bash
git fetch origin <base-branch>
git status --short --branch
git diff --stat <base>...HEAD
git diff --name-only <base>...HEAD
git log <base>..HEAD --oneline
```

If intended changes are still uncommitted, either commit them first or state that this is a working-tree review. Ignore unrelated dirty files.

## Run The Reviewer Pass

Spawn exactly **one** read-only subagent. The point is independence: the reviewer must not have watched the implementation being written, so it judges the diff on its own reading rather than on the story behind it. Do not summarize or characterize the diff for it — hand it the spec and the file list and let it read the code itself.

```text
Use the repository at <repo>. Review <base>...HEAD (commits: <commit list>, changed files: <file list>) against the spec below. Read the diff and the surrounding code yourself. Do not edit files.

<full contents of SPEC.md and/or every ticket-*.md>

Report only these three things:
- MISSING: a requirement the spec asked for that the diff does not implement, or implements only partially.
- UNASKED: behavior, abstraction, or scope in the diff that the spec never asked for.
- WRONG: a requirement that looks implemented, but where the implementation does not do what the spec describes.

Quote the exact spec line for every finding, and give file:line from the diff. Say explicitly when a category has nothing. Do not report bugs, style, conventions, or performance unless the spec speaks to them. Prefer no finding over a speculative one. Under 400 words.
```

If subagents are unavailable, do the same review in the main context, label it `local-only`, and note that the independent reading was lost.

## Output

```markdown
## Code vs Spec
- Spec: `.agents/tasks/<number>/SPEC.md` (or the ticket files read)
- Base: <base>

### Missing
- <spec line> -> file:line, what is absent

### Unasked
- file:line, what the spec never asked for

### Wrong
- <spec line> -> file:line, how the implementation differs
```

State every empty category as empty rather than dropping its heading — "Unasked: none" is a result, and a silently missing section reads as an oversight.

Do not add a `PASS`/`BLOCKED` line. A gap against the spec is usually a decision to discuss (the spec may be the thing that is wrong), not a binary verdict.

For PR bodies:

```markdown
## Spec conformance
- `code-vs-spec` against `.agents/tasks/<number>/SPEC.md`
- Missing / unasked / wrong: none, or listed above with the decision taken
```
