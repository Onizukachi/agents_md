---
name: leveltravel-tests
description: Run LevelTravel Rails tests with the repository local Docker gate, selecting native ARM64 on Apple Silicon or the TeamCity-compatible amd64 helper on x86_64, and report local evidence separately from the authoritative remote TeamCity rails-rspec gate.
---

# LevelTravel Tests

Use this skill whenever running or reporting test verification for this repository.

The repository local full-test entry point is:

```bash
bash .agents/skills/leveltravel-tests/scripts/local_rspec.sh
```

It selects the supported local path for the host architecture:

- Apple Silicon (`arm64`): native ARM64 Docker RSpec as the broad local gate. It exercises the full Rails test flow, but it is not byte-for-byte TeamCity-equivalent.
- x86_64: the canonical amd64 helper that reproduces the TeamCity Docker RSpec shape.

The remote TeamCity `rails-rspec` build remains the authoritative amd64 parity gate and must pass before merge.

## Confirm The Workspace

Before running tests, confirm these files exist:

- `docker-compose-integration.yml`
- `lib/build/app/integration.Dockerfile` (the canonical TeamCity build source)
- `script/ci/ci.sh`
- `Gemfile`

Inspect the workspace:

```bash
git status --short --branch
```

Do not print secret values. It is fine to report whether a usable credential was found and where it came from, without printing the credential itself.

## Credentials And Preflight

The helpers need a GitHub token with access to `LevelTravel/proto` during `bundle install`. They resolve it in this order:

1. an existing non-empty `PROTO_REPO_TOKEN` environment variable;
2. `gh auth token`, when the GitHub CLI is authenticated.

Do not interpolate the token into a command shown in logs. The Docker build must receive it as a BuildKit secret, not a build argument.

Treat both local paths as requiring private base images from `cr.yandex`. If Docker reports an authorization error, stop and ask the developer to run the repository-standard login flow:

```bash
lt login
```

Do not run this command automatically because it starts the approved Google/Boundary login flow and updates local Docker credentials. If `lt login` is unavailable or access is denied, report the local gate as `BLOCKED` and request approved registry access. Do not suggest `yc container registry configure-docker` as the default remediation; do not assume developers have direct Yandex Cloud IAM access.

Before expensive work, the entry point should fail fast when Docker is unavailable, the host architecture is unsupported, credentials are missing, or required images cannot be used for the selected platform.

Optional environment variables:

- `BUILD_NUMBER`: diagnostic label used in generated resource names. The helper adds a per-run suffix so concurrent tasks remain isolated.
- `WORKER_NAME`: base for Docker resource names. The helper still derives unique names for the current run.
- `LOCAL_RSPEC_ARCH`: override architecture selection for diagnostics. By default the entry point uses `uname -m` and corrects translated macOS shells through `sysctl.proc_translated`; `arm64` and `aarch64` select the native helper, while `x86_64` and `amd64` select the canonical helper.
- `DOCKER_REGISTRY`: registry that contains the canonical `rails-builder-test` image.
- `RAILS_BUILDER_TAG`: immutable Ruby ABI-specific builder tag. Defaults to `ruby-3.4.10`.
- `DEV_RAILS_IMAGE`: native ARM64 Ruby/Rails base image override.
- `MYSQL_IMAGE` and `REDIS_IMAGE`: source image overrides; helpers pull the selected platform and copy it to architecture-specific local tags before Compose starts.
- `BUNDLE_JOBS`: Bundler parallelism for the native ARM64 image build.
- `BREAKING_CHANGES`: when set, the helper checks that the referenced file exists.
- `RUNTIME_LOG_DIR`: host directory mounted to `/temp`. Defaults to a run-scoped directory under `tmp/teamcity` on amd64 or `tmp/teamcity-arm64` on ARM64.

Do not add a global Docker prune flag. Local cleanup must be scoped to resources created by the current run.

## Local Full Gate

Run the architecture-aware entry point:

```bash
bash .agents/skills/leveltravel-tests/scripts/local_rspec.sh
```

After editing any local gate helper, run its deterministic orchestration checks before the full gate:

```bash
bash .agents/skills/leveltravel-tests/scripts/test_local_rspec_tooling.sh
```

Both helpers serialize LevelTravel full local runs with a machine-wide lock, including when a helper is invoked directly, so two tasks cannot overload Docker or interfere with one another. If another full gate already owns the lock, report that state instead of starting a second run.

On Apple Silicon it delegates to:

```bash
bash .agents/skills/leveltravel-tests/scripts/native_arm64_rspec.sh
```

This path uses native ARM64 dependencies and runs the repository test script without QEMU. It is the required broad local gate on M-chip machines, but it is not TeamCity-equivalent because the remote build uses amd64 images and agents.

On x86_64 the entry point delegates to:

```bash
bash .agents/skills/leveltravel-tests/scripts/teamcity_rspec.sh
```

This is the local TeamCity-compatible path.

Derive the amd64 helper's temporary secret-safe Dockerfile from `lib/build/app/integration.Dockerfile`. Change only the GitHub credential transport from build arguments to a BuildKit secret. Fail closed when the canonical credential stanza changes so the local helper cannot silently drift from TeamCity.

## Canonical amd64 Diagnostic

To investigate amd64 parity explicitly, run the canonical helper directly:

```bash
bash .agents/skills/leveltravel-tests/scripts/teamcity_rspec.sh
```

On Apple Silicon this is diagnostic only. It uses amd64 emulation and may stall in `bundle install`, database preparation, or `parallel_rspec`; such a stall is a local emulation blocker, not a product-code or test failure. Do not replace a successful native ARM64 gate with a required local QEMU run.

## Resource Isolation And Cleanup

Each helper invocation must use a unique Compose project, container names, image tag, runtime-log directory, and Docker network. Concurrent Codex tasks must not share or tear down each other's services.

On success, failure, interruption, or signal, cleanup must remove only resources created by that invocation:

- the run-scoped test container and integration image;
- the run-scoped Compose project, including its anonymous MySQL volume, via `down -v --remove-orphans`;
- the exact external network created for the run;
- the run-scoped temporary Dockerfile and Compose override. Runtime logs stay in their run-scoped directory for diagnostics.

Never use `docker container prune`, `docker volume prune`, or another global cleanup command as part of the test helper. Historical Docker debris should be inspected and cleaned separately with explicit user approval.

## Focused Development Specs

For quick local feedback, focused host-side specs are acceptable when the local Ruby app boots:

```bash
bundle exec rspec spec/path/to/spec.rb
```

Reporting rules:

- label these as focused or host-side checks;
- do not call them a full local gate or CI-equivalent;
- if local Ruby cannot boot because of environment or native dependency issues, report the exact boot blocker.

Do not use `FILES_TO_RUN=... bash script/ci/ci.sh` as evidence of a focused CI run while `TEAMCITY_CI=1`; the CI path can ignore `FILES_TO_RUN` and execute the full suite.

## Exact Reporting Semantics

Always include the exact command and observed outcome. Use one of these labels:

```markdown
## Tests
- PASS local full ARM64 gate (not TeamCity-equivalent): `bash .agents/skills/leveltravel-tests/scripts/local_rspec.sh`
- PASS local TeamCity-compatible amd64 gate: `bash .agents/skills/leveltravel-tests/scripts/local_rspec.sh`
- PASS remote authoritative amd64 gate: TeamCity `rails-rspec` <build URL>
- PASS focused check: `bundle exec rspec spec/path/to/spec.rb`
- FAIL product/test: `<exact command>` - <failing example or application error>
- BLOCKED local infrastructure: `<exact command>` - <credential, Docker, registry, platform, or emulation blocker>
- PENDING remote authoritative amd64 gate: TeamCity `rails-rspec`
```

Rules:

- Never describe the native ARM64 run as TeamCity-equivalent or amd64 parity.
- Never describe an emulation, registry, Docker, disk, or credential blocker as a test failure.
- Never let a focused check imply that the full local gate passed.
- PR creation may proceed after the appropriate local gate and review pass, but the PR is not merge-ready until remote TeamCity `rails-rspec` passes.
