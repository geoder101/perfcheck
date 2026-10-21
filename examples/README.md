# perfcheck Marimo curriculum

These developer learning materials teach the supported `perfcheck` CLI workflow.
The CLI remains the only supported public surface. Lessons are self-contained and
write any artifacts only to temporary workspaces.

## Setup

From the repository root, install the optional lesson tools once:

```bash
uv sync --group examples
```

## Lessons

Each lesson takes about five minutes. Start at 01, then continue in numeric
order. To author a lesson, open its explicit path with `marimo edit`. To consume
it interactively, use `marimo run`. To run the same lesson noninteractively,
use its explicit Python command from the repository root.

### 01. [01-overview.py](01-overview.py), workflow overview

- **Goal:** learn the collect, summarize, and compare evidence flow.
- **Prerequisite:** setup above.
- **CLI commands exercised:** `perfcheck collect`, `perfcheck summarize`, and
  `perfcheck compare`.
- **Duration:** 5 minutes.
- **Author:** `uv run --group examples marimo edit examples/01-overview.py`
- **Consumer:** `uv run --group examples marimo run examples/01-overview.py`
- **Script:** `uv --directory . run --group examples python examples/01-overview.py`

### 02. [02-collect.py](02-collect.py), collect a raw run

- **Goal:** collect deterministic raw performance evidence.
- **Prerequisite:** complete 01.
- **CLI commands exercised:** `perfcheck collect`.
- **Duration:** 5 minutes.
- **Author:** `uv run --group examples marimo edit examples/02-collect.py`
- **Consumer:** `uv run --group examples marimo run examples/02-collect.py`
- **Script:** `uv --directory . run --group examples python examples/02-collect.py`

### 03. [03-summarize.py](03-summarize.py), verify and summarize evidence

- **Goal:** verify raw evidence and create a canonical summary.
- **Prerequisite:** complete 02.
- **CLI commands exercised:** `perfcheck summarize`.
- **Duration:** 5 minutes.
- **Author:** `uv run --group examples marimo edit examples/03-summarize.py`
- **Consumer:** `uv run --group examples marimo run examples/03-summarize.py`
- **Script:** `uv --directory . run --group examples python examples/03-summarize.py`

### 04. [04-compare.py](04-compare.py), compare cohorts

- **Goal:** compare baseline and current evidence under a policy.
- **Prerequisite:** complete 03.
- **CLI commands exercised:** `perfcheck collect`, `perfcheck summarize`, and
  `perfcheck compare`.
- **Duration:** 5 minutes.
- **Author:** `uv run --group examples marimo edit examples/04-compare.py`
- **Consumer:** `uv run --group examples marimo run examples/04-compare.py`
- **Script:** `uv --directory . run --group examples python examples/04-compare.py`

### 05. [05-failures-and-ci.py](05-failures-and-ci.py), handle failures in CI

- **Goal:** inspect a safe nonzero CLI result and its CI meaning.
- **Prerequisite:** complete 04.
- **CLI commands exercised:** `perfcheck compare`.
- **Duration:** 5 minutes.
- **Author:** `uv run --group examples marimo edit examples/05-failures-and-ci.py`
- **Consumer:** `uv run --group examples marimo run examples/05-failures-and-ci.py`
- **Script:** `uv --directory . run --group examples python examples/05-failures-and-ci.py`

### 06. [06-statistical-foundations.py](06-statistical-foundations.py), statistical foundations

- **Goal:** distinguish populations, samples, realizations, and sampling distributions.
- **Prerequisite:** complete 05.
- **CLI command explained:** the collect-to-compare evidence flow.
- **Duration:** 5 minutes.
- **Author:** `uv run --group examples marimo edit examples/06-statistical-foundations.py`
- **Consumer:** `uv run --group examples marimo run examples/06-statistical-foundations.py`
- **Script:** `uv --directory . run --group examples python examples/06-statistical-foundations.py`

### 07. [07-summary-and-eligibility.py](07-summary-and-eligibility.py), summaries and eligibility

- **Goal:** calculate fixed per-run summaries and inspect eligibility evidence.
- **Prerequisite:** complete 06.
- **CLI command explained:** `perfcheck summarize`.
- **Duration:** 5 minutes.
- **Author:** `uv run --group examples marimo edit examples/07-summary-and-eligibility.py`
- **Consumer:** `uv run --group examples marimo run examples/07-summary-and-eligibility.py`
- **Script:** `uv --directory . run --group examples python examples/07-summary-and-eligibility.py`

### 08. [08-bootstrap-and-decisions.py](08-bootstrap-and-decisions.py), bootstrap decisions

- **Goal:** inspect oriented bootstrap evidence, advisory references, and limits.
- **Prerequisite:** complete 07.
- **CLI command explained:** `perfcheck compare`.
- **Duration:** 5 minutes.
- **Author:** `uv run --group examples marimo edit examples/08-bootstrap-and-decisions.py`
- **Consumer:** `uv run --group examples marimo run examples/08-bootstrap-and-decisions.py`
- **Script:** `uv --directory . run --group examples python examples/08-bootstrap-and-decisions.py`
