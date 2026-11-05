#!/usr/bin/env bash
# Generic starting point. Adapt version/toolchain steps to each repository.
set -euo pipefail

checks=0
run_check() {
  echo "::group::$*"
  "$@"
  echo '::endgroup::'
  checks=$((checks + 1))
}

if [[ -f package.json ]]; then
  command -v node >/dev/null || { echo 'Node.js is required' >&2; exit 1; }
  if [[ -f pnpm-lock.yaml ]]; then
    corepack enable
    run_check pnpm install --frozen-lockfile
    package_runner=(pnpm run)
  elif [[ -f yarn.lock ]]; then
    corepack enable
    if grep -q 'yarnPath:' .yarnrc.yml 2>/dev/null || [[ -f .yarnrc.yml ]]; then
      run_check yarn install --immutable
    else
      run_check yarn install --frozen-lockfile
    fi
    package_runner=(yarn run)
  elif [[ -f package-lock.json ]]; then
    run_check npm ci
    package_runner=(npm run)
  else
    echo 'Commit a Node lockfile before enabling CI' >&2
    exit 1
  fi

  for script in lint typecheck test build; do
    if node -e 'let p=require("./package.json");process.exit(p.scripts&&Object.prototype.hasOwnProperty.call(p.scripts, process.argv[1])?0:1)' "$script"; then
      CI=true run_check "${package_runner[@]}" "$script"
    fi
  done
fi

if [[ -f composer.json ]]; then
  command -v composer >/dev/null || { echo 'Composer must be installed on the CI runner' >&2; exit 1; }
  [[ -f composer.lock ]] || { echo 'Commit composer.lock before enabling CI' >&2; exit 1; }
  run_check composer install --no-interaction --prefer-dist --no-progress
  [[ ! -x vendor/bin/phpunit ]] || run_check vendor/bin/phpunit
  [[ ! -x vendor/bin/phpstan ]] || run_check vendor/bin/phpstan analyse --no-progress
  [[ ! -x vendor/bin/pint ]] || run_check vendor/bin/pint --test
fi

if [[ -f pyproject.toml || -f requirements.txt ]]; then
  if [[ -f requirements.txt ]]; then
    run_check python -m pip install -r requirements.txt
  elif [[ -f pyproject.toml ]]; then
    run_check python -m pip install -e .
  fi
  if [[ -d tests ]]; then
    python -m pytest --version >/dev/null 2>&1 || { echo 'Tests exist but pytest is not installed' >&2; exit 1; }
    run_check python -m pytest
  fi
  if python -m ruff --version >/dev/null 2>&1; then
    run_check python -m ruff check .
  fi
fi

if [[ $checks -eq 0 ]]; then
  echo 'No project checks found. Add stack-specific checks to scripts/ci.sh.'
else
  echo "Executed $checks setup/check commands."
fi
