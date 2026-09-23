#!/usr/bin/env bash
# Runs every local automated check (PLAN.md V1) and prints one PASS/FAIL line per check.
set -u
cd "$(dirname "$0")/.."
bin=.venv/bin
[ -x "$bin/python" ] || bin=.venv/Scripts  # a Windows venv

failed=0
results=()
check() {
  local name=$1; shift
  if "$@"; then results+=("PASS  $name"); else results+=("FAIL  $name"); failed=1; fi
}

check "ruff check"          "$bin/ruff" check .
check "ruff format --check" "$bin/ruff" format --check .
check "mypy --strict src"   "$bin/mypy" --strict src
check "pytest --cov"        "$bin/pytest" --cov
check "pytest, C locale"    env PYTHONUTF8=0 LC_ALL=C "$bin/pytest" -q

printf '\n'
printf '%s\n' "${results[@]}"
exit $failed
