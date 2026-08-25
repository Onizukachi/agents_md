#!/usr/bin/env bash
# One-time cleanup for machines still holding symlinks from the old
# git@github.com:LevelTravel/skills.git checkout in ~/.codex/skills and
# ~/.claude/skills. `lt-skills sync` now installs those same skills as
# managed copies instead, but it will not adopt a symlink into a git
# checkout — it just skips it — so the stale link has to go first.
#
# Usage: scripts/migrate_shared_skills_to_lt_skills.sh [--sync]
#   --sync  also run `lt-skills sync --all` afterward to reinstall
#           whatever was just removed, as managed copies.

set -euo pipefail

codex_root="${CODEX_HOME:-$HOME/.codex}"
claude_root="${CLAUDE_HOME:-$HOME/.claude}"

removed=0
for root in "$codex_root/skills" "$claude_root/skills"; do
  test -d "$root" || continue
  for entry in "$root"/*; do
    test -L "$entry" || continue
    target="$(readlink "$entry")"
    test -d "$target" || continue
    remote="$(git -C "$target" remote get-url origin 2>/dev/null || true)"
    case "$remote" in
    *LevelTravel/skills.git)
      echo "removing $entry -> $target"
      rm -f "$entry"
      removed=$((removed + 1))
      ;;
    esac
  done
done

echo "removed $removed stale symlink(s)"

if [ "${1:-}" = "--sync" ]; then
  command -v lt-skills >/dev/null ||
    { echo "lt-skills not found; install it, then run: lt-skills sync --all" >&2; exit 1; }
  lt-skills sync --all
fi
