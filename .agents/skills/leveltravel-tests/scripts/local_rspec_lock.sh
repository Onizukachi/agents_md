#!/usr/bin/env bash

leveltravel_reexec_with_rspec_lock() {
  local helper="$1"
  local lock_file="${TMPDIR:-/tmp}/leveltravel-local-rspec.lock"
  local status

  shift

  if [ "${LEVELTRAVEL_RSPEC_LOCK_HELD:-}" = 1 ]; then
    return
  fi

  if command -v lockf >/dev/null 2>&1; then
    set +e
    LEVELTRAVEL_RSPEC_LOCK_HELD=1 lockf -t 0 "$lock_file" bash "$helper" "$@"
    status=$?
    set -e
  elif command -v flock >/dev/null 2>&1; then
    set +e
    LEVELTRAVEL_RSPEC_LOCK_HELD=1 flock -n -E 75 "$lock_file" bash "$helper" "$@"
    status=$?
    set -e
  else
    echo "Warning: lockf/flock is unavailable; running without a machine-wide CI lock." >&2
    export LEVELTRAVEL_RSPEC_LOCK_HELD=1
    return
  fi

  if [ "$status" -eq 75 ]; then
    echo "Another LevelTravel full local RSpec gate is already running." >&2
  fi

  exit "$status"
}
