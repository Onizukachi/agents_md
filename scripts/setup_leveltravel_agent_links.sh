#!/usr/bin/env bash

set -euo pipefail

agent_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
project_root="${1:-$agent_root/../leveltravel}"
codex_root="${CODEX_HOME:-$HOME/.codex}"
claude_root="${CLAUDE_HOME:-$HOME/.claude}"

personal_skills=(
  'leveltravel-migrations'
  'leveltravel-frontend-asset-recovery'
  'leveltravel-activeadmin-ui-check'
)

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

mkdir -p "$codex_root/skills"
mkdir -p "$claude_root/skills"
for skill in "${personal_skills[@]}"; do
  link_if_missing "$agent_root/.agents/skills/$skill" "$codex_root/skills/$skill"
  link_if_missing "$agent_root/.agents/skills/$skill" "$claude_root/skills/$skill"
done

echo 'setup-leveltravel-agent-links: links are ready'
