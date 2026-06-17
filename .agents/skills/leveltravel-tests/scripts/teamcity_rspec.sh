#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$repo_root"

sanitize() {
  printf '%s' "$1" | tr -c '[:alnum:]_.-' '-' | sed 's/^-*//; s/-*$//'
}

build_number="${BUILD_NUMBER:-local-$(date +%Y%m%d%H%M%S)}"
worker_name="${WORKER_NAME:-leveltravel-$(sanitize "${USER:-codex}")}"
worker_network="${WORKER_NETWORK:-${worker_name}-integration}"
runtime_log_dir="${RUNTIME_LOG_DIR:-${repo_root}/tmp/teamcity}"
container_name="rspec_${build_number}"
image_name="integration:${build_number}"
compose_project="${worker_name}-integration"

export DOCKER_DEFAULT_PLATFORM="${DOCKER_DEFAULT_PLATFORM:-linux/amd64}"
export DOCKER_REGISTRY="${DOCKER_REGISTRY:-cr.yandex/crp2b4c44b0t0smqf2nj}"

require_env() {
  local name="$1"
  if [ -z "${!name:-}" ]; then
    echo "Missing required environment variable: ${name}" >&2
    exit 2
  fi
}

cleanup() {
  docker stop "$container_name" >/dev/null 2>&1 || true
  docker rmi --force "$image_name" >/dev/null 2>&1 || true
  WORKER_NAME="$worker_name" WORKER_NETWORK="$worker_network" \
    docker compose -f docker-compose-integration.yml -p "$compose_project" down || true
  docker container prune -f || true
  if [ "${PRUNE_VOLUMES:-false}" = "true" ]; then
    docker volume prune -f -a || true
  fi
}

require_env PROTO_REPO_TOKEN

if [ -n "${BREAKING_CHANGES:-}" ]; then
  echo "$BREAKING_CHANGES"
  if [ -f "$BREAKING_CHANGES" ]; then
    echo "Breaking changes checked: OK"
  else
    echo "It looks like your branch is outdated. Rebase it from fresh develop branch." >&2
    exit 1
  fi
fi

mkdir -p "$runtime_log_dir"
touch "${runtime_log_dir}/parallel_runtime_rspec.log"

trap cleanup EXIT

docker network create "$worker_network" || true

WORKER_NAME="$worker_name" WORKER_NETWORK="$worker_network" \
  docker compose -f docker-compose-integration.yml \
  -p "$compose_project" \
  up --remove-orphans -d

docker build -f ./lib/build/app/integration.Dockerfile . \
  -t "$image_name" \
  --build-arg "PROTO_REPO_TOKEN=${PROTO_REPO_TOKEN}" \
  --build-arg "ECR_REPO=${DOCKER_REGISTRY}"

docker run \
  -v "${runtime_log_dir}:/temp" \
  --network="$worker_network" \
  --name="$container_name" \
  --rm \
  -e "REDIS_HOST=${worker_name}.redis-ci" \
  -e "MYSQL_HOST=${worker_name}.mysql-ci" \
  "$image_name"
