#!/usr/bin/env bash

set -euo pipefail

agent_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
project_root="${1:-$agent_root/../leveltravel}"
codex_root="${CODEX_HOME:-$HOME/.codex}"
claude_root="${CLAUDE_HOME:-$HOME/.claude}"

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

# Personal skills (this checkout) go straight into both runtimes. Registry-distributed
# skills (integration-*, mm-gateway, yandex-*, etc.) are installed and kept current by
# `lt-skills sync` instead, which writes its own copies into both directories below —
# this script must not symlink or otherwise manage them.
mkdir -p "$codex_root/skills"
mkdir -p "$claude_root/skills"
if [ -d "$agent_root/.agents/skills" ]; then
  for personal_skill in "$agent_root/.agents/skills"/*; do
    test -e "$personal_skill" || continue
    skill_name="$(basename "$personal_skill")"
    link_if_missing "$personal_skill" "$codex_root/skills/$skill_name"
    link_if_missing "$personal_skill" "$claude_root/skills/$skill_name"
  done
fi

echo 'setup-leveltravel-agent-links: links are ready'
