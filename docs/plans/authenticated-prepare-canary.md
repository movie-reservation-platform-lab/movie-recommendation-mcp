# Implementation Plan: Authenticated Prepare Canary

## 1. Summary

[Issue #12](https://github.com/movie-reservation-platform-lab/movie-recommendation-mcp/issues/12)
adopts merged [actions PR #18](https://github.com/movie-reservation-platform-lab/movie-platform-actions/pull/18)
at `036531133bcefd454b5afc0eb55f8ba0328901ea`. This is a small CI caller migration.

## 2. Goals

Coordinate both publisher actions and the PR scanner checkout; supply the required
prepare token; protect the caller contract with offline tests.

## 3. Non-goals

Application, Docker/dependency, exemption, schema, permission, or deployment changes.
No merge, publication/admission dispatch, ECR copy, or deployment.

## 4. Current State

Inspected upstream main: `7b56272d06cade0caee7368cad7117a4b5fa6919`; local main
matches and the starting worktree is clean. `.github/workflows/ci.yml` pins all
three tooling consumers to `bb40579c285df0b581c48b10f9b34574d5c78639`.
Publishing already has `contents: read` and a canonical push/main guard.
`automation/tests/test_release_contract.py` checks pins and publication contracts.

## 5. Requirements and Assumptions

Preserve v1alpha3, PR production-image scanning, all job permissions, and quality
gates. The merged caller migration notes require an explicit prepare token.
No implementation questions remain; live access and publication remain unverified.

## 6. Proposed Design

Change the three pins atomically and add `github-token: ${{ github.token }}` to
prepare. Update README release references and link the previous plan to this one.
Historical scan policy revisions remain unchanged as evidence.

## 7. Alternatives Considered

Coordinated adoption keeps PR/local scanning and publication on one reviewed
release. Updating prepare alone would leave tooling versions inconsistent and
omit related hardening; reject that partial migration.

## 8. API / Interface Changes

Prepare gains its required token input. Its authenticated exact-main lookup fails
closed on missing token, lookup failure, or a commit that differs from the run SHA.

## 9. Data Model / Persistence Changes

None. Evidence remains v1alpha3.

## 10. Security, Privacy, and Abuse Considerations

Use the job token expression, retaining existing permissions. Passing a token
does not reduce its authority. Publication stays restricted to canonical main
pushes. The release also hardens evidence failure paths (including bounded legacy
report reads and sanitized errors) and scanner cleanup; it is not only an auth fix.

## 11. Performance, Scalability, and Reliability Considerations

Upstream prepare uses one bounded authenticated lookup without anonymous fallback.
Central-policy access and scanner acquisition remain separate live dependencies.

## 12. Implementation Steps

1. Update `.github/workflows/ci.yml`: three pins and prepare input only.
2. Extend `automation/tests/test_release_contract.py`: exact reviewed pins,
   step-scoped prepare token, unchanged permissions and exact publication guard.
3. Update `README.md` and the prior PR-security plan's current pin reference.
4. Run offline checks, review the diff, commit with `[ai]`, push one branch and
   open one `[ai]` PR closing #12. Inspect ordinary hosted PR status separately.

## 13. Testing Strategy

Run `uv sync --frozen`, then `uv run --frozen --no-sync` with
`pytest tests automation/tests`, `ruff check .`, `ruff format --check .`, and
`python -m compileall src tests automation`. Run working, staged, and branch
`git diff --check`. Check negative token/pin/PR-guard regressions offline.

## 14. Rollout / Migration Plan

This PR is the canary; remaining consumers migrate separately after validation.
Offline tests do not prove hosted scanning, private-organization token access, or
canonical publication. Hosted PR checks cannot exercise prepare because
publication is disabled on PRs. Live publication/admission needs later authority.
Rollback reverts all three pins to `bb40579c285df0b581c48b10f9b34574d5c78639` and
removes the new prepare token input together, including matching tests/docs.

## 15. Risks and Mitigations

- Missing token or pin drift: step-scoped input and exact coordinated-pin tests.
- Accidentally enabling PR publication: assert the complete job guard.
- Overstated acceptance: distinguish offline, hosted PR, and canonical checks.

## 16. Done Criteria

One issue, branch, and small pushed PR; offline checks pass; live status is
reported separately; all scope restrictions hold.

## 17. Review Checklist

- [x] Requirements, scope, existing conventions, and alternatives inspected.
- [x] Security, reliability, validation, rollout, and rollback specified.
- [x] Final diff and checks reviewed before PR handoff.

Offline result (2026-09-15): frozen sync, 22 tests, Ruff lint/format, compile,
and diff checks passed. Seven temporary in-memory mutations confirmed token,
pin, permission, and publication-guard regressions are rejected. Read-only
security review found no material issues; the configured review model was
unavailable, so the same role instructions ran with the available model.
Live canonical prepare/publication acceptance remains outstanding.

## 18. Handoff Prompt for Implementation Agent

Implement steps 1–4 with the exact reviewed SHA. Preserve all stated boundaries,
run the checks in section 13, and report live acceptance separately. The user
has authorized implementation, issue creation, branch push, and PR creation.
