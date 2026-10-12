---
name: python-control-flow
description: Use when writing, refactoring, or reviewing Python code in this FastMCP repository for readability, including flat control flow, guard clauses, redundant else branches, helper extraction, explicit conditions, validation ordering, mutable state, and behavior-preserving refactors.
---

# Python Control Flow

Optimize for low cognitive complexity, not minimum indentation or line count.
Code should read top to bottom, make exceptional cases obvious, and keep the
happy path straightforward. Favor boring, explicit code, especially at trust
boundaries such as tool input validation, downstream URLs, and propagated
headers. Pair with `python-mcp-service` for adapter contracts and `testing` for
coverage.

## Flat Control Flow And Guard Clauses

- Keep nesting shallow, ideally one or two levels. Treat this as a guideline;
  extra nesting is fine when it genuinely reads better.
- Handle invalid input, terminal cases, and failures first with guard clauses
  and early returns, then let the main path run unindented.
- Do not add abstractions solely to reduce indentation.

Prefer:

```python
def _parse_recommendations(response: httpx.Response) -> list[dict[str, Any]]:
    if response.status_code >= 400:
        raise RecommendationClientError(response.status_code, {"error": "upstream_error"})
    payload = response.json()
    if not isinstance(payload, dict):
        raise RecommendationClientError(502, {"error": "malformed_response"})

    return payload.get("recommendations", [])
```

over nesting the success path inside `if response.is_success: if isinstance(...): ... else: raise ...`.

## Else Branches

- After `return`, `raise`, `break`, or `continue`, drop the redundant `else`.
- Keep `if/elif/else` when branches are mutually exclusive and converge on
  shared logic afterward. Do not split a clear chain into independent `if`
  statements when that changes behavior or hides exclusivity.

## Helpers And Conditions

- Extract helpers that name a real responsibility or rule, such as
  `_classify_downstream_failure()` or `_allowed_propagation_headers()`.
- Do not extract trivial helpers that only hide a few lines and force readers
  to jump between functions. Keep related logic together.
- Avoid nested ternaries, dense one-liners, and comprehensions that obscure
  intent. Move a genuinely complex condition into a well-named predicate;
  leave simple boolean expressions inline.

## Validation Before Business Logic

- Validate identifiers, ranges, configuration, and invariants before
  downstream I/O instead of interleaving checks with execution.
- For security-sensitive checks (header allowlists, URL validation, future
  authorization), do not let early returns or short-circuiting skip validation
  of remaining inputs. Preserve fail-closed behavior.

## State And Length

- Return results directly instead of flag variables that only drive the final
  return, e.g. `return any(is_disallowed(name) for name in headers)`.
- Keep an explicit loop when it gives better diagnostics or preserves
  validation and side-effect ordering.
- A few extra lines are fine when they make edge cases explicit or simplify
  debugging. Avoid premature generalization and forced idioms.

## Preserve Semantics

Readability changes must not change observable behavior unless requested.
Check validation order and completeness, exception types and messages, safe
error envelopes, side-effect and telemetry ordering, short-circuit behavior,
fail-closed guarantees, and public tool contracts. Explain any meaningful
behavioral difference or trade-off.

## Review Checklist

1. Unnecessary nesting that guard clauses or early returns would flatten.
2. Redundant `else` after terminal statements.
3. Complex conditions that deserve a named predicate.
4. Helpers that represent meaningful responsibilities, not indirection.
5. Unnecessary mutable state.
6. Preserved behavior, validation guarantees, and error handling.
7. Non-obvious decisions and trade-offs explained.

Apply this to new code and to code under review. Do not refactor unrelated
code purely for style; avoid unnecessary diffs.
