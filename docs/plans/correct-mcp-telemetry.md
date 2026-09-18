# Implementation Plan: Correct Recommendation MCP Telemetry

## 1. Summary

Correct recommendation MCP trace parenting, returned-failure outcomes, metric
cardinality, resource identity, and local emitted-signal evidence without
changing the two public MCP tool contracts. Use the existing OpenTelemetry SDK
and in-memory exporters; do not add a dependency or an infrastructure change.

## 2. Goals

- Join a valid incoming W3C trace before creating each MCP tool span.
- Keep instrumented downstream work beneath the active MCP span.
- Record dependency and unexpected failures as errors even when the safe tool
  result is returned instead of raised.
- Restrict metric attributes to the two allowlisted tools and a finite outcome
  set.
- Emit canonical service resource identity and correlated bounded JSON logs.
- Supply deterministic local exporter evidence for the infra issue #57 mapping.

## 3. Non-goals

- Changing tool names, arguments, result envelopes, downstream behavior, or
  retry semantics.
- Removing compatibility fault inputs in this issue.
- Changing collector configuration, dashboards, alerts, deployment selection,
  or AWS resources.
- Claiming backend acceptance or live queryability from local evidence.

## 4. Current State

`src/axum_tools_mcp/server.py` catches `RecommendationClientError` inside
`tool_span` and returns a safe error. The context manager therefore exits
normally and records `success`. `tool_span` also starts without extracting its
`traceparent`/`tracestate`, while `RequestMetadata` merely forwards those values
to the downstream client. Arbitrary fault text is currently a metric label.

`src/axum_tools_mcp/telemetry.py` already configures OTLP HTTP exporters and
HTTPX instrumentation. It uses `service.environment` rather than the advisory
contract's `deployment.environment.name`, and logs do not automatically carry
the active trace/span identifiers.

The advisory contract and implementation plan were read from the current
uncommitted issue-57 infra checkout on 2026-09-18. Producer evidence must
correct that contract before collector implementation if observed names or
semantics differ.

## 5. Requirements and Assumptions

### Confirmed Requirements

- Preserve `recommendation_get_movies` and `recommendation_health` signatures
  and response shapes.
- Preserve allowlisted HTTP propagation and safe downstream errors.
- Metrics may contain only bounded tool and outcome dimensions.
- IDs and compatibility fault values may appear only as bounded span/log fields.
- Ordinary tests remain network- and credential-independent.

### Assumptions

- FastMCP schema validation that rejects a call before entering the decorated
  function is outside this manual tool-span boundary.
- Clamping `limit` remains successful behavior because that is the established
  public contract.
- The initial bounded outcome set is `success`, `dependency_error`, and
  `internal_error`.

### Open Questions

- None blocking implementation. AMP/CloudWatch translated names and live export
  cadence remain infrastructure acceptance evidence, not producer-local facts.

## 6. Proposed Design

Extract W3C headers with `TraceContextTextMapPropagator` and pass the extracted
context to `start_as_current_span`. Yield a small tool-call observation from the
context manager. Callers mark a returned dependency failure on that observation;
unexpected raised exceptions are recorded and re-raised by the context manager.
At exit, one counter point and one duration point receive only the hard-coded
tool name and finite outcome.

Build the SDK resource from canonical local defaults and merge standard
`OTEL_RESOURCE_ATTRIBUTES`/`OTEL_SERVICE_NAME` environment values. JSON logs add
UTC timestamp, deployment identity, and active trace/span IDs. String fields are
bounded, and the raw recommendation preference is not logged.

## 7. Alternatives Considered

### Raise and catch a private exception outside `tool_span`

- Pros: existing context manager would observe an exception.
- Cons: complicates ordinary safe-return control flow and risks changing tool
  behavior.
- Decision: rejected.

### Infer failure by inspecting the returned dictionary

- Pros: minimal caller edits.
- Cons: couples telemetry to response shape and cannot represent unexpected
  internal errors clearly.
- Decision: rejected in favor of explicit bounded outcome recording.

## 8. API / Interface Changes

No MCP, HTTP, configuration, or response-contract change. Internal telemetry
helpers gain explicit context and outcome handling.

## 9. Data Model / Persistence Changes

None.

## 10. Security, Privacy, and Abuse Considerations

- Ignore invalid W3C context rather than trusting it as a valid parent.
- Never put trace, correlation, request, preference, fault, exception, URL, or
  user-controlled values in metric attributes.
- Bound propagated diagnostic strings in spans and logs.
- Keep raw downstream payloads and exception details out of safe results and
  span status descriptions.

## 11. Performance, Scalability, and Reliability Considerations

The change adds no network call and records the same number of telemetry points.
Exporter absence remains fail-open. Attribute sets remain finite, preventing
caller-driven time-series growth.

## 12. Implementation Steps

1. Refactor telemetry lifecycle and context extraction.
   - Files: `src/axum_tools_mcp/telemetry.py`.
   - Verification: focused in-memory span/metric tests.
2. Report returned dependency outcomes explicitly.
   - Files: `src/axum_tools_mcp/server.py`.
   - Verification: existing response tests plus success/failure telemetry tests.
3. Add exact emitted-signal evidence.
   - Files: `tests/test_telemetry.py`,
     `docs/observability/recommendation-mcp-emitted-signals.md`.
   - Verification: evidence values are asserted from SDK in-memory exporters.
4. Run all repository checks and container smoke.

## 13. Testing Strategy

- Verify valid parent trace/span IDs and an active child span for downstream
  work; verify invalid context starts a new trace safely.
- Verify success, returned dependency failure, and raised internal failure span
  status/outcome plus counter and duration attributes.
- Verify no metric point contains fault or identifier attributes.
- Verify canonical resource identity and no-exporter behavior.
- Preserve existing tool/client/health/propagation regression tests.

## 14. Rollout / Migration Plan

Merge and publish an immutable producer image through existing CI. Infra issue
#57 reconciles the observed payload before wiring changes. Environment selection
and live backend acceptance are separate coordinated steps. Rollback selects the
previous immutable producer image with the previous composition.

## 15. Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
| --- | ---: | ---: | --- |
| Returned failures still look successful | High | Low | Assert span status and metric outcome from the public tool call. |
| Context extraction accepts malformed input | Medium | Low | Use the standard W3C propagator and test malformed context. |
| Caller data enters metric labels | High | Low | Construct attributes only from internal constants and assert exact keys. |
| Local names are mistaken for backend names | Medium | Medium | Document emitted evidence separately from future accepted/queryable mappings. |

## 16. Done Criteria

- Incoming W3C context parents the MCP span and downstream child work.
- Dependency failures record `dependency_error`, never `success`.
- Metric attribute keys and values are finite and test-proven.
- Canonical resources and correlated logs are emitted without sensitive fields.
- Exact local payload evidence is documented and asserted.
- Frozen tests, automation tests, Ruff, compile, diff check, and container smoke
  pass.

## 17. Review Checklist

- [x] Requirements and non-goals are explicit.
- [x] Existing code and test conventions were inspected.
- [x] Alternatives were considered.
- [x] Security, cardinality, reliability, testing, and rollback are covered.
- [x] Steps name concrete files and verification.

## 18. Handoff Prompt for Implementation Agent

```text
Implement docs/plans/correct-mcp-telemetry.md for issue #6. Preserve public MCP
contracts and safe error responses. Use existing OpenTelemetry dependencies,
in-memory exporter tests, and bounded internal outcome constants. Do not alter
infra, publish, deploy, or claim live backend acceptance. Run the full frozen
repository checks and production container smoke.
```
