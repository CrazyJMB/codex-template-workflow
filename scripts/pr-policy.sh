#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if command -v python >/dev/null; then
  exec python "$script_dir/pr-policy.py" "$@"
fi
exec python3 "$script_dir/pr-policy.py" "$@"
