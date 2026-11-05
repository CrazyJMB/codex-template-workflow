#!/usr/bin/env bash
# Adapt runtime installation in ci.yml to each repository.
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
if command -v python >/dev/null; then
  python_runner=python
else
  python_runner=python3
fi
"$python_runner" scripts/check-template.py

project_checks=0
project_stacks=0
run_setup() {
  echo "::group::$*"
  "$@"
  echo '::endgroup::'
}

run_check() {
  run_setup "$@"
  project_checks=$((project_checks + 1))
}

require_checks() {
  if [[ "$project_checks" -eq "$stack_checks_before" ]]; then
    echo "$1 project has no configured lint, type, test, or build checks. Configure scripts/ci.sh before enabling CI." >&2
    exit 1
  fi
}

if [[ -f package.json ]]; then
  project_stacks=$((project_stacks + 1))
  stack_checks_before=$project_checks
  command -v node >/dev/null || { echo 'Node.js is required' >&2; exit 1; }
  if [[ -f pnpm-lock.yaml ]]; then
    corepack enable
    run_setup pnpm install --frozen-lockfile
    package_runner=(pnpm run)
  elif [[ -f yarn.lock ]]; then
    corepack enable
    if grep -q 'yarnPath:' .yarnrc.yml 2>/dev/null || [[ -f .yarnrc.yml ]]; then
      run_setup yarn install --immutable
    else
      run_setup yarn install --frozen-lockfile
    fi
    package_runner=(yarn run)
  elif [[ -f package-lock.json ]]; then
    run_setup npm ci
    package_runner=(npm run)
  else
    echo 'Commit a Node lockfile before enabling CI' >&2
    exit 1
  fi

  for script in lint typecheck test build; do
    if node -e 'let p=require("./package.json");let s=p.scripts?.[process.argv[1]];process.exit(typeof s==="string"&&s.trim()?0:1)' "$script"; then
      CI=true run_check "${package_runner[@]}" "$script"
    fi
  done
  require_checks Node.js
fi

if [[ -f composer.json ]]; then
  project_stacks=$((project_stacks + 1))
  stack_checks_before=$project_checks
  command -v composer >/dev/null || { echo 'Composer must be installed on the CI runner' >&2; exit 1; }
  [[ -f composer.lock ]] || { echo 'Commit composer.lock before enabling CI' >&2; exit 1; }
  run_setup composer install --no-interaction --prefer-dist --no-progress
  [[ ! -x vendor/bin/phpunit ]] || run_check vendor/bin/phpunit
  [[ ! -x vendor/bin/phpstan ]] || run_check vendor/bin/phpstan analyse --no-progress
  [[ ! -x vendor/bin/pint ]] || run_check vendor/bin/pint --test
  require_checks PHP
fi

if [[ -f pyproject.toml || -f requirements.txt ]]; then
  project_stacks=$((project_stacks + 1))
  stack_checks_before=$project_checks
  if [[ -f requirements.txt ]]; then
    run_setup "$python_runner" -m pip install -r requirements.txt
  elif [[ -f pyproject.toml ]]; then
    run_setup "$python_runner" -m pip install -e .
  fi
  if [[ -d tests ]] && find tests -path tests/template -prune -o -type f -name 'test*.py' -print -quit | grep -q .; then
    "$python_runner" -m pytest --version >/dev/null 2>&1 || { echo 'Application tests exist but pytest is not installed' >&2; exit 1; }
    run_check "$python_runner" -m pytest --ignore=tests/template
  fi
  if "$python_runner" -m ruff --version >/dev/null 2>&1; then
    run_check "$python_runner" -m ruff check .
  fi
  require_checks Python
fi

if [[ $project_stacks -eq 0 ]]; then
  echo 'Template checks passed. No supported application manifest found; configure application checks when adding a project.'
else
  echo "Template checks passed. Executed $project_checks application validation commands."
fi
