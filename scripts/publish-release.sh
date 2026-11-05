#!/usr/bin/env bash
# Upload to a draft first; never replace a published release's artifacts.
set -euo pipefail

tag="${1:?Usage: publish-release.sh vX.Y.Z notes-file}"
notes="${2:?Pass the release notes path}"
[[ "$tag" =~ ^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]] || { echo 'Invalid version tag' >&2; exit 1; }
: "${GITHUB_REPOSITORY:?Set GITHUB_REPOSITORY}"
export RELEASE_TAG="$tag"
# A failed API request stops publication; it is never treated as a missing release.
draft=$(gh api --paginate "repos/$GITHUB_REPOSITORY/releases" \
  --jq '.[] | select(.tag_name == env.RELEASE_TAG) | .draft')
case "$draft" in
  false) echo 'Release is already published; refusing to replace its artifacts.' >&2; exit 1 ;;
  true) ;;
  '') gh release create "$tag" --draft --title "$tag" --notes-file "$notes" --verify-tag ;;
  *) echo 'Unexpected release state' >&2; exit 1 ;;
esac
gh release upload "$tag" dist/*.zip dist/*.tar.gz dist/SHA256SUMS --clobber
gh release edit "$tag" --notes-file "$notes" --draft=false
