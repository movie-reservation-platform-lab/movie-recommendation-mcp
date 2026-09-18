# Movie Recommendation MCP

FastMCP wrapper around the Rust movie recommendation API.

This repository was extracted from
`movie-reservation-platform-lab/movie-recommendation-service/axum-tools-mcp` so
the MCP component can have an independent CI and artifact pipeline.

## Run

```sh
uv run movie-recommendation-mcp
```

The production container runs as UID `10001` and listens on port `8092`:

```sh
docker build --tag movie-recommendation-mcp:local .
docker run --rm --network host movie-recommendation-mcp:local
```

The optional development target keeps `uv`, curl, source, and test tooling in a
separate image without adding them to production:

```sh
docker build --target development --tag movie-recommendation-mcp:development .
docker run --rm --network host movie-recommendation-mcp:development
```

The production target starts again from the clean Python runtime stage and
copies only the built virtual environment. Adding development tools therefore
does not change the published runtime contents.

The demo assumes the MCP and recommendation API containers share one ECS task
network namespace, so the default downstream address remains
`127.0.0.1:8082`. Override the downstream URL when running the containers
independently.

Defaults:

- MCP endpoint: `http://127.0.0.1:8092/mcp`
- Health endpoint: `http://127.0.0.1:8092/health`
- Downstream API: `http://127.0.0.1:8082`

Useful environment variables:

- `MOVIE_RECOMMENDATION_API_URL`
- `AXUM_TOOLS_API_URL` for compatibility with the original demo extraction
- `PORT`
- `HOST`
- `OTEL_SERVICE_NAME`
- `OTEL_EXPORTER_OTLP_ENDPOINT`
- `OTEL_EXPORTER_OTLP_PROTOCOL`
- `OTEL_RESOURCE_ATTRIBUTES`

## Tools

- `recommendation_get_movies`
  - Inputs: `limit`, optional `preference`, optional `fault`, optional
    `traceparent`, optional `tracestate`, optional `correlation_id`, optional
    `request_id`, and optional `demo_fault`.
  - Calls Rust `GET /recommendations`.
  - Success payload: `{"ok": true, "service_name": "movie-recommendation-mcp", "fault": "<fault-or-none>", "recommendations": [...]}`
  - Downstream error payload: `{"ok": false, "service_name": "movie-recommendation-mcp", "fault": "<fault-or-none>", "status_code": <int>, "error": "recommendation_dependency_failed"}`
- `recommendation_health`
  - Inputs: optional `traceparent`, optional `tracestate`, optional
    `correlation_id`, optional `request_id`, and optional `demo_fault`.
  - Calls Rust `GET /health`.
  - Success payload: `{"ok": true, "service_name": "movie-recommendation-mcp", "health": {...}}`

Both tools forward:

- `traceparent`
- `tracestate`
- `X-Correlation-Id`
- `X-Request-Id`
- `X-Demo-Fault`

The emitted metric, trace, resource, and structured-log contract is recorded in
[the local producer evidence](docs/observability/recommendation-mcp-emitted-signals.md).
Collector acceptance and live backend queryability are verified separately by
the platform repositories.

## Extraction Decisions

- Keep the internal Python import path as `axum_tools_mcp` for this extraction
  slice. The public package, console script, service name, image, and repository
  are already named `movie-recommendation-mcp`; renaming the import path would
  add churn without changing the external MCP contract consumed by the agent.
- Keep the tool names `recommendation_get_movies` and `recommendation_health`.
  The proven reservation-agent demo allowlisted `recommendation_get_movies` and
  called it with `limit`, `preference`, `fault`, and propagation arguments.
- Keep `AXUM_TOOLS_API_URL` as a compatibility fallback, but prefer
  `MOVIE_RECOMMENDATION_API_URL` for new runtime configuration.

## Artifact Contract

Platform infrastructure consumes this component as an immutable application
artifact, not as source code:

- OCI image built from this repository's `Dockerfile`.
- Private ECR image reference pinned by digest:
  `<account>.dkr.ecr.<region>.amazonaws.com/movie-recommendation-mcp@sha256:<64-hex-digest>`.
- Separate release identifier, such as the Git commit SHA or release version,
  recorded alongside the digest by the consuming environment/infra repository.
- Runtime command: `movie-recommendation-mcp`.
- Container port and default `PORT`: `8092`.
- MCP endpoint: `/mcp`.
- Health endpoint: `/health`.
- Required runtime configuration is environment-driven; the downstream API URL
  is supplied with `MOVIE_RECOMMENDATION_API_URL` or the compatibility fallback
  `AXUM_TOOLS_API_URL`.
- Deployment composition, environment manifests, promotion state, and AWS
  resources stay outside this repository.

## Checks

```sh
uv sync --frozen
uv run --frozen --no-sync pytest tests
uv run --frozen --no-sync pytest automation/tests
uv run --frozen --no-sync ruff check .
uv run --frozen --no-sync ruff format --check .
uv run --frozen --no-sync python -m compileall src tests automation
```

Pushes to `main` publish a Linux AMD64 candidate to GHCR as
`sha-<commit>-run-<run-id>-attempt-<attempt>`. CI disables BuildKit's automatic registry attestation to keep
the candidate a single-image manifest, then records explicit GitHub build
provenance against the published digest for the environment admission gate.

### Container security evidence

The pinned organization-owned actions publish the signed
`recommendation-mcp-security-evidence-<run-id>-attempt-<attempt>` artifact:
`component-candidate-evidence-v1alpha3.json`, verified image provenance,
CycloneDX SBOM, and subject-bound vulnerability report. Evidence is retained
for 14 days. Missing provenance or any CRITICAL finding without a current,
exact central exemption fails publication of the canonical evidence package.
Raw findings stay visible; covered findings produce `passed-with-exemptions`.
HIGH findings remain visible for admission review.

Run/attempt tags are discovery hints, not deployment selectors. Environment
verification independently checks the successful canonical run and signed
package before admitting its exact digest to ECR. This producer has no AWS
credentials or deployment authority. Older runs without this package are not
eligible for the new admission path; use a fresh successful main run.
The environment reader must support v1alpha3 before admission. It independently
reevaluates original findings against the latest approved central policy.
See [the shared action contract](https://github.com/movie-reservation-platform-lab/movie-platform-actions/blob/036531133bcefd454b5afc0eb55f8ba0328901ea/docs/container-candidate-actions.md).

This canary adopts [actions PR #18](https://github.com/movie-reservation-platform-lab/movie-platform-actions/pull/18)
at `036531133bcefd454b5afc0eb55f8ba0328901ea` for both publisher actions and the
PR/local scanner. Prepare receives `github-token: ${{ github.token }}` for its
authenticated canonical-main lookup, using the publishing job's existing
`contents: read` permission. The job's other permissions remain required;
passing its token does not reduce that token's authority. This release also
hardens evidence failure paths (including bounded legacy report reads and safe
errors) and scanner cleanup. Evidence remains v1alpha3.

Offline caller tests verify wiring and guards. Hosted PR scanning does not
exercise prepare or prove private-repository access or canonical publication;
those require separate live rollout acceptance. Publication remains restricted
to push events on this repository's canonical main. Rollback reverts both action
pins, the PR tooling checkout, and the documented local tooling pin to
`bb40579c285df0b581c48b10f9b34574d5c78639`, and removes the new prepare token input
together. See the [canary plan](docs/plans/authenticated-prepare-canary.md).

### PR and local vulnerability checks

`container-security-check` builds the production linux/amd64 image on PRs and
other non-canonical runs. It uses the same reviewed shared tooling and v1alpha3
policy as publication, with only `contents: read`. The GitHub token is supplied
only to the scan/evaluation step to read approved policy from the actions repo.
An uncovered CRITICAL or a scanner/policy retrieval error fails the job.

The complete report, policy decisions and summary are retained for 14 days as
`recommendation-mcp-pr-vulnerability-report-<run>-attempt-<attempt>`, including
after a failed gate. These local-image diagnostics are not signed candidate
evidence. Canonical main publication independently scans its exact GHCR digest.

To reproduce using a sibling actions checkout at the reviewed commit:

```sh
git -C ../movie-platform-actions rev-parse HEAD
# Expected: 036531133bcefd454b5afc0eb55f8ba0328901ea
docker build --pull --platform linux/amd64 --target prod \
  --tag movie-recommendation-mcp:local .
# Supply GH_TOKEN securely through your normal environment setup.
node ../movie-platform-actions/local-tools/container-security/lib/scan.mjs \
  movie-recommendation-mcp:local \
  --evidence-version v1alpha3 --component recommendation-mcp
```

The helper writes an ignored `.local-container-security/run-*/` directory.
Exit 0 means policy pass, 1 means blocking findings, and 2 means an operational
or validation failure. Request exemptions separately in
[the central governance repository](https://github.com/movie-reservation-platform-lab/movie-platform-actions/blob/036531133bcefd454b5afc0eb55f8ba0328901ea/security-exemptions/README.md)
using the exact CVE/package/version/PURL from the complete report and supporting
applicability evidence. An unmerged request does not unblock the gate. After
maintainer approval reaches central main, re-run the PR check; no new producer
pin is needed for policy changes.
