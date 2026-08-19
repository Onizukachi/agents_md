#!/usr/bin/env bash

set -euo pipefail

agent_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
project_root="${1:-$agent_root/../leveltravel}"
codex_root="${CODEX_HOME:-$HOME/.codex}"
claude_root="${CLAUDE_HOME:-$HOME/.claude}"
skills_root="${SKILLS_REPO:-$agent_root/../skills}"

die() {
  echo "setup-leveltravel-agent-links: $*" >&2
  exit 1
}

link_if_missing() {
  local target="$1"
  local destination="$2"

  if test -L "$destination"; then
    test "$(readlink "$destination")" = "$target" ||
      die "$destination points to $(readlink "$destination"), expected $target"
    return
  fi

  test ! -e "$destination" || die "$destination already exists; move it aside after inspection"
  ln -s "$target" "$destination"
}

exclude_if_missing() {
  local pattern="$1"
  local exclude_file="$project_root/.git/info/exclude"

  mkdir -p "$(dirname "$exclude_file")"
  test -e "$exclude_file" || : >"$exclude_file"
  grep -qxF "$pattern" "$exclude_file" || printf '%s\n' "$pattern" >>"$exclude_file"
}

test -d "$project_root/.git" || die "not a LevelTravel checkout: $project_root"

link_if_missing '../agents_md/AGENTS.md' "$project_root/AGENTS.md"
link_if_missing 'AGENTS.md' "$project_root/CLAUDE.md"
link_if_missing '../agents_md/CONTEXT.md' "$project_root/CONTEXT.md"
mkdir -p "$project_root/.agents"
link_if_missing '../../agents_md/.agents/docs' "$project_root/.agents/docs"
link_if_missing '../../agents_md/.agents/tasks' "$project_root/.agents/tasks"

# Mirror the project's own tracked skills (.agents/skills/*, committed to the
# LevelTravel repository) into .claude/skills, so Claude Code discovers them
# the same way Codex already does by scanning .agents/skills directly.
mkdir -p "$project_root/.claude/skills"
if [ -d "$project_root/.agents/skills" ]; then
  for project_skill in "$project_root/.agents/skills"/*; do
    test -e "$project_skill" || continue
    skill_name="$(basename "$project_skill")"
    link_if_missing "../../.agents/skills/$skill_name" "$project_root/.claude/skills/$skill_name"
  done
fi

# Every link created inside the checkout above is machine-local and must never be
# committed, so keep it out of `git status` through the repository's local exclude
# file rather than through a tracked .gitignore.
exclude_if_missing '/AGENTS.md'
exclude_if_missing '/CLAUDE.md'
exclude_if_missing '/CONTEXT.md'
exclude_if_missing '/.agents/docs'
exclude_if_missing '/.agents/tasks'
exclude_if_missing '/.claude/skills'

mkdir -p "$codex_root/skills"
mkdir -p "$claude_root/skills"
if [ -d "$agent_root/.agents/skills" ]; then
  for personal_skill in "$agent_root/.agents/skills"/*; do
    test -e "$personal_skill" || continue
    skill_name="$(basename "$personal_skill")"
    link_if_missing "$personal_skill" "$codex_root/skills/$skill_name"
  done
fi

# Shared skills live in their own checkout (git@github.com:LevelTravel/skills.git).
# Link everything it publishes: the repository is the single source of truth, so no
# per-skill list is maintained here and a new shared skill needs only a git pull.
# Without this, shared skills were reachable only through skill-importer, which is
# itself a shared skill and therefore unavailable on a fresh machine.
if [ -d "$skills_root/skills" ]; then
  for shared_skill in "$skills_root/skills"/*; do
    test -f "$shared_skill/SKILL.md" || continue
    skill_name="$(basename "$shared_skill")"
    link_if_missing "$(cd "$shared_skill" && pwd -P)" "$codex_root/skills/$skill_name"
  done
else
  echo "setup-leveltravel-agent-links: no shared skills checkout at $skills_root, skipping shared skills" >&2
fi

# Mirror every skill available to Codex (personal and shared above, plus anything
# installed by hand) into Claude Code too, so both runtimes discover the same set
# without a second per-skill list to maintain. Copied skills are linked by path,
# not just symlinked ones. Codex's own `.system` skills stay out: the glob skips
# dotted names.
for codex_skill in "$codex_root/skills"/*; do
  test -d "$codex_skill" || continue
  skill_name="$(basename "$codex_skill")"
  if test -L "$codex_skill"; then
    mirror_target="$(readlink "$codex_skill")"
  else
    mirror_target="$codex_skill"
  fi
  link_if_missing "$mirror_target" "$claude_root/skills/$skill_name"
done

echo 'setup-leveltravel-agent-links: links are ready'
