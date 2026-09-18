# Recommendation MCP Emitted-Signal Evidence

This is producer-local **emitted** evidence for
`movie-recommendation-mcp#6`. It was captured on 2026-09-18 with the locked
OpenTelemetry Python SDK 1.42.1 and in-memory SDK exporters. It does not prove
collector acceptance, AMP/CloudWatch translation, or live queryability.

The advisory source was the issue-57 working copy of
`movie-platform-infra/docs/observability/service-signal-contract.md` reviewed on
2026-09-18. Infrastructure should reconcile that contract with these observed
values before implementing collector filters or queries.

## Resource identity

Both spans and metrics carry:

| Attribute | Local evidence value | Runtime source |
| --- | --- | --- |
| `service.name` | `movie-recommendation-mcp` | `OTEL_SERVICE_NAME`, with canonical default |
| `service.namespace` | `movie-platform` | `OTEL_RESOURCE_ATTRIBUTES`, with canonical default |
| `service.version` | immutable version selected by the environment | `SERVICE_VERSION` |
| `deployment.environment.name` | environment name | `OTEL_RESOURCE_ATTRIBUTES`, falling back to `DEPLOYMENT_ENVIRONMENT` |

Standard SDK resource attributes such as `telemetry.sdk.*` are also present.

## Tool metrics

| Native instrument | SDK data | Unit | Temporality | Exact attributes |
| --- | --- | --- | --- | --- |
| `axum_tools_mcp_tool_calls_total` | monotonic `Sum` | `{call}` | cumulative | `mcp.tool.name`, `outcome` |
| `axum_tools_mcp_tool_duration_ms` | `Histogram` | `ms` | cumulative | `mcp.tool.name`, `outcome` |

Allowed tool values are `recommendation_get_movies` and
`recommendation_health`. Allowed outcome values are `success`,
`dependency_error`, and `internal_error`. A completed call emits one counter
increment and one real duration observation. Before the first call, and while
idle, the producer does not invent requests or zero-duration observations.

Fault values, preferences, request IDs, correlation IDs, trace IDs, URLs,
exception messages, and downstream payloads are absent from metric attributes.
An observed returned dependency failure produced:

```json
{
  "instrument": "axum_tools_mcp_tool_calls_total",
  "unit": "{call}",
  "type": "Sum",
  "temporality": "CUMULATIVE",
  "value": 1,
  "attributes": {
    "mcp.tool.name": "recommendation_get_movies",
    "outcome": "dependency_error"
  }
}
```

AMP series names, CloudWatch dimensions, collector export cadence, and backend
freshness behavior remain **unknown until infra acceptance evidence exists**.
Do not convert missing or stale points into a healthy zero.

## Traces and propagation

- MCP span names are `mcp.tool.recommendation_get_movies` and
  `mcp.tool.recommendation_health` with `SERVER` kind.
- Valid incoming `traceparent` and `tracestate` are extracted before creating
  the MCP span. Invalid context safely starts a new trace.
- Instrumented HTTPX calls create a downstream `CLIENT` span beneath the MCP
  span and inject that client span into the outbound W3C header.
- Success uses span status `OK`; a safe returned dependency error uses `ERROR`
  with description and `mcp.tool.outcome` equal to `dependency_error`.
- An unexpected raised error uses the bounded outcome `internal_error` and a
  bounded exception type. The exception message is not copied into span status
  or metric attributes.
- Compatibility fault, correlation, and request values are bounded span fields,
  not metric labels.

## Structured logs

JSON stdout events include UTC timestamp, severity, event/message,
`service_name`, `service_version`, `deployment_environment`, and active
`trace_id`/`span_id`. Tool, outcome-related event, correlation, request, and
compatibility fault fields are bounded. Raw recommendation preference text is
not logged.

## Reproduce

The network-independent evidence assertions are in `tests/test_telemetry.py`:

```sh
uv sync --frozen
uv run --frozen --no-sync pytest tests/test_telemetry.py -vv
```

They cover the real HTTPX instrumentation boundary, W3C parent/child IDs,
success and failure statuses, exact metric keys/values, canonical resources,
bounded correlated logs, invalid context, and exporter-free operation.
