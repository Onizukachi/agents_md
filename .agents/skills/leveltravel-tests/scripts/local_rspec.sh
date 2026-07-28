#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

detect_architecture() {
  local detected translated

  detected="$(uname -m)"
  if [ "$detected" = x86_64 ] && [ "$(uname -s)" = Darwin ]; then
    translated="$(sysctl -n sysctl.proc_translated 2>/dev/null || true)"
    if [ "$translated" = 1 ]; then
      detected=arm64
    fi
  fi

  printf '%s\n' "$detected"
}

architecture="${LOCAL_RSPEC_ARCH:-$(detect_architecture)}"

case "$architecture" in
  arm64|aarch64)
    helper="${script_dir}/native_arm64_rspec.sh"
    ;;
  x86_64|amd64)
    helper="${script_dir}/teamcity_rspec.sh"
    ;;
  *)
    echo "Unsupported local RSpec architecture: ${architecture}" >&2
    exit 2
    ;;
esac

exec bash "$helper" "$@"
