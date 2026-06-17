---
name: leveltravel-tests
description: Run LevelTravel tests using the same Docker RSpec flow as the TeamCity rails-rspec PR build. Use when verifying Rails changes, preparing a PR, checking CI-equivalent RSpec, or running focused development specs without confusing them with the PR gate.
---

# LevelTravel Tests

Use this skill whenever running or reporting test verification for this repository.

The authoritative PR gate is the TeamCity `rails-rspec` Docker flow. Host-side `bundle exec rspec` can be useful for fast feedback, but it is not equivalent to CI.

## Confirm The Workspace

Before running tests, confirm these files exist:

- `docker-compose-integration.yml`
- `lib/build/app/integration.Dockerfile`
- `script/ci/ci.sh`
- `Gemfile`

Inspect the workspace:

```bash
git status --short --branch
```

Do not print secret values. It is fine to say whether required environment variables are present.

## TeamCity PR Build Shape

The TeamCity PR build runs these phases:

1. Check for breaking changes marker.
2. Create the Docker network.
3. Start MySQL and Redis from `docker-compose-integration.yml`.
4. Build `lib/build/app/integration.Dockerfile` as `integration:%build.number%`.
5. Run the image on the worker network with:
   - `REDIS_HOST=%env.WORKER_NAME%.redis-ci`
   - `MYSQL_HOST=%env.WORKER_NAME%.mysql-ci`
   - `/opt/buildagent/temp/buildTmp/.teamcity` mounted at `/temp`
6. Always stop the test container, remove the integration image, stop compose services, and prune CI containers and volumes.

Inside the image, `TEAMCITY_CI=1` is set by `integration.Dockerfile`, and `script/ci/ci.sh` runs `parallel_rspec` with TeamCity runtime logs.

## Required Inputs

For a CI-equivalent local run, Docker must be available and this environment variable must be set:

- `PROTO_REPO_TOKEN`: used during Docker build as `BUNDLE_GITHUB__COM`.

Optional environment variables:

- `BUILD_NUMBER`: image tag and container suffix. Defaults to a timestamped local value in the helper script.
- `WORKER_NAME`: compose container prefix. Defaults to a sanitized local value in the helper script.
- `WORKER_NETWORK`: Docker network name. Defaults to `${WORKER_NAME}-integration`.
- `DOCKER_REGISTRY`: passed to Docker build as `ECR_REPO`. Defaults to `cr.yandex/crp2b4c44b0t0smqf2nj`, the registry that contains `rails-builder-test`.
- `DOCKER_DEFAULT_PLATFORM`: Docker platform for compose and build. Defaults to `linux/amd64`, matching TeamCity agents and avoiding Apple Silicon arm64 image mismatches.
- `BREAKING_CHANGES`: when set, the helper script checks that the referenced file exists.
- `RUNTIME_LOG_DIR`: host directory mounted to `/temp`. Defaults to `tmp/teamcity`.
- `PRUNE_VOLUMES=true`: match TeamCity's final `docker volume prune -f -a`. Defaults to `false` locally to avoid deleting unrelated developer volumes.

If private Yandex registry pulls fail locally, configure Docker credentials with:

```bash
yc container registry configure-docker
```

Before a CI-equivalent run, ensure the runtime log exists because `script/ci/ci.sh` copies `/temp/parallel_runtime_rspec.log` when `TEAMCITY_CI=1`:

```bash
mkdir -p tmp/teamcity
touch tmp/teamcity/parallel_runtime_rspec.log
```

## Canonical CI-Equivalent Command

Prefer the repository skill helper:

```bash
bash .agents/skills/leveltravel-tests/scripts/teamcity_rspec.sh
```

For exact TeamCity-style local cleanup, opt in to volume pruning:

```bash
PRUNE_VOLUMES=true bash .agents/skills/leveltravel-tests/scripts/teamcity_rspec.sh
```

The helper follows the TeamCity steps and preserves the safer local default of not pruning volumes unless explicitly requested.

On Apple Silicon, this runs the CI amd64 image through emulation. If `parallel:create` or `parallel_rspec` makes no progress for a long time while `qemu-x86_64` processes consume CPU, report it as a local emulation blocker rather than a code failure.

## Native Apple Silicon Command

For local M-chip verification, use the native arm64 helper:

```bash
PROTO_REPO_TOKEN="$(gh auth token)" bash .agents/skills/leveltravel-tests/scripts/native_arm64_rspec.sh
```

This is not byte-for-byte TeamCity. TeamCity's `rails-builder-test` base image and `mysql:8.0.22` are amd64-only, so the helper builds from the arm64-capable `dev-rails:2025-04` image and overrides compose to use `mysql:8.0` plus `redis:latest`.

Use this mode when the amd64 TeamCity-compatible flow is blocked by Apple Silicon emulation. Report it separately from the canonical CI-equivalent gate.

## Manual TeamCity Commands

Use these commands when the helper is unavailable or when reproducing CI step by step:

```bash
export DOCKER_DEFAULT_PLATFORM="${DOCKER_DEFAULT_PLATFORM:-linux/amd64}"
export DOCKER_REGISTRY="${DOCKER_REGISTRY:-cr.yandex/crp2b4c44b0t0smqf2nj}"

docker network create "$WORKER_NETWORK" || true

WORKER_NAME="$WORKER_NAME" WORKER_NETWORK="$WORKER_NETWORK" \
  docker compose -f docker-compose-integration.yml \
  -p "${WORKER_NAME}-integration" \
  up --remove-orphans -d

docker build -f ./lib/build/app/integration.Dockerfile . \
  -t "integration:${BUILD_NUMBER}" \
  --build-arg "PROTO_REPO_TOKEN=${PROTO_REPO_TOKEN}" \
  --build-arg "ECR_REPO=${DOCKER_REGISTRY}"

docker run \
  -v "$(pwd)/tmp/teamcity:/temp" \
  --network="${WORKER_NETWORK}" \
  --name="rspec_${BUILD_NUMBER}" \
  --rm \
  -e "REDIS_HOST=${WORKER_NAME}.redis-ci" \
  -e "MYSQL_HOST=${WORKER_NAME}.mysql-ci" \
  "integration:${BUILD_NUMBER}"
```

Always clean up:

```bash
docker stop "rspec_${BUILD_NUMBER}" || true
docker rmi --force "integration:${BUILD_NUMBER}" || true
WORKER_NAME="$WORKER_NAME" WORKER_NETWORK="$WORKER_NETWORK" \
  docker compose -f docker-compose-integration.yml -p "${WORKER_NAME}-integration" down
docker container prune -f
```

Only run this final command when CI-equivalent destructive cleanup is explicitly acceptable:

```bash
docker volume prune -f -a
```

## Focused Development Specs

For quick local feedback, focused host-side specs are acceptable when the local Ruby app boots:

```bash
bundle exec rspec spec/path/to/spec.rb
FILES_TO_RUN=spec/path/to/spec.rb bash script/ci/ci.sh
```

Reporting rules:

- Label these as focused or host-side checks.
- Do not call them CI-equivalent.
- If local Ruby cannot boot because of environment or native dependency issues, report the exact boot blocker.

## Reporting

When summarizing tests, include exact commands and outcomes:

```markdown
## Tests
- PASS: `bash .agents/skills/leveltravel-tests/scripts/teamcity_rspec.sh`
- PASS: `bundle exec rspec spec/path/to/spec.rb`
- BLOCKED: `bash .agents/skills/leveltravel-tests/scripts/teamcity_rspec.sh` - missing `PROTO_REPO_TOKEN`
```

If the TeamCity-compatible gate was not run, say why. Do not let a focused command imply full PR readiness.
