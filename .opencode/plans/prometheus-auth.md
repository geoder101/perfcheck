# Extend the Prometheus collector with HTTP Basic + Bearer authentication

## Context

`perfcheck collect` currently reads the Prometheus bearer token directly from the
process environment inside the transport layer (`src/perfcheck/prometheus.py:73`,
`token = getenv("PERFCHECK_PROMETHEUS_BEARER_TOKEN")`) and sends
`Authorization: Bearer <token>`. The token is recursively redacted in
`prometheus_ingress.py` but the transport itself reads global env state, which
makes it hard to unit test and mixes config resolution with transport.

This work makes the collector **pure**: it stops reading env directly and instead
accepts an explicit, resolved `AuthConfig`. A separate resolver (`resolve_auth`)
reads env vars as a *fallback* for backward compatibility, so a plain
`PERFCHECK_PROMETHEUS_BEARER_TOKEN` still works exactly as today through the CLI.

**Auth is a runtime/CLI concern, NOT part of the suite policy.** There is no
`SuitePolicy.auth` field, no `PolicyAuth` model, and no change to policy
serialization, hashing, or stored policy golden files. The resolver resolves auth
from CLI flags + env only (precedence is strictly **CLI flag > env var**, two
tiers). The resolved `AuthConfig` is passed at runtime from `cli.py` through
`collection_service.collect_run` into `PrometheusQueryRangeCollector.collect` and
is never persisted in the policy snapshot, artifact, report, provenance, or logs.

### Locked design decisions (implement within these; do not re-debate)

- **Schemes** (enum, default `none` for byte-identical backward compatibility):
  `none`, `bearer`, `basic`. OAuth2 / API-key are **out of scope**.
- **Auth is runtime-only.** Do NOT add any auth field to `SuitePolicy`, do NOT add
  a `PolicyAuth` model, and do NOT change `policy_content_sha256`, canonical
  serialization, or any stored policy golden file. `policy_models.py` is **out of
  scope**.
- **Surfaces & precedence** (strictly CLI flag > env var — two tiers only):
  - scheme: `--prometheus-auth-scheme` > `PERFCHECK_PROMETHEUS_AUTH_SCHEME` (values none/bearer/basic)
  - bearer token: `--prometheus-bearer-token` > `PERFCHECK_PROMETHEUS_BEARER_TOKEN`
  - basic username: `--prometheus-auth-basic-user` > `PERFCHECK_PROMETHEUS_BASIC_USERNAME`
  - basic password: `--prometheus-auth-basic-password` > `PERFCHECK_PROMETHEUS_BASIC_PASSWORD`
- **Backward-compat inference** (only when no explicit scheme is chosen via flag or env):
  `PERFCHECK_PROMETHEUS_BEARER_TOKEN` alone → infer `bearer`; both basic env vars → infer `basic`; else `none`.
- The resolver reads env in exactly one place (backward-compat bridge). The
  transport (`prometheus.py`) no longer calls `getenv` and takes an explicit
  resolved `AuthConfig` (**keyword-only, default `AuthConfig.NONE`**) so all
  existing direct-transport test callers keep compiling.
- **Never persist secrets.** `bearer_token` and `basic_password` must never reach
  any persisted artifact, report, provenance, or log. `AuthConfig` is a runtime
  dataclass, never a policy/artifact field.
- **Endpoint safety (unchanged):** `resolve_endpoint` still rejects userinfo/
  query/fragment. Response classification/validation logic is unchanged.
- **Redaction (extend, do not break):** `artifact_validation.contains_secret`
  currently blocks `authorization:` and `bearer ` substrings. Keep that list
  intact and verify no secret-bearing value reaches persisted evidence. Extend
  ingress redaction to scrub basic-auth credentials from responses when
  `scheme=basic` (bearer scrubbing already exists).
- **Scope gate:** keep the public surface CLI-only. Don't change artifact schemas
  or content-hash verification. Don't add OAuth2/api-key.

### Existing callers that must keep passing (verify against this list)

Direct transport `collect(...)` calls — all are currently **no-auth** except three:
- `tests/test_prometheus_query_range.py` — `test_collect_uses_override_url_and_bearer_token_without_retaining_it` (env Bearer) → **update to pass explicit `auth_config`**.
- `tests/test_prometheus_query_range.py` — `test_collect_redacts_nested_credential_aliases_from_all_response_evidence` → **update to pass explicit `auth_config=bearer`**.
- `tests/test_prometheus_query_range.py` — `test_collect_redacts_bearer_value_from_query_provenance_and_hostile_json_key` → **update to pass explicit `auth_config=bearer`**.
- All other `collect(...)` calls (`test_prometheus_sample_validation.py`,
  `test_cleanup_boundaries.py`, `test_numerical_ingress.py`, `test_collection_client.py`,
  and the no-auth branches of `test_prometheus_query_range.py`) stay as-is (default `none`).
- `tests/test_collection_orchestration.py` — `collect_run(...)` calls (4 positional args) keep working because `auth_config` is keyword-only default `none`.
- CLI-path tests that set `PERFCHECK_PROMETHEUS_BEARER_TOKEN` and invoke `collect` **through the CLI** keep working because `resolve_auth` reads env: `test_cli_collect.py::test_collect_writes_redacted_unavailable_record_and_exits_four`, `tests/collection_failure_support.py::install_transport`, `tests/test_secret_redaction.py::test_token_echo_fixture_keeps_collected_artifacts_secret_free`.
- Examples (`examples/_support.py::collect_arguments`, `tests/test_examples*.py`) invoke `collect` via the CLI with env token; unaffected. Docs inputs hash (`src/**/*.py`, `docs/**/*.rst`, `docs/conf.py`, `docs/_templates/**`) — adding `.rst` triggers a fresh `just docs-check`; keep README edits minimal (README is not a docs input).

## Task Dependency Graph

| Task | Depends On | Reason |
|------|------------|-------- |
| 1. Transport accepts `AuthConfig` (no-auth byte-identical) | None | Foundation: makes `PrometheusQueryRangeCollector.collect` pure. New param keyword-only default `none`. |
| 2. `AuthConfig`/`AuthScheme`/resolver (`collection_auth.py`) | None | New module; pure, env-backed, testable. Independent of transport wiring. |
| 3. `collect_run` threads `auth_config` | 1, 2 | Wires resolved `AuthConfig` from CLI into the collector. |
| 4. CLI flags + auth resolution wiring | 2, 3 | Typer options + `resolve_auth` + pass `auth_config` to `collect_run`. |
| 5. Ingress redaction extends for `basic` | 1 | Reuses redaction primitives; only exercised when `scheme=basic`. |
| 6. Tests: transport per-scheme (`test_prometheus_query_range.py`) | 1, 2 | TDD transport headers + no-secret. |
| 7. Tests: resolver unit tests (new `test_collection_auth.py`) | 2 | Precedence + backward-compat env + validation errors. |
| 8. Tests: CLI collect flags + precedence (`test_cli_collect.py`) | 3, 4 | Flags, precedence, env fallback, redaction, exit codes. |
| 9. Tests: secret redaction (`test_secret_redaction.py`) | 1, 5 | Artifact/stdout/stderr secret-free for both schemes; e2e echo server. |
| 10. Tests: collection-service (`test_collection_orchestration.py`) | 3 | `auth_config` threaded; per-scheme transport; policy identity unchanged. |
| 11. Docs (README usage, CLI `--help`, docs page) | 4 | Usage, precedence, examples. |
| 12. `just check` verification gate | 1–11 | Lock verify, format-check, lint, typecheck, tests, examples-check, docs-check, build. |

## Parallel Execution Graph

- **Wave 1 (start immediately, no dependencies — pure units):**
  - Task 1 (transport `AuthConfig`), Task 2 (resolver module).
  - These two touch independent layers and can be developed/verified in parallel.
- **Wave 2 (after Wave 1):**
  - Task 5 (ingress redaction) ← Task 1
  - Task 3 (`collect_run` wiring) ← Task 1, 2
- **Wave 3 (after Wave 2):**
  - Task 4 (CLI flags + resolution) ← Task 2, 3
- **Tests (drive implementation — TDD):**
  - Task 6 (transport) ← Wave 1
  - Task 7 (resolver) ← Wave 1
  - Task 8 (CLI) ← Wave 3
  - Task 9 (redaction) ← Wave 1, 5
  - Task 10 (collection-service) ← Wave 2
  - Test tasks can parallelize among themselves once their source units exist.
- **Wave 4 (final):** Task 11 (docs) + Task 12 (`just check`).
- **Critical path:** Task 1 → Task 3 → Task 4 → Task 12.

## Tasks

### Task 1: Transport accepts explicit `AuthConfig` (no-auth byte-identical)

**Description**: Remove the `getenv` call from `PrometheusQueryRangeCollector.collect`
and build request headers from an explicit `AuthConfig`. `none` → `{}` (byte-identical
to today). `bearer` → `Authorization: Bearer <token>`. `basic` →
`Authorization: Basic <base64(user:pass)>`. Thread the secret value(s) into redaction
helpers for errors and response provenance. Keep `resolve_endpoint` unchanged.

**Delegation Recommendation**:
- Category: `deep-low` - transport/config pure-function refactor with strict redaction invariants.
- Skills: [`programming`] - enforces typed errors / exhaustive match per repo conventions.

**Skills Evaluation**:
- INCLUDED `programming`: typed errors, exhaustive `match` on scheme/`FailureKind`, strict typing under BasePyright `typeCheckingMode="all"`.
- OMITTED `refactor`: the change is a small, bounded signature change, not a structural refactor.
- OMITTED `security-research`: not a vulnerability audit; the secret-invariants are covered by dedicated tests.

**Depends On**: None
**Acceptance Criteria**:
- `collect(range_query, *, prometheus_url_override=None, auth_config: AuthConfig = AuthConfig.NONE)` is keyword-only.
- With `auth_config=AuthConfig.NONE`, the outgoing request headers are exactly `{}` and all existing transport tests pass unchanged (no `authorization` header).
- With `scheme=bearer`, `Authorization: Bearer <token>` is sent; with `scheme=basic`, `Authorization: Basic <b64>` is sent.
- `resolve_endpoint` still rejects userinfo/query/fragment; no new imports of `os`/`getenv` in `prometheus.py`.
- `just check` green (this task alone is insufficient; see Task 12 for the gate).

### Task 2: `AuthConfig`, `AuthScheme`, and `resolve_auth` (new `src/perfcheck/collection_auth.py`)

**Description**: Add a new pure module with `AuthScheme(StrEnum)` (`none`/`bearer`/`basic`,
`none` default), `AuthConfig(frozen dataclass)` (`scheme`, `bearer_token|None`,
`basic_username|None`, `basic_password|None`), `AuthConfig.NONE` constant, and
`AuthResolutionError(PerfcheckError)` for invalid resolution (scheme chosen but
missing required secret). Implement `resolve_auth(scheme, bearer_token, basic_username,
basic_password)` where the four positional args are the **CLI-flag** values (or `None`);
the function then applies env-var fallback and two-tier (CLI > env) precedence, then
backward-compat inference:

- Precedence per surface (CLI flag > env var):
  - scheme `=` CLI `--prometheus-auth-scheme` `> PERFCHECK_PROMETHEUS_AUTH_SCHEME`
  - bearer token `=` CLI `--prometheus-bearer-token` `> PERFCHECK_PROMETHEUS_BEARER_TOKEN`
  - basic user `=` CLI `--prometheus-auth-basic-user` `> PERFCHECK_PROMETHEUS_BASIC_USERNAME`
  - basic password `=` CLI `--prometheus-auth-basic-password` `> PERFCHECK_PROMETHEUS_BASIC_PASSWORD`
- If no explicit scheme was chosen (no flag and no `PERFCHECK_PROMETHEUS_AUTH_SCHEME`): infer `bearer` from a present token, else `basic` from present user+password, else `none`.
- Validate: `bearer` requires a token, `basic` requires user + password, else raise `AuthResolutionError`.

Single `os.getenv`-based site for auth env vars. No policy dependency.

**Delegation Recommendation**:
- Category: `deep-low` - pure resolver with precedence and typed validation.
- Skills: [`programming`] - exhaustive validation, typed errors.

**Skills Evaluation**:
- INCLUDED `programming`: strict modern typing, typed errors, exhaustive validation.
- OMITTED `ast-grep`: no AST-redesign needed; targeted string additions.
- OMITTED `refactor`: additive module, not a restructure.

**Depends On**: None
**Acceptance Criteria**:
- `resolve_auth` is pure given env, returns exactly one `AuthConfig` per precedence matrix (CLI > env) for all four surfaces.
- Backward compatibility: with only `PERFCHECK_PROMETHEUS_BEARER_TOKEN` set, `resolve_auth` returns `scheme=bearer` + that token.
- `AuthResolutionError` is raised when `bearer` has no token or `basic` is missing user or password; message is secret-free.
- `AuthConfig.NONE` is the default and carries no secrets.
- No policy dependency; no env var is parsed from a policy.

### Task 3: `collect_run` threads `auth_config` (`src/perfcheck/collection_service.py`)

**Description**: Add keyword-only `auth_config: AuthConfig = AuthConfig.NONE` to
`collect_run`. Pass `auth_config` into `PrometheusQueryRangeCollector.collect` for
every metric. The transport redacts any secrets; `collect_run` never serializes
`AuthConfig`. The in-repo signature usage (`test_collection_orchestration.py`, 4
positional args) is unaffected by the new keyword-only param.

**Delegation Recommendation**:
- Category: `deep-low` - thin wiring across the collection boundary.
- Skills: [`programming`] - type-only change.

**Skills Evaluation**:
- INCLUDED `programming`: typed parameter, matches existing `collect_run` signature style.
- OMITTED `refactor`: additive parameter, no restructuring.
- OMITTED `security-research`: secrets stay in the transport layer; covered by redaction tests.

**Depends On**: Task 1, Task 2
**Acceptance Criteria**:
- `collect_run(policy, run_id, interval, prometheus_url_override, *, auth_config=AuthConfig.NONE)` signature.
- No `AuthConfig` value appears in the persisted run artifact, provenance, or logs.
- Existing `test_collection_orchestration.py` still passes with the new keyword-only param defaulting to `none`.

### Task 4: CLI flags + auth resolution (`src/perfcheck/cli.py`)

**Description**: Add four typer options to `collect_command` (all `str | None`,
grouped under a `prometheus-*` namespace in `--help`): `--prometheus-auth-scheme`,
`--prometheus-bearer-token`, `--prometheus-auth-basic-user`,
`--prometheus-auth-basic-password`. Parse `--prometheus-auth-scheme` into `AuthScheme`.
Build a `collection_auth.resolve_auth(...)` call from the non-`None` flag values;
pass the resulting `AuthConfig` keyword-only to `collect_run` inside the existing
`runnify(collect_run)(...)` call. Add concise help text explaining scheme values and
the CLI > env precedence. Keep the `noqa: PLR0913` convention on `collect_command`.
Map `AuthResolutionError` (a `PerfcheckError`) to a stable CLI diagnostic (exit `3`)
without leaking the secret.

**Delegation Recommendation**:
- Category: `deep-low` - typer option wiring with existing error/exit conventions.
- Skills: [`programming`] - typer patterns, existing `_exit_input_error` handling.

**Skills Evaluation**:
- INCLUDED `programming`: matches existing typer option + `_run_command` error-handling conventions.
- OMITTED `frontend`: this is CLI flags, not UI.
- OMITTED `ast-grep`: no AST-redesign; standard option additions.

**Depends On**: Task 2, Task 3
**Acceptance Criteria**:
- `just cli collect --help` shows all four options under a `prometheus-*` group with help text.
- Flags win over env (no policy tier); precedence verified by Task 8.
- Passing `--prometheus-auth-scheme=basic` without password yields exit `3` (input error), no secret in output.
- Existing `--prometheus-url` behavior and all CLI collect tests unchanged except the added auth flows.

### Task 5: Ingress redaction extends for `basic` (`src/perfcheck/prometheus_ingress.py`)

**Description**: Extend redaction so that, when `scheme=basic`, basic-auth credentials
are scrubbed from responses and error text, while leaving the existing bearer/assignment
redaction byte-identical for `none`/`bearer`. Add a helper to also strip a
`user:pass`-style credential pair and any `Authorization: Basic <...>` occurrence from
response strings when provided. Keep `_SENSITIVE_KEY_NAMES` unchanged (it already
blocks the bearer/assignment patterns) and rely on `contains_secret` to verify no
secret reaches persisted evidence.

**Delegation Recommendation**:
- Category: `deep-low` - redaction regex extension with strict backward compat.
- Skills: [`programming`] - typed regex helpers, exhaustive behavior.

**Skills Evaluation**:
- INCLUDED `programming`: strict regex/typed helpers consistent with `redact_text`/`redact_json`.
- OMITTED `security-research`: not an audit; this is a redaction extension covered by tests.
- OMITTED `refactor`: additive redaction, not a restructure.

**Depends On**: Task 1
**Acceptance Criteria**:
- `none`/`bearer` redaction output is byte-identical to today (existing ingress tests pass unchanged).
- With `basic`, a response echoing the basic credential is fully redacted (secret absent from provenance/repr/serialization).
- `contains_secret` blocklist still rejects `authorization:` and `bearer `; no secret reaches persisted evidence.

### Task 6: Transport per-scheme headers + no-secret (`tests/test_prometheus_query_range.py`)

**Description**: Extend `test_prometheus_query_range.py`. Update the three
env-based bearer tests to pass an explicit `auth_config` (so they exercise the pure
transport). Add: (a) per-scheme header assertions (`none`→`{}`, `bearer`→
`Authorization: Bearer <t>`, `basic`→`Authorization: Basic <b64>`); (b) `none` is
byte-identical (no auth header); (c) no secret retained in `repr(result)`,
`json.dumps(result.response.body)`, or `result.request` for both `bearer` and `basic`;
(d) basic auth echoes from a hostile response are redacted. Keep existing transport
tests that use default `none`.

**Delegation Recommendation**:
- Category: `deep-low` - deterministic transport behavior via MockTransport.
- Skills: [`programming`] - Given/When/Then structure, typed assertions.

**Skills Evaluation**:
- INCLUDED `programming`: matches the repo's Given/When/Then transport-test style.
- OMITTED `playwright`/`browser`: no interactive browser; `httpx2.MockTransport` is the seam.
- OMITTED `visual-qa`: not UI.

**Depends On**: Task 1, Task 2
**Acceptance Criteria**:
- All `test_prometheus_query_range.py` tests pass; new per-scheme and redaction tests pass.
- `just test tests/test_prometheus_query_range.py` green.

### Task 7: Resolver unit tests (new `tests/test_collection_auth.py`)

**Description**: New module testing `resolve_auth`. Parametrized precedence matrix for
all four surfaces (CLI > env); backward-compat env-only bearer; inference when no
scheme chosen; `AuthResolutionError` for `bearer`-without-token and `basic`-without
user/password; `AuthConfig.NONE` default; secrets never equal in the returned config's
non-applicable fields. Use `monkeypatch` for env and direct kwargs for CLI-flag values.
No policy inputs.

**Delegation Recommendation**:
- Category: `deep-low` - pure-function precedence tests.
- Skills: [`programming`] - parametrized precedence matrices.

**Skills Evaluation**:
- INCLUDED `programming`: parametrized matrices match repo conventions.
- OMITTED `data-scientist`: no dataset analysis.
- OMITTED `security-research`: secret-absence is asserted via plain equality, not an audit.

**Depends On**: Task 2
**Acceptance Criteria**:
- Full precedence matrix + backward-compat + error cases covered.
- `just test tests/test_collection_auth.py` green.

### Task 8: CLI collect flags + precedence (`tests/test_cli_collect.py`)

**Description**: Extend `test_cli_collect.py`. Add: (a) `--help` lists the four options;
(b) flag wins over env (set both, assert the flag header); (c) env fallback still works
(no flag, set env → Bearer header); (d) basic env vars + flags resolve to `Basic` header;
(e) `--prometheus-auth-scheme=basic` with missing password exits `3`; (f) collected
artifact/stdout/stderr are secret-free for both schemes; (g) `none` (default, no auth
inputs) keeps working. Reuse the `create_collection_client` transport injection pattern.
No policy fixtures for auth.

**Delegation Recommendation**:
- Category: `deep-low` - CLI boundary + precedence via CliRunner.
- Skills: [`programming`] - CliRunner assertions, exit-code contracts.

**Skills Evaluation**:
- INCLUDED `programming`: matches existing `test_cli_collect.py` CliRunner patterns.
- OMITTED `playwright`/`browser`: CLI via `CliRunner`, not a browser.
- OMITTED `frontend`: CLI flags, not UI.

**Depends On**: Task 3, Task 4
**Acceptance Criteria**:
- All flag/env precedence cases pass; exit-code and redaction contracts hold.
- `just test tests/test_cli_collect.py` green.

### Task 9: Secret redaction (`tests/test_secret_redaction.py`)

**Description**: Extend `test_secret_redaction.py`. Keep the existing bearer echo-server
tests. Add: (a) basic-auth round trip through `collect` → `summarize` → `compare` via the
local fixture server (add a basic-echo capability to `tests/fixtures/mock_prometheus_server.py`
if needed, mirroring `echo_token_body`); (b) no secret (token or password) in the persisted
run/summary, reports, provenance, stdout, or stderr for both `bearer` and `basic`;
(c) verify against `artifact_validation.contains_secret` blocklist. Use
`mock_prometheus_endpoint` and the generated console script. No policy auth.

**Delegation Recommendation**:
- Category: `deep-low` - end-to-end redaction through the CLI.
- Skills: [`programming`] - subprocess CLI + artifact assertions.

**Skills Evaluation**:
- INCLUDED `programming`: matches the existing e2e redaction test structure.
- OMITTED `playwright`/`browser`: uses the local HTTP fixture server, not a browser.
- OMITTED `security-research`: redaction verified by artifact/stdout assertions.

**Depends On**: Task 1, Task 5
**Acceptance Criteria**:
- Both schemes produce secret-free artifacts, reports, provenance, and streams.
- `just test tests/test_secret_redaction.py` green.

### Task 10: Collection-service tests (`tests/test_collection_orchestration.py`)

**Description**: Extend `test_collection_orchestration.py`: (a) verify `collect_run`
threads `auth_config` so each metric's transport sends the correct per-scheme header;
(b) default `auth_config` is `none` (no auth header); (c) no `AuthConfig`/secret appears
in the persisted run; (d) policy identity (`policy_sha256`) is unchanged (policy is not
touched by this feature). Reuse the `factory_clients` + `MockTransport` harness.

**Delegation Recommendation**:
- Category: `deep-low` - collection wiring tests.
- Skills: [`programming`] - async harness, policy-hash assertions.

**Skills Evaluation**:
- INCLUDED `programming`: matches the existing async `collect_run` harness.
- OMITTED `data-scientist`: no analysis.
- OMITTED `security-research`: secret-absence asserted via artifact content checks.

**Depends On**: Task 3
**Acceptance Criteria**:
- `auth_config` threading verified per metric; policy identity unchanged; secrets absent.
- `just test tests/test_collection_orchestration.py` green.

### Task 11: Documentation (README usage, CLI `--help`, docs page)

**Description**: Add a concise "Prometheus authentication" subsection to the root
`README.md` (usage + precedence table + flag list). Extend `docs/how-to/collect-a-run.rst`
with the auth options and a short "Authenticate the collection" step, and add a new
how-to page `docs/how-to/prometheus-authentication.rst` (following the existing
Goal/Prerequisite/Steps/Expected observable/Related material structure) with a full
precedence table and examples. Register the new page in `docs/how-to/index.rst`. Update
`docs/reference/cli.rst` `collect` section with the new flags. Keep RST valid (no
dangling `:doc:` targets) since `docs-check` builds with warnings-as-errors. Document
auth as a runtime/CLI concern only (no policy).

**Delegation Recommendation**:
- Category: `writing` - user-facing CLI/policy documentation.
- Skills: [] - prose/documentation writing; no code skills needed.

**Skills Evaluation**:
- INCLUDED `writing`: this is authored user documentation following repo conventions.
- OMITTED `programming`: docs are RST prose, not executable code.
- OMITTED `frontend`: RST documentation, not HTML/CSS UI.

**Depends On**: Task 4
**Acceptance Criteria**:
- README documents the four flags, precedence, and scheme values.
- New how-to page exists, is registered in `docs/how-to/index.rst`, and builds cleanly.
- `docs/reference/cli.rst` documents the new `collect` flags.
- `just docs-check` builds with no warnings/errors.

### Task 12: `just check` verification gate

**Description**: Run the full standard gate and confirm every phase is green before
declaring done: `just check` (`lock-check`, `format-check`, `lint`, `typecheck`,
`test`, `examples-check`, `docs-check`, `build`). Standard gate is coverage-free. Fix
any failures (format via `just format`, etc.) and re-run until clean. Do not enable
coverage/mutation. Never commit secrets, tokens, or passwords.

**Delegation Recommendation**:
- Category: `deep-low` - full-suite verification and failure triage.
- Skills: [`programming`] - interpreting lint/type/test results and fixing.

**Skills Evaluation**:
- INCLUDED `programming`: triage across format/lint/type/test/docs/build.
- OMITTED `review-work`: run only if the user asks for a post-implementation gate review.
- OMITTED `security-research`: already covered by Task 5/9 redaction work.

**Depends On**: Tasks 1–11
**Acceptance Criteria**:
- `just check` exits 0 across all phases.
- No regressions in existing tests; new tests pass; no secrets anywhere.

## Commit Strategy

Commit atomically by layer, TDD-first (tests and their source in the same commit or
tests-first per task). Each commit is a self-contained, reviewable unit. Use the
`git-master` skill if committing. **Do not add `Co-authored-by` or any AI attribution
to commit messages.** Suggested sequence:

1. `feat(auth): add AuthConfig/AuthScheme and resolve_auth` — Task 2 + Task 7 (module + resolver tests). Commit tests + source together.
2. `feat(auth): collector accepts explicit AuthConfig` — Task 1 + Task 6. Transport pure + per-scheme transport tests.
3. `feat(auth): thread auth_config through collect_run` — Task 3 + Task 10.
4. `feat(auth): CLI auth flags and resolution wiring` — Task 4 + Task 8.
5. `feat(auth): extend ingress redaction for basic auth` — Task 5 + Task 9.
6. `docs(auth): Prometheus authentication guide, README, and CLI reference` — Task 11.
7. (Optional) final verify step only if requested.

Keep the plan at `.omo/plans/prometheus-auth.md` as a non-committed artifact unless the
user asks to commit it. Never commit secrets, tokens, or passwords; verify with
`git diff --cached` and a grep for `secret`/`token`/`password` in staged content before
any commit.

## Success Criteria

- `just check` passes all phases (lock verify, format-check, lint, typecheck, tests,
  examples-check, docs-check, build), coverage-free.
- The no-auth (`none`) path is byte-identical: all pre-existing tests pass unchanged,
  and no-auth requests carry no `Authorization` header.
- Basic + Bearer are configurable via `--prometheus-auth-scheme`,
  `--prometheus-bearer-token`, `--prometheus-auth-basic-user`,
  `--prometheus-auth-basic-password`, and env vars; precedence is strictly
  CLI flag > env var and is covered by tests.
- The plain `PERFCHECK_PROMETHEUS_BEARER_TOKEN` env path still works via the resolver.
- **Zero secrets** reach any persisted artifact, report, provenance, stdout/stderr, or
  log for either scheme — verified by `test_secret_redaction.py` and the
  `contains_secret` blocklist.
- Policy is untouched: `policy_content_sha256`, canonical serialization, and stored
  policy golden files are unchanged (no `SuitePolicy.auth`, no `PolicyAuth`).
- Endpoint-safety and response classification/validation logic are unchanged.
- Public surface remains CLI-only; no OAuth2/api-key schemes added; no artifact-schema
  or content-hash changes.

## TODO List (ADD THESE)

> CALLER: Add these TODOs using TodoWrite/TaskCreate and execute by wave.

### Wave 1 (Start Immediately - No Dependencies)

- [ ] **2. `collection_auth.py`: `AuthScheme`/`AuthConfig`/`resolve_auth`**
  - What: New module — `AuthScheme(StrEnum none/bearer/basic)`, `AuthConfig(frozen dataclass)` + `AuthConfig.NONE`, `AuthResolutionError(PerfcheckError)`, `resolve_auth(scheme/bearer_token/basic_username/basic_password)` reading env with two-tier (CLI > env) precedence and backward-compat inference. No policy dependency.
  - Depends: None
  - Blocks: 3, 4, 6, 7
  - Category: `deep-low`
  - Skills: [`programming`]
  - QA: `just test tests/test_collection_auth.py` green (after Task 7); module imports cleanly; no `os`/getenv outside resolver.
- [ ] **1. Transport accepts `AuthConfig` (byte-identical none)**
  - What: `collect(range_query, *, prometheus_url_override=None, auth_config=AuthConfig.NONE)` keyword-only; remove `getenv`; build headers per scheme; thread secret(s) to redaction; leave `resolve_endpoint` untouched.
  - Depends: None
  - Blocks: 3, 5, 6, 10
  - Category: `deep-low`
  - Skills: [`programming`]
  - QA: `just test tests/test_prometheus_query_range.py` (default-none tests pass with no auth header).

### Wave 2 (After Wave 1 Completes)

- [ ] **3. `collect_run` threads `auth_config`**
  - What: Add keyword-only `auth_config=AuthConfig.NONE` to `collect_run`; pass to `collector.collect`; never serialize `AuthConfig`.
  - Depends: 1, 2
  - Blocks: 4, 10
  - Category: `deep-low`
  - Skills: [`programming`]
  - QA: `just test tests/test_collection_orchestration.py` (existing 4-arg calls still pass).
- [ ] **5. Ingress redaction extends for `basic`**
  - What: Scrub basic-auth credentials from responses/errors when `scheme=basic`; keep `none`/`bearer` byte-identical; rely on `contains_secret` to confirm no secret reaches persisted evidence.
  - Depends: 1
  - Blocks: 9
  - Category: `deep-low`
  - Skills: [`programming`]
  - QA: existing ingress/transport tests unchanged; `just test tests/test_prometheus_query_range.py` + `tests/test_secret_redaction.py` green.

### Wave 3 (After Wave 2 Completes)

- [ ] **4. CLI auth flags + resolution wiring**
  - What: Four typer options on `collect_command` (`--prometheus-auth-scheme/--prometheus-bearer-token/--prometheus-auth-basic-user/--prometheus-auth-basic-password`); parse scheme into `AuthScheme`; `resolve_auth` call; pass `auth_config` to `collect_run`; map `AuthResolutionError`→exit 3.
  - Depends: 2, 3
  - Blocks: 8, 11
  - Category: `deep-low`
  - Skills: [`programming`]
  - QA: `just cli collect --help` shows the four options; `just test tests/test_cli_collect.py` green (after Task 8).

### Wave 4 (Final - Docs + Gate)

- [ ] **11. Documentation (README + how-to page + CLI reference)**
  - What: README auth subsection; new `docs/how-to/prometheus-authentication.rst` registered in `docs/how-to/index.rst`; update `docs/reference/cli.rst`; keep RST warning-clean; document auth as runtime/CLI-only.
  - Depends: 4
  - Blocks: 12
  - Category: `writing`
  - Skills: []
  - QA: `just docs-check` clean.
- [ ] **12. `just check` verification gate**
  - What: Run `just check` (lock-check, format-check, lint, typecheck, test, examples-check, docs-check, build); fix and re-run until all green; coverage-free.
  - Depends: 1–11
  - Blocks: none (final)
  - Category: `deep-low`
  - Skills: [`programming`]
  - QA: `just check` exits 0; confirm no secrets and no plan file staged unless explicitly asked.

## Execution Instructions

1. **Wave 1** — fire Tasks 2 and 1 in parallel (pure, independent layers):
   ```
   task(category="deep-low", load_skills=["programming"], run_in_background=true, prompt="Task 2: ...")
   task(category="deep-low", load_skills=["programming"], run_in_background=true, prompt="Task 1: ...")
   ```
   Drive each with its TDD test (Tasks 7, 6).
2. **Wave 2** — after Wave 1, fire Tasks 3 and 5 in parallel:
   ```
   task(category="deep-low", load_skills=["programming"], run_in_background=true, prompt="Task 3: ...")
   task(category="deep-low", load_skills=["programming"], run_in_background=true, prompt="Task 5: ...")
   ```
3. **Wave 3** — after Wave 2, fire Task 4:
   ```
   task(category="deep-low", load_skills=["programming"], run_in_background=true, prompt="Task 4: ...")
   ```
4. **Wave 4** — Task 11 (docs) then Task 12 (`just check`); run `just check` last to confirm the whole gate.
5. Final QA: re-run `just check`; verify no secret bytes in `git diff`/artifacts; confirm the no-auth path is byte-identical and `policy_models.py`/stored policy fixtures are untouched.
