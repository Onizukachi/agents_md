#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$repo_root"

sanitize() {
  printf '%s' "$1" | tr -c '[:alnum:]_.-' '-' | sed 's/^-*//; s/-*$//'
}

build_number="${BUILD_NUMBER:-local-arm64-$(date +%Y%m%d%H%M%S)}"
worker_name="${WORKER_NAME:-leveltravel-$(sanitize "${USER:-codex}")-arm64}"
worker_network="${WORKER_NETWORK:-${worker_name}-integration}"
runtime_log_dir="${RUNTIME_LOG_DIR:-${repo_root}/tmp/teamcity-arm64}"
container_name="rspec_${build_number}"
image_name="integration-arm64:${build_number}"
compose_project="${worker_name}-integration"
dev_rails_image="${DEV_RAILS_IMAGE:-cr.yandex/crpg68tj52nf0fbhfo1e/dev-rails:2025-04}"
bundle_jobs="${BUNDLE_JOBS:-6}"

compose_override="$(mktemp "${TMPDIR:-/tmp}/leveltravel-compose-arm64.XXXXXX")"
dockerfile="$(mktemp "${TMPDIR:-/tmp}/leveltravel-arm64-Dockerfile.XXXXXX")"

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
    docker compose -f docker-compose-integration.yml -f "$compose_override" -p "$compose_project" down || true
  docker container prune -f || true
  rm -f "$compose_override" "$dockerfile"
}

require_env PROTO_REPO_TOKEN

cat > "$compose_override" <<'COMPOSE'
services:
  db:
    image: mysql:8.0
  redis:
    image: redis:latest
COMPOSE

cat > "$dockerfile" <<'DOCKERFILE'
# syntax=docker/dockerfile:1.4
ARG DEV_RAILS_IMAGE=cr.yandex/crpg68tj52nf0fbhfo1e/dev-rails:2025-04
FROM --platform=linux/arm64 ${DEV_RAILS_IMAGE}

ARG BUNDLE_JOBS=6

ENV APP_HOME=/app \
    RAILS_ENV=test \
    RSPEC_VERBOSE="true" \
    TEAMCITY_CI=1 \
    LD_PRELOAD=""

WORKDIR /app
COPY . .

RUN --mount=type=secret,id=proto_repo_token \
    rm -rf /usr/local/bundle/cache/bundler/git && \
    bundle config git.allow_insecure true && \
    bundle config set without 'development' && \
    BUNDLE_GITHUB__COM="LevelTravel:$(cat /run/secrets/proto_repo_token)" \
      bundle install --jobs "${BUNDLE_JOBS}" --retry 2

RUN ruby ./script/ci/clean_schema.rb

ENTRYPOINT ["bash", "./script/ci/ci.sh"]
DOCKERFILE

mkdir -p "$runtime_log_dir"
touch "${runtime_log_dir}/parallel_runtime_rspec.log"

trap cleanup EXIT

docker network create "$worker_network" || true

WORKER_NAME="$worker_name" WORKER_NETWORK="$worker_network" \
  docker compose -f docker-compose-integration.yml -f "$compose_override" \
  -p "$compose_project" \
  up --remove-orphans -d

DOCKER_BUILDKIT=1 docker build --platform linux/arm64 -f "$dockerfile" . \
  -t "$image_name" \
  --secret id=proto_repo_token,env=PROTO_REPO_TOKEN \
  --build-arg "DEV_RAILS_IMAGE=${dev_rails_image}" \
  --build-arg "BUNDLE_JOBS=${bundle_jobs}"

docker run \
  -v "${runtime_log_dir}:/temp" \
  --network="$worker_network" \
  --name="$container_name" \
  --rm \
  -e "REDIS_HOST=${worker_name}.redis-ci" \
  -e "MYSQL_HOST=${worker_name}.mysql-ci" \
  "$image_name"
