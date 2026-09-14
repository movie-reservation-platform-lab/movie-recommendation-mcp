# Implementation Plan: Container Security PR Gate

## Verification result (2026-09-14)

The revised production image passed the shared v3 policy with zero CRITICAL,
53 HIGH and zero exemptions after refreshing perl-base to 5.40.1-6+deb13u1.
No exemption request is needed for the three findings in the earlier local build.
Debian marks all three fixed in that update:
[CVE-2026-13221](https://security-tracker.debian.org/tracker/CVE-2026-13221),
[CVE-2026-42496](https://security-tracker.debian.org/tracker/CVE-2026-42496) and
[CVE-2026-8376](https://security-tracker.debian.org/tracker/CVE-2026-8376).

- Local image ID: `sha256:5b3ecb8e7020d667ff586f2341859c7265cd71b5e20f58cce44284d801644ad6`.
- Scanner: Trivy 0.70.0, digest
  `sha256:be1190afcb28352bfddc4ddeb71470835d16462af68d310f9f4bca710961a41e`.
- Policy revision: `bb40579c285df0b581c48b10f9b34574d5c78639`,
  evaluated at `2026-09-14T20:44:11Z`.
- Local diagnostics retained outside Git under
  `/tmp/recommendation-mcp-issue10-fixed-scan/run-r5ZbzC/`.
- Frozen pytest: 21 passed; Ruff lint/format, compile and diff checks passed.
- Real container: health and MCP health tool passed with a task-local stub;
  both expected tool names were discovered; UID 10001, no uv/curl/source.
- Read-only security/maintainability review found no material code defects.

Local diagnostics are not publication or admission evidence. Hosted PR checks
and subsequent authorized canonical publication remain separate validation.

> Superseded implementation decisions (2026-09-14): the user requested completing
> this work, creating its PR, adopting the latest shared actions, running a fresh
> vulnerability check, and then requesting central exemptions. The decisions below
> take precedence over the historical two-pass/zero-raw-CRITICAL plan retained here.

## Current implementation and acceptance

- Preserve the prepared Trixie runtime minimization and development target.
- Fresh 2026-09-14 inspection found Debian's fixed perl-base 5.40.1-6+deb13u1
  available. Refresh that installed base package in prod and rescan before
  requesting any exemption. If no CRITICAL remains, document that no request is
  needed rather than filing exemptions for obsolete package versions.
- Pin both publisher actions and the PR tooling checkout to
  `bb40579c285df0b581c48b10f9b34574d5c78639` (actions PR #13).
- Add `container-security-check` for non-canonical executions. Build prod for
  linux/amd64, then use the checked-in Node 24 helper with
  `--evidence-version v1alpha3 --component recommendation-mcp`.
- Select `evidence-version: v1alpha3` in canonical publication as well.
- Use contents:read only, no registry login, and expose GH_TOKEN only to the scan
  step. Pin the separate tooling checkout and disable persisted credentials.
- Keep the helper's exit code; upload its dedicated runner-temp diagnostic
  directory after policy failure, retained for 14 days.
- Extend automation tests for trigger coverage, permissions, matching pins/version,
  failure propagation and report retention. Update README with local reproduction.
- Run frozen Python tests/lint/format/compile, build, runtime smoke and a fresh v3
  scan. Record the exact image ID, report hash, policy revision and remaining CVEs.
- Open the producer PR even if uncovered CRITICAL findings remain. The user now
  explicitly requests the governed-exemption route; zero raw CRITICAL is no longer
  the handoff criterion. Every unapproved CRITICAL must still block.
- Prepare a separate draft actions-repository request from primary advisories and
  exact runtime findings. Proposed approval metadata is pending a maintainer
  decision; no exemption is approved or merged by this task.
- Reassess all hosted producer PR checks and their retained report. Publication
  success and environment-owned hosted v3 admission activation remain later gates.
- The shared helper replaces the two-pass alternative because it uses the same
  evaluator as publication and honors current central policy without local ignores.
- Budget 20 minutes for the PR job; its scanner and policy retrieval have their
  own bounded execution. Acquisition failures stop evaluation without fallback.
- Rollback reverts the producer workflow/image/pin change. No merge, publication
  dispatch, image push, ECR admission, deployment or AWS mutation is authorized.

The sections below preserve the earlier investigation and image-design rationale;
references to a future shared helper, two scans and zero raw CRITICAL are historical.

## 1. Summary

[Issue #10](https://github.com/movie-reservation-platform-lab/movie-recommendation-mcp/issues/10)
tracks a security-sensitive CI and runtime-image correction. First test a
minimized Debian Trixie Python 3.12 image, keep `uv` in build-only stages,
remove runtime `curl`, and add a credential-free PR-time
`linux/amd64` image vulnerability gate. The PR gate will retain a complete
all-severity Trivy JSON report and use a separate CRITICAL-only Trivy pass to
fail closed without copying the shared publication evaluator into this
repository.

## 2. Goals

- Remove the five CRITICAL findings that rejected main run `34474678097`
  without CVE exceptions or policy weakening.
- Build, scan, and smoke-test the proposed amd64 runtime before PR handoff.
- Run an equivalent CRITICAL vulnerability gate before merge on PR and other
  non-canonical executions, with only `contents: read` permission.
- Retain the complete OS/library report even when the policy pass fails.
- Preserve canonical main publication, exact-digest scanning, attestations,
  and signed evidence handoff.
- Include the pre-existing `AGENTS.md` and hybrid-teaching skill files in the
  same branch and PR as requested.

## 3. Non-goals

- Vulnerability allowlists, applicability suppressions, severity changes, or
  global `ignore-unfixed` behavior.
- Treating PR diagnostics as publication/admission evidence.
- Publishing, manually dispatching, admitting to ECR, deploying, or changing
  AWS/shared environment state.
- Reimplementing the shared action's subject-bound evidence evaluator.
- Changing FastMCP tools, transport contracts, or Python dependencies.

## 4. Current State

- `.github/workflows/ci.yml` runs quality, contract, automation, and container
  smoke jobs for PRs. Only the canonical `publish-image` job invokes the pinned
  shared `container-evidence` action and therefore only main scans for
  vulnerabilities.
- `publish-image` builds a single `linux/amd64` image, passes its exact digest
  to the shared action, and has the narrowly required package, OIDC, and
  attestation write permissions.
- `Dockerfile` uses `python:3.12-slim-bookworm`, installs `ca-certificates`,
  `curl`, and `tini`, and copies the `uv` binaries and the whole `/app` build
  directory into production.
- A fresh local amd64 baseline build on 2026-09-10 reproduced five CRITICAL
  findings: SQLite `CVE-2025-7458`, Perl `CVE-2026-13221`,
  `CVE-2026-42496`, `CVE-2026-8376`, and zlib `CVE-2023-45853`.
- Debian's tracker lists Trixie's SQLite and zlib versions as fixed but still
  lists Trixie's Perl version as vulnerable for all three cited Perl records,
  so switching Debian releases alone does not meet the unmodified gate.
- `automation/tests/test_release_contract.py` protects publication ordering,
  action pins, permissions, and smoke/runtime properties but has no PR scan
  regression.
- The organization action pin contains a substantial, tested evaluator capable
  of local subjects internally, but exposes it only through the signed
  exact-digest publication composite.

## 5. Requirements and Assumptions

### Confirmed Requirements

- The branch starts at current `origin/main` commit `1db48e4`.
- Every new commit and the PR title use the `[ai]` prefix.
- PR scans include OS and language packages, unfixed findings, and all
  severities in the retained report.
- CRITICAL findings fail the PR job, and report upload runs after policy
  failure when the workflow was not cancelled.
- Main retains the exact shared-action call and exact build digest input.

### Assumptions

- `python:3.12-slim-trixie` can resolve the locked runtime dependencies and
  pass the existing smoke contract. This must be proven before adopting it.
- Python's standard-library HTTP client is sufficient for the image health
  check, allowing removal of runtime `curl`.
- A second pinned Trivy invocation is an acceptable short-term policy
  evaluator: the first invocation writes the complete report with exit code
  zero; the second selects only CRITICAL findings and exits nonzero on a match.

### Open Questions

- Implementation evidence determines whether the Trixie candidate is viable
  and which findings, if any, remain after minimization.
- Remaining non-applicable findings must not be silently suppressed. A
  governed VEX path is tracked in `movie-platform-actions#5`; Alpine or a more
  bespoke runtime remains a fallback only if Trixie cannot pass without an
  unavailable exception mechanism.
- The shared-actions repository should later expose a read-only local-image
  vulnerability-gate composite so producers can share subject validation,
  summary formatting, scanner pins, and policy logic. This PR documents but
  does not implement that cross-repository enhancement.

## 6. Proposed Design

Use one Trixie Python base for dependency and build stages, but create the
production stage directly from the clean Python runtime rather than the
`uv`-bearing build-tools stage. Install only `ca-certificates` and `tini` in
production, create the non-root user, and copy only `/venv`. Replace the shell
and curl health check with `python -c` using `urllib.request`. This preserves
glibc, Python 3.12, and executable contracts while removing runtime `uv`, curl,
and source/build metadata and upgrading SQLite/zlib to Trixie's fixed versions.
Provide a separate optional `development` target derived from `build-tools`
that contains `uv`, curl, source, tests, automation, and development
dependencies, including the workflow file exercised by automation tests; no
production or CI publication stage inherits from it. Include the Dockerfile
and workflow as fixtures so the repository automation suite runs inside the
development image.

Add `container-security-check` alongside `container-smoke`. It runs only when
the canonical main publisher does not run, depends on `quality` and
`automation-tests`, declares only `contents: read`, builds the production image
for `linux/amd64`, emits the complete JSON report with the same pinned
Trivy-action/version used by publication, performs a CRITICAL-only fail-closed
scan, and uploads the complete report under a PR-diagnostic artifact name with
`if: !cancelled()`. The publisher does not consume this local report and keeps
its existing exact-digest shared action.

## 7. Alternatives Considered

### Alternative A: Debian Trixie slim

- Pros: Small change with the same libc/distribution family.
- Cons: Debian currently lists Trixie's Perl package as vulnerable to the three
  cited advisories, so the unchanged scanner policy may still fail.
- Decision: Chosen as the lowest-risk first experiment because it keeps glibc,
  fixes SQLite/zlib, and supplies evidence about the remaining package set.

### Alternative B: Distroless or manually assembled Python runtime

- Pros: Very small OS inventory and no package manager/shell.
- Cons: Official distroless Python version compatibility and copied CPython
  shared-library completeness add more runtime risk and bespoke maintenance.
- Decision: Rejected for this bounded incident fix unless Trixie cannot be made
  policy-compliant without unsafe package manipulation.

### Alternative C: Alpine Python runtime

- Pros: Removes Debian package findings and has a small runtime inventory.
- Cons: Changes glibc to musl and therefore introduces a wider native-wheel and
  runtime compatibility boundary.
- Decision: Retained as a tested fallback, not the first remediation.

### Alternative D: Copy the shared evaluator locally

- Pros: Full report validation and rich summary immediately.
- Cons: Duplicates substantial security policy code and creates drift across
  producers.
- Decision: Rejected. Use pinned Trivy policy behavior now and track a shared
  read-only composite enhancement.

### Alternative E: One report scan plus one CRITICAL policy scan

- Pros: Small workflow-only implementation, fail-closed behavior, no policy
  code duplication, same scanner/database within one job, and report retention
  independent of policy result.
- Cons: Scans the local image twice and lacks the shared evaluator's explicit
  JSON subject/schema validation and rich summary.
- Decision: Chosen as the bounded fix; document the shared-action enhancement.

## 8. API / Interface Changes

No MCP or runtime API change. CI gains the stable job/check name
`container-security-check` and the diagnostic artifact
`recommendation-mcp-pr-vulnerability-report-<run>-attempt-<attempt>`.

## 9. Data Model / Persistence Changes

None. PR vulnerability JSON is retained for 14 days as diagnostics only. It is
not signed candidate evidence and is never accepted by the environment
admission path.

## 10. Security, Privacy, and Abuse Considerations

- The PR job has no package, OIDC, attestation, AWS, or deployment write
  permission and never logs in to a registry.
- Checkout credentials remain disabled. Third-party actions use full commit
  pins.
- Both scans include unfixed OS and library findings; no CVE is suppressed.
- Report upload uses an exact path rather than a workspace glob and runs after
  policy failure, but not after cancellation.
- The canonical publisher retains exact-digest subject binding and signed
  evidence. A local tag/report cannot cross that boundary.
- Trixie changes the OS package versions and runtime contents, so the actual
  health/MCP runtime must be exercised rather than inferred.

## 11. Performance, Scalability, and Reliability Considerations

The PR gate adds one image build and two bounded five-minute scan passes after
quality/automation checks. Docker layer and Trivy caching on hosted runners may
reduce repeated work, but no latency claim is made before a live PR run. A
scanner/setup/report error fails closed; `if-no-files-found: error` prevents a
green diagnostic upload when the complete report is absent.

## 12. Implementation Steps

1. Minimize and migrate the runtime image.
   - Change: Use Trixie Python 3.12, isolate `uv` to build/development stages,
     remove curl from production, copy only the venv, and use a Python health
     check. Add an explicit development target with `uv`, curl, source, tests,
     automation, and dev dependencies.
   - Files/modules likely affected: `Dockerfile`,
     `automation/tests/test_release_contract.py`.
   - Notes: Preserve UID 10001, port 8092, `tini`, update checks, and runtime
     command.
   - Verification: Build for amd64, inspect architecture/user/files, run the
     full container smoke behavior, and scan with pinned Trivy 0.70.0.

2. Add the non-publishing vulnerability job.
   - Change: Add local amd64 build, complete report scan, CRITICAL policy scan,
     and unconditional-on-failure report upload for non-canonical execution.
   - Files/modules likely affected: `.github/workflows/ci.yml`.
   - Notes: Retain top-level `contents: read`; no write permission or registry
     action. Do not add this diagnostic to publisher evidence.
   - Verification: Workflow contract tests and a live PR check.

3. Add repository automation regressions.
   - Change: Assert PR/non-canonical coverage, needs, read-only permissions,
     all-severity/unfixed report options, CRITICAL nonzero exit behavior,
     post-failure upload condition/retention, and unchanged exact-digest main
     handoff.
   - Files/modules likely affected:
     `automation/tests/test_release_contract.py`.
   - Verification: Focused and full frozen pytest runs.

4. Document operator and shared-action follow-up.
   - Change: Describe the PR check, local evidence boundary, reproduction
     command, runtime minimization, and desired shared local-image composite.
   - Files/modules likely affected: `README.md`, this plan.
   - Verification: Review links/claims against the workflow and local results.

5. Include preserved AI guidance and prepare review artifacts.
   - Change: Retain the existing `AGENTS.md`, `.ai/meta/`, and
     `.ai/skills/hybrid-teaching-mode/` changes in the branch.
   - Files/modules likely affected: existing uncommitted AI guidance files.
   - Verification: Inspect the staged diff for scope/secrets and run sync or
     metadata validation if the repository provides it.

## 13. Testing Strategy

- Focused automation: `uv run --frozen --no-sync pytest automation/tests`.
- Full Python/automation: `uv run --frozen --no-sync pytest tests automation/tests`.
- Tooling: Ruff lint, Ruff format check, compileall, and `git diff --check`.
- Image: `docker build --platform linux/amd64`, pinned Trivy 0.70.0 complete
  and CRITICAL scans with `ignore-unfixed=false`, package/runtime inspection,
  non-root health/MCP/downstream smoke.
- Hosted acceptance: ordinary PR checks only. Do not dispatch or claim the
  canonical main publication acceptance in this PR.

## 14. Rollout / Migration Plan

Merge is outside this task. Review the PR and its `container-security-check`
artifact/status. After an authorized merge, the normal canonical main push is
the only acceptable proof that the newly published exact digest passes signed
evidence generation. Roll back by reverting the Dockerfile/workflow commit;
never bypass the CRITICAL gate. A shared-action enhancement can later replace
the two-pass PR scan in a separately reviewed pin update.

## 15. Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|---|---:|---:|---|
| The Trixie runtime changes dependency behavior | High | Low | Prove build and smoke locally; stop and revise the plan if incompatible. |
| Scanner database changes after local verification | Medium | Medium | Keep policy strict and retain hosted reports; do not claim future main acceptance. |
| PR policy and shared evaluator drift | Medium | Medium | Pin identical Trivy action/version/options and track a shared PR composite enhancement. |
| Upload is skipped after policy failure | High | Low | Use `if: !cancelled()` and protect it with ordering/contract tests. |
| PR diagnostics are mistaken for signed evidence | High | Low | Distinct artifact name and job; main alone invokes exact-digest attestation/evidence. |
| Trixie still reports non-applicable Perl findings | High | High | Do not suppress silently; remove the package safely, use the governed shared VEX mechanism, or test Alpine as a fallback. |

## 16. Done Criteria

- The replacement amd64 image builds and smoke-tests successfully.
- Pinned Trivy reports zero CRITICAL findings without ignores/exceptions.
- The PR check is non-publishing, read-only, fails on CRITICAL, and retains the
  complete report after policy failure.
- Main's exact-digest signed evidence invocation remains intact and protected
  by regression tests.
- All repository checks pass.
- Issue, branch, commits, push, and PR exist with required `[ai]` prefixes;
  no merge/publication dispatch/admission/deployment is performed.

## 17. Review Checklist

- [x] Requirements and non-goals are explicit.
- [x] Existing workflow, image, tests, reference implementation, and shared
  action boundary were inspected.
- [x] Runtime and gate alternatives were compared.
- [x] Security, reliability, test, rollout, and rollback implications are
  explicit.
- [ ] Trixie compatibility is proven by build/scan/smoke evidence.
- [ ] Final implementation and hosted PR results are reviewed.

## 18. Handoff Prompt for Implementation Agent

```text
Implement docs/plans/container-security-pr-gate.md for issue #10.

Constraints:
- Preserve MCP behavior and main exact-digest signed evidence publication.
- Add only a read-only, non-publishing PR/local-image diagnostic gate.
- Do not add vulnerability exceptions or weaken the CRITICAL policy.
- Do not duplicate the shared evaluator; document the shared-action follow-up.
- Include the existing AGENTS.md and hybrid-teaching .ai changes.
- Prefix every commit and the PR title with [ai].
- Do not merge, dispatch publication, admit to ECR, deploy, or mutate AWS.

Relevant files/modules:
- Dockerfile
- .github/workflows/ci.yml
- automation/tests/test_release_contract.py
- README.md
- AGENTS.md and .ai/skills/hybrid-teaching-mode/

Expected verification commands:
- uv sync --frozen
- uv run --frozen --no-sync pytest tests automation/tests
- uv run --frozen --no-sync ruff check .
- uv run --frozen --no-sync ruff format --check .
- uv run --frozen --no-sync python -m compileall src tests automation
- git diff --check
- docker build/scan/smoke commands described in the plan
```
