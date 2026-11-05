# Contributing

1. Branch from `develop` (`feature/`, `fix/`, `refactor/`, `docs/`, `chore/`, `test/`, `ci/`, or `perf/`).
2. Make one focused change and run the checks in `scripts/ci.sh`.
3. Open a PR to `develop` with a conventional title and a linked Issue when available.
4. Wait for passing checks and manual owner review. The owner chooses **Squash and merge**.
5. Do not push to `main` or `develop` directly; delete merged temporary branches.

Releases require an explicit owner request, a reviewed release-preparation PR into `develop`, and a reviewed `develop` → `main` PR. See `WORKFLOW.md`.
