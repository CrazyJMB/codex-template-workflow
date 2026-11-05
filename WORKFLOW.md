# Codex Cloud + GitHub workflow

## One-time setup

1. Copy this template to a repository (preserve existing application files). Keep existing project README; merge any existing `AGENTS.md` and `CHANGELOG.md` rather than overwriting them.
2. Create permanent `main` and `develop` branches, and keep `main` as the stable default branch. Protect both against deletion and force-pushes.
3. In **Settings → Rules → Rulesets** (or branch protection), require a pull request and passing checks on both branches. Set required checks to **`verify`** (CI) and **`policy`** (PR policy). Do not require formal approving reviews for a solo author. Enable conversation resolution. Rules and available features depend on the repository's GitHub plan.
4. In **Settings → General → Pull Requests**, enable **Allow squash merging** and **Allow merge commits**, disable **Allow auto-merge**, and enable **Automatically delete head branches**. Use squash only for tasks into `develop`; use a merge commit for `develop` → `main` releases. Never delete permanent branches.
5. Allow GitHub Actions to run. `.github/workflows/label-pr.yml` creates and applies PR `type:*` labels based on branch prefixes. `.github/workflows/release.yml` needs permission to publish GitHub Releases (`contents: write` is specified in the workflow). Confirm repository/organization Actions policies allow this.
6. Configure the project runtime and dependency installation for both Codex Cloud and CI. Modify `scripts/ci.sh` and `.github/workflows/ci.yml` to match the project (Node, Python, PHP, other). Ensure test scripts are noninteractive. Add custom build commands to `scripts/build-release.sh` when compiled artifacts are needed.
7. In **Codex Cloud**, create/publish an environment for the GitHub repository, configure its setup, and ensure the task starts from `develop`. `AGENTS.md` is read by Codex, but actual remote push/PR operations still depend on the environment and available GitHub permissions.
8. Bootstrap these workflow files into both protected branches before turning on required checks. Run a test PR to confirm labels, CI, and merge permissions.

## Task flow

- Create `feature/short-name`, `fix/short-name`, `refactor/short-name`, `docs/short-name`, `chore/short-name`, `test/short-name`, `ci/short-name`, or `perf/short-name` from `develop`.
- Optional GitHub Issue link; PR title should be conventional (`feat: ...`, `fix: ...`, etc.).
- Codex changes code, runs checks, pushes a branch, and opens a PR to `develop` when supported.
- GitHub assigns `type:feature`, `type:fix`, etc., and requires `verify` and `policy` to pass.
- The owner reviews manually, chooses **Squash and merge**, and GitHub deletes the temporary branch.

## Release flow (manual trigger only)

1. Ask Codex to prepare a release. Run `python3 scripts/propose-version.py` when GitHub CLI is available; compare its proposal with breaking changes, planned scope, and PRs since the last release. The proposal is advisory only.
2. After the owner chooses `vX.Y.Z`, Codex branches `chore/release-vX.Y.Z` from `develop`, updates the app's own version metadata, and adds a dated `## [X.Y.Z] - YYYY-MM-DD` section in `CHANGELOG.md` (Keep a Changelog format). Add `UPGRADING.md` **only** when operators must perform manual steps between versions.
3. Open a short `chore: prepare vX.Y.Z` PR into `develop`; the owner reviews and squash-merges it.
4. Open a `release: vX.Y.Z` PR from **`develop` into `main`**. The owner verifies CI, changelog, version and upgrade steps, then selects **Create a merge commit**. Never squash a release PR.
5. On the now-updated `main` commit, the owner creates and pushes the annotated tag:

   ```bash
   git fetch origin
   git switch main
   git pull --ff-only origin main
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   git push origin vX.Y.Z
   ```

6. The tag workflow verifies that the commit is on `main` and that declared project versions match, reads the matching changelog section, creates versioned source ZIP/TAR.GZ packages, invokes optional `scripts/build-release.sh`, adds SHA256 checksums, and publishes a GitHub Release. No manual deployment is performed.
7. If publishing fails, fix the release tooling by reviewed PR, then rerun the failed workflow for the same existing tag; do not silently replace published tags.

## Hotfix flow

- Only with explicit owner approval, start `hotfix/short-name` from `main` and submit a PR directly to `main`.
- Include the corrected version, changelog section, and any upgrade instructions in that PR. The owner reviews, uses a **merge commit**, and manually tags the resulting main commit; release packaging is the same as above.
- Sync `main` back into `develop` via a separate reviewed `sync: merge main into develop` PR. Keep both permanent branches.

## Versioning and labels

| Change | Branch | PR label | SemVer proposal |
| --- | --- | --- | --- |
| New compatible feature | `feature/*` | `type:feature` | MINOR |
| Bug fix | `fix/*` | `type:fix` | PATCH |
| Urgent stable fix | `hotfix/*` | `type:hotfix` | PATCH |
| Refactor/docs/tests/CI | matching prefix | `type:refactor`, `type:docs`, etc. | Owner decision (usually PATCH) |
| Breaking public change | any appropriate task prefix | plus manual `breaking` label | MAJOR |
| Release preparation | `chore/release-vX.Y.Z` | `type:chore` | Not itself a new feature |

Git **tags** are only for released versions (`vX.Y.Z`), not individual tasks. `type:*` labels are PR labels, not Git tags.

## Limitations

- GitHub cannot count an author's approval of their own PR. Requiring a second approving reviewer conflicts with the solo-author setup; the owner must consciously perform the manual merge.
- Actions cannot reliably enforce which *merge button* a human chooses when both squash and merge commits are allowed. Following the documented release procedure matters.
- The generic CI script is a starting point; a repository must configure real lint/tests/build and dependencies. A green workflow in an empty repository is not proof of code correctness.
- The version proposal uses up to 500 recently merged PRs on `develop` and GitHub Release publication time; validate its scope, particularly for backports or unusual release histories.
- Custom compiled binaries and deployment steps are stack-specific. The packaging hook intentionally contains no guessed build commands.
