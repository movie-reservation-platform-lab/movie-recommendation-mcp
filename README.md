# Movie Recommendation MCP

FastMCP wrapper around the Rust movie recommendation API.

This repository was extracted from
`movie-reservation-platform-lab/movie-recommendation-service/axum-tools-mcp` so
the MCP component can have an independent CI and artifact pipeline.

## Run

```sh
uv run movie-recommendation-mcp
```

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
  - Inputs: `limit`, optional `preference`, optional `fault`, and optional propagation fields.
  - Calls Rust `GET /recommendations`.
- `recommendation_health`
  - Calls Rust `GET /health`.

Both tools forward:

- `traceparent`
- `tracestate`
- `X-Correlation-Id`
- `X-Request-Id`
- `X-Demo-Fault`

## Checks

```sh
uv run python -m compileall src
```
