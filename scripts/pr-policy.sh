#!/usr/bin/env bash
set -euo pipefail

file="${1:?Pass the GitHub event JSON path}"
base="$(jq -r '.pull_request.base.ref' "$file")"
head="$(jq -r '.pull_request.head.ref' "$file")"
title="$(jq -r '.pull_request.title' "$file")"

case "$head" in
  feature/*) category=feature; prefix=feat ;;
  fix/*) category=fix; prefix=fix ;;
  hotfix/*) category=hotfix; prefix=hotfix ;;
  refactor/*) category=refactor; prefix=refactor ;;
  docs/*) category=docs; prefix=docs ;;
  chore/*) category=chore; prefix=chore ;;
  test/*) category=test; prefix=test ;;
  ci/*) category=ci; prefix=ci ;;
  perf/*) category=perf; prefix=perf ;;
  release/*) category=release; prefix=release ;;
  sync/*) category=sync; prefix=sync ;;
  develop) category=release; prefix=release ;;
  main) category=sync; prefix=sync ;;
  *) echo "Invalid branch name: $head" >&2; exit 1 ;;
esac

if [[ "$base" == develop ]]; then
  [[ "$head" != develop ]] || { echo 'develop cannot target itself' >&2; exit 1; }
  [[ "$head" != main || "$category" == sync ]] || exit 1
  [[ "$category" != hotfix ]] || { echo 'Hotfixes should target main first' >&2; exit 1; }
elif [[ "$base" == main ]]; then
  [[ "$head" == develop || "$category" == hotfix ]] || { echo 'Only develop releases or urgent hotfixes may target main' >&2; exit 1; }
else
  echo "Unexpected target: $base" >&2; exit 1
fi

if [[ "$prefix" == release ]]; then
  [[ "$title" =~ ^release:\ v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]] || { echo 'Expected title: release: vX.Y.Z' >&2; exit 1; }
else
  [[ "$title" =~ ^${prefix}(\([a-zA-Z0-9._/-]+\))?(!)?:\ .+ ]] || { echo "Expected Conventional Commit-style PR title starting with $prefix:" >&2; exit 1; }
fi

if ! jq -e --arg label "type:$category"   '([.pull_request.labels[].name | select(startswith("type:"))] == [$label])' "$file" >/dev/null; then
  echo "PR needs label type:$category. Auto-label workflow should add it shortly." >&2
  exit 1
fi

echo "PR policy passed: $head → $base ($category)"
