# Codex Cloud + GitHub workflow

## Template tools

Keep `README.md` as a project scaffold and `CHANGELOG.md` empty until the adopting
project has its own content. Do not record template maintenance as project history.

The template tooling requires Git, Bash (Git Bash on Windows), and Python 3.11+.
Application checks also require the project's runtime and package manager. GitHub
CLI (`gh`) must be authenticated for version proposals and release publication.
Run commands from the repository root; use `python3` if that is your Python command.

| Command | Purpose |
| --- | --- |
| `python scripts/check-setup.py` | Inspect local tools, `origin`, and permanent branches |
| `python scripts/check-template.py` | Check template Python/Bash syntax and regression tests |
| `bash scripts/ci.sh` | Run template checks and applicable application checks |
| `python scripts/check-release.py vX.Y.Z` | Validate release metadata and notes without publishing |
| `python scripts/propose-version.py` | Suggest a version from unreleased merged PRs |

`scripts/` contains automation, `tests/template/` its regression tests, and
`.github/workflows/` the CI, coordinated PR policy, and release workflows. Customize
`scripts/build-release.sh.example` when a project needs compiled artifacts.

## One-time setup

1. Copy this template to a repository (preserve existing application files). Keep existing project README; merge any existing `AGENTS.md` and `CHANGELOG.md` rather than overwriting them.
2. Configure the GitHub remote as `origin`. Create permanent `main` and `develop` branches from the project's chosen starting revision, and keep `main` as the stable default branch. Protect both against deletion and force-pushes. Run `python scripts/check-setup.py` to diagnose missing local tools, remote, or branches; it never changes them.
3. In **Settings → Rules → Rulesets** (or branch protection), require a pull request and passing checks on both branches. Set required checks to **`verify`** (CI) and **`policy`** (PR policy). Do not require formal approving reviews for a solo author. Enable conversation resolution. Rules and available features depend on the repository's GitHub plan.
4. In **Settings → General → Pull Requests**, enable **Allow squash merging** and **Allow merge commits**, disable **Allow auto-merge**, and enable **Automatically delete head branches**. Use squash only for tasks into `develop`; use a merge commit for `develop` → `main` releases. Never delete permanent branches.
5. Allow GitHub Actions to run. `.github/workflows/pr-policy.yml` labels and validates current PR metadata in one job. It uses `pull_request_target`, checks out only the trusted base revision, and never executes PR code. Its token needs `issues: write`; release publication needs `contents: write`. Confirm repository/organization Actions policies allow this. Install the policy files in both target branches before testing them.
6. Configure the project runtime and dependency installation for both Codex Cloud and CI. Modify `scripts/ci.sh` and `.github/workflows/ci.yml` to match the project (Node, Python, PHP, other). Run `python scripts/check-template.py` for template syntax and tests. Every detected application stack must also have a real validation command; installing dependencies is insufficient. Keep template tests under `tests/template/` and application tests separate. Ensure test scripts are noninteractive. Add custom build commands to `scripts/build-release.sh` when compiled artifacts are needed.
7. In **Codex Cloud**, create/publish an environment for the GitHub repository, configure its setup, and ensure the task starts from `develop`. `AGENTS.md` is read by Codex, but actual remote push/PR operations still depend on the environment and available GitHub permissions.
8. Bootstrap these workflow files into both protected branches before turning on required checks. Run a test PR to confirm labels, CI, and merge permissions.

## Task flow

- Create `feature/short-name`, `fix/short-name`, `refactor/short-name`, `docs/short-name`, `chore/short-name`, `test/short-name`, `ci/short-name`, or `perf/short-name` from `develop`.
- Optional GitHub Issue link; PR title should be conventional (`feat: ...`, `fix: ...`, etc.).
- Codex changes code, runs checks, pushes a branch, and opens a PR to `develop` when supported.
- The policy job assigns `type:feature`, `type:fix`, etc., then validates the live labels. A title with `!` also adds `breaking`; manually assigned breaking labels are preserved. GitHub requires `verify` and `policy` to pass.
- The owner reviews manually, chooses **Squash and merge**, and GitHub deletes the temporary branch.

## Release flow (manual trigger only)

1. Ask Codex to prepare a release. With authenticated GitHub CLI, fetch complete history (`git fetch --unshallow origin` first if necessary, then `git fetch origin --tags`, including `origin/main` and `origin/develop`). Run `python scripts/propose-version.py`; it compares merged PR commits reachable from `develop` against the highest stable SemVer release tag reachable from `main`, paginating GitHub results. A release merge commit on `main` need not be an ancestor of `develop`. Missing history or API failures stop the proposal. Review breaking changes and planned scope; the proposal is advisory only.
2. After the owner chooses `vX.Y.Z`, Codex branches `chore/release-vX.Y.Z` from `develop`, updates the app's own version metadata, and adds a dated `## [X.Y.Z] - YYYY-MM-DD` section in `CHANGELOG.md` (Keep a Changelog format). Add `UPGRADING.md` **only** when operators must perform manual steps between versions.
3. Run `python scripts/check-release.py vX.Y.Z`, then open a short `chore: prepare vX.Y.Z` PR into `develop`. CI validates version metadata and meaningful, dated release notes on preparation, release, and hotfix PRs. The owner reviews and squash-merges the preparation PR.
4. Open a `release: vX.Y.Z` PR from **`develop` into `main`**. The owner verifies CI, changelog, version and upgrade steps, then selects **Create a merge commit**. Never squash a release PR.
5. On the now-updated `main` commit, the owner creates and pushes the annotated tag:

   ```bash
   git fetch origin
   git switch main
   git pull --ff-only origin main
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   git push origin vX.Y.Z
   ```

6. The tag workflow verifies the annotated tag points to a commit on `main` and that declared project versions match, reads the matching changelog section, creates versioned source ZIP/TAR.GZ packages, invokes optional `scripts/build-release.sh`, adds SHA256 checksums, then uploads to a draft GitHub Release before publishing it. Published assets are never overwritten. No deployment is performed.
7. For a transient publishing failure, rerun the failed workflow for the same tag; an incomplete draft can be retried. A rerun keeps the original revision and cannot incorporate later tooling fixes. For a tooling defect, review and merge the fix through `develop` into `main`, then explicitly run **Publish release** from `main` with the existing tag (`gh workflow run release.yml --ref main -f tag=vX.Y.Z`). This recovery uses reviewed tooling from `main` and source from the original tag. It refuses to change an already published release. Never move or replace a published tag.

## Hotfix flow

- Only with explicit owner approval, start `hotfix/short-name` from `main` and submit a `fix: ...` PR directly to `main`.
- Include the corrected version, changelog section, and any upgrade instructions in that PR. The owner reviews, uses a **merge commit**, and manually tags the resulting main commit; release packaging is the same as above.
- Sync `main` back into `develop` via a separate reviewed `sync: merge main into develop` PR. Keep both permanent branches.

## Versioning and labels

| Change | Branch | PR label | SemVer proposal |
| --- | --- | --- | --- |
| New compatible feature | `feature/*` | `type:feature` | MINOR |
| Bug fix | `fix/*` | `type:fix` | PATCH |
| Urgent stable fix | `hotfix/*` | `type:hotfix` | PATCH |
| Refactor/docs/tests/CI | matching prefix | `type:refactor`, `type:docs`, etc. | Owner decision (usually PATCH) |
| Breaking public change | any appropriate task prefix | plus `breaking` (automatic for `!` titles, or manual) | MAJOR |
| Release preparation | `chore/release-vX.Y.Z` | `type:chore` | Not itself a new feature |

Git **tags** are only for released versions (`vX.Y.Z`), not individual tasks. `type:*` labels are PR labels, not Git tags.

## Limitations

- GitHub cannot count an author's approval of their own PR. Requiring a second approving reviewer conflicts with the solo-author setup; the owner must consciously perform the manual merge.
- Actions cannot reliably enforce which *merge button* a human chooses when both squash and merge commits are allowed. Following the documented release procedure matters.
- The generic CI script is a starting point; a repository must configure real lint/tests/build and dependencies. In the bare template, green CI verifies template tooling only; it makes no claim about application code.
- Version proposals use PR classifications and commit ancestry, not release publication dates. Missing labels, direct commits, backports, or unusual histories still require owner review. Only published, stable SemVer releases are considered baselines.
- Custom compiled binaries and deployment steps are stack-specific. The packaging hook intentionally contains no guessed build commands.
