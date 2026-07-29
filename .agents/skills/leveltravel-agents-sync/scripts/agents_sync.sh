#!/usr/bin/env bash

set -euo pipefail

PROJECT_SKILLS=(
  'leveltravel-hotfix-workflow'
  'leveltravel-pr-review'
  'leveltravel-pr-workflow'
  'leveltravel-tests'
)
OVERLAY_FILES=(
  'AGENTS.md'
  'CLAUDE.md'
)
SNAPSHOT_ROOT=''

cleanup_snapshot() {
  if test -n "$SNAPSHOT_ROOT" && test -d "$SNAPSHOT_ROOT"; then
    rm -rf -- "$SNAPSHOT_ROOT"
  fi
}

die() {
  echo "agents-sync: $*" >&2
  exit 1
}

usage() {
  cat >&2 <<'USAGE'
Usage:
  agents_sync.sh pull [PROJECT_ROOT] [MIRROR_ROOT]
  agents_sync.sh publish [PROJECT_ROOT] [MIRROR_ROOT] [COMMIT_MESSAGE]
  agents_sync.sh check [PROJECT_ROOT] [MIRROR_ROOT]

Defaults:
  PROJECT_ROOT  current directory
  MIRROR_ROOT   sibling directory ../agents_md
USAGE
  exit 2
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "required command is missing: $1"
}

canonical_dir() {
  test -d "$1" || die "directory does not exist: $1"
  (cd "$1" && pwd -P)
}

assert_git_root() {
  local expected_root="$1"
  local actual_root

  actual_root="$(git -C "$expected_root" rev-parse --show-toplevel 2>/dev/null)" ||
    die "not a git repository: $expected_root"
  actual_root="$(canonical_dir "$actual_root")"
  test "$actual_root" = "$expected_root" ||
    die "expected git root $expected_root, found $actual_root"
}

assert_mirror_clean() {
  local status

  status="$(git -C "$MIRROR_ROOT" status --porcelain)"
  test -z "$status" || {
    echo "$status" >&2
    die "mirror has local changes; resolve them before syncing"
  }
}

assert_project_excludes() {
  local overlay_file

  for overlay_file in "${OVERLAY_FILES[@]}"; do
    git -C "$PROJECT_ROOT" check-ignore -q --no-index -- "$overlay_file" ||
      die "$overlay_file is not ignored; configure .git/info/exclude first"
  done
  git -C "$PROJECT_ROOT" check-ignore -q --no-index -- .agents/tasks/.agents-sync-probe ||
    die ".agents/tasks is not ignored; configure .git/info/exclude first"
  git -C "$PROJECT_ROOT" check-ignore -q --no-index -- .agents/docs/.agents-sync-probe ||
    die ".agents/docs is not ignored; configure .git/info/exclude first"
  git -C "$PROJECT_ROOT" check-ignore -q --no-index -- \
    .agents/skills/leveltravel-agents-sync/.agents-sync-probe ||
    die "private skills are not ignored; configure .git/info/exclude first"

  if git -C "$PROJECT_ROOT" check-ignore -q --no-index -- \
    .agents/skills/leveltravel-tests/.agents-sync-probe; then
    die "develop-owned skills are ignored; configure .git/info/exclude allowlist"
  fi
}

require_overlay_source() {
  local root="$1"
  local overlay_file

  for overlay_file in "${OVERLAY_FILES[@]}"; do
    test -f "$root/$overlay_file" || die "missing $overlay_file in $root"
  done
  test -d "$root/.agents/docs" || die "missing .agents/docs in $root"
  test -d "$root/.agents/tasks" || die "missing .agents/tasks in $root"
  test -d "$root/.agents/skills" || die "missing .agents/skills in $root"
}

private_skill_excludes() {
  local skill

  echo '--exclude=.git'
  for skill in "${PROJECT_SKILLS[@]}"; do
    echo "--exclude=$skill/"
  done
}

sync_tree() {
  local source_dir="$1"
  local target_dir="$2"
  shift 2

  mkdir -p "$target_dir"
  rsync -a --delete "$@" "$source_dir/" "$target_dir/"
}

sync_overlay() {
  local source_root="$1"
  local target_root="$2"
  local excludes=()
  local exclude
  local overlay_file

  require_overlay_source "$source_root"
  mkdir -p "$target_root/.agents"
  for overlay_file in "${OVERLAY_FILES[@]}"; do
    rsync -a "$source_root/$overlay_file" "$target_root/"
  done
  sync_tree "$source_root/.agents/docs" "$target_root/.agents/docs" --exclude='.git'
  sync_tree "$source_root/.agents/tasks" "$target_root/.agents/tasks" --exclude='.git'

  while IFS= read -r exclude; do
    excludes+=("$exclude")
  done < <(private_skill_excludes)

  sync_tree \
    "$source_root/.agents/skills" \
    "$target_root/.agents/skills" \
    "${excludes[@]}"
}

make_develop_snapshot() {
  local snapshot_root="$1"
  local paths=()
  local skill

  git -C "$PROJECT_ROOT" show-ref --verify --quiet refs/remotes/origin/develop ||
    die "origin/develop is unavailable"

  for skill in "${PROJECT_SKILLS[@]}"; do
    paths+=(".agents/skills/$skill")
  done

  git -C "$PROJECT_ROOT" archive origin/develop -- "${paths[@]}" |
    tar -x -C "$snapshot_root"
}

sync_develop_skills_to_mirror() {
  local snapshot_root="$1"
  local skill

  for skill in "${PROJECT_SKILLS[@]}"; do
    sync_tree \
      "$snapshot_root/.agents/skills/$skill" \
      "$MIRROR_ROOT/.agents/skills/$skill" \
      --exclude='.git'
  done
}

compare_tree() {
  local label="$1"
  local source_dir="$2"
  local target_dir="$3"
  shift 3
  local output

  output="$(
    rsync -rclnpi --no-times --omit-dir-times --delete \
      "$@" "$source_dir/" "$target_dir/" |
      awk 'substr($0, 1, 10) != ".f..T.... "'
  )"
  if test -n "$output"; then
    echo "agents-sync: $label differs:" >&2
    echo "$output" >&2
    return 1
  fi
}

compare_overlay() {
  local source_root="$1"
  local target_root="$2"
  local excludes=()
  local exclude
  local failed=0
  local overlay_file

  require_overlay_source "$source_root"
  for overlay_file in "${OVERLAY_FILES[@]}"; do
    cmp -s "$source_root/$overlay_file" "$target_root/$overlay_file" || {
      echo "agents-sync: $overlay_file differs" >&2
      failed=1
    }
  done
  compare_tree \
    '.agents/docs' \
    "$source_root/.agents/docs" \
    "$target_root/.agents/docs" \
    --exclude='.git' || failed=1
  compare_tree \
    '.agents/tasks' \
    "$source_root/.agents/tasks" \
    "$target_root/.agents/tasks" \
    --exclude='.git' || failed=1

  while IFS= read -r exclude; do
    excludes+=("$exclude")
  done < <(private_skill_excludes)

  compare_tree \
    'private skills' \
    "$source_root/.agents/skills" \
    "$target_root/.agents/skills" \
    "${excludes[@]}" || failed=1

  return "$failed"
}

compare_develop_skills() {
  local snapshot_root="$1"
  local skill
  local failed=0

  for skill in "${PROJECT_SKILLS[@]}"; do
    compare_tree \
      "$skill" \
      "$snapshot_root/.agents/skills/$skill" \
      "$MIRROR_ROOT/.agents/skills/$skill" \
      --exclude='.git' || failed=1
  done

  return "$failed"
}

pull_overlay() {
  local tracked_before
  local tracked_after

  assert_mirror_clean
  assert_project_excludes
  tracked_before="$(git -C "$PROJECT_ROOT" status --porcelain=v1 --untracked-files=no)"

  git -C "$MIRROR_ROOT" pull --ff-only
  sync_overlay "$MIRROR_ROOT" "$PROJECT_ROOT"

  tracked_after="$(git -C "$PROJECT_ROOT" status --porcelain=v1 --untracked-files=no)"
  test "$tracked_before" = "$tracked_after" ||
    die "pull changed tracked project files; inspect the worktree"

  compare_overlay "$MIRROR_ROOT" "$PROJECT_ROOT"
  echo 'agents-sync: mirror-owned files pulled; tracked project files are unchanged'
}

publish_mirror() {
  local commit_message="$1"

  assert_mirror_clean
  assert_project_excludes
  git -C "$MIRROR_ROOT" pull --ff-only
  git -C "$PROJECT_ROOT" fetch \
    origin \
    refs/heads/develop:refs/remotes/origin/develop

  SNAPSHOT_ROOT="$(mktemp -d)"
  trap cleanup_snapshot EXIT
  make_develop_snapshot "$SNAPSHOT_ROOT"

  sync_overlay "$PROJECT_ROOT" "$MIRROR_ROOT"
  sync_develop_skills_to_mirror "$SNAPSHOT_ROOT"

  compare_overlay "$PROJECT_ROOT" "$MIRROR_ROOT"
  compare_develop_skills "$SNAPSHOT_ROOT"
  git -C "$MIRROR_ROOT" diff --check
  git -C "$MIRROR_ROOT" add "${OVERLAY_FILES[@]}" .agents

  if git -C "$MIRROR_ROOT" diff --cached --quiet; then
    echo 'agents-sync: mirror already matches the project overlay and origin/develop'
    return
  fi

  git -C "$MIRROR_ROOT" diff --cached --check
  git -C "$MIRROR_ROOT" commit -m "$commit_message"
  git -C "$MIRROR_ROOT" push
  echo 'agents-sync: mirror committed and pushed'
}

check_sync() {
  local failed=0

  assert_project_excludes
  SNAPSHOT_ROOT="$(mktemp -d)"
  trap cleanup_snapshot EXIT
  make_develop_snapshot "$SNAPSHOT_ROOT"

  compare_overlay "$PROJECT_ROOT" "$MIRROR_ROOT" || failed=1
  compare_develop_skills "$SNAPSHOT_ROOT" || failed=1
  test "$failed" -eq 0 || die "project and mirror are not synchronized"

  echo 'agents-sync: mirror-owned files match the project; develop-owned skills match origin/develop'
}

main() {
  local action="${1:-}"
  local project_arg="${2:-$(pwd)}"
  local mirror_arg="${3:-$project_arg/../agents_md}"
  local commit_message="${4:-Sync LevelTravel agent files}"

  case "$action" in
    pull | publish | check) ;;
    *) usage ;;
  esac

  require_command git
  require_command rsync
  require_command tar
  require_command cmp
  require_command awk

  PROJECT_ROOT="$(canonical_dir "$project_arg")"
  MIRROR_ROOT="$(canonical_dir "$mirror_arg")"
  export PROJECT_ROOT MIRROR_ROOT

  assert_git_root "$PROJECT_ROOT"
  assert_git_root "$MIRROR_ROOT"
  test "$PROJECT_ROOT" != "$MIRROR_ROOT" ||
    die "project and mirror must be different repositories"

  case "$action" in
    pull) pull_overlay ;;
    publish) publish_mirror "$commit_message" ;;
    check) check_sync ;;
  esac
}

main "$@"
