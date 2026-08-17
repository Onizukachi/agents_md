#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${script_dir}/local_rspec_lock.sh"
leveltravel_reexec_with_rspec_lock "${script_dir}/$(basename "${BASH_SOURCE[0]}")" "$@"

repo_root="$(cd "${script_dir}/../../../.." && pwd)"
cd "$repo_root"

sanitize() {
  printf '%s' "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | tr -c '[:alnum:]_-' '-' \
    | sed 's/^-*//; s/-*$//'
}

build_label="$(sanitize "${BUILD_NUMBER:-local}")"
build_label="${build_label:0:16}"
[ -n "$build_label" ] || build_label=local
run_id="${build_label}-$(date +%Y%m%d%H%M%S)-$$"
worker_base="$(sanitize "${WORKER_NAME:-leveltravel-${USER:-codex}}")"
worker_base="${worker_base:0:18}"
[ -n "$worker_base" ] || worker_base=leveltravel-codex
worker_name="${worker_base}-${run_id}"
network_base="$(sanitize "${WORKER_NETWORK:-${worker_base}-integration}")"
network_base="${network_base:0:18}"
[ -n "$network_base" ] || network_base=leveltravel-integration
worker_network="${network_base}-${run_id}"
runtime_log_dir="${RUNTIME_LOG_DIR:-${repo_root}/tmp/teamcity}/${run_id}"
container_name="rspec_${run_id}"
image_name="integration:${run_id}"
compose_project="${worker_name}-i"
docker_registry="${DOCKER_REGISTRY:-cr.yandex/crp2b4c44b0t0smqf2nj}"
rails_builder_tag="${RAILS_BUILDER_TAG:-ruby-3.4.10}"
mysql_source_image="${MYSQL_IMAGE:-mysql:8.0.22}"
redis_source_image="${REDIS_IMAGE:-redis:latest}"
mysql_image="leveltravel-ci-mysql:${run_id}-amd64"
redis_image="leveltravel-ci-redis:${run_id}-amd64"
compose_override="$(mktemp "${TMPDIR:-/tmp}/leveltravel-compose-amd64.XXXXXX")"
dockerfile="$(mktemp "${TMPDIR:-/tmp}/leveltravel-amd64-Dockerfile.XXXXXX")"
network_created=false
proto_repo_token="${PROTO_REPO_TOKEN:-}"

cleanup() {
  docker stop "$container_name" >/dev/null 2>&1 || true
  WORKER_NAME="$worker_name" WORKER_NETWORK="$worker_network" \
    docker compose -f docker-compose-integration.yml -f "$compose_override" \
      -p "$compose_project" down -v --remove-orphans >/dev/null 2>&1 || true
  docker image rm --force "$image_name" >/dev/null 2>&1 || true
  docker image rm "$mysql_image" "$redis_image" >/dev/null 2>&1 || true
  if [ "$network_created" = true ]; then
    docker network rm "$worker_network" >/dev/null 2>&1 || true
  fi
  rm -f "$compose_override" "$dockerfile"
}

trap cleanup EXIT

resolve_proto_token() {
  local candidate

  if [ -n "$proto_repo_token" ]; then
    return
  fi

  if command -v gh >/dev/null 2>&1; then
    candidate="$(gh auth token 2>/dev/null || true)"
    if [ -n "$candidate" ]; then
      proto_repo_token="$candidate"
      return
    fi
  fi

  echo "Missing a GitHub credential with access to LevelTravel/proto." >&2
  echo "Set PROTO_REPO_TOKEN or authenticate the GitHub CLI with gh auth login." >&2
  exit 2
}

check_image_architecture() {
  local image="$1"
  local expected="$2"
  local actual

  actual="$(docker image inspect "$image" --format '{{.Architecture}}')"
  if [ "$actual" != "$expected" ]; then
    echo "Unexpected architecture for ${image}: wanted ${expected}, got ${actual}." >&2
    exit 2
  fi
}

command -v docker >/dev/null 2>&1 || {
  echo "Docker is required for the local RSpec gate." >&2
  exit 2
}
docker info >/dev/null
docker compose version >/dev/null
resolve_proto_token

if command -v gh >/dev/null 2>&1 && \
   ! GH_TOKEN="$proto_repo_token" gh api repos/LevelTravel/proto --silent >/dev/null 2>&1; then
  echo "The resolved GitHub credential cannot access LevelTravel/proto." >&2
  exit 2
fi

if [ -n "${BREAKING_CHANGES:-}" ]; then
  echo "$BREAKING_CHANGES"
  if [ -f "$BREAKING_CHANGES" ]; then
    echo "Breaking changes checked: OK"
  else
    echo "It looks like your branch is outdated. Rebase it from fresh develop branch." >&2
    exit 1
  fi
fi

docker pull --platform linux/amd64 "$mysql_source_image"
docker tag "$mysql_source_image" "$mysql_image"
docker pull --platform linux/amd64 "$redis_source_image"
docker tag "$redis_source_image" "$redis_image"
check_image_architecture "$mysql_image" amd64
check_image_architecture "$redis_image" amd64

cat > "$compose_override" <<COMPOSE
services:
  db:
    image: ${mysql_image}
    platform: linux/amd64
    pull_policy: never
    healthcheck:
      test: ["CMD-SHELL", "mysqladmin ping -h 127.0.0.1 --silent"]
      interval: 2s
      timeout: 2s
      retries: 60
  redis:
    image: ${redis_image}
    platform: linux/amd64
    pull_policy: never
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 2s
      timeout: 2s
      retries: 60
COMPOSE

bash "${script_dir}/render_local_integration_dockerfile.sh" \
  "${repo_root}/lib/build/app/integration.Dockerfile" \
  "$dockerfile"

mkdir -p "$runtime_log_dir"
touch "${runtime_log_dir}/parallel_runtime_rspec.log"

PROTO_REPO_TOKEN="$proto_repo_token" DOCKER_BUILDKIT=1 \
  docker build --platform linux/amd64 -f "$dockerfile" . \
  -t "$image_name" \
  --secret id=proto_repo_token,env=PROTO_REPO_TOKEN \
  --build-arg "ECR_REPO=${docker_registry}" \
  --build-arg "RAILS_BUILDER_TAG=${rails_builder_tag}"

docker network create "$worker_network"
network_created=true

WORKER_NAME="$worker_name" WORKER_NETWORK="$worker_network" \
  docker compose -f docker-compose-integration.yml -f "$compose_override" \
    -p "$compose_project" up --remove-orphans -d --wait --wait-timeout 120

docker run \
  --platform linux/amd64 \
  -v "${runtime_log_dir}:/temp" \
  --network="$worker_network" \
  --name="$container_name" \
  --rm \
  -e REDIS_HOST=redis \
  -e MYSQL_HOST=db \
  "$image_name"
