#!/usr/bin/env bash
set -euo pipefail

source_dockerfile="${1:?Usage: render_local_integration_dockerfile.sh SOURCE DESTINATION}"
destination_dockerfile="${2:?Usage: render_local_integration_dockerfile.sh SOURCE DESTINATION}"

if [ ! -f "$source_dockerfile" ]; then
  echo "Canonical integration Dockerfile not found: ${source_dockerfile}" >&2
  exit 2
fi

if [ "$source_dockerfile" = "$destination_dockerfile" ]; then
  echo "Source and destination Dockerfiles must differ." >&2
  exit 2
fi

render_tmp="$(mktemp "${destination_dockerfile}.XXXXXX")"

cleanup_render() {
  if [ -n "${render_tmp:-}" ]; then
    rm -f "$render_tmp"
  fi
}
trap cleanup_render EXIT HUP INT TERM

if ! LC_ALL=C awk '
  function fail(message) {
    print "Cannot safely derive the BuildKit Dockerfile from " FILENAME ": " message > "/dev/stderr"
    exit 42
  }

  {
    line[NR] = $0

    if ($0 == "ARG PROTO_REPO_TOKEN=xxxx") {
      proto_arg_count++
      proto_arg_line = NR
    }
    if ($0 == "ARG BUNDLE_GITHUB__COM=\"LevelTravel:$PROTO_REPO_TOKEN\"") {
      bundle_arg_count++
      bundle_arg_line = NR
    }
    if (index($0, "PROTO_REPO_TOKEN") || index($0, "BUNDLE_GITHUB__COM")) {
      credential_reference_count++
    }
    if (index($0, "proto_repo_token")) {
      secret_reference_count++
    }
    if ($0 ~ /bundle[[:space:]]+install([[:space:]]|$)/) {
      bundle_install_reference_count++
    }
    if ($0 ~ /^[[:space:]]*bundle[[:space:]]+install([[:space:]]|$)/) {
      bundle_install_command_count++
      bundle_install_line = NR
    }
    if ($0 ~ /^#[[:space:]]*syntax[[:space:]]*=/) {
      syntax_directive_count++
      syntax_directive_line = NR
    }
  }

  END {
    if (proto_arg_count != 1 || bundle_arg_count != 1 ||
        bundle_arg_line != proto_arg_line + 1 ||
        credential_reference_count != 2) {
      fail("expected exactly one adjacent canonical credential ARG stanza")
    }
    if (secret_reference_count != 0) {
      fail("canonical Dockerfile already references proto_repo_token")
    }
    if (syntax_directive_count > 1 ||
        (syntax_directive_count == 1 && syntax_directive_line != 1)) {
      fail("syntax directive must be absent or be the first line")
    }
    if (bundle_install_reference_count != 1 ||
        bundle_install_command_count != 1) {
      fail("expected exactly one standalone bundle install command")
    }
    if (bundle_arg_line >= bundle_install_line) {
      fail("credential ARG stanza must precede bundle install")
    }

    for (line_number = bundle_install_line - 1; line_number > 0; line_number--) {
      if (line[line_number] ~ /^RUN[[:space:]]+/) {
        if (line[line_number] !~ /\\[[:space:]]*$/) {
          fail("RUN instruction before bundle install is not continued")
        }
        bundle_run_line = line_number
        break
      }
      if (line[line_number] !~ /\\[[:space:]]*$/) {
        fail("bundle install is not inside the expected multiline RUN instruction")
      }
    }
    if (!bundle_run_line) {
      fail("could not find the RUN instruction containing bundle install")
    }

    match(line[bundle_run_line], /^RUN[[:space:]]+/)
    run_command = substr(line[bundle_run_line], RLENGTH + 1)
    line[bundle_run_line] = \
      "RUN --mount=type=secret,id=proto_repo_token,required=true " run_command

    match(line[bundle_install_line], /^[[:space:]]*/)
    indent = substr(line[bundle_install_line], 1, RLENGTH)
    command = substr(line[bundle_install_line], RLENGTH + 1)
    line[bundle_install_line] = indent \
      "BUNDLE_GITHUB__COM=\"LevelTravel:$(cat /run/secrets/proto_repo_token)\" " command

    if (syntax_directive_count == 0) {
      print "# syntax=docker/dockerfile:1.4"
    }
    for (line_number = 1; line_number <= NR; line_number++) {
      if (line_number == proto_arg_line || line_number == bundle_arg_line) {
        continue
      }
      print line[line_number]
    }
  }
' "$source_dockerfile" > "$render_tmp"; then
  echo "Refusing to replace ${destination_dockerfile}; canonical credential/build stanza drifted." >&2
  exit 2
fi

if grep -F 'PROTO_REPO_TOKEN' "$render_tmp" >/dev/null ||
   [ "$(grep -Fc 'BUNDLE_GITHUB__COM="LevelTravel:$(cat /run/secrets/proto_repo_token)"' "$render_tmp" || true)" != 1 ] ||
   [ "$(grep -Fc 'RUN --mount=type=secret,id=proto_repo_token,required=true ' "$render_tmp" || true)" != 1 ]; then
  echo "Generated Dockerfile failed the secret-transport safety check." >&2
  exit 2
fi

mv -f "$render_tmp" "$destination_dockerfile"
render_tmp=
trap - EXIT HUP INT TERM
