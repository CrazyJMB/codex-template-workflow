#!/usr/bin/env bash
set -euo pipefail

tag="${1:?Usage: package-release.sh vX.Y.Z}"
[[ "$tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo 'Invalid tag' >&2; exit 1; }
repo="$(basename "${GITHUB_REPOSITORY:-$(git rev-parse --show-toplevel)}")"
mkdir -p dist
# Versioned source archives. GitHub also provides its own source downloads.
git archive --format=zip --prefix="$repo-$tag/" HEAD -o "dist/$repo-$tag-source.zip"
git archive --format=tar --prefix="$repo-$tag/" HEAD | gzip -n > "dist/$repo-$tag-source.tar.gz"

# Optional project-specific compiled artifacts. Implement this hook per stack.
if [[ -f scripts/build-release.sh ]]; then
  bash scripts/build-release.sh "$tag" "$(pwd)/dist"
fi

(
  cd dist
  mapfile -d '' packages < <(find . -maxdepth 1 -type f \( -name '*.zip' -o -name '*.tar.gz' \) -print0 | sort -z)
  [[ "${#packages[@]}" -gt 0 ]] || { echo 'No packages created' >&2; exit 1; }
  sha256sum "${packages[@]}" > SHA256SUMS
)
echo 'Release packages and checksums created in dist/'
