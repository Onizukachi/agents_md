---
name: claude-review
description: Run an independent, read-only Claude Code review of a LevelTravel diff against an approved plan, returning structured findings for a Codex delivery loop. Use only when explicitly requested by a delivery workflow or user.
---

# Claude Cross-Review

This is an independent cross-review, adapted from the two-axis Standards/Spec approach in `mattpocock/skills`' `code-review` skill. It runs one Claude reviewer, not internal reviewer subagents, and never edits the repository.

## Inputs

Require both inputs:

- `--base <git-ref>`: the branch, tag, or commit used for `git diff <base>...HEAD`;
- `--plan <path>`: the explicitly approved task artifact.

Resolve the base and confirm the diff is non-empty before launching Claude. Gather the changed-file list, commit list, test commands/results, relevant repository standards, and the approved plan. Do not include findings from other reviewers.

## Run Claude

When running under **Codex**, invoke the locally discovered Claude slash-skill with the requested profile and structured schema. Keep the session read-only; use an appropriate read-only permission/tool policy available in the installed Claude CLI.

```bash
claude -p "/claude-review --base <base> --plan <plan-path>" \
  --model claude-sonnet-5 \
  --effort xhigh \
  --permission-mode plan \
  --output-format json \
  --json-schema '<schema below>'
```

The prompt context must instruct Claude to inspect the diff and adjacent code itself, follow `AGENTS.md` and `CLAUDE.md`, and assess these separate axes:

- **Spec:** approved-plan requirements that are missing, partial, incorrectly implemented, or exceeded;
- **Standards and operational safety:** concrete regression risks, Rails behavior, migrations and rollout, Sidekiq idempotency, N+1/query behavior, external contracts, nil/input handling, security, and missing meaningful tests.

Do not report style-only preferences. Findings need changed-code evidence or directly affected context. Claude must not make changes, commits, or network mutations.

Use this JSON Schema with `--json-schema`:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["verdict", "summary", "findings", "positive_checks", "unverified_areas"],
  "properties": {
    "verdict": {"type": "string", "enum": ["approve", "changes_requested", "blocked"]},
    "summary": {"type": "string"},
    "findings": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["severity", "confidence", "category", "file", "line", "title", "evidence", "impact", "recommendation"],
        "properties": {
          "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
          "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
          "category": {"type": "string", "enum": ["spec", "regression", "security", "data", "concurrency", "test", "convention"]},
          "file": {"type": "string"},
          "line": {"type": "integer", "minimum": 1},
          "title": {"type": "string"},
          "evidence": {"type": "string"},
          "impact": {"type": "string"},
          "recommendation": {"type": "string"}
        }
      }
    },
    "positive_checks": {"type": "array", "items": {"type": "string"}},
    "unverified_areas": {"type": "array", "items": {"type": "string"}}
  }
}
```

`--output-format json` wraps Claude's response; parse its result content and validate it against the schema before acting on findings. A malformed result is a blocked review, not an approval.

When running under **Claude Code** because this slash-skill was invoked, do not start another `claude` process. Use the supplied `--base` and `--plan`, inspect the repository read-only, and emit exactly the object defined by the schema. The outer Codex caller will collect it.

## Handoff

Return the raw Claude result and normalized findings to the calling agent. The caller, not Claude, adjudicates and fixes findings. A `critical`, `high`, or `medium` finding remains unresolved until it is fixed or rejected with evidence.
