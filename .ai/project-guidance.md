# Project AI Guidance

This repository owns the Python FastMCP wrapper around the Rust recommendation
API. It exposes stable recommendation tools to `movie-reservation-agent` and
keeps transport, downstream HTTP, and observability propagation at the adapter
boundary.

## Repository Layout

- `src/axum_tools_mcp/`: FastMCP tools, downstream recommendation client,
  health routes, telemetry, and process entry point.
- `tests/`: tool-contract, downstream-error, propagation, and smoke-oriented
  coverage.
- `.ai/`: canonical AI guidance, skills, and read-only review agents.

The internal package name is inherited from the experimental source. Rename it
only through an explicit compatibility and artifact-entry-point migration.

## Development Commands

- Install/sync: `uv sync --frozen`
- Tests: `uv run --frozen --no-sync pytest`
- Lint: `uv run --frozen --no-sync ruff check .`
- Format check: `uv run --frozen --no-sync ruff format --check .`
- Compile check: `uv run --frozen --no-sync python -m compileall src tests`
- Run locally: `uv run --frozen --no-sync movie-recommendation-mcp`

Inspect `pyproject.toml` and CI before changing or inventing commands.

## Tool And Adapter Contracts

- Keep `recommendation_get_movies` and `recommendation_health` stable unless a
  coordinated agent migration explicitly changes them.
- Keep MCP tools thin: validate input, construct metadata, call the downstream
  client, and map a stable tool result.
- Keep endpoint configuration, HTTP lifecycle, timeouts, response parsing, and
  downstream error classification in the client/adapter boundary.
- Preserve `traceparent`, `tracestate`, `X-Correlation-Id`, `X-Request-Id`, and
  `X-Demo-Fault` without forwarding arbitrary caller headers.
- Keep metric labels bounded. Request, trace, correlation, movie, and user IDs
  belong in spans/log fields, not metric labels.
- Return bounded safe errors without raw downstream bodies or stack traces.

## Repository Boundaries

- The Rust API owns recommendation behavior.
- The agent owns orchestration and user-facing dialogue behavior.
- This repository owns MCP translation and the downstream HTTP adapter.
- Publish an immutable container image; selection and deployment belong to the
  platform repositories.

## Testing Guidance

- Test tool names, input mapping, downstream failures, timeout behavior,
  propagated metadata, health behavior, and telemetry-safe outcomes.
- Use `httpx.MockTransport` or narrow fakes for ordinary tests.
- Keep real local-service smoke tests separately configured and deterministic.

## Safety

- Do not commit secrets, credentials, tokens, local env values, or production
  payloads.
- Treat downstream URLs, propagated headers, provider errors, and future
  mutating tools as security-sensitive boundaries.
- Do not push, deploy, promote, or mutate AWS/shared environment state without
  explicit user instruction.

## Planning And Review

- Use `principal-engineer-planner` before tool-contract, package rename,
  transport, topology, observability, or compatibility changes.
- Save implementation plans under `docs/plans/`.
- Ask review agents for findings first and require file/line evidence.
