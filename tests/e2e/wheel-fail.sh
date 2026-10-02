#!/usr/bin/env sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
bin=${PERFCHECK_BIN:?PERFCHECK_BIN is required}
work=${PERFCHECK_SMOKE_DIR:?PERFCHECK_SMOKE_DIR is required}
endpoint=${PERFCHECK_PROMETHEUS_URL:-http://127.0.0.1:18090}
policy="$root/tests/fixtures/policy-fail.json"
for pair in baseline-1:01 baseline-2:02 current-1:03 current-2:04; do
  run=${pair%:*}
  day=${pair#*:}
  "$bin" collect --suite "$policy" --prometheus-url "$endpoint" --run-id "$run" --start "2026-07-${day}T10:00:00Z" --end "2026-07-${day}T10:10:00Z" --out "$work/$run.json"
  "$bin" summarize --policy "$policy" --run "$work/$run.json" --out "$work/$run.summary.json"
done
"$bin" compare --policy "$policy" --current "$work/current-1.summary.json" --current "$work/current-2.summary.json" --baseline "$work/baseline-1.summary.json" --baseline "$work/baseline-2.summary.json" --report-json "$work/fail.json" --report-md "$work/fail.md"
