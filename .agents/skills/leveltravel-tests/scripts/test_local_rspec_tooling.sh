#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../../../.." && pwd)"
tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/leveltravel-rspec-tooling-test.XXXXXX")"
fake_bin="${tmp_dir}/bin"
test_scripts="${tmp_dir}/scripts"
mkdir -p "$fake_bin" "$test_scripts"

cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

cat > "${fake_bin}/uname" <<'STUB'
#!/bin/bash
if [ "${TEST_UNAME_FAIL:-0}" = 1 ]; then
  echo "uname must not be called when LOCAL_RSPEC_ARCH is set" >&2
  exit 99
fi
case "${1:-}" in
  -m)
    printf '%s\n' "${TEST_UNAME_M:?}"
    ;;
  -s)
    printf '%s\n' "${TEST_UNAME_S:?}"
    ;;
  *)
    exit 2
    ;;
esac
STUB

cat > "${fake_bin}/sysctl" <<'STUB'
#!/bin/bash
if [ "${TEST_SYSCTL_FAIL:-0}" = 1 ]; then
  echo "sysctl must not be called for this architecture" >&2
  exit 99
fi
if [ "${TEST_TRANSLATED:-missing}" = missing ]; then
  exit 1
fi
printf '%s\n' "$TEST_TRANSLATED"
STUB

cat > "${test_scripts}/native_arm64_rspec.sh" <<'STUB'
#!/bin/bash
{
  printf '%s\n' "${0##*/}"
  printf '<%s>\n' "$@"
} > "${TEST_CAPTURE:?}"
STUB

cp "${script_dir}/local_rspec.sh" "${test_scripts}/local_rspec.sh"
cp "${test_scripts}/native_arm64_rspec.sh" "${test_scripts}/teamcity_rspec.sh"
chmod +x \
  "${fake_bin}/uname" \
  "${fake_bin}/sysctl" \
  "${test_scripts}/local_rspec.sh" \
  "${test_scripts}/native_arm64_rspec.sh" \
  "${test_scripts}/teamcity_rspec.sh"

assert_index=0

assert_helper() {
  local label="$1"
  local expected="$2"
  local uname_m="$3"
  local uname_s="$4"
  local translated="$5"
  local override="${6:-}"
  assert_index=$((assert_index + 1))
  local capture="${tmp_dir}/capture-${assert_index}"
  local actual

  (
    export PATH="${fake_bin}:$PATH"
    export TEST_CAPTURE="$capture"
    export TEST_UNAME_M="$uname_m"
    export TEST_UNAME_S="$uname_s"
    export TEST_TRANSLATED="$translated"
    export TEST_SYSCTL_FAIL=0
    unset LOCAL_RSPEC_ARCH TEST_UNAME_FAIL

    if [ -n "$override" ]; then
      export LOCAL_RSPEC_ARCH="$override"
      export TEST_UNAME_FAIL=1
      export TEST_SYSCTL_FAIL=1
    elif [ "$uname_s" != Darwin ] || [ "$uname_m" != x86_64 ]; then
      export TEST_SYSCTL_FAIL=1
    fi

    /bin/bash "${test_scripts}/local_rspec.sh" alpha "two words"
  )

  actual="$(sed -n '1p' "$capture")"
  if [ "$actual" != "$expected" ]; then
    echo "${label}: expected ${expected}, got ${actual}" >&2
    exit 1
  fi
  [ "$(sed -n '2p' "$capture")" = "<alpha>" ]
  [ "$(sed -n '3p' "$capture")" = "<two words>" ]
}

assert_helper "native Apple Silicon" native_arm64_rspec.sh arm64 Darwin 0
assert_helper "Rosetta Apple Silicon" native_arm64_rspec.sh x86_64 Darwin 1
assert_helper "Intel macOS" teamcity_rspec.sh x86_64 Darwin 0
assert_helper "Intel macOS without Rosetta sysctl" teamcity_rspec.sh x86_64 Darwin missing
assert_helper "Linux amd64" teamcity_rspec.sh x86_64 Linux missing
assert_helper "Linux arm64" native_arm64_rspec.sh aarch64 Linux missing
assert_helper "explicit amd64 override" teamcity_rspec.sh arm64 Darwin 0 amd64
assert_helper "explicit arm64 override" native_arm64_rspec.sh x86_64 Linux missing arm64

if PATH="${fake_bin}:$PATH" \
   TEST_UNAME_M=riscv64 \
   TEST_UNAME_S=Linux \
   TEST_TRANSLATED=missing \
   TEST_SYSCTL_FAIL=1 \
     /bin/bash "${test_scripts}/local_rspec.sh" >"${tmp_dir}/unsupported.out" 2>"${tmp_dir}/unsupported.err"; then
  echo "Unsupported architecture unexpectedly succeeded." >&2
  exit 1
fi
grep -F "Unsupported local RSpec architecture: riscv64" "${tmp_dir}/unsupported.err" >/dev/null

canonical="${repo_root}/lib/build/app/integration.Dockerfile"
rendered="${tmp_dir}/integration.Dockerfile"
bash "${script_dir}/render_local_integration_dockerfile.sh" "$canonical" "$rendered"

grep -Fx "# syntax=docker/dockerfile:1.4" "$rendered" >/dev/null
grep -F "RUN --mount=type=secret,id=proto_repo_token,required=true" "$rendered" >/dev/null
grep -F 'BUNDLE_GITHUB__COM="LevelTravel:$(cat /run/secrets/proto_repo_token)"' "$rendered" >/dev/null
grep -F 'ENTRYPOINT ["bash", "./script/ci/ci.sh"]' "$rendered" >/dev/null
if grep -Eq '^ARG (PROTO_REPO_TOKEN|BUNDLE_GITHUB__COM)' "$rendered"; then
  echo "Rendered Dockerfile exposes a token build argument." >&2
  exit 1
fi

canonical_with_sentinel="${tmp_dir}/canonical-with-preserved-changes.Dockerfile"
awk '
  $0 == "RUN  rm -rf /usr/local/bundle/cache/bundler/git && \\" {
    print "RUN  echo renderer-preserves-this && \\"
    print "     rm -rf /usr/local/bundle/cache/bundler/git && \\"
    next
  }
  /^[[:space:]]+bundle install/ {
    sub(/--jobs 6 --retry 2/, "--jobs 4 --retry 3")
  }
  {
    print
  }
  END {
    print ""
    print "LABEL renderer-preserves-label=true"
  }
' "$canonical" > "$canonical_with_sentinel"
bash "${script_dir}/render_local_integration_dockerfile.sh" \
  "$canonical_with_sentinel" \
  "${tmp_dir}/rendered-with-sentinel.Dockerfile"
grep -F "RUN --mount=type=secret,id=proto_repo_token,required=true echo renderer-preserves-this" \
  "${tmp_dir}/rendered-with-sentinel.Dockerfile" >/dev/null
grep -F "bundle install --jobs 4 --retry 3" "${tmp_dir}/rendered-with-sentinel.Dockerfile" >/dev/null
grep -F "LABEL renderer-preserves-label=true" "${tmp_dir}/rendered-with-sentinel.Dockerfile" >/dev/null

assert_render_fails() {
  local label="$1"
  local source="$2"
  local destination="${tmp_dir}/failed-render-${label}.Dockerfile"

  printf 'destination-must-remain-unchanged\n' > "$destination"
  if bash "${script_dir}/render_local_integration_dockerfile.sh" \
       "$source" "$destination" >/dev/null 2>&1; then
    echo "${label}: unsafe Dockerfile unexpectedly rendered." >&2
    exit 1
  fi
  grep -Fx "destination-must-remain-unchanged" "$destination" >/dev/null
}

credential_drift="${tmp_dir}/credential-drift.Dockerfile"
sed 's/ARG PROTO_REPO_TOKEN=xxxx/ARG PROTO_REPO_TOKEN=changed/' \
  "$canonical" > "$credential_drift"
assert_render_fails credential-drift "$credential_drift"

credential_gap="${tmp_dir}/credential-gap.Dockerfile"
awk '
  {
    print
    if ($0 == "ARG PROTO_REPO_TOKEN=xxxx") {
      print ""
    }
  }
' "$canonical" > "$credential_gap"
assert_render_fails credential-gap "$credential_gap"

extra_token_reference="${tmp_dir}/extra-token-reference.Dockerfile"
{
  cat "$canonical"
  printf '\nENV PROTO_REPO_TOKEN=unexpected\n'
} > "$extra_token_reference"
assert_render_fails extra-token-reference "$extra_token_reference"

duplicate_bundle_install="${tmp_dir}/duplicate-bundle-install.Dockerfile"
awk '
  {
    print
    if ($0 ~ /^[[:space:]]+bundle install/) {
      print
    }
  }
' "$canonical" > "$duplicate_bundle_install"
assert_render_fails duplicate-bundle-install "$duplicate_bundle_install"

broken_run="${tmp_dir}/broken-run.Dockerfile"
awk '
  $0 == "RUN  rm -rf /usr/local/bundle/cache/bundler/git && \\" {
    print "RUN  rm -rf /usr/local/bundle/cache/bundler/git"
    next
  }
  {
    print
  }
' "$canonical" > "$broken_run"
assert_render_fails broken-run "$broken_run"

existing_secret_reference="${tmp_dir}/existing-secret-reference.Dockerfile"
{
  cat "$canonical"
  printf '\n# proto_repo_token\n'
} > "$existing_secret_reference"
assert_render_fails existing-secret-reference "$existing_secret_reference"

syntax_source="${tmp_dir}/syntax-source.Dockerfile"
{
  printf '# syntax=docker/dockerfile:1.7\n'
  cat "$canonical"
} > "$syntax_source"
bash "${script_dir}/render_local_integration_dockerfile.sh" \
  "$syntax_source" \
  "${tmp_dir}/rendered-with-syntax.Dockerfile"
[ "$(grep -c '^# syntax=' "${tmp_dir}/rendered-with-syntax.Dockerfile")" = 1 ]
grep -Fx "# syntax=docker/dockerfile:1.7" "${tmp_dir}/rendered-with-syntax.Dockerfile" >/dev/null

fake_docker_bin="${tmp_dir}/fake-docker-bin"
fake_docker_log="${tmp_dir}/fake-docker.log"
fake_dockerfile_capture="${tmp_dir}/fake-docker-build.Dockerfile"
mkdir -p "$fake_docker_bin"

cat > "${fake_docker_bin}/docker" <<'STUB'
#!/bin/bash
{
  printf 'docker'
  printf ' <%s>' "$@"
  printf '\n'
} >> "${TEST_DOCKER_LOG:?}"

if [ "${1:-}" = image ] && [ "${2:-}" = inspect ]; then
  printf 'amd64\n'
  exit 0
fi

if [ "${1:-}" = build ]; then
  shift
  while [ "$#" -gt 0 ]; do
    if [ "$1" = -f ]; then
      cp "$2" "${TEST_DOCKERFILE_CAPTURE:?}"
      break
    fi
    shift
  done
fi
STUB

cat > "${fake_docker_bin}/gh" <<'STUB'
#!/bin/bash
if [ "${1:-}" = api ]; then
  exit 0
fi
echo "Unexpected gh invocation: $*" >&2
exit 99
STUB

chmod +x "${fake_docker_bin}/docker" "${fake_docker_bin}/gh"

secret_sentinel="tooling-test-secret-must-not-leak"
PATH="${fake_docker_bin}:$PATH" \
LEVELTRAVEL_RSPEC_LOCK_HELD=1 \
PROTO_REPO_TOKEN="$secret_sentinel" \
TEST_DOCKER_LOG="$fake_docker_log" \
TEST_DOCKERFILE_CAPTURE="$fake_dockerfile_capture" \
TMPDIR="$tmp_dir" \
RUNTIME_LOG_DIR="${tmp_dir}/runtime" \
BUILD_NUMBER=tooling-test \
WORKER_NAME=tooling-worker \
DOCKER_REGISTRY=registry.example/team \
MYSQL_IMAGE=mysql:tooling \
REDIS_IMAGE=redis:tooling \
  /bin/bash "${script_dir}/teamcity_rspec.sh"

grep -F '<--secret> <id=proto_repo_token,env=PROTO_REPO_TOKEN>' "$fake_docker_log" >/dev/null
grep -F '<--build-arg> <ECR_REPO=registry.example/team>' "$fake_docker_log" >/dev/null
grep -F '<down> <-v> <--remove-orphans>' "$fake_docker_log" >/dev/null
grep -F 'RUN --mount=type=secret,id=proto_repo_token,required=true' "$fake_dockerfile_capture" >/dev/null
if grep -F "$secret_sentinel" "$fake_docker_log" "$fake_dockerfile_capture" >/dev/null; then
  echo "Fake-Docker smoke exposed the proto token." >&2
  exit 1
fi

echo "local RSpec tooling tests: PASS"
