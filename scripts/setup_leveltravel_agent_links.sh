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

test -d "$project_root/.git" || die "not a LevelTravel checkout: $project_root"

link_if_missing '../agents_md/AGENTS.md' "$project_root/AGENTS.md"
link_if_missing 'AGENTS.md' "$project_root/CLAUDE.md"
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

mkdir -p "$codex_root/skills"
mkdir -p "$claude_root/skills"
if [ -d "$agent_root/.agents/skills" ]; then
  for personal_skill in "$agent_root/.agents/skills"/*; do
    test -e "$personal_skill" || continue
    skill_name="$(basename "$personal_skill")"
    link_if_missing "$personal_skill" "$codex_root/skills/$skill_name"
  done
fi

# Mirror every skill already symlinked into Codex (personal skills above, plus
# any shared skill installed via skill-importer) into Claude Code too, so both
# runtimes discover the same set without a second per-skill list to maintain.
for codex_skill in "$codex_root/skills"/*; do
  test -L "$codex_skill" || continue
  skill_name="$(basename "$codex_skill")"
  link_if_missing "$(readlink "$codex_skill")" "$claude_root/skills/$skill_name"
done

echo 'setup-leveltravel-agent-links: links are ready'
